# AirDrop-compatible receiver for PC

ทำให้เครื่อง PC/Notebook ปรากฏใน AirDrop sheet ของ iPhone/iPad และ Samsung
Quick Share (ซึ่งตอนนี้พูดโปรโตคอล AirDrop ได้ในโหมดส่งไปอุปกรณ์ Apple) แล้วรับไฟล์
ที่ถูกส่งมาได้ โดยไม่ต้องมีแอปอื่นติดตั้งเพิ่มบนมือถือ

## วิธีทำงาน

โปรโตคอล AirDrop ถูกวิศวกรรมย้อนกลับ (reverse-engineered) มาแล้วโดยทีมวิจัย
(ดู "Open Sesame" ของ TU Darmstadt และโปรเจกต์ OpenDrop) และมีขั้นตอนหลักๆ คือ:

1. **ประกาศตัวตนผ่าน Bluetooth LE** — สิ่งที่ทำให้ไอคอน PC โผล่ในหน้าจอ AirDrop
   ของ iOS จริงๆ คือสัญญาณ BLE นี้ (ยืนยันจากการทดสอบจริง: mDNS อย่างเดียวไม่พอ
   ต่อให้เครื่องส่งมองเห็น service ผ่าน mDNS ได้ แต่ AirDrop UI จะไม่แสดงถ้าไม่มี BLE
   beacon ควบคู่ไปด้วย) — ดูรายละเอียดที่ `ble_beacon_windows.py`
2. **ค้นหาอุปกรณ์ผ่าน Bonjour/mDNS** — ประกาศ service ชื่อ `_airdrop._tcp.local.`
   เพื่อให้เครื่องส่งมองเห็น IP/พอร์ตสำหรับต่อผ่าน HTTPS
3. **ตรวจสอบว่าถึงกันไหม** — เครื่องส่งยิง `POST /Discover` มาก่อน
4. **ขออนุญาตส่ง** — เครื่องส่งยิง `POST /Ask` พร้อมชื่อไฟล์ ให้ผู้ใช้ที่ PC
   ยืนยันรับ/ปฏิเสธ
5. **โอนไฟล์จริง** — เครื่องส่งยิง `POST /Upload` พร้อมไฟล์ทั้งหมดในรูป cpio
   archive ก้อนเดียว

ขั้นที่ 2-5 คุยกันผ่าน HTTPS (TLS self-signed certificate) บนพอร์ตเดียวกับที่
ประกาศไว้ใน mDNS (ค่าเริ่มต้น 8770)

## ข้อจำกัดที่ควรรู้ก่อนใช้

- **ต้องอยู่ Wi-Fi เครือข่ายเดียวกัน** ระหว่าง PC กับมือถือ AirDrop จริงมีโหมด
  ทำงานแบบไม่ต้องแชร์ Wi-Fi โดยใช้ AWDL (Apple Wireless Direct Link) ซึ่งเป็น
  เลเยอร์ Wi-Fi พิเศษของ Apple ที่ต้องเข้าถึงฮาร์ดแวร์วิทยุระดับ driver — เครื่องมือนี้
  **ไม่ได้ทำ AWDL** เพราะทำได้ยากมากและทดสอบไม่ได้ในสภาพแวดล้อมทั่วไป ทางแก้คือ
  ต่อ Wi-Fi วงเดียวกันทั้งสองเครื่อง (ฮอตสปอตจากมือถือก็ใช้ได้)
- ใช้ certificate self-signed ธรรมดา (ไม่ใช่ Apple push cert ตัวจริง) ดังนั้นจะใช้
  ได้กับโหมด **"Everyone" ของ AirDrop เท่านั้น** ไม่ใช่ "Contacts Only"
- ทดสอบ/ปรับ TXT record หรือ magic values บางตัวของ mDNS อาจต้องลองจริงกับ
  อุปกรณ์ในมือ เพราะ Apple ไม่เคยเปิดสเปกนี้เป็นทางการ — ค่าที่ใส่ไว้อ้างอิงจาก
  เอกสารสาธารณะที่มีอยู่ ไม่ได้การันตีว่าใช้ได้ 100% กับทุกเวอร์ชัน iOS/One UI
- **BLE beacon (`ble_beacon_windows.py`) ใช้ได้เฉพาะ Windows** และเนื้อหา payload
  ข้างในเป็นการสร้างขึ้นจากงานวิจัยสาธารณะที่ยังไม่ยืนยัน 100% ว่าตรงกับของจริง
  ถ้าลองแล้วยังไม่เห็น PC ในหน้า AirDrop นี่คือจุดแรกที่ต้องปรับ — วิธีเทียบที่แม่นสุดคือ
  ใช้แอปสแกน BLE เช่น nRF Connect บนมือถืออีกเครื่อง จับสัญญาณจากอุปกรณ์ Apple จริง
  ที่เปิดรับ AirDrop อยู่ มาเทียบ byte กับที่โค้ดนี้ส่งออกไป
- ยังไม่รองรับ macOS/Linux สำหรับชั้น BLE (โค้ดจะข้ามส่วนนี้ไปเฉยๆ บนเครื่องที่ไม่ใช่
  Windows แล้วทำงานต่อแบบไม่มี BLE beacon)

## การใช้งาน

```bash
cd airdrop-tool
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 airdrop_server.py --name "ห้องทำงาน PC" --out-dir ~/Downloads/AirDrop
```

จากนั้นที่มือถือ:
- **iPhone**: เปิดหน้าที่ต้องการแชร์ → กด Share → AirDrop → ต้องเห็นชื่อ PC ปรากฏ
  (ถ้ายังไม่เห็น ให้ตรวจว่า AirDrop ของ iPhone เปิดเป็น "Everyone" และอยู่ Wi-Fi
  วงเดียวกับ PC)
- **Samsung (One UI ที่รองรับ)**: เปิด Quick Share → เลือกไฟล์ → ถ้ารุ่นนั้นรองรับการ
  ส่งแบบ AirDrop-compatible จะเห็นชื่อ PC ในรายชื่ออุปกรณ์ที่พบ

ทุกครั้งที่มีการขอส่งไฟล์ โปรแกรมจะถามในเทอร์มินัลว่ายอมรับหรือไม่
(ใส่ `--auto-accept` ถ้าต้องการรับอัตโนมัติโดยไม่ถาม — ใช้ด้วยความระมัดระวัง
เพราะเปิดรับไฟล์จากใครก็ได้ในเครือข่ายเดียวกัน)

## โครงสร้างไฟล์

- `airdrop_server.py` — entrypoint หลัก, HTTPS server + ประกาศ mDNS + เปิด BLE beacon
- `ble_beacon_windows.py` — BLE beacon ที่ทำให้ไอคอนโผล่ในหน้า AirDrop (Windows only, experimental)
- `plist_protocol.py` — สร้าง/อ่าน binary plist ตาม endpoint ของ AirDrop
- `cpio_reader.py` — ตัวอ่าน cpio archive แบบ newc format (ไม่ต้องพึ่ง binary ภายนอก)
- `certs.py` — สร้างและ cache self-signed TLS certificate
- `check_mdns.py` — สคริปต์ตรวจสอบว่า mDNS service ประกาศออกไปถึงเครือข่ายจริงไหม (ใช้ตอน debug)

## ลิขสิทธิ์

สงวนลิขสิทธิ์ทั้งหมด — ดูรายละเอียดที่ [`LICENSE`](../LICENSE) ที่ root ของ repo
