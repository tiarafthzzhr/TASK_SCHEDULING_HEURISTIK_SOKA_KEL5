# Dataset GoCJ sebelumnya (lengkap)

Seluruh **22 file** dari folder dataset proyek sebelumnya disalin tanpa mengubah isi:

- 19 file GoCJ_Dataset_100.txt sampai GoCJ_Dataset_1000.txt, dengan kenaikan 50 task.
- Original_DataSet.txt.
- GoCJ_DataSet_Monte_Carlo.xlsx.
- GoCJ Java Generator.txt.

manifest.json mencatat nama, ukuran byte, SHA-256 dan jumlah task setiap dataset. Hash diperiksa terhadap file sumber saat disalin. Workbook dan generator disertakan sebagai bahan sumber; scheduler membaca file dataset TXT numerik.

Sumber: Hussain et al., **GoCJ: Google Cloud Jobs Dataset**, [Mendeley Data](https://data.mendeley.com/datasets/b7bp6xhrcd/1). Dataset tidak dibuat ulang dan tidak diklaim sebagai buatan kelompok.

Default menjalankan seluruh dataset 100 task. Gunakan -DatasetSize 1000 untuk seluruh dataset 1000, atau -AllDatasets untuk seluruh 19 ukuran secara berurutan. -Tasks hanya digunakan bila sengaja ingin subset kecil. Pemilihan dataset tidak menggabungkan atau menggandakan isi file.

Panjang GoCJ dikalikan iterations-per-mi untuk membentuk pekerjaan SHA-256 nyata di pod Kubernetes. Nilai MI adalah skala beban, bukan pengukuran instruksi hardware. Nama dataset, jumlah task sumber dan SHA-256 turut dicatat pada summary.json setiap run.
