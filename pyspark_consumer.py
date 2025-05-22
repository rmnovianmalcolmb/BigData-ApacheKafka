from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, expr, window, when, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, TimestampType

# Versi package Kafka harus sesuai dengan versi Spark di image bde2020/spark-*:latest
KAFKA_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"

# Inisialisasi SparkSession
spark = SparkSession.builder \
    .appName("WarehouseMonitor") \
    .config("spark.jars.packages", KAFKA_PACKAGE) \
    .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true") \
    .config("spark.sql.session.timeZone", "UTC") \
    .getOrCreate()

# Mengurangi log yang verbose dari Spark, tampilkan hanya WARN ke atas
spark.sparkContext.setLogLevel("WARN")

print("Spark Session Dimulai.")

# Konfigurasi Kafka
KAFKA_BROKER = "kafka:9093" # Terhubung ke Kafka via nama service di Docker network
TOPIC_SUHU = "sensor-suhu-gudang"
TOPIC_KELEMBABAN = "sensor-kelembaban-gudang"

print(f"Mencoba terhubung ke Kafka Broker: {KAFKA_BROKER}")
print(f"Topik Suhu: {TOPIC_SUHU}")
print(f"Topik Kelembaban: {TOPIC_KELEMBABAN}")

# Skema untuk data suhu dari Kafka
schema_suhu = StructType([
    StructField("gudang_id", StringType(), True),
    StructField("suhu", IntegerType(), True),
    StructField("timestamp", DoubleType(), True)
])

# Skema untuk data kelembaban dari Kafka
schema_kelembaban = StructType([
    StructField("gudang_id", StringType(), True),
    StructField("kelembaban", IntegerType(), True),
    StructField("timestamp", DoubleType(), True)
])

# Fungsi untuk membaca stream dari Kafka dan memprosesnya
def read_kafka_stream(topic, schema, stream_name):
    print(f"Membaca stream dari topik: {topic} ({stream_name})")
    df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", topic) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load() \
        .select(
            from_json(col("value").cast("string"), schema).alias("data"),
            col("timestamp").alias("kafka_processing_timestamp") # Kafka ingestion time
        )
    
    select_exprs = [
        col("data.gudang_id").alias(f"gudang_id_{stream_name}"),
        col("data.timestamp").cast(TimestampType()).alias(f"event_time_{stream_name}"), # Actual sensor event time
        col("kafka_processing_timestamp")
    ]
    
    if "suhu" in schema.fieldNames():
        select_exprs.append(col("data.suhu").alias("suhu"))
    
    if "kelembaban" in schema.fieldNames():
        select_exprs.append(col("data.kelembaban").alias("kelembaban"))
    
    return df.select(*select_exprs)

# Membaca dan memproses stream suhu
df_suhu = read_kafka_stream(TOPIC_SUHU, schema_suhu, "suhu")

# Membaca dan memproses stream kelembaban
df_kelembaban = read_kafka_stream(TOPIC_KELEMBABAN, schema_kelembaban, "kelembaban")

print("Stream suhu dan kelembaban telah didefinisikan.")

# --- Peringatan Suhu Tinggi (Format Kustom) ---
peringatan_suhu_tinggi_df = df_suhu.filter(col("suhu").isNotNull() & (col("suhu") > 80)) \
    .select(
        col("gudang_id_suhu").alias("gudang_id"),
        col("suhu"),
        col("event_time_suhu").alias("event_time")
    )

def process_batch_suhu_tinggi(batch_df, epoch_id):
    if not batch_df.isEmpty():
        alerts = batch_df.collect()
        for alert in alerts:
            print("[Peringatan Suhu Tinggi]")
            print(f"Gudang {alert.gudang_id}: Suhu {alert.suhu}°C") # Removed timestamp for exact match

query_peringatan_suhu = peringatan_suhu_tinggi_df.writeStream \
    .outputMode("append") \
    .trigger(processingTime="5 seconds") \
    .foreachBatch(process_batch_suhu_tinggi) \
    .start()
print("Query peringatan suhu tinggi dimulai (dengan format kustom).")


# --- Peringatan Kelembaban Tinggi (Format Kustom) ---
peringatan_kelembaban_tinggi_df = df_kelembaban.filter(col("kelembaban").isNotNull() & (col("kelembaban") > 70)) \
    .select(
        col("gudang_id_kelembaban").alias("gudang_id"),
        col("kelembaban"),
        col("event_time_kelembaban").alias("event_time")
    )

def process_batch_kelembaban_tinggi(batch_df, epoch_id):
    if not batch_df.isEmpty():
        alerts = batch_df.collect()
        for alert in alerts:
            print("[Peringatan Kelembaban Tinggi]")
            print(f"Gudang {alert.gudang_id}: Kelembaban {alert.kelembaban}%")

query_peringatan_kelembaban = peringatan_kelembaban_tinggi_df.writeStream \
    .outputMode("append") \
    .trigger(processingTime="10 seconds") \
    .foreachBatch(process_batch_kelembaban_tinggi) \
    .start()
print("Query peringatan kelembaban tinggi dimulai (dengan format kustom).")


# --- Gabungan Stream ---
WATERMARK_DELAY = "20 seconds" # How late can data be
WINDOW_DURATION = "10 seconds" # Time window for joining events

df_suhu_watermarked = df_suhu.withWatermark("event_time_suhu", WATERMARK_DELAY)
df_kelembaban_watermarked = df_kelembaban.withWatermark("event_time_kelembaban", WATERMARK_DELAY)

# Join stream
df_joined = df_suhu_watermarked.join(
    df_kelembaban_watermarked,
    expr(f"""
        gudang_id_suhu = gudang_id_kelembaban AND
        event_time_suhu >= event_time_kelembaban - interval {WINDOW_DURATION.split()[0]} seconds AND
        event_time_suhu <= event_time_kelembaban + interval {WINDOW_DURATION.split()[0]} seconds
    """),
    "inner"  #  get matching pairs
).select(
    col("gudang_id_suhu").alias("gudang_id"),
    col("suhu"),
    col("kelembaban"),
    when(col("event_time_suhu") > col("event_time_kelembaban"), col("event_time_suhu"))
        .otherwise(col("event_time_kelembaban")).alias("event_time")
)

# Peringatan Gabungan
df_peringatan_gabungan = df_joined.withColumn(
    "status_text",
    when((col("suhu") > 80) & (col("kelembaban") > 70), "Bahaya tinggi! Barang berisiko rusak")
    .when((col("suhu") > 80) & (col("kelembaban") <= 70), "Suhu tinggi, kelembaban normal")
    .when((col("suhu") <= 80) & (col("kelembaban") > 70), "Kelembaban tinggi, suhu aman")
    .otherwise("Aman")
).withColumn(
    "header",
    when(col("status_text") == "Bahaya tinggi! Barang berisiko rusak", "[PERINGATAN KRITIS]")
    .otherwise("[INFO GABUNGAN]") 
)

# print the actual processing time, we can fetch it inside the batch
def get_current_processing_time_str():
    return spark.sql("SELECT current_timestamp() as ts").first().ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def process_batch_gabungan(batch_df, epoch_id):
    current_proc_time_str = get_current_processing_time_str()
    print(f"--- Batch Gabungan {epoch_id} (Data Diproses: {current_proc_time_str}) ---")
    if not batch_df.isEmpty():
        collected_rows = batch_df.orderBy("gudang_id", "event_time").collect()
        for row in collected_rows:
            print(f"{row.header}")
            print(f"Gudang {row.gudang_id}:") 
            print(f"  - Suhu: {row.suhu}°C")
            print(f"  - Kelembaban: {row.kelembaban}%")
            print(f"  - Status: {row.status_text}")
            print("-" * 40) # separator
    else:
        print("Tidak ada data gabungan untuk diproses di batch ini.")

query_gabungan = df_peringatan_gabungan.writeStream \
    .outputMode("append") \
    .trigger(processingTime="5 seconds") \
    .foreachBatch(process_batch_gabungan) \
    .start()

print("Query peringatan gabungan dimulai.")
print("Menunggu data stream... Tekan Ctrl+C untuk menghentikan.")

try:
    spark.streams.awaitAnyTermination()
except KeyboardInterrupt:
    print("Streaming dihentikan oleh pengguna (KeyboardInterrupt).")
except Exception as e:
    print(f"Terjadi error pada streaming: {e}")
finally:
    print("Menghentikan semua stream query aktif...")
    active_streams = spark.streams.active
    for s in active_streams:
        try:
            stream_name = s.name if s.name else s.id
            print(f"Stopping stream {stream_name}...")
            s.stop()
            s.awaitTermination(timeout=5) 
            print(f"Stream {stream_name} dihentikan.")
        except Exception as e_stop:
            stream_name_err = s.name if s.name else s.id
            print(f"Error saat menghentikan stream {stream_name_err}: {e_stop}")
    
    print("Menutup Spark session.")
    spark.stop()
    print("Spark session berhasil ditutup.")