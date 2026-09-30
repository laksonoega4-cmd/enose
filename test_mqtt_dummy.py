import ssl
import time
import json
import paho.mqtt.client as mqtt

BROKER = "x15beb69.ala.asia-southeast1.emqxsl.com"
PORT = 8883
USER = "pub-classA"
PASS = "kelasA"
DEVICE_ID = "DAQ_DUMMY01"

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Terkoneksi ke broker dengan code: {rc}")
    # Subscribe ke semua topik enose
    client.subscribe("enose/#")
    print("[MQTT] Subscribed ke topik: enose/#")
    
    # Kirim status online (LWT retain test)
    status_payload = json.dumps({
        "device_id": DEVICE_ID,
        "status": "online",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+07:00")
    })
    client.publish(f"enose/{DEVICE_ID}/status", status_payload, qos=1, retain=True)

def on_message(client, userdata, msg):
    print(f"\n[DITERIMA] Topik: {msg.topic}")
    try:
        data = json.loads(msg.payload.decode())
        print(f"Payload JSON:\n{json.dumps(data, indent=2)}")
    except Exception:
        print(f"Payload Raw: {msg.payload}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="VSCODE_MONITOR_TEST")
client.username_pw_set(USER, PASS)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

client.on_connect = on_connect
client.on_message = on_message

print(f"Menghubungkan ke {BROKER}:{PORT}...")
client.connect(BROKER, PORT, keepalive=60)
client.loop_start()

time.sleep(2)

# Coba kirim data dummy sesuai spesifikasi buku instruksi Section 27
inference_dummy = {
    "device_id": DEVICE_ID,
    "coffee_id": "C01",
    "prediction": "Arabica",
    "confidence": 0.943,
    "temperature": 29.5,
    "humidity": 62.1,
    "inference_time_ms": 84,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+07:00"),
    "batch_id": "B1",
    "aliquot_id": "A01",
    "measurement_id": "DAQ01_B01_C01_A01_M01",
    "model_version": "v1.0",
    "fw_version": "1.0.0",
    "seq": 1
}

telemetry_dummy = {
    "device_id": DEVICE_ID,
    "temperature": 29.5,
    "humidity": 62.1,
    "gas_raw": {
        "mq3": 13245, "mq6": 10233, "mq7": 9871, "mq135": 15002,
        "tgs2600": 8123, "tgs2602": 7644, "tgs2611": 9011, "tgs2620": 10442
    },
    "gas_v": {
        "mq3": 1.6556, "mq6": 1.2791, "mq7": 1.2339, "mq135": 1.8753,
        "tgs2600": 1.0154, "tgs2602": 0.9555, "tgs2611": 1.1264, "tgs2620": 1.3053
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+07:00")
}

print("\nMengirim dummy telemetry...")
client.publish(f"enose/{DEVICE_ID}/telemetry", json.dumps(telemetry_dummy), qos=0)

time.sleep(1)

print("\nMengirim dummy inference...")
client.publish(f"enose/{DEVICE_ID}/inference", json.dumps(inference_dummy), qos=1)

time.sleep(3)
client.loop_stop()
client.disconnect()
print("\nPengujian selesai!")
