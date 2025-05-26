# BigData-ApacheKafka

Nama : RM. Novian Malcolm Bayuputra

NRP : 5027231035

# Komponen Utama

### 1. `docker-compose.yml`
File konfigurasi ini mendefinisikan dan menjalankan semua layanan yang dibutuhkan dalam kontainer Docker, termasuk:
* **Zookeeper**: Diperlukan oleh Kafka untuk manajemen cluster.
* **Kafka**: Message broker untuk menangani aliran data sensor. Dua topik (`sensor-suhu-gudang` dan `sensor-kelembaban-gudang`) otomatis dibuat.
* **Hadoop Cluster** (Namenode, Datanode, ResourceManager, NodeManager, HistoryServer): Menyediakan lingkungan HDFS dan YARN. Meskipun tidak secara langsung digunakan untuk penyimpanan output dalam skrip consumer pada proyek ini, ini adalah bagian dari stack `bde2020` yang umum digunakan dengan Spark.
* **Spark Cluster** (Master, Worker): Lingkungan untuk menjalankan aplikasi PySpark.
* **producer-suhu**: Kontainer Python yang menjalankan `producer_suhu.py`.
* **producer-kelembaban**: Kontainer Python yang menjalankan `producer_kelembaban.py`.

---
### 2. `producer_suhu.py`
Skrip Python ini mensimulasikan sensor suhu. Fitur utamanya adalah:
* Mengirim data suhu acak untuk tiga gudang (G1, G2, G3).
* Data dikirim ke topik Kafka `sensor-suhu-gudang` setiap detik.

---
### 3. `producer_kelembaban.py`
Skrip Python ini mensimulasikan sensor kelembaban. Fitur utamanya adalah:
* Mengirim data kelembaban acak untuk tiga gudang (G1, G2, G3).
* Data dikirim ke topik Kafka `sensor-kelembaban-gudang` setiap detik.

---
### 4. `pyspark_consumer.py`
Aplikasi PySpark Structured Streaming ini melakukan tugas-tugas berikut:
* Terhubung ke Kafka dan membaca data dari topik suhu dan kelembaban.
* Mem-parsing data JSON yang diterima dari Kafka.
* Memfilter data suhu:
    * Mencetak peringatan **suhu tinggi** jika suhu > 80°C.
* Memfilter data kelembaban:
    * Mencetak peringatan **kelembaban tinggi** jika kelembaban > 70%.
* Menggabungkan (join) stream suhu dan kelembaban berdasarkan `gudang_id` dan `event_time` (dengan menggunakan watermarking dan windowing) untuk mendeteksi kondisi gabungan.
* Mencetak peringatan gabungan dengan status:
    * Bahaya tinggi
    * Suhu tinggi
    * Kelembaban tinggi
    * Aman

---
### 5. `requirements_producers.txt`
File ini berisi daftar dependensi Python yang dibutuhkan oleh skrip producer (`producer_suhu.py` dan `producer_kelembaban.py`).
* Dependensi utama adalah `kafka-python`.
* Dependensi ini akan diinstal secara otomatis di dalam kontainer producer saat proses build.

---
## Langkah Pengerjaan

### 1. Menyiapkan dan Menjalankan Infrastruktur dengan Docker Compose

1.  Pastikan Docker dan Docker Compose sudah terinstal di sistem.
2.  Simpan semua file (`docker-compose.yml`, `pyspark_consumer.py`, `producer_suhu.py`, `producer_kelembaban.py`, `requirements_producers.txt`) dalam satu direktori.
3.  Buka terminal di direktori tersebut dan jalankan perintah berikut untuk membangun dan memulai semua layanan (Kafka, Zookeeper, Hadoop, Spark, dan kedua Producer) dalam mode detached (`-d`):
    ```bash
    docker-compose up -d
    ```
    Perintah ini akan secara otomatis:
    * Memulai Zookeeper dan Kafka.
    * Membuat topik Kafka `sensor-suhu-gudang` dan `sensor-kelembaban-gudang`.
    * Memulai cluster Hadoop dan Spark.
    * Memulai container `producer-suhu` dan `producer-kelembaban`, yang akan mulai mengirim data ke Kafka.

4.  Kita dapat memeriksa log dari producer untuk memastikan data dikirim:
    ```bash
    docker logs -f producer-suhu
    docker logs -f producer-kelembaban
    ```

5.  Kita juga bisa memeriksa log Kafka jika diperlukan:
    ```bash
    docker logs -f kafka
    ```

### 2. Menjalankan Consumer PySpark

Skrip consumer `pyspark_consumer.py` perlu dijalankan di dalam container Spark Master.

**Cara A: Masuk ke Shell Container dan Jalankan `spark-submit`**

1.  Masuk ke dalam shell container `spark-master`:
    ```bash
    docker exec -it spark-master /bin/bash
    ```
2.  Setelah berada di dalam shell container (biasanya `root@<container_id>:/#` atau serupa), navigasikan ke direktori tempat skrip di-mount (sesuai `volumes` di `docker-compose.yml`):
    ```bash
    cd /app
    ```
3.  Jalankan skrip consumer menggunakan `spark-submit`. Paket Kafka sudah didefinisikan dalam skrip PySpark, jadi `spark-submit` akan mengunduhnya jika belum ada.
    ```bash
    spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 pyspark_consumer.py
    ```

**Cara B: Langsung `execute` dari Command Host**

Kita dapat langsung `execute` perintah `spark-submit` melalui `docker-compose`:
```bash
docker-compose exec spark-master //spark/bin/spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 //app/pyspark_consumer.py
```

Consumer akan mulai memproses data dari Kafka dan menampilkan output peringatan suhu, kelembaban, dan gabungan di konsol terminal tersebut.

### 3. Memantau Output

* **Terminal Producer (via `docker logs`)**: Kita akan melihat pesan JSON dikirim setiap detik.
* **Terminal Consumer (di dalam container `spark-master` atau output `docker-compose exec`)**: Kita akan melihat:
    * Log inisialisasi Spark.
    * Pesan "[Peringatan Suhu Tinggi]" jika suhu > 80°C.
    * Pesan "[Peringatan Kelembaban Tinggi]" jika kelembaban > 70%.
    * Blok "--- Batch Gabungan ---" yang berisi status gabungan dari suhu dan kelembaban untuk setiap gudang yang datanya berhasil di-join.

### 4. Penghentian Layanan

Untuk menghentikan semua layanan yang dijalankan oleh Docker Compose (termasuk producer, Kafka, Spark, dll.):
```bash
docker-compose down
```
Perintah ini juga akan menghapus container dan network yang dibuat, tetapi volume (seperti `hadoop_namenode`) akan tetap ada kecuali kita menambahkan opsi `--volumes`.

---

## Dokumentasi

- Docker
  
![image](https://github.com/user-attachments/assets/0031212e-0059-4725-a703-479b6071cb51)

- Producer Suhu
  
![image](https://github.com/user-attachments/assets/86f0b3a7-a34a-48eb-ad1c-e31195cf8630)

- Producer Kelembaban

![image](https://github.com/user-attachments/assets/780c1acf-a7a8-489f-adf6-7980b3c8ef86)

- Output

![image](https://github.com/user-attachments/assets/5d3ce66a-4724-4909-9b26-756835d94308)
