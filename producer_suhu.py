import time
import json
import random
from kafka import KafkaProducer

# Konfigurasi Kafka
KAFKA_BROKER = 'kafka:9093' 
TOPIC_NAME = 'sensor-suhu-gudang'
GUDANG_IDS = ["G1", "G2", "G3"]

# Inisialisasi Producer
producer = None
while producer is None:
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            api_version=(0, 10, 1) # Beberapa versi Kafka memerlukan ini
        )
        print(f"Berhasil terhubung ke Kafka broker: {KAFKA_BROKER} untuk suhu.")
    except Exception as e:
        print(f"Gagal terhubung ke Kafka broker untuk suhu: {e}. Mencoba lagi dalam 5 detik...")
        time.sleep(5)


print(f"Mengirim data suhu ke topik: {TOPIC_NAME}")

try:
    while True:
        gudang_id = random.choice(GUDANG_IDS)
        if gudang_id == "G1":
            suhu = random.randint(78, 88) 
        elif gudang_id == "G2":
            suhu = random.randint(75, 85)
        else: # G3
            suhu = random.randint(70, 82)

        message = {
            "gudang_id": gudang_id,
            "suhu": suhu,
            "timestamp": time.time() # Menambahkan timestamp untuk event time sebenarnya
        }

        producer.send(TOPIC_NAME, value=message)
        print(f"Terkirim (Suhu): {message}")

        time.sleep(1) 
except KeyboardInterrupt:
    print("Producer suhu dihentikan.")
except Exception as e:
    print(f"Error pada producer suhu: {e}")
finally:
    if producer:
        producer.flush()
        producer.close()
        print("Producer suhu ditutup.")