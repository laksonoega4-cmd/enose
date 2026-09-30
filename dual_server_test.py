import ssl
import time
import json
import paho.mqtt.client as mqtt

# Configuration for Server 1: EMQX Cloud (Class A Internal)
SERVER1 = {
    "name": "EMQX Cloud (Server 1 - Kelas A)",
    "host": "x15beb69.ala.asia-southeast1.emqxsl.com",
    "port": 8883,
    "user": "pub-classA",
    "pass": "kelasA",
    "topics": ["enose/DAQ01/telemetry", "enose/DAQ01/inference", "sensor/dummy"]
}

# Configuration for Server 2: HiveMQ Cloud (Kelas C Server & Dashboard)
SERVER2 = {
    "name": "HiveMQ Cloud (Server 2 - Kelas C)",
    "host": "50337aad3a524a49919d2896b549979d.s1.eu.hivemq.cloud",
    "port": 8883,
    "user": "ayuu-0406",
    "pass": "04062006",
    "topics": ["sensor/dummy", "enose/DAQ01/inference", "enose/DAQ01/telemetry"]
}

results = {}

def test_broker(cfg):
    print(f"\n==========================================")
    print(f"Menguji Koneksi: {cfg['name']}")
    print(f"Host: {cfg['host']}:{cfg['port']}")
    print(f"User: {cfg['user']}")
    print(f"==========================================")
    
    received_msgs = []
    connected_flag = False

    def on_connect(client, userdata, flags, rc, properties=None):
        nonlocal connected_flag
        if rc == 0:
            print(f"  [OK] Berhasil terkoneksi ke {cfg['name']} (RC=0)")
            connected_flag = True
            for t in cfg['topics']:
                client.subscribe(t)
                print(f"  [SUB] Subscribed ke: {t}")
        else:
            print(f"  [FAIL] Gagal koneksi (RC={rc})")

    def on_message(client, userdata, msg):
        payload_str = msg.payload.decode('utf-8', errors='ignore')
        print(f"  [MSG RECV] Topik: {msg.topic}")
        received_msgs.append((msg.topic, payload_str))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"TEST_PROBE_{int(time.time())}")
    client.username_pw_set(cfg['user'], cfg['pass'])
    
    # HiveMQ Cloud & EMQX require standard TLS
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    client.tls_set_context(context)
    client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(cfg['host'], cfg['port'], keepalive=30)
        client.loop_start()
        
        # Tunggu koneksi
        for _ in range(50):
            if connected_flag:
                break
            time.sleep(0.1)

        if not connected_flag:
            print(f"  [TIMEOUT] Tidak dapat terhubung dalam 5 detik.")
            client.loop_stop()
            results[cfg['name']] = False
            return False

        # Kirim payload dummy sesuai format Buku Panduan E-Nose Bab 27.1
        dummy_telemetry = {
            "device_id": "DAQ01",
            "coffee_id": "C01",
            "batch_id": "B1",
            "aliquot_id": "A01",
            "measurement_id": "DAQ01_B01_C01_A01_M01",
            "temperature": 28.7,
            "humidity": 61.4,
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

        dummy_inference = {
            "device_id": "DAQ01",
            "coffee_id": "C01",
            "prediction": "Arabica",
            "confidence": 0.943,
            "temperature": 28.7,
            "humidity": 61.4,
            "inference_time_ms": 84,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+07:00")
        }

        # Publish ke topik dummy dan inferensi
        for t in cfg['topics']:
            payload = dummy_inference if "inference" in t else dummy_telemetry
            client.publish(t, json.dumps(payload), qos=1)
            print(f"  [PUB] Published dummy ke: {t}")

        # Tunggu pesan loopback
        time.sleep(2)
        client.loop_stop()
        client.disconnect()
        
        results[cfg['name']] = (connected_flag and len(received_msgs) > 0)
        print(f"  [SUMMARY] Pesan diterima kembali (Loopback): {len(received_msgs)}")
        return True

    except Exception as e:
        print(f"  [ERROR] Terjadi error: {e}")
        results[cfg['name']] = False
        return False

if __name__ == "__main__":
    print("Memulai pengujian koneksi ke KEDUA SERVER MQTT...")
    test_broker(SERVER1)
    test_broker(SERVER2)
    
    print("\n================ HASIL AKHIR PENGUJIAN ================")
    for server, ok in results.items():
        status = "BERHASIL (ONLINE & SUDAH BISA DITERIMA)" if ok else "GAGAL"
        print(f"{server}: {status}")
    print("=======================================================")
