#!/usr/bin/env python3
# Copyright (c) 2026 Sevastopol. All Rights Reserved. See ../LICENSE.
"""Simple LAN file drop: any phone on the same Wi-Fi can send files to this
PC (and this PC can send files back) through a normal web browser — no app,
no undocumented protocols.

Unlike airdrop-tool/ (which reimplements Apple's AirDrop wire protocol and
has an unresolved BLE discovery issue), this works with any phone — iPhone,
Samsung, anything with a browser — because it's just plain HTTP and an HTML
form. Scan the printed QR code (or type the URL) on the phone:
  - to send TO this PC: pick files (or drag & drop) in the upload form
  - to receive FROM this PC: drop files into --send-dir, they show up as
    download links on the same page
"""
import argparse
import html
import mimetypes
import re
import socket
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

DEFAULT_PORT = 8000

FILE_ICONS = {
    ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️",
    ".webp": "🖼️", ".heic": "🖼️", ".bmp": "🖼️", ".svg": "🖼️",
    ".mp4": "🎬", ".mov": "🎬", ".avi": "🎬", ".mkv": "🎬", ".webm": "🎬",
    ".mp3": "🎵", ".wav": "🎵", ".m4a": "🎵", ".aac": "🎵", ".flac": "🎵",
    ".pdf": "📄",
    ".zip": "🗜️", ".rar": "🗜️", ".7z": "🗜️", ".tar": "🗜️", ".gz": "🗜️",
    ".doc": "📝", ".docx": "📝", ".txt": "📝", ".rtf": "📝",
    ".xls": "📊", ".xlsx": "📊", ".csv": "📊",
    ".ppt": "📑", ".pptx": "📑",
}

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LAN Drop — {computer_name}</title>
<style>
  :root {{
    --bg: #f2f2f7; --card: #ffffff; --text: #1d1d1f; --muted: #6e6e73;
    --accent: #0071e3; --accent-active: #0058b0; --border: #e5e5ea;
    --success-bg: #e6f7ec; --success-text: #1e7e3c; --dropzone-bg: #f9f9fb;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #000000; --card: #1c1c1e; --text: #f5f5f7; --muted: #98989d;
      --accent: #0a84ff; --accent-active: #409cff; --border: #38383a;
      --success-bg: #123321; --success-text: #57d67c; --dropzone-bg: #2c2c2e;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Sarabun, Roboto, sans-serif;
    max-width: 520px; margin: 0 auto; padding: 28px 16px 40px;
    background: var(--bg); color: var(--text);
  }}
  header {{ text-align: center; margin-bottom: 24px; }}
  header .badge {{
    display: inline-block; font-size: 0.8rem; color: var(--muted);
    background: var(--card); border: 1px solid var(--border);
    padding: 4px 12px; border-radius: 999px; margin-bottom: 10px;
  }}
  h1 {{ font-size: 1.5rem; margin: 0; }}
  h2 {{ font-size: 1.05rem; margin: 28px 0 12px; color: var(--text); }}
  .card {{
    background: var(--card); border-radius: 20px; padding: 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .status-banner {{
    padding: 14px 16px; border-radius: 14px; margin-bottom: 18px;
    font-weight: 600; font-size: 0.95rem;
    background: var(--success-bg); color: var(--success-text);
  }}
  .dropzone {{
    border: 2px dashed var(--border); border-radius: 16px;
    background: var(--dropzone-bg); text-align: center;
    padding: 32px 16px; cursor: pointer; transition: border-color .15s, background .15s;
  }}
  .dropzone.dragover {{ border-color: var(--accent); background: var(--success-bg); }}
  .dropzone .icon {{ font-size: 2.2rem; display: block; margin-bottom: 8px; }}
  .dropzone .hint {{ color: var(--muted); font-size: 0.9rem; display: block; margin-top: 4px; }}
  .selected-names {{
    margin-top: 10px; font-size: 0.85rem; color: var(--accent); word-break: break-word;
  }}
  input[type=file] {{ display: none; }}
  button {{
    width: 100%; margin-top: 18px; padding: 15px; font-size: 1.05rem;
    border: none; border-radius: 12px; background: var(--accent); color: white;
    font-weight: 600; cursor: pointer; transition: background .15s;
  }}
  button:active {{ background: var(--accent-active); }}
  ul.file-list {{ list-style: none; margin: 0; padding: 0; }}
  .file-item {{
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    padding: 12px 0; border-bottom: 1px solid var(--border);
  }}
  .file-item:last-child {{ border-bottom: none; }}
  .file-item .file-label {{ display: flex; align-items: center; gap: 10px; min-width: 0; }}
  .file-item .file-label a {{ color: var(--text); text-decoration: none; }}
  .file-item .file-label a:active {{ color: var(--accent); }}
  .file-name {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .file-meta {{ color: var(--muted); font-size: 0.8rem; white-space: nowrap; flex-shrink: 0; }}
  .empty {{ color: var(--muted); font-size: 0.9rem; padding: 8px 0; }}
  footer {{ text-align: center; margin-top: 36px; color: var(--muted); font-size: 0.78rem; }}
</style>
</head>
<body>
<header>
  <span class="badge">📶 LAN Drop</span>
  <h1>{computer_name}</h1>
</header>

{status}

<div class="card">
  <form method="POST" action="/upload" enctype="multipart/form-data" id="uploadForm">
    <label class="dropzone" for="fileInput" id="dropzone">
      <span class="icon">📤</span>
      <span>แตะเพื่อเลือกไฟล์ หรือลากไฟล์มาวางที่นี่</span>
      <span class="hint">เลือกได้หลายไฟล์พร้อมกัน</span>
      <div class="selected-names" id="selectedNames"></div>
    </label>
    <input type="file" name="file" id="fileInput" multiple required>
    <button type="submit">ส่งไฟล์เข้า {computer_name}</button>
  </form>
</div>

<h2>ไฟล์ที่ได้รับแล้ว</h2>
<div class="card">
  <ul class="file-list">{received_list}</ul>
</div>

<h2>ไฟล์จาก PC (แตะเพื่อดาวน์โหลด)</h2>
<div class="card">
  <ul class="file-list">{send_list}</ul>
</div>

<footer>© 2026 Sevastopol · สงวนลิขสิทธิ์ทั้งหมด</footer>

<script>
(function() {{
  var dropzone = document.getElementById('dropzone');
  var input = document.getElementById('fileInput');
  var namesEl = document.getElementById('selectedNames');

  function updateNames() {{
    if (!input.files || input.files.length === 0) {{
      namesEl.textContent = '';
      return;
    }}
    var names = [];
    for (var i = 0; i < input.files.length; i++) {{
      names.push(input.files[i].name);
    }}
    namesEl.textContent = names.join(', ');
  }}

  input.addEventListener('change', updateNames);

  ['dragenter', 'dragover'].forEach(function(evt) {{
    dropzone.addEventListener(evt, function(e) {{
      e.preventDefault();
      dropzone.classList.add('dragover');
    }});
  }});
  ['dragleave', 'drop'].forEach(function(evt) {{
    dropzone.addEventListener(evt, function(e) {{
      e.preventDefault();
      dropzone.classList.remove('dragover');
    }});
  }});
  dropzone.addEventListener('drop', function(e) {{
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {{
      input.files = e.dataTransfer.files;
      updateNames();
    }}
  }});
}})();
</script>
</body>
</html>
"""


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def format_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def format_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%H:%M น.")


def file_icon(name: str) -> str:
    return FILE_ICONS.get(Path(name).suffix.lower(), "📎")


def render_file_items(files, downloadable: bool) -> str:
    items = []
    for f in files:
        stat = f.stat()
        icon = file_icon(f.name)
        name_escaped = html.escape(f.name)
        meta = f"{format_size(stat.st_size)} · {format_time(stat.st_mtime)}"
        if downloadable:
            label = f'<a href="/download/{name_escaped}">{icon} <span class="file-name">{name_escaped}</span></a>'
        else:
            label = f'{icon} <span class="file-name">{name_escaped}</span>'
        items.append(
            f'<li class="file-item"><span class="file-label">{label}</span>'
            f'<span class="file-meta">{meta}</span></li>'
        )
    return "".join(items) or '<li class="empty">ยังไม่มีไฟล์</li>'


def parse_multipart(content_type: str, body: bytes):
    """Minimal multipart/form-data parser: returns [(filename, data), ...].

    Avoids depending on the `cgi` module (removed in Python 3.13) or a
    third-party multipart library for what browsers send in practice.
    """
    match = re.search(r'boundary="?([^";]+)"?', content_type)
    if not match:
        return []
    boundary = ("--" + match.group(1)).encode()

    files = []
    for part in body.split(boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        header_blob, sep, content = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = header_blob.decode("utf-8", "replace")
        name_match = re.search(r'filename="([^"]*)"', headers)
        if not name_match or not name_match.group(1):
            continue
        if content.endswith(b"\r\n"):
            content = content[:-2]
        files.append((name_match.group(1), content))
    return files


class DropHandler(BaseHTTPRequestHandler):
    server_version = "LanDrop/2.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_page(parsed.query)
        elif parsed.path.startswith("/download/"):
            self._handle_download(parsed.path)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        else:
            self.send_error(404)

    def _serve_page(self, query_string=""):
        params = parse_qs(query_string)
        uploaded = params.get("uploaded", [None])[0]
        status_html = ""
        if uploaded is not None:
            count = html.escape(uploaded)
            status_html = f'<div class="status-banner">✅ ส่งไฟล์สำเร็จ {count} ไฟล์</div>'

        received = sorted(self.server.out_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if self.server.out_dir.exists() else []
        send_files = sorted(
            (p for p in self.server.send_dir.glob("*") if p.is_file()),
            key=lambda p: p.stat().st_mtime, reverse=True,
        ) if self.server.send_dir.exists() else []

        page = PAGE_TEMPLATE.format(
            computer_name=html.escape(self.server.computer_name),
            status=status_html,
            received_list=render_file_items(received, downloadable=False),
            send_list=render_file_items(send_files, downloadable=True),
        )
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_download(self, path):
        requested_name = unquote(path[len("/download/"):])
        # Resolve strictly inside send_dir — reject any path-traversal attempt
        # (e.g. "../../etc/passwd") regardless of how it's encoded.
        safe_name = Path(requested_name).name
        file_path = (self.server.send_dir / safe_name).resolve()
        send_dir_resolved = self.server.send_dir.resolve()
        if send_dir_resolved not in file_path.parents or not file_path.is_file():
            self.send_error(404)
            return

        content_type, _ = mimetypes.guess_type(file_path.name)
        content_type = content_type or "application/octet-stream"
        data = file_path.read_bytes()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # Images: serve inline so Safari opens them directly (long-press to
        # save to Photos in one step). Everything else: force a download so
        # it lands in the phone's Files/Downloads.
        if not content_type.startswith("image/"):
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.end_headers()
        self.wfile.write(data)

    def _handle_upload(self):
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        files = parse_multipart(content_type, body)

        saved = []
        for filename, data in files:
            dest = self.server.save_file(filename, data)
            saved.append(dest)
            print(f"[landrop] received {dest} ({len(data)} bytes)")

        self.send_response(303)
        self.send_header("Location", f"/?uploaded={len(saved)}")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


class DropServer(ThreadingHTTPServer):
    def __init__(self, address, handler, computer_name: str, out_dir: Path, send_dir: Path):
        super().__init__(address, handler)
        self.computer_name = computer_name
        self.out_dir = out_dir
        self.send_dir = send_dir

    def save_file(self, name: str, data: bytes) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        dest = self.out_dir / Path(name).name
        counter = 1
        while dest.exists():
            dest = self.out_dir / f"{dest.stem}_{counter}{dest.suffix}"
            counter += 1
        dest.write_bytes(data)
        return dest


def print_qr(url: str):
    try:
        import qrcode
    except ImportError:
        print("[landrop] (ติดตั้ง 'qrcode' ด้วย pip เพื่อให้แสดง QR code ในเทอร์มินัลได้: pip install qrcode)")
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=socket.gethostname(), help="ชื่อเครื่องที่แสดงบนหน้าเว็บ")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--out-dir", default=str(Path.home() / "LanDropReceived"),
                         help="Where files sent FROM the phone are saved")
    parser.add_argument("--send-dir", default=str(Path.home() / "LanDropToSend"),
                         help="Drop files here to make them downloadable BY the phone")
    args = parser.parse_args()

    ip = local_ip()
    out_dir = Path(args.out_dir)
    send_dir = Path(args.send_dir)
    send_dir.mkdir(parents=True, exist_ok=True)
    url = f"http://{ip}:{args.port}/"

    httpd = DropServer(("0.0.0.0", args.port), DropHandler, args.name, out_dir, send_dir)

    print("LAN Drop — Copyright (c) 2026 Sevastopol. All Rights Reserved.")
    print(f"[landrop] receiving as '{args.name}' at {url}")
    print(f"[landrop] files sent from phone will be saved to {out_dir}")
    print(f"[landrop] put files here to let the phone download them: {send_dir}")
    print("[landrop] scan this QR code on your phone (must be on the same Wi-Fi network):")
    print_qr(url)
    print(f"[landrop] started {datetime.now().isoformat(timespec='seconds')} — Ctrl+C to stop")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
