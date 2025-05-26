import time
import json
import random
from kafka import KafkaProducer

# Konfigurasi Kafka
KAFKA_BROKER = 'kafka:9093' # Terhubung ke Kafka via nama service di Docker network
TOPIC_NAME = 'sensor-kelembaban-gudang'
GUDANG_IDS = ["G1", "G2", "G3"]

# Inisialisasi Producer
producer = None
while producer is None:
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            api_version=(0, 10, 1)
        )
        print(f"Berhasil terhubung ke Kafka broker: {KAFKA_BROKER} untuk kelembaban.")
    except Exception as e:
        print(f"Gagal terhubung ke Kafka broker untuk kelembaban: {e}. Mencoba lagi dalam 5 detik...")
        time.sleep(5)

print(f"Mengirim data kelembaban ke topik: {TOPIC_NAME}")

try:
    while True:
        gudang_id = random.choice(GUDANG_IDS)
        if gudang_id == "G1":
            kelembaban = random.randint(68, 78)
        elif gudang_id == "G3":
            kelembaban = random.randint(65, 75)
        else:
            kelembaban = random.randint(60, 72)

        message = {
            "gudang_id": gudang_id,
            "kelembaban": kelembaban,
            "timestamp": time.time() # Menambahkan timestamp untuk event time sebenarnya
        }

        producer.send(TOPIC_NAME, value=message)
        print(f"Terkirim (Kelembaban): {message}")

        time.sleep(1)
except KeyboardInterrupt:
    print("Producer kelembaban dihentikan.")
except Exception as e:
    print(f"Error pada producer kelembaban: {e}")
finally:
    if producer:
        producer.flush()
        producer.close()
        print("Producer kelembaban ditutup.")
