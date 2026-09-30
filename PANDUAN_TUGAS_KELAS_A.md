# PANDUAN LENGKAP INTEGRASI MQTT, DUMMY TEST & DASHBOARD (KELAS A & KELAS C)
**Mata Kuliah:** Teknologi Internet of Things — Kelas 5A (Kolaborasi Kelas C)  
**Project:** Smart Coffee Processing E-Nose & TinyML Classification  
**Repository:** `esp32s3-rust-coffee-enose`

---

## 1. Posisi dan Peran Kelas A vs Kelas C

Berdasarkan Dokumen Instruksi Tugas Case-Based Project (CBP):
- **Kelas A (Posisi Anda):**
  - Bertanggung jawab pada **Sensing, DAQ (ESP32-S3 + ADS1115 + DHT22), Pemrosesan Sinyal & TinyML Edge**.
  - Mengakuisisi respon sensor E-Nose dan mengirimkan **Telemetri** serta **Hasil Inferensi** melalui protokol MQTT ke Cloud Broker.
  - Mengirimkan data uji coba (Dummy Test) agar tim Kelas C dapat memetakan widget dashboard dan database mereka.
- **Kelas C:**
  - Bertindak sebagai **Cloud Backend, Database Administrator, dan Dashboard Central**.
  - Menyiapkan broker HiveMQ Cloud, menerima telemetri & inferensi dari Kelas A, dan menampilkannya di Dashboard.

---

## 2. Kredensial Kedua Server MQTT

### Server 1: HiveMQ Cloud (Server Utama Kelas C)
- **Host / Broker:** `50337aad3a524a49919d2896b549979d.s1.eu.hivemq.cloud`
- **Port:** `8883` (Wajib SSL/TLS MQTTS)
- **Username:** `ayuu-0406`
- **Password:** `04062006`
- **Topik Utama Kelas C:** `sensor/dummy`
- **Topik Baku E-Nose:** `enose/DAQ01/telemetry`, `enose/DAQ01/inference`, `enose/DAQ01/status`

### Server 2: EMQX Cloud (Serverless Cadangan Kelas A)
- **Host / Broker:** `x15beb69.ala.asia-southeast1.emqxsl.com`
- **Port:** `8883` (Wajib SSL/TLS MQTTS)
- **Username:** `pub-classA`
- **Password:** `kelasA`
- **Device ID:** `DAQ01`

---

## 3. Format Payload JSON yang Dikirim ke Dashboard Kelas C

Payload dirancang kompatibel ganda (mendukung format nested standar buku panduan E-Nose Bab 27.1 DAN flat keys untuk widget dashboard sederhana):

```json
{
  "device_id": "DAQ01",
  "coffee_id": "C01",
  "species": "Arabica",
  "bean_state": "Roasted",
  "prediction": "Arabica",
  "confidence": 0.952,
  "temperature": 29.1,
  "humidity": 61.8,
  "inference_time_ms": 82,
  "time_sec": 120,
  "mq3": 1.6556,
  "mq6": 1.2791,
  "mq7": 1.2339,
  "mq135": 1.8753,
  "tgs2600": 1.0154,
  "tgs2602": 0.9555,
  "tgs2611": 1.1264,
  "tgs2620": 1.3053,
  "gas_raw": {
    "mq3": 13245, "mq6": 10233, "mq7": 9871, "mq135": 15002,
    "tgs2600": 8123, "tgs2602": 7644, "tgs2611": 9011, "tgs2620": 10442
  },
  "gas_v": {
    "mq3": 1.6556, "mq6": 1.2791, "mq7": 1.2339, "mq135": 1.8753,
    "tgs2600": 1.0154, "tgs2602": 0.9555, "tgs2611": 1.1264, "tgs2620": 1.3053
  },
  "timestamp": "2026-09-23T20:05:00+07:00",
  "seq": 120
}
```

---

## 4. Cara Menjalankan Uji Dummy di Visual Studio (VS Code)

Buka folder project di Visual Studio Code (`File -> Open Folder` arahkan ke folder ini).

### Opsi A: Streamer Simultan ke KEDUA Server (Rekomendasi Utama)
Di terminal VS Code, jalankan:
```bash
python dual_server_streamer.py
```
*Skrip ini akan:*
1. Mengkoneksikan ke **Server 1 (EMQX)** dan **Server 2 (HiveMQ Kelas C)** secara simultan dengan enkripsi TLS port 8883.
2. Mengirimkan data 8 sensor MOS, DHT22, dan inferensi TinyML secara terus menerus (1 Hz).
3. Menampilkan dashboard terminal langsung di VS Code.
4. Dashboard Kelas C akan langsung menerima data live pada topik `sensor/dummy` dan `enose/DAQ01/#`.
5. Data otomatis dicatat ke database SQLite lokal `enose_database.sqlite`.

### Opsi B: Monitor Live Penerima di VS Code
Di terminal kedua (Split Terminal di VS Code), jalankan:
```bash
python vscode_enose_monitor.py hivemq
```
*Skrip ini bertindak sebagai viewer/penerima real-time untuk memverifikasi data yang masuk ke broker HiveMQ Cloud Kelas C.*

### Opsi C: Verifikasi Cepat (Quick Self-Test)
```bash
python verify_dual_flow.py
```
*Menguji handshake SSL/TLS, otentikasi username/password, dan loopback kirim-terima ke kedua server sekaligus.*

---

## 5. Pesan untuk Rekan Tim Kelas C

Beritahu tim Kelas C bahwa:
1. Data dummy sudah mengalir aktif ke HiveMQ Cloud mereka pada topik **`sensor/dummy`** dan **`enose/DAQ01/inference`**.
2. Key yang dapat digunakan pada widget dashboard:
   - Suhu: `temperature`
   - Kelembapan: `humidity`
   - Klasifikasi: `prediction` (Nilai: "Arabica" / "Robusta")
   - Tingkat Keyakinan: `confidence` (Nilai desimal misal 0.95)
   - Respon Gas: `mq3`, `mq6`, `mq7`, `mq135`, `tgs2600`, `tgs2602`, `tgs2611`, `tgs2620`
3. **Catatan Sesuai Buku Panduan Bab 28.2:** Jangan gunakan label "Accuracy: 95%" pada satu kartu prediksi di dashboard. Gunakan label **"Confidence: 95%"** (Tingkat Keyakinan Prediksi) agar tidak disalahkan dosen penguji saat technical defense!
