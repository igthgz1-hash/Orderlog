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
