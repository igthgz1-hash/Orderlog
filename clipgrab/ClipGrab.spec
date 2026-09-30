# PyInstaller spec — build: pyinstaller ClipGrab.spec
from PyInstaller.utils.hooks import collect_all

datas = [("static", "static")]
binaries, hiddenimports = [], ["yt_dlp"]
for pkg in ("yt_dlp", "imageio_ffmpeg"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(["app.py"], datas=datas, binaries=binaries, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ClipGrab", console=True, upx=False)
