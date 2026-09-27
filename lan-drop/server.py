#!/usr/bin/env python3
"""Simple LAN file drop: any phone on the same Wi-Fi can send files to this
PC through a normal web browser — no app, no undocumented protocols.

Unlike airdrop-tool/ (which reimplements Apple's AirDrop wire protocol and
has an unresolved BLE discovery issue), this works with any phone — iPhone,
Samsung, anything with a browser — because it's just plain HTTP and an HTML
form. Scan the printed QR code (or type the URL) on the phone, pick files,
upload.
"""
import argparse
import html
import re
import socket
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_PORT = 8000

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ส่งไฟล์ไปที่ {computer_name}</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", Sarabun, sans-serif; max-width: 480px;
         margin: 0 auto; padding: 24px 16px; background: #f5f5f7; color: #1d1d1f; }}
  h1 {{ font-size: 1.4rem; }}
  form {{ background: white; border-radius: 16px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
  input[type=file] {{ display: block; width: 100%; margin-bottom: 16px; }}
  button {{ width: 100%; padding: 14px; font-size: 1.1rem; border: none; border-radius: 10px;
           background: #0071e3; color: white; font-weight: 600; }}
  button:active {{ background: #0058b0; }}
  ul {{ padding-left: 20px; }}
  .status {{ color: #34a853; font-weight: 600; margin-bottom: 16px; }}
</style>
</head>
<body>
<h1>ส่งไฟล์ไปที่ "{computer_name}"</h1>
{status}
<form method="POST" action="/upload" enctype="multipart/form-data">
  <input type="file" name="file" multiple required>
  <button type="submit">ส่งไฟล์</button>
</form>
<h2>ไฟล์ที่ได้รับแล้ว</h2>
<ul>{file_list}</ul>
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
    server_version = "LanDrop/1.0"

    def do_GET(self):
        if self.path == "/":
            self._serve_page()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/upload":
            self._handle_upload()
        else:
            self.send_error(404)

    def _serve_page(self, status_html=""):
        files = sorted(self.server.out_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True) \
            if self.server.out_dir.exists() else []
        file_list = "".join(f"<li>{html.escape(f.name)}</li>" for f in files) or "<li>ยังไม่มีไฟล์</li>"
        page = PAGE_TEMPLATE.format(
            computer_name=html.escape(self.server.computer_name),
            status=status_html,
            file_list=file_list,
        )
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
        self.send_header("Location", "/")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


class DropServer(ThreadingHTTPServer):
    def __init__(self, address, handler, computer_name: str, out_dir: Path):
        super().__init__(address, handler)
        self.computer_name = computer_name
        self.out_dir = out_dir

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
    parser.add_argument("--out-dir", default=str(Path.home() / "LanDropReceived"))
    args = parser.parse_args()

    ip = local_ip()
    out_dir = Path(args.out_dir)
    url = f"http://{ip}:{args.port}/"

    httpd = DropServer(("0.0.0.0", args.port), DropHandler, args.name, out_dir)

    print(f"[landrop] receiving as '{args.name}' at {url}")
    print(f"[landrop] files will be saved to {out_dir}")
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
