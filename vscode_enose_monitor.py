"""
=============================================================================
Smart Coffee E-Nose - VS Code MQTT Monitor & Database Logger
Mata Kuliah: Teknologi Internet of Things - Kelas 5A (Kolaborasi Kelas C)
=============================================================================
Fungsi:
- Berfungsi sebagai monitor live di terminal Visual Studio Code.
- Menerima data telemetri (8 MOS + DHT22) dan hasil inferensi TinyML
  dari broker HiveMQ Cloud (Kelas C) dan/atau EMQX Cloud (Kelas A).
- Mendengarkan topik: sensor/dummy, enose/#.
- Menyimpan seluruh log ke database lokal SQLite (enose_database.sqlite).
=============================================================================
"""

import ssl
import sys
import json
import time
import sqlite3
import os
from datetime import datetime
import paho.mqtt.client as mqtt

# Konfigurasi Server
BROKERS = {
    "hivemq": {
        "name": "HiveMQ Cloud (Server Kelas C)",
        "host": "50337aad3a524a49919d2896b549979d.s1.eu.hivemq.cloud",
        "port": 8883,
        "user": "ayuu-0406",
        "pass": "04062006",
    },
    "emqx": {
        "name": "EMQX Cloud (Server Kelas A)",
        "host": "x15beb69.ala.asia-southeast1.emqxsl.com",
        "port": 8883,
        "user": "pub-classA",
        "pass": "kelasA",
    }
}

DB_FILE = "enose_database.sqlite"
CSV_DIR = "01_raw_data"

def init_db():
    os.makedirs(CSV_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inference_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        coffee_id TEXT,
        prediction TEXT,
        confidence REAL,
        temperature REAL,
        humidity REAL,
        inference_time_ms INTEGER,
        batch_id TEXT,
        aliquot_id TEXT,
        measurement_id TEXT,
        model_version TEXT,
        fw_version TEXT,
        seq INTEGER,
        timestamp TEXT,
        received_at TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telemetry_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        coffee_id TEXT,
        temp REAL,
        rh REAL,
        gas_v TEXT,
        gas_raw TEXT,
        timestamp TEXT,
        server1_sent INTEGER,
        server2_sent INTEGER,
        received_at TEXT
    )""")
    conn.commit()
    conn.close()

def save_inference_to_db(data):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO inference_logs (
            device_id, coffee_id, prediction, confidence, temperature, humidity,
            inference_time_ms, batch_id, aliquot_id, measurement_id, model_version,
            fw_version, seq, timestamp, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("device_id"),
            data.get("coffee_id"),
            data.get("prediction"),
            data.get("confidence"),
            data.get("temperature"),
            data.get("humidity"),
            data.get("inference_time_ms"),
            data.get("batch_id"),
            data.get("aliquot_id"),
            data.get("measurement_id"),
            data.get("model_version"),
            data.get("fw_version"),
            data.get("seq"),
            data.get("timestamp"),
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

def save_telemetry_to_db(data):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO telemetry_logs (
            device_id, coffee_id, temp, rh, gas_v, gas_raw, timestamp, server1_sent, server2_sent, received_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("device_id"),
            data.get("coffee_id"),
            data.get("temperature"),
            data.get("humidity"),
            json.dumps(data.get("gas_v", {})),
            json.dumps(data.get("gas_raw", {})),
            data.get("timestamp"),
            1, 1,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] {e}")

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0 or str(rc) == "Success":
        server_name = userdata.get("name", "Broker")
        print("\n" + "=" * 70)
        print(f"[OK] TERHUBUNG KE BROKER: {server_name}")
        print("=" * 70)
        topics = [
            ("sensor/dummy", 0),
            ("enose/+/telemetry", 0),
            ("enose/+/inference", 1),
            ("enose/+/status", 1),
            ("enose/+/ota/#", 1)
        ]
        for t, qos in topics:
            client.subscribe(t, qos=qos)
            print(f" [+] Subscribed: {t}")
        print("\nMenunggu data live dari simulator atau ESP32-S3...\n" + "-" * 70)
    else:
        print(f"[FAIL] Gagal terkoneksi! Return code: {rc}")

def on_message(client, userdata, msg):
    now_str = datetime.now().strftime("%H:%M:%S")
    topic = msg.topic
    server_name = userdata.get("name", "Broker")

    try:
        data = json.loads(msg.payload.decode('utf-8'))
    except Exception:
        print(f"[{now_str}] [{server_name}] [{topic}] RAW: {msg.payload[:40]}...")
        return

    # 1. Cek apakah ini payload INFERENSI
    if "prediction" in data or "/inference" in topic:
        pred = data.get("prediction", "UNKNOWN")
        conf = data.get("confidence", 0.0)
        dev = data.get("device_id", "DAQ01")
        temp = data.get("temperature", 0.0)
        hum = data.get("humidity", 0.0)
        t_ms = data.get("inference_time_ms", 0)
        c_id = data.get("coffee_id", "-")
        b_id = data.get("batch_id", "-")
        print(f"\n[{now_str}] >>> [TINYML INFERENCE] ({server_name})")
        print(f"       Device: {dev} | Sample: {c_id} (Batch {b_id})")
        print(f"       Prediksi : \033[92m{pred}\033[0m")
        print(f"       Confidence: {conf*100:.1f}% | Latensi: {t_ms} ms")
        print(f"       T: {temp}C | RH: {hum}%")
        save_inference_to_db(data)

    # 2. Cek apakah ini payload TELEMETRI SENSOR
    elif "gas_v" in data or "gas_raw" in data or "mq3" in data:
        dev = data.get("device_id", "DAQ01")
        temp = data.get("temperature", "-")
        hum = data.get("humidity", "-")
        t_sec = data.get("time_sec", "-")
        c_id = data.get("coffee_id", "-")
        
        # Ambil ringkasan sensor gas
        mq3 = data.get("mq3", data.get("gas_v", {}).get("mq3", "-"))
        s6 = data.get("tgs2602", data.get("gas_v", {}).get("tgs2602", "-"))
        mq135 = data.get("mq135", data.get("gas_v", {}).get("mq135", "-"))
        
        print(f"[{now_str}] [TELEMETRI] ({server_name}) Dev:{dev} t={t_sec}s | Sample:{c_id} | "
              f"T:{temp}C, RH:{hum}% | MQ3:{mq3}V, S6:{s6}V, MQ135:{mq135}V")
        save_telemetry_to_db(data)

    # 3. Status atau Perintah Lain
    else:
        print(f"[{now_str}] [{server_name}] [{topic}]: {json.dumps(data)}")

def start_monitor(target="hivemq"):
    init_db()
    cfg = BROKERS.get(target, BROKERS["hivemq"])
    print(f"Memulai VS Code E-Nose Monitor untuk: {cfg['name']}...")
    print(f"Host: {cfg['host']}:{cfg['port']}")
    print(f"User: {cfg['user']}")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"VSCODE_MONITOR_{int(time.time())}", userdata=cfg)
    client.username_pw_set(cfg['user'], cfg['pass'])
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    client.tls_set_context(ctx)
    client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(cfg['host'], cfg['port'], keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nMonitor dihentikan oleh user.")
        client.disconnect()
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")

if __name__ == "__main__":
    target_server = "hivemq"
    if len(sys.argv) > 1 and sys.argv[1].lower() in BROKERS:
        target_server = sys.argv[1].lower()
    start_monitor(target_server)
