"""ClipGrab – ดาวน์โหลดคลิปจาก Social Media ด้วย yt-dlp (รันบนเครื่องตัวเอง)"""
import ipaddress
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import uuid
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, request, send_file, send_from_directory
import yt_dlp

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))
DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "clipgrab")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def find_ffmpeg():
    """หา ffmpeg จากระบบก่อน ถ้าไม่มีใช้ตัวที่มากับ imageio-ffmpeg (ฝังในตัวติดตั้ง)"""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return None


FFMPEG = find_ffmpeg()
HAS_FFMPEG = FFMPEG is not None
JOB_TTL = 60 * 60  # ลบไฟล์เก่าหลัง 1 ชั่วโมง

jobs = {}
jobs_lock = threading.Lock()


def validate_url(url):
    """รับเฉพาะ http(s) และไม่ยอมให้ชี้ไปยังเครือข่ายภายใน (กัน SSRF)"""
    p = urlparse(url or "")
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("URL ไม่ถูกต้อง")
    try:
        for info in socket.getaddrinfo(p.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValueError("ไม่อนุญาตให้ใช้ URL ภายในเครือข่าย")
    except socket.gaierror:
        raise ValueError("ไม่พบโฮสต์ของ URL นี้")
    return url


def format_selector(quality):
    if quality == "audio":
        return "bestaudio/best"
    if quality == "best":
        return "bv*+ba/b" if HAS_FFMPEG else "b"
    h = int(quality)
    if HAS_FFMPEG:
        return f"bv*[height<={h}]+ba/b[height<={h}]/b"
    return f"b[height<={h}]/b"


def cleanup_old():
    now = time.time()
    with jobs_lock:
        for jid, j in list(jobs.items()):
            if now - j["created"] > JOB_TTL:
                shutil.rmtree(j["dir"], ignore_errors=True)
                del jobs[jid]


def run_job(jid, url, quality, audio_fmt):
    job = jobs[jid]

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                job["progress"] = round(d["downloaded_bytes"] / total * 100, 1)
            job["speed"] = d.get("speed")
            job["eta"] = d.get("eta")
        elif d["status"] == "finished":
            job["progress"] = 100
            job["status"] = "processing"

    opts = {
        "format": format_selector(quality),
        "outtmpl": os.path.join(job["dir"], "%(title).150B [%(id)s].%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": False,
        "progress_hooks": [hook],
        "max_filesize": 4 * 1024**3,
    }
    if HAS_FFMPEG:
        opts["ffmpeg_location"] = FFMPEG
    if quality == "audio":
        if HAS_FFMPEG:
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": audio_fmt,
                "preferredquality": "0" if audio_fmt == "mp3" else None,
            }]
    elif HAS_FFMPEG:
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        files = [f for f in os.listdir(job["dir"]) if not f.endswith((".part", ".ytdl"))]
        if not files:
            raise RuntimeError("ไม่พบไฟล์ที่ดาวน์โหลด")
        job["file"] = max(files, key=lambda f: os.path.getsize(os.path.join(job["dir"], f)))
        job["status"] = "done"
    except Exception as e:  # noqa: BLE001
        job["status"] = "error"
        job["error"] = str(e).replace("ERROR: ", "")[:300]


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/info")
def info():
    try:
        url = validate_url((request.get_json(force=True) or {}).get("url", "").strip())
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as ydl:
            data = ydl.extract_info(url, download=False)
    except Exception as e:  # noqa: BLE001
        return jsonify(error=str(e).replace("ERROR: ", "")[:300]), 400
    heights = sorted({f["height"] for f in data.get("formats", []) if f.get("height")}, reverse=True)
    return jsonify(
        title=data.get("title"),
        uploader=data.get("uploader"),
        thumbnail=data.get("thumbnail"),
        duration=data.get("duration"),
        heights=heights,
        ffmpeg=HAS_FFMPEG,
    )


@app.post("/api/download")
def download():
    body = request.get_json(force=True) or {}
    quality = str(body.get("quality", "best"))
    audio_fmt = body.get("audio_format", "mp3")
    if quality not in ("best", "audio") and not quality.isdigit():
        return jsonify(error="คุณภาพไม่ถูกต้อง"), 400
    if audio_fmt not in ("mp3", "m4a", "opus", "wav"):
        return jsonify(error="รูปแบบเสียงไม่ถูกต้อง"), 400
    try:
        url = validate_url(body.get("url", "").strip())
    except ValueError as e:
        return jsonify(error=str(e)), 400
    cleanup_old()
    jid = uuid.uuid4().hex
    d = os.path.join(DOWNLOAD_DIR, jid)
    os.makedirs(d)
    jobs[jid] = {"status": "downloading", "progress": 0, "dir": d, "created": time.time()}
    threading.Thread(target=run_job, args=(jid, url, quality, audio_fmt), daemon=True).start()
    return jsonify(id=jid)


@app.get("/api/progress/<jid>")
def progress(jid):
    j = jobs.get(jid) or abort(404)
    return jsonify({k: j.get(k) for k in ("status", "progress", "speed", "eta", "error", "file")})


@app.get("/api/file/<jid>")
def file(jid):
    j = jobs.get(jid) or abort(404)
    if j["status"] != "done":
        abort(409)
    return send_file(os.path.join(j["dir"], j["file"]), as_attachment=True, download_name=j["file"])


def free_port(preferred):
    for port in range(preferred, preferred + 20):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


if __name__ == "__main__":
    import webbrowser

    if not HAS_FFMPEG:
        print("⚠ ไม่พบ ffmpeg: จะรวมภาพ+เสียง/แปลงเป็น MP3 ไม่ได้")
    port = free_port(int(os.environ.get("PORT", 5000)))
    url = f"http://127.0.0.1:{port}"
    print(f"ClipGrab กำลังทำงานที่ {url}\n(ปิดหน้าต่างนี้เพื่อออกจากโปรแกรม)")
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port)
