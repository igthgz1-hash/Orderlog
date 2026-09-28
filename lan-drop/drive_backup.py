# Copyright (c) 2026 Sevastopol. All Rights Reserved. See ../LICENSE.
"""Optional Google Drive backup for files transferred via LAN Drop.

Files received from the phone, and files the phone downloads from this PC,
get uploaded (in the background, so it never slows down or blocks the HTTP
response) into subfolders of a folder in the Google Drive account you sign
in as during one-time setup:

    <folder_name>/
      Received/   <- files the phone sent to this PC
      Sent/       <- files this PC sent to the phone

Setup (see README.md "Google Drive backup" section for the full walkthrough):
  1. In Google Cloud Console, create a project and enable the Drive API.
  2. Create an OAuth 2.0 Client ID of type "Desktop app".
  3. Download its JSON and save it as credentials.json next to server.py.
  4. Run the server with --backup-to-drive; the first run opens a browser
     asking you to sign in and approve access — do this once. A token.json
     is then cached locally so future runs don't need the browser again.

Only requires the "drive.file" scope: this app can only see/manage files
it creates itself, never your existing Drive contents.
"""
import mimetypes
import sys
import threading
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

RECEIVED = "Received"
SENT = "Sent"


class DriveBackup:
    def __init__(
        self,
        credentials_path: Path,
        token_path: Path,
        folder_name: str,
        delete_after_upload: bool = True,
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.folder_name = folder_name
        self.delete_after_upload = delete_after_upload
        self._service = None
        self._root_folder_id = None
        self._subfolder_ids = {}
        self._uploaded_once = set()
        self._lock = threading.Lock()

    def _get_service(self):
        # Imported lazily so these optional deps are only required when
        # --backup-to-drive is actually used.
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"Google Drive credentials not found at {self.credentials_path}. "
                        "See README.md 'Google Drive backup' section for setup steps."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                print("[landrop-drive] opening browser for Google sign-in (one-time setup)...")
                # timeout_seconds: if the browser sign-in is abandoned or
                # blocked (e.g. Google's "Access blocked" screen, which never
                # redirects back), this would otherwise wait forever while
                # holding _lock — freezing every future backup attempt.
                creds = flow.run_local_server(port=0, timeout_seconds=180)
            self.token_path.write_text(creds.to_json())

        return build("drive", "v3", credentials=creds)

    def _find_or_create_folder(self, service, name: str, parent_id: str | None) -> str:
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        results = service.files().list(q=query, spaces="drive", fields="files(id)").execute()
        matches = results.get("files", [])
        if matches:
            return matches[0]["id"]
        metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            metadata["parents"] = [parent_id]
        folder = service.files().create(body=metadata, fields="id").execute()
        return folder["id"]

    def _ensure_subfolder(self, service, category: str) -> str:
        if category in self._subfolder_ids:
            return self._subfolder_ids[category]
        if self._root_folder_id is None:
            self._root_folder_id = self._find_or_create_folder(service, self.folder_name, None)
        folder_id = self._find_or_create_folder(service, category, self._root_folder_id)
        self._subfolder_ids[category] = folder_id
        return folder_id

    def upload_async(self, file_path: Path, category: str = RECEIVED, delete_after=None, once: bool = False):
        """Fire-and-forget: back up file_path on a background thread.

        category: subfolder name ("Received" or "Sent").
        delete_after: overrides self.delete_after_upload for this call when
            not None. "Sent" files (already the PC's own copy, possibly
            needed for repeat downloads) should always pass delete_after=False.
        once: if True, skip if this exact file was already backed up in this
            process's lifetime — used for "Sent" files, which the /download
            endpoint could otherwise re-upload on every repeat download.
        """
        if once:
            key = (category, str(file_path.resolve()))
            if key in self._uploaded_once:
                return
            self._uploaded_once.add(key)

        if delete_after is None:
            delete_after = self.delete_after_upload

        thread = threading.Thread(target=self._upload, args=(file_path, category, delete_after), daemon=True)
        thread.start()

    def _upload(self, file_path: Path, category: str, delete_after: bool):
        from googleapiclient.http import MediaIoBaseUpload

        try:
            with self._lock:
                if self._service is None:
                    self._service = self._get_service()
                service = self._service
                folder_id = self._ensure_subfolder(service, category)

            content_type, _ = mimetypes.guess_type(file_path.name)
            content_type = content_type or "application/octet-stream"
            metadata = {"name": file_path.name, "parents": [folder_id]}

            # Open (and close, via `with`) the file ourselves rather than
            # letting MediaFileUpload manage its own handle — it doesn't
            # reliably close that handle after execute(), which on Windows
            # blocks the unlink() below with WinError 32 ("used by another
            # process") even though the upload already succeeded.
            with open(file_path, "rb") as fh:
                media = MediaIoBaseUpload(fh, mimetype=content_type, resumable=True)
                service.files().create(body=metadata, media_body=media, fields="id").execute()

            print(f"[landrop-drive] backed up '{file_path.name}' to Google Drive ({category})")

            if delete_after:
                # Only reached after the API call above returned without
                # raising, i.e. Drive has confirmed the file was created —
                # safe to free up local disk space now. The file handle
                # above is guaranteed closed by this point (the `with` block
                # already exited), so this won't hit WinError 32.
                try:
                    file_path.unlink()
                    print(f"[landrop-drive] deleted local copy of '{file_path.name}' to free disk space")
                except OSError as exc:
                    print(f"[landrop-drive] backed up but could not delete local file '{file_path.name}': {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — a failed backup must never crash the server
            print(f"[landrop-drive] backup failed for '{file_path.name}': {exc}", file=sys.stderr)
