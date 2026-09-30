import ssl
import time
import json
import paho.mqtt.client as mqtt

# Configuration
BROKER_EMQX = {
    "name": "EMQX (Server 1)",
    "host": "x15beb69.ala.asia-southeast1.emqxsl.com",
    "port": 8883,
    "user": "pub-classA",
    "pass": "kelasA",
}

BROKER_HIVEMQ = {
    "name": "HiveMQ Cloud (Server 2 - Kelas C)",
    "host": "50337aad3a524a49919d2896b549979d.s1.eu.hivemq.cloud",
    "port": 8883,
    "user": "ayuu-0406",
    "pass": "04062006",
}

received_emqx = []
received_hivemq = []

def make_client(cfg, rec_list):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"VERIFY_{cfg['user']}_{int(time.time()*1000)%10000}")
    c.username_pw_set(cfg['user'], cfg['pass'])
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    c.tls_set_context(ctx)
    c.tls_insecure_set(True)

    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0 or str(rc) == "Success":
            print(f"  [SUB OK] Connected to {cfg['name']}")
            client.subscribe("sensor/dummy", qos=0)
            client.subscribe("enose/+/telemetry", qos=0)
            client.subscribe("enose/+/inference", qos=1)

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            rec_list.append((msg.topic, payload))
        except Exception as e:
            rec_list.append((msg.topic, str(msg.payload)))

    c.on_connect = on_connect
    c.on_message = on_message
    return c

print("=" * 70)
print(" VERIFIKASI END-TO-END DATA DUMMY KE KEDUA SERVER (KELAS A & C)")
print("=" * 70)

c_emqx = make_client(BROKER_EMQX, received_emqx)
c_hivemq = make_client(BROKER_HIVEMQ, received_hivemq)

c_emqx.connect(BROKER_EMQX['host'], BROKER_EMQX['port'], keepalive=30)
c_hivemq.connect(BROKER_HIVEMQ['host'], BROKER_HIVEMQ['port'], keepalive=30)

c_emqx.loop_start()
c_hivemq.loop_start()

time.sleep(2.5)

# Sekarang kirim data dummy
test_data = {
    "device_id": "DAQ01",
    "coffee_id": "C01",
    "species": "Arabica",
    "prediction": "Arabica",
    "confidence": 0.952,
    "temperature": 29.1,
    "humidity": 61.8,
    "inference_time_ms": 82,
    "mq3": 1.65,
    "tgs2602": 0.98,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+07:00")
}

print("\n[*] Mengirim data dummy ke topik 'sensor/dummy' dan 'enose/DAQ01/inference'...")
c_emqx.publish("enose/DAQ01/inference", json.dumps(test_data), qos=1)
c_hivemq.publish("sensor/dummy", json.dumps(test_data), qos=1)
c_hivemq.publish("enose/DAQ01/inference", json.dumps(test_data), qos=1)

time.sleep(2.5)

c_emqx.loop_stop()
c_emqx.disconnect()
c_hivemq.loop_stop()
c_hivemq.disconnect()

print("\n" + "=" * 70)
print(f"Hasil Verifikasi:")
print(f"1. EMQX Cloud (Kelas A)       : Menerima {len(received_emqx)} pesan")
for top, p in received_emqx:
    print(f"   -> Topik [{top}] : Prediksi={p.get('prediction')} (Conf: {p.get('confidence')})")

print(f"2. HiveMQ Cloud (Kelas C)     : Menerima {len(received_hivemq)} pesan")
for top, p in received_hivemq:
    print(f"   -> Topik [{top}] : Prediksi={p.get('prediction')} (Conf: {p.get('confidence')}), Temp={p.get('temperature')}C")

if len(received_emqx) > 0 and len(received_hivemq) > 0:
    print("\n>>> STATUS: SUKSES PENUH! Data dummy terbaca di kedua server & siap untuk dashboard Kelas C!")
else:
    print("\n>>> STATUS: Periksa koneksi salah satu broker.")
print("=" * 70)
