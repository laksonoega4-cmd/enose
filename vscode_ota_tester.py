"""
=============================================================================
Smart Coffee E-Nose - VS Code OTA Tester (Simulasi Server OTA Kelas C)
Mata Kuliah: Teknologi Internet of Things - Kelas 5A
Fungsi: Menguji prosedur OTA ke perangkat Kelas A (DAQ_DUMMY01).
        1. Menyediakan server HTTP lokal untuk file binary firmware (.bin)
        2. Menghitung hash SHA-256 dari firmware
        3. Mengirim trigger OTA via MQTT broker EMQX
        4. Memonitor status & respon balik progres OTA
=============================================================================
"""

import ssl
import os
import sys
import json
import time
import hashlib
import socket
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import paho.mqtt.client as mqtt

# ==================== KONFIGURASI ====================
BROKER_HOST = "x15beb69.ala.asia-southeast1.emqxsl.com"
BROKER_PORT = 8883
MQTT_USER = "pub-classA"
MQTT_PASS = "kelasA"
TARGET_DEVICE = "DAQ_DUMMY01"
HTTP_PORT = 8080

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def compute_sha256(filepath):
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def start_http_server(port):
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[+] OTA Controller terhubung ke Broker EMQX ({BROKER_HOST}:{BROKER_PORT})")
    # Dengarkan feedback status OTA dari perangkat
    status_topic = f"enose/{TARGET_DEVICE}/ota/#"
    client.subscribe(status_topic, qos=1)
    client.subscribe(f"enose/{TARGET_DEVICE}/status", qos=1)
    print(f"[+] Subscribed ke status OTA: {status_topic}")

def on_message(client, userdata, msg):
    topic = msg.topic
    print(f"\n[RESPON OTA DARI DEVICE] Topik: {topic}")
    try:
        data = json.loads(msg.payload.decode())
        state = data.get("ota_state", data.get("status", "N/A"))
        pct = data.get("progress_pct", "")
        msg_text = data.get("message", "")
        print(f"  Status : \033[94m{state}\033[0m {f'({pct}%)' if pct != '' else ''}")
        if msg_text:
            print(f"  Pesan  : {msg_text}")
    except Exception:
        print(f"  Payload: {msg.payload.decode('utf-8', errors='ignore')}")

def main():
    print("="*70)
    print("      VS CODE OTA TESTER (SIMULASI PENGIRIMAN OTA DARI KELAS C)      ")
    print("="*70)
    
    # Cari file firmware .bin di direktori
    bin_files = [f for f in os.listdir(".") if f.endswith(".bin")]
    if not bin_files:
        print("[!] Tidak ditemukan file .bin di direktori saat ini.")
        print("    Membuat dummy firmware file 'firmware-test.bin'...")
        with open("firmware-test.bin", "wb") as f:
            f.write(b"ESP32-S3_DUMMY_FIRMWARE_V1.0.1_" + os.urandom(1024))
        bin_file = "firmware-test.bin"
    else:
        bin_file = bin_files[0]
        print(f"[+] Ditemukan file firmware: {bin_file}")
        
    fw_hash = compute_sha256(bin_file)
    fw_size = os.path.getsize(bin_file)
    local_ip = get_local_ip()
    fw_url = f"http://{local_ip}:{HTTP_PORT}/{bin_file}"
    
    print(f"[+] File Size : {fw_size} bytes")
    print(f"[+] SHA-256   : {fw_hash}")
    print(f"[+] Host IP   : {local_ip}")
    print(f"[+] URL OTA   : {fw_url}")
    
    # Start HTTP Server
    print(f"\n[1] Menjalankan HTTP server lokal pada port {HTTP_PORT}...")
    start_http_server(HTTP_PORT)
    print("    [V] HTTP server aktif dan siap melayani unduhan firmware.")
    
    # Koneksi ke MQTT
    print("\n[2] Menghubungkan ke MQTT Broker...")
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="VSCODE_OTA_DISPATCHER")
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)
    client.on_connect = on_connect
    client.on_message = on_message
    
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()
    time.sleep(2)
    
    print("\n" + "="*70)
    print("Ketik 'kirim' untuk mengirim perintah OTA ke device:")
    print("Ketik 'keluar' untuk keluar.")
    print("="*70)
    
    # Mengirim perintah trigger OTA ke target device
    ota_payload = {
        "action": "OTA_UPDATE",
        "target_device": TARGET_DEVICE,
        "version": "1.0.1",
        "title": "ESP32-S3 E-Nose Firmware",
        "url": fw_url,
        "size": fw_size,
        "checksum": fw_hash,
        "checksum_algorithm": "SHA256",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+07:00")
    }
    
    trigger_topic = f"enose/{TARGET_DEVICE}/ota/trigger"
    print(f"\n[>] Mengirim Trigger OTA ke Topik: {trigger_topic}")
    print(f"[>] Isi Payload:\n{json.dumps(ota_payload, indent=2)}")
    client.publish(trigger_topic, json.dumps(ota_payload), qos=1)
    print("\n[+] Trigger OTA terkirim! Menunggu respon dari perangkat...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nOTA Tester dihentikan.")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
