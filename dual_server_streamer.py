"""
=============================================================================
Smart Coffee E-Nose - Dual Server Streamer & Visual Studio Live Dashboard
Mata Kuliah: Teknologi Internet of Things - Kelas 5A (Kolaborasi Kelas C)
=============================================================================
Fungsi:
1. Mensimulasikan perangkat ESP32-S3 E-Nose (DAQ01) dengan 8 sensor gas MOS
   (MQ-3, MQ-6, MQ-7, MQ-135, TGS2600, TGS2602, TGS2611, TGS2620) + DHT22 (T & RH).
2. Mengirimkan data telemetri & inferensi TinyML secara simultan ke KEDUA SERVER:
   - Server 1: EMQX Cloud (Serverless Kelas A)
   - Server 2: HiveMQ Cloud (Server & Dashboard Kelas C)
3. Menampilkan status transmisi live dashboard langsung di Visual Studio terminal.
4. Menyimpan seluruh log telemetri dan inferensi ke SQLite lokal (enose_database.sqlite).
=============================================================================
"""

import ssl
import sys
import json
import time
import math
import random
import sqlite3
import os
from datetime import datetime
import paho.mqtt.client as mqtt

# ==================== KONFIGURASI SERVER ====================
# Server 1: EMQX Cloud (Kelas A)
SERVER1_CFG = {
    "name": "EMQX Cloud (Kelas A)",
    "host": "x15beb69.ala.asia-southeast1.emqxsl.com",
    "port": 8883,
    "user": "pub-classA",
    "pass": "kelasA",
    "topics_pub": [
        "enose/DAQ01/telemetry",
        "enose/DAQ01/inference",
        "enose/DAQ01/status",
        "sensor/dummy"
    ]
}

# Server 2: HiveMQ Cloud (Kelas C)
SERVER2_CFG = {
    "name": "HiveMQ Cloud (Kelas C)",
    "host": "50337aad3a524a49919d2896b549979d.s1.eu.hivemq.cloud",
    "port": 8883,
    "user": "ayuu-0406",
    "pass": "04062006",
    "topics_pub": [
        "sensor/dummy",
        "enose/DAQ01/inference",
        "enose/DAQ01/telemetry",
        "enose/DAQ01/status"
    ]
}

DEVICE_ID = "DAQ01"
DB_FILE = "enose_database.sqlite"

# Daftar Sampel Kopi (Buku Panduan Hal 16 & 21)
SAMPLES = [
    {"coffee_id": "C01", "species": "Arabica", "state": "Green", "batch": "B1", "aliquot": "A01"},
    {"coffee_id": "C02", "species": "Robusta", "state": "Roasted", "batch": "B2", "aliquot": "A01"},
    {"coffee_id": "C07", "species": "Arabica", "state": "Roasted", "batch": "B3", "aliquot": "A04"},
    {"coffee_id": "R00", "species": "Reference", "state": "Standard", "batch": "B1", "aliquot": "A01"}
]

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
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
        server2_sent INTEGER
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS inference_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id TEXT,
        coffee_id TEXT,
        prediction TEXT,
        confidence REAL,
        temp REAL,
        rh REAL,
        latency_ms INTEGER,
        timestamp TEXT
    )""")
    conn.commit()
    conn.close()

def log_telemetry_db(payload, s1_ok, s2_ok):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
        INSERT INTO telemetry_logs (device_id, coffee_id, temp, rh, gas_v, gas_raw, timestamp, server1_sent, server2_sent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.get("device_id"),
            payload.get("coffee_id"),
            payload.get("temperature"),
            payload.get("humidity"),
            json.dumps(payload.get("gas_v")),
            json.dumps(payload.get("gas_raw")),
            payload.get("timestamp"),
            1 if s1_ok else 0,
            1 if s2_ok else 0
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        pass

def log_inference_db(payload):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
        INSERT INTO inference_logs (device_id, coffee_id, prediction, confidence, temp, rh, latency_ms, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload.get("device_id"),
            payload.get("coffee_id"),
            payload.get("prediction"),
            payload.get("confidence"),
            payload.get("temperature"),
            payload.get("humidity"),
            payload.get("inference_time_ms"),
            payload.get("timestamp")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        pass

# Setup MQTT Client Helper
def create_mqtt_client(cfg):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"ENOSE_STREAM_{cfg['user']}_{int(time.time())}")
    client.username_pw_set(cfg['user'], cfg['pass'])
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    client.tls_set_context(ctx)
    client.tls_insecure_set(True)
    return client

# Sensor Simulation Engine (300-second session model per sample)
SESSION_DURATION = 300

class EnoseSimulator:
    def __init__(self):
        self.step = 0
        self.sample_idx = 0
        self.current_sample = SAMPLES[self.sample_idx]
        self.cycle_count = 1
        self.base_v = [1.25, 1.05, 1.12, 1.55, 0.85, 0.72, 0.95, 1.15]
        self.gains = [0.85, 0.52, 0.45, 0.92, 0.75, 0.98, 0.42, 0.65]

    def next_second(self):
        self.step += 1
        t = self.step
        
        # Jendela Waktu (Sesuai Permintaan Dosen: 300 detik per batch sampel):
        # 0-40s: Baseline window
        # 40-240s: Response window (difusi aroma kopi)
        # 240-300s: Stable late window (puncak respon)
        if t <= 40:
            diff = 0.0
        elif t <= 240:
            tau = 75.0
            diff = 1.0 - math.exp(-(t - 40) / tau)
        else:
            diff = 1.0 - math.exp(-200.0 / 75.0)
            
        noise = lambda: random.uniform(-0.008, 0.008)
        
        # Respons sensor dalam domain tegangan Vout
        gas_v = {}
        gas_raw = {}
        sensor_names = ["mq3", "mq6", "mq7", "mq135", "tgs2600", "tgs2602", "tgs2611", "tgs2620"]
        
        for i, name in enumerate(sensor_names):
            # Arabica memberikan respons TGS2602 dan MQ-3 lebih tinggi; Robusta MQ-135 dan MQ-6
            species_mult = 1.15 if self.current_sample["species"] == "Arabica" and i in [0, 5] else 1.0
            val_v = round(self.base_v[i] + (self.gains[i] * diff * species_mult) + noise(), 4)
            # ADS1115 16-bit code (FSR +-4.096V, 1 LSB = 125 uV)
            raw_code = int((val_v / 4.096) * 32767)
            gas_v[name] = max(0.0, val_v)
            gas_raw[name] = max(0, min(32767, raw_code))
            
        temp = round(28.5 + (0.5 * math.sin(t / 60.0)) + random.uniform(-0.1, 0.1), 1)
        rh = round(62.0 + (1.2 * math.cos(t / 70.0)) + random.uniform(-0.2, 0.2), 1)
        
        # Cek apakah 300 detik telah selesai
        cycle_finished = False
        if self.step >= SESSION_DURATION:
            cycle_finished = True
            self.step = 0
            self.sample_idx = (self.sample_idx + 1) % len(SAMPLES)
            self.current_sample = SAMPLES[self.sample_idx]
            self.cycle_count += 1
        
        return gas_v, gas_raw, temp, rh, t, cycle_finished

def run_streamer(max_iterations=None, interval=1.0):
    init_db()
    print("=" * 75)
    print(" [STREAMER] SMART COFFEE E-NOSE - DUAL SERVER STREAMER (KELAS A & C)")
    print("=" * 75)
    print(f"[*] Menghubungkan ke SERVER 1 (Kelas A): {SERVER1_CFG['host']}")
    print(f"[*] Menghubungkan ke SERVER 2 (Kelas C): {SERVER2_CFG['host']}")
    print("=" * 75)

    s1_connected = False
    s2_connected = False

    def on_connect_s1(c, u, f, rc, p=None):
        nonlocal s1_connected
        s1_connected = (rc == 0 or str(rc) == "Success")
        if s1_connected:
            print(f"  [OK] Server 1 (EMQX Cloud) Terkoneksi!")

    def on_connect_s2(c, u, f, rc, p=None):
        nonlocal s2_connected
        s2_connected = (rc == 0 or str(rc) == "Success")
        if s2_connected:
            print(f"  [OK] Server 2 (HiveMQ Cloud - Kelas C) Terkoneksi!")

    c1 = create_mqtt_client(SERVER1_CFG)
    c1.on_connect = on_connect_s1
    c2 = create_mqtt_client(SERVER2_CFG)
    c2.on_connect = on_connect_s2

    try:
        c1.connect(SERVER1_CFG['host'], SERVER1_CFG['port'], keepalive=60)
        c1.loop_start()
    except Exception as e:
        print(f"  [!] Gagal connect Server 1: {e}")

    try:
        c2.connect(SERVER2_CFG['host'], SERVER2_CFG['port'], keepalive=60)
        c2.loop_start()
    except Exception as e:
        print(f"  [!] Gagal connect Server 2: {e}")

    # Tunggu koneksi handshake
    time.sleep(2.5)

    sim = EnoseSimulator()
    print("\n[+] Memulai streaming data dummy secara real-time...")
    print("[+] Tekan Ctrl+C untuk menghentikan streaming kapan saja.\n")

    seq = 0
    try:
        while max_iterations is None or seq < max_iterations:
            seq += 1
            gas_v, gas_raw, temp, rh, t_sec, cycle_finished = sim.next_second()
            cur_s = sim.current_sample
            now_iso = datetime.now().astimezone().isoformat()

            # 1. Payload Telemetri (Format Standar E-Nose + Flat Keys untuk Fleksibilitas Dashboard)
            telemetry_payload = {
                "device_id": DEVICE_ID,
                "coffee_id": cur_s["coffee_id"],
                "batch_id": cur_s["batch"],
                "aliquot_id": cur_s["aliquot"],
                "time_sec": t_sec,
                "temperature": temp,
                "humidity": rh,
                "mq3": gas_v["mq3"],
                "mq6": gas_v["mq6"],
                "mq7": gas_v["mq7"],
                "mq135": gas_v["mq135"],
                "tgs2600": gas_v["tgs2600"],
                "tgs2602": gas_v["tgs2602"],
                "tgs2611": gas_v["tgs2611"],
                "tgs2620": gas_v["tgs2620"],
                "gas_v": gas_v,
                "gas_raw": gas_raw,
                "timestamp": now_iso,
                "seq": seq
            }

            # 2. Payload Inferensi (dikirim periodik setiap 10 detik / saat t >= 40)
            inference_payload = None
            if t_sec % 10 == 0:
                is_arabica = (cur_s["species"] == "Arabica")
                conf = round(random.uniform(0.92, 0.98), 3) if is_arabica else round(random.uniform(0.88, 0.95), 3)
                inference_payload = {
                    "device_id": DEVICE_ID,
                    "coffee_id": cur_s["coffee_id"],
                    "prediction": cur_s["species"],
                    "confidence": conf,
                    "bean_state": cur_s["state"],
                    "temperature": temp,
                    "humidity": rh,
                    "inference_time_ms": random.randint(78, 92),
                    "model_version": "tinyml-v1.0",
                    "fw_version": "1.0.0",
                    "timestamp": now_iso,
                    "seq": seq
                }

            # Payload BERSIH khusus sensor/dummy untuk Dashboard Kelas C
            # (tanpa nested gas_v & gas_raw yang duplikat — supaya mudah dibaca di HiveMQ WebClient)
            dummy_clean_payload = {
                "device_id":  DEVICE_ID,
                "coffee_id":  cur_s["coffee_id"],
                "sample":     cur_s["species"],
                "time_sec":   t_sec,
                "temperature": temp,
                "humidity":   rh,
                "MQ3_V":      gas_v["mq3"],
                "MQ6_V":      gas_v["mq6"],
                "MQ7_V":      gas_v["mq7"],
                "MQ135_V":    gas_v["mq135"],
                "TGS2600_V":  gas_v["tgs2600"],
                "TGS2602_V":  gas_v["tgs2602"],
                "TGS2611_V":  gas_v["tgs2611"],
                "TGS2620_V":  gas_v["tgs2620"],
                "prediction": cur_s["species"] if t_sec % 10 == 0 else "sampling",
                "confidence": round(random.uniform(0.92, 0.98), 3) if t_sec % 10 == 0 else None,
                "timestamp":  now_iso,
                "seq":        seq
            }
            # Hapus key None agar JSON lebih bersih
            dummy_clean_payload = {k: v for k, v in dummy_clean_payload.items() if v is not None}

            # Publikasikan Telemetri ke KEDUA SERVER
            s1_pub_ok = False
            s2_pub_ok = False
            tel_json       = json.dumps(telemetry_payload)
            dummy_clean_json = json.dumps(dummy_clean_payload)

            if s1_connected:
                c1.publish("enose/DAQ01/telemetry", tel_json, qos=0)
                c1.publish("sensor/dummy", dummy_clean_json, qos=0)
                s1_pub_ok = True

            if s2_connected:
                # HiveMQ Cloud untuk Kelas C — pakai payload bersih di sensor/dummy
                c2.publish("sensor/dummy", dummy_clean_json, qos=0)
                c2.publish("enose/DAQ01/telemetry", tel_json, qos=0)
                s2_pub_ok = True

            # Publikasikan Inferensi bila ada
            if inference_payload:
                inf_json = json.dumps(inference_payload)
                if s1_connected:
                    c1.publish("enose/DAQ01/inference", inf_json, qos=1)
                if s2_connected:
                    c2.publish("enose/DAQ01/inference", inf_json, qos=1)
                    c2.publish("sensor/dummy", inf_json, qos=1)
                log_inference_db(inference_payload)

            log_telemetry_db(telemetry_payload, s1_pub_ok, s2_pub_ok)

            # Tampilan Live Dashboard di Visual Studio Terminal
            inf_info = f" | TinyML: {inference_payload['prediction']} ({inference_payload['confidence']*100:.1f}%)" if inference_payload else ""
            s1_stat = "[OK]" if s1_pub_ok else "[FAIL]"
            s2_stat = "[OK]" if s2_pub_ok else "[FAIL]"
            print(f"[{datetime.now().strftime('%H:%M:%S')}] t={t_sec:03d}s/300s | "
                  f"Sample: {cur_s['coffee_id']} ({cur_s['species']}) | "
                  f"T: {temp}C, RH: {rh}% | "
                  f"MQ3:{gas_v['mq3']}V S6:{gas_v['tgs2602']}V | "
                  f"EMQX:{s1_stat} HiveMQ(Kelas C):{s2_stat}"
                  f"{inf_info}")

            if cycle_finished:
                print("\n" + "=" * 75)
                print(f"[CYCLE SELESAI] Sampling 300 detik untuk sampel {cur_s['coffee_id']} ({cur_s['species']}) SELESAI!")
                print(f"Otomatis beralih ke sampel kopi berikutnya: {sim.current_sample['coffee_id']} ({sim.current_sample['species']})...")
                print("=" * 75 + "\n")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n[!] Dihentikan oleh user (KeyboardInterrupt).")

    finally:
        print("\n[*] Menutup koneksi MQTT...")
        c1.loop_stop()
        c1.disconnect()
        c2.loop_stop()
        c2.disconnect()
        print("[+] Selesai. Data telah tersimpan di SQLite (enose_database.sqlite).")

if __name__ == "__main__":
    count = None
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            pass
    run_streamer(max_iterations=count, interval=1.0)
