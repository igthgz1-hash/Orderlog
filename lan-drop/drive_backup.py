# Copyright (c) 2026 Sevastopol. All Rights Reserved. See ../LICENSE.
"""Optional Google Drive backup for files received via LAN Drop.

Every file the phone sends to this PC also gets uploaded (in the
background, so it never slows down or blocks the upload response) to a
folder in the Google Drive account you sign in as during one-time setup.

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
import sys
import threading
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


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
        self._folder_id = None
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

    def _ensure_folder(self, service) -> str:
        if self._folder_id:
            return self._folder_id
        query = (
            f"name='{self.folder_name}' and mimeType='application/vnd.google-apps.folder' "
            "and trashed=false"
        )
        results = service.files().list(q=query, spaces="drive", fields="files(id)").execute()
        matches = results.get("files", [])
        if matches:
            self._folder_id = matches[0]["id"]
        else:
            metadata = {"name": self.folder_name, "mimeType": "application/vnd.google-apps.folder"}
            folder = service.files().create(body=metadata, fields="id").execute()
            self._folder_id = folder["id"]
        return self._folder_id

    def upload_async(self, file_path: Path):
        """Fire-and-forget: back up file_path on a background thread."""
        thread = threading.Thread(target=self._upload, args=(file_path,), daemon=True)
        thread.start()

    def _upload(self, file_path: Path):
        from googleapiclient.http import MediaFileUpload

        try:
            with self._lock:
                if self._service is None:
                    self._service = self._get_service()
                service = self._service
                folder_id = self._ensure_folder(service)

            metadata = {"name": file_path.name, "parents": [folder_id]}
            media = MediaFileUpload(str(file_path), resumable=True)
            service.files().create(body=metadata, media_body=media, fields="id").execute()
            print(f"[landrop-drive] backed up '{file_path.name}' to Google Drive")

            if self.delete_after_upload:
                # Only reached after the API call above returned without
                # raising, i.e. Drive has confirmed the file was created —
                # safe to free up local disk space now.
                try:
                    file_path.unlink()
                    print(f"[landrop-drive] deleted local copy of '{file_path.name}' to free disk space")
                except OSError as exc:
                    print(f"[landrop-drive] backed up but could not delete local file '{file_path.name}': {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — a failed backup must never crash the server
            print(f"[landrop-drive] backup failed for '{file_path.name}': {exc}", file=sys.stderr)
