#!/usr/bin/env python3
"""AirDrop-compatible file receiver for PCs.

Makes this machine discoverable in the AirDrop share sheet on iPhones/iPads
and in Samsung Quick Share (which added AirDrop wire-protocol compatibility),
as long as the sending device and this PC are on the same Wi-Fi network.

Discovery + transfer follow the reverse-engineered AirDrop protocol:
  1. Bonjour/mDNS advertises a "_airdrop._tcp" service.
  2. The sender opens a TLS connection and POSTs to /Discover to check
     reachability, then /Ask with file metadata for the user to accept,
     then /Upload with the actual file data as a cpio archive.

Limitations (see README.md):
  * Only works when both devices share a Wi-Fi network. Apple's
    no-shared-Wi-Fi fallback uses AWDL (a proprietary peer-to-peer Wi-Fi
    link) which is not reimplemented here.
  * Uses a plain self-signed TLS certificate, so this only works in
    AirDrop's "Everyone" (not "Contacts Only") discovery mode.
"""
import argparse
import socket
import ssl
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import certs
import cpio_reader
import plist_protocol

DEFAULT_PORT = 8770


def local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class AirDropHandler(BaseHTTPRequestHandler):
    server_version = "AirDropTool/1.0"

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def do_POST(self):  # noqa: N802 (matches BaseHTTPRequestHandler naming)
        if self.path == "/Discover":
            self._handle_discover()
        elif self.path == "/Ask":
            self._handle_ask()
        elif self.path == "/Upload":
            self._handle_upload()
        else:
            self.send_error(404)

    def _handle_discover(self):
        self._read_body()
        body = plist_protocol.discover_response(self.server.computer_name)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_ask(self):
        body = self._read_body()
        ask = plist_protocol.parse_ask_request(body)
        accepted = self.server.decide_accept(ask)
        if accepted:
            response = plist_protocol.ask_accept_response()
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
        else:
            self.send_response(401)
            self.end_headers()

    def _handle_upload(self):
        body = self._read_body()
        entries = cpio_reader.read_entries(body)
        saved = []
        for entry in entries:
            if entry.is_directory:
                continue
            dest = self.server.save_file(entry.name, entry.data)
            saved.append(dest)
        for path in saved:
            print(f"[airdrop] saved {path}")
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *args):  # quieter default logging
        pass


class AirDropServer(ThreadingHTTPServer):
    def __init__(self, address, handler, computer_name: str, out_dir: Path, auto_accept: bool):
        super().__init__(address, handler)
        self.computer_name = computer_name
        self.out_dir = out_dir
        self.auto_accept = auto_accept

    def decide_accept(self, ask: plist_protocol.AskRequest) -> bool:
        files = ", ".join(ask.file_names) or "(unknown file)"
        print(f"\n[airdrop] {ask.sender_computer_name} wants to send: {files}")
        if self.auto_accept:
            print("[airdrop] auto-accepting")
            return True
        answer = input("[airdrop] Accept? [y/N] ").strip().lower()
        return answer == "y"

    def save_file(self, name: str, data: bytes) -> Path:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        dest = self.out_dir / Path(name).name
        counter = 1
        while dest.exists():
            dest = self.out_dir / f"{dest.stem}_{counter}{dest.suffix}"
            counter += 1
        dest.write_bytes(data)
        return dest


def register_mdns(computer_name: str, port: int, ip: str):
    try:
        from zeroconf import ServiceInfo, Zeroconf
    except ImportError:
        print(
            "[airdrop] 'zeroconf' is not installed, so this PC will NOT show up "
            "in the AirDrop sheet automatically.\n"
            "          Install it with: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return None

    hostname = f"{computer_name.replace(' ', '-')}.local."
    info = ServiceInfo(
        "_airdrop._tcp.local.",
        f"{computer_name}._airdrop._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties={"flags": "507"},
        server=hostname,
    )
    zc = Zeroconf()
    zc.register_service(info)
    print(f"[airdrop] advertising as '{computer_name}' via mDNS on {ip}:{port}")
    return zc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default=socket.gethostname(), help="Name shown in the AirDrop sheet")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--out-dir", default=str(Path.home() / "AirDropReceived"))
    parser.add_argument(
        "--auto-accept",
        action="store_true",
        help="Accept incoming transfers without prompting (use with care)",
    )
    args = parser.parse_args()

    ip = local_ip()
    out_dir = Path(args.out_dir)
    cert_path, key_path = certs.ensure_cert(args.name)

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    httpd = AirDropServer(("0.0.0.0", args.port), AirDropHandler, args.name, out_dir, args.auto_accept)
    httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)

    zc = register_mdns(args.name, args.port, ip)

    print(f"[airdrop] receiving as '{args.name}' on https://{ip}:{args.port}")
    print(f"[airdrop] files will be saved to {out_dir}")
    print("[airdrop] make sure this PC and the sending phone are on the same Wi-Fi network")
    print(f"[airdrop] started {datetime.now().isoformat(timespec='seconds')} — Ctrl+C to stop")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if zc is not None:
            zc.close()
        httpd.shutdown()


if __name__ == "__main__":
    main()
