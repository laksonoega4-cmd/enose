"""
=============================================================================
Smart Coffee E-Nose - VS Code Dummy Data & Device Simulator (Kelas A)
Mata Kuliah: Teknologi Internet of Things - Kelas 5A
Fungsi: Mensimulasikan perangkat ESP32-S3 Kelas A (DAQ_DUMMY01) mengirimkan
        telemetri 8 sensor gas MOS, data DHT22, dan hasil inferensi TinyML,
        serta merespons perintah OTA dari Kelas C.
=============================================================================
"""

import ssl
import sys
import json
import time
import math
import random
from datetime import datetime
import paho.mqtt.client as mqtt

# ==================== KONFIGURASI ====================
BROKER_HOST = "x15beb69.ala.asia-southeast1.emqxsl.com"
BROKER_PORT = 8883
MQTT_USER = "pub-classA"
MQTT_PASS = "kelasA"
DEVICE_ID = "DAQ_DUMMY01"

# Profil Kopi Dummy (Sesuai Buku Panduan Bagian 12 & 17)
SAMPLE_PROFILES = [
    {"coffee_id": "C01", "species": "Arabica", "state": "Green", "batch": "B1", "aliquot": "A01"},
    {"coffee_id": "C02", "species": "Robusta", "state": "Roasted", "batch": "B2", "aliquot": "A01"},
    {"coffee_id": "C07", "species": "Arabica", "state": "Roasted", "batch": "B3", "aliquot": "A04"},
    {"coffee_id": "R00", "species": "Reference", "state": "Standard", "batch": "B1", "aliquot": "A01"}
]

current_sample_idx = 0
seq_counter = 0

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0 or str(rc) == "Success":
        print(f"[+] Terkoneksi ke EMQX Cloud ({BROKER_HOST}:{BROKER_PORT})")
        print(f"[+] Device ID: {DEVICE_ID} aktif (Mode: Simulator Dummy Data)")
        
        # Publish status online (Retained)
        status_payload = json.dumps({
            "device_id": DEVICE_ID,
            "status": "online",
            "fw_version": "1.0.0",
            "role": "Class-A DAQ Transmitter",
            "timestamp": datetime.now().astimezone().isoformat()
        })
        client.publish(f"enose/{DEVICE_ID}/status", status_payload, qos=1, retain=True)
        
        # Dengarkan topik perintah OTA dari Kelas C
        ota_sub_topic = f"enose/{DEVICE_ID}/ota/trigger"
        client.subscribe(ota_sub_topic, qos=1)
        client.subscribe(f"enose/{DEVICE_ID}/command", qos=1)
        print(f"[+] Mendengarkan perintah OTA di topik: {ota_sub_topic}")
        print("\nMemulai transmisi data dummy ke broker MQTT...")
    else:
        print(f"[X] Gagal terkoneksi, return code: {rc}")

def on_message(client, userdata, msg):
    topic = msg.topic
    print(f"\n[!] PERINTAH DITERIMA DARI BROKER: Topik [{topic}]")
    try:
        data = json.loads(msg.payload.decode())
        print(f"Payload: {json.dumps(data, indent=2)}")
        
        if "ota/trigger" in topic:
            target_version = data.get("version", "1.0.1")
            fw_url = data.get("url", "http://example.com/firmware.bin")
            checksum = data.get("checksum", "sha256...")
            
            print(f"\n>>> [OTA SIMULATOR] Menerima instruksi update firmware ke versi: {target_version}")
            print(f">>> [OTA SIMULATOR] URL: {fw_url}")
            
            # Balas progres OTA ke broker agar Kelas C / Dashboard melihat statusnya
            ota_status_topic = f"enose/{DEVICE_ID}/ota/status"
            
            # Step 1: Downloading
            print(">>> [OTA STEP 1/3] Downloading firmware chunk...")
            client.publish(ota_status_topic, json.dumps({
                "device_id": DEVICE_ID,
                "ota_state": "DOWNLOADING",
                "progress_pct": 35,
                "target_version": target_version
            }), qos=1)
            time.sleep(2)
            
            # Step 2: Verifying
            print(">>> [OTA STEP 2/3] Verifying checksum...")
            client.publish(ota_status_topic, json.dumps({
                "device_id": DEVICE_ID,
                "ota_state": "VERIFYING",
                "progress_pct": 100,
                "checksum_status": "MATCH"
            }), qos=1)
            time.sleep(2)
            
            # Step 3: Updated & Rebooting
            print(">>> [OTA STEP 3/3] Flash success! Rebooting...")
            client.publish(ota_status_topic, json.dumps({
                "device_id": DEVICE_ID,
                "ota_state": "UPDATED",
                "message": f"Successfully upgraded to version {target_version}. Rebooting."
            }), qos=1)
            
    except Exception as e:
        print(f"[ERROR] Gagal memproses perintah: {e}")

def generate_sensor_values(step_s):
    # Simulasi dinamika respon gas MOS (baseline -> exponential rise -> plateau)
    tau = 120.0 # konstanta waktu difusi VOC
    rise = 1.0 - math.exp(-step_s / tau) if step_s > 0 else 0.0
    
    # 8 Sensor Gas MOS: S1-S8 (MQ-3, MQ-6, MQ-7, MQ-135, TGS2600, TGS2602, TGS2611, TGS2620)
    # Tegangan dasar (baseline V) + respon gas
    base_v = [1.2, 1.0, 1.1, 1.5, 0.8, 0.7, 0.9, 1.1]
    gains = [0.8, 0.5, 0.4, 0.9, 0.7, 0.95, 0.4, 0.6]
    
    sensor_names = ["mq3", "mq6", "mq7", "mq135", "tgs2600", "tgs2602", "tgs2611", "tgs2620"]
    raw_dict = {}
    v_dict = {}
    
    noise = random.uniform(-0.02, 0.02)
    for i, name in enumerate(sensor_names):
        v = base_v[i] + (gains[i] * rise) + noise
        v = max(0.1, min(4.8, v))
        v_dict[name] = round(v, 4)
        # ADC ADS1115 16-bit approx (gain 1x +-4.096V)
        adc_raw = int(v * (32767.0 / 4.096))
        raw_dict[name] = adc_raw
        
    temp = round(28.5 + random.uniform(-0.3, 0.5), 1)
    rh = round(60.2 + random.uniform(-0.8, 0.8), 1)
    
    return raw_dict, v_dict, temp, rh

def main():
    global current_sample_idx, seq_counter
    
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE_ID}_SIM")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    
    # Last Will and Testament (LWT)
    lwt_payload = json.dumps({
        "device_id": DEVICE_ID,
        "status": "offline",
        "reason": "connection lost"
    })
    client.will_set(f"enose/{DEVICE_ID}/status", lwt_payload, qos=1, retain=True)
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"Menghubungkan {DEVICE_ID} ke EMQX Cloud broker...")
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()
    
    time.sleep(2)
    
    step_s = 0
    try:
        while True:
            seq_counter += 1
            sample = SAMPLE_PROFILES[current_sample_idx]
            raw_vals, v_vals, temp, rh = generate_sensor_values(step_s)
            now_iso = datetime.now().astimezone().isoformat()
            
            # 1. Publish Telemetri (Sensor data mentah) - QoS 0
            telemetry_payload = {
                "device_id": DEVICE_ID,
                "step_s": step_s,
                "temperature": temp,
                "humidity": rh,
                "gas_raw": raw_vals,
                "gas_v": v_vals,
                "timestamp": now_iso
            }
            client.publish(f"enose/{DEVICE_ID}/telemetry", json.dumps(telemetry_payload), qos=0)
            print(f"[{time.strftime('%H:%M:%S')}] Telemetri dikirim (step {step_s}s) - T: {temp}°C, RH: {rh}%")
            
            # 2. Tiap kelipatan 15 detik (atau saat akhir siklus): Kirim hasil Inferensi TinyML
            if step_s > 0 and step_s % 15 == 0:
                confidence = round(random.uniform(0.88, 0.98), 3)
                inference_payload = {
                    "device_id": DEVICE_ID,
                    "coffee_id": sample["coffee_id"],
                    "prediction": sample["species"],
                    "confidence": confidence,
                    "temperature": temp,
                    "humidity": rh,
                    "inference_time_ms": random.randint(65, 95),
                    "timestamp": now_iso,
                    "batch_id": sample["batch"],
                    "aliquot_id": sample["aliquot"],
                    "measurement_id": f"{DEVICE_ID}_{sample['batch']}_{sample['coffee_id']}_{sample['aliquot']}_M{seq_counter:02d}",
                    "model_version": "v1.0-tinyml",
                    "fw_version": "1.0.0",
                    "seq": seq_counter
                }
                client.publish(f"enose/{DEVICE_ID}/inference", json.dumps(inference_payload), qos=1)
                print(f" >>> [INFERENCE DIPUBLISH] Hasil: {sample['species']} ({confidence*100:.1f}%) untuk Sample {sample['coffee_id']}")
                
            step_s += 3
            if step_s > 100:
                step_s = 0
                current_sample_idx = (current_sample_idx + 1) % len(SAMPLE_PROFILES)
                
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\nSimulator dimatikan...")
        offline_payload = json.dumps({"device_id": DEVICE_ID, "status": "offline"})
        client.publish(f"enose/{DEVICE_ID}/status", offline_payload, qos=1, retain=True)
        time.sleep(1)
        client.loop_stop()
        client.disconnect()
        print("Selesai.")

if __name__ == "__main__":
    main()
