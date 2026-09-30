# ClipGrab

เว็บแอปรันบนเครื่องตัวเอง สำหรับดาวน์โหลดคลิปจาก Social Media (YouTube, TikTok, Facebook, Instagram, X/Twitter, Reddit ฯลฯ — รองรับทุกเว็บที่ [yt-dlp](https://github.com/yt-dlp/yt-dlp) รองรับ)

- เลือกคุณภาพ: ต้นฉบับ (สูงสุด) / 1080p / 720p / 480p / 360p
- โหลดเฉพาะเสียง: MP3 / M4A / Opus / WAV
- แสดงความคืบหน้า และลบไฟล์ชั่วคราวอัตโนมัติหลัง 1 ชั่วโมง

## ติดตั้งและรัน
```bash
cd clipgrab
pip install -r requirements.txt
# ติดตั้ง ffmpeg (จำเป็นสำหรับรวมภาพ+เสียงคุณภาพสูง และแปลงเป็น MP3)
#   macOS: brew install ffmpeg | Ubuntu: sudo apt install ffmpeg | Windows: winget install ffmpeg
python app.py
```
เปิด http://127.0.0.1:5000

หากดาวน์โหลดไม่ได้ ให้อัปเดต: `pip install -U yt-dlp`

## หมายเหตุ
ใช้ดาวน์โหลดเฉพาะเนื้อหาที่คุณเป็นเจ้าของ หรือได้รับอนุญาต โปรดเคารพลิขสิทธิ์และข้อกำหนดของแต่ละแพลตฟอร์ม
แอปผูกกับ 127.0.0.1 เท่านั้น ไม่ควรเปิดให้ใช้งานสาธารณะโดยไม่เพิ่มระบบยืนยันตัวตน

## ไฟล์ติดตั้ง (Windows / Mac) — ไม่ต้องลง Python หรือ ffmpeg
ตัวโปรแกรมฝัง ffmpeg มาให้แล้ว สร้างไฟล์ได้ด้วย GitHub Actions (`.github/workflows/build-clipgrab.yml`):
1. ไปที่แท็บ **Actions → Build ClipGrab installers → Run workflow** (หรือ push แท็บ `clipgrab-v1.0` เพื่อออกเป็น Release)
2. รอประมาณ 5 นาที แล้วดาวน์โหลดจาก **Artifacts** (หรือหน้า Releases)
   - `ClipGrab-Windows.zip` → แตกไฟล์ ดับเบิลคลิก `ClipGrab.exe` (ถ้า SmartScreen เตือน กด *More info → Run anyway*)
   - `ClipGrab-Mac-AppleSilicon.zip` (M1/M2/M3) หรือ `ClipGrab-Mac-Intel.zip` → แตกไฟล์ คลิกขวา `OpenClipGrab.command` → Open
3. โปรแกรมจะเปิดเบราว์เซอร์เอง ปิดหน้าต่างดำ/Terminal เพื่อออก

ถ้าดาวน์โหลดจากเว็บไหนไม่ได้ ให้รัน workflow ใหม่เพื่อได้ yt-dlp เวอร์ชันล่าสุด

สร้างเองในเครื่อง: `pip install -r requirements.txt pyinstaller && pyinstaller ClipGrab.spec` → ได้ไฟล์ใน `dist/`
