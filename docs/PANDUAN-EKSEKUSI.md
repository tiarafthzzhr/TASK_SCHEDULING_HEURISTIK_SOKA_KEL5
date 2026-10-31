> Panduan teknis dan perintah lengkap. Penjelasan arsitektur serta foto eksperimen ada di [README utama](../README.md).

# Task Scheduling Heuristik - Kelompok 5

Implementasi **Round Robin (RR)** pada Kubernetes lokal memakai **Docker Engine di Ubuntu WSL 2 + kind**. Task CPU benar-benar dijalankan dalam empat pod Python pada satu laptop.

Repository tujuan: [TASK_SCHEDULING_HEURISTIK_SOKA_KEL5](https://github.com/tiarafthzzhr/TASK_SCHEDULING_HEURISTIK_SOKA_KEL5).

## Arsitektur

```text
1 cluster: soka-local
+-- soka-local-control-plane       pengelolaan Kubernetes
+-- soka-local-worker
|   +-- rr-worker-0                task 0, 4, 8, ...
|   +-- rr-worker-1                task 1, 5, 9, ...
+-- soka-local-worker2
    +-- rr-worker-2                task 2, 6, 10, ...
    +-- rr-worker-3                task 3, 7, 11, ...
```

**1 cluster -> 2 worker node -> masing-masing 2 pod**, ditambah 1 control-plane. Total tiga node Kubernetes. Node kind berupa container dan pod bukan VM. Sebutkan sebagai lab Kubernetes lokal satu laptop; interpretasi syarat host/VM pada tugas perlu sesuai persetujuan dosen.

## Alur kerja

1. Docker Engine menyediakan container node kind di Ubuntu WSL 2.
2. kind membuat cluster dan Kubernetes menempatkan dua pod pada setiap worker node melalui nodeSelector.
3. Scheduler memeriksa node Ready, pod Running/Ready, node aktual dan UID pod.
4. Dataset GoCJ dibaca dan task dipetakan menggunakan `worker_index = task_index % 4`.
5. Controller Python mengirim task melalui kubectl exec. Antrean setiap pod serial, empat antrean berjalan paralel.
6. Worker menjalankan SHA-256 berulang, lalu mengembalikan checksum, CPU time dan wall time.
7. Scheduler menyimpan hasil dan menampilkan tabel ringkasan.

Kubernetes menempatkan pod; RR proyek membagi task ke pod. Ini bukan penggantian scheduler internal Kubernetes. Lihat [diagram dan alur demonstrasi](../docs/alur-kubernetes.md).

## Beralih dari percobaan dua laptop

Di Ubuntu laptopmu, hentikan agent percobaan yang sebelumnya menunggu server teman:

```bash
sudo systemctl disable --now k3s-agent
sudo systemctl start docker
docker info
```

Jika docker info ditolak karena izin socket, jangan jalankan setup dulu. Tambahkan akun Ubuntu ke grup Docker melalui `sudo usermod -aG docker "$USER"`, lalu buka sesi WSL baru agar keanggotaan grup berlaku. Grup Docker memberi akses administratif ke daemon.

Kembali ke PowerShell Windows, masuk ke folder repository ini lalu jalankan setup di bawah. Tidak perlu menghapus data K3s, mengubah IP Wi-Fi, mengatur firewall kampus, atau menghubungi server teman. Kubeconfig kind disimpan terpisah di `.kube/kind.yaml`, diabaikan Git, dan tidak memakai konfigurasi K3s sebelumnya.

## Persiapan pertama

Prasyarat: Docker Engine aktif di Ubuntu WSL 2 serta Python 3.10+. Gunakan Engine native Ubuntu yang sudah disiapkan. Docker Desktop juga bisa digunakan sebagai alternatif dengan integrasi WSL, tetapi jangan mencampur dua daemon pada distro yang sama. kind dan kubectl dipasang oleh setup ke folder proyek.

Buka PowerShell pada folder repository yang berisi file ini, lalu jalankan:

```powershell
.\run-kubernetes.ps1 -Mode setup
```

Installer mengunduh kind v0.33.0 dan kubectl v1.37.0 dengan pemeriksaan SHA-256 ke `.tools/kubernetes-bin/`, tanpa sudo. Setup awal membutuhkan internet untuk image Kubernetes dan Python. Setup tidak menghapus cluster yang sudah ada. Jika layout cluster berbeda, proses dihentikan sebelum menerapkan resource.

Jika kubectl Linux belum tersedia, ikuti [panduan instalasi kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/).

## Menjalankan task

Docker Engine yang dipakai harus tetap aktif. Dari PowerShell pada folder repository:

```powershell
# Verifikasi topologi
.\run-kubernetes.ps1 -Mode verify

# Lihat rencana delapan task, tanpa eksekusi
.\run-kubernetes.ps1 -Mode plan -Tasks 8

# Jalankan seluruh dataset 100 task
.\run-kubernetes.ps1
```

Seluruh dataset lama disertakan: 19 ukuran dari 100 sampai 1000 task (kelipatan 50). Workbook Monte Carlo, dataset original dan generator historis juga dibawa tanpa perubahan. Default menjalankan seluruh 100 task, bukan hanya 20 task contoh.

```powershell
# Seluruh 1000 task dari file dataset 1000, bukan potongan dataset 100
.\run-kubernetes.ps1 -DatasetSize 1000

# Semua 19 dataset dijalankan berurutan (10.450 task total)
.\run-kubernetes.ps1 -AllDatasets

# Contoh kecil: hanya 20 task pertama dataset 100
.\run-kubernetes.ps1 -DatasetSize 100 -Tasks 20
```

Setiap dataset menghasilkan folder run terpisah. Rangkaian berhenti jika satu run gagal. Eksekusi seluruh dataset dapat memerlukan waktu lama; tidak dijalankan otomatis saat penyalinan file.

Jika script diblokir PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-kubernetes.ps1
```

Alternatif dari Ubuntu WSL, setelah masuk folder repository:

```bash
python3 kubernetes/install_kind.py
export SOKA_CLUSTER_MODE=kind
export SOKA_KUBE_CONTEXT=kind-soka-local
export SOKA_IN_CLUSTER=0
export KUBECONFIG="$PWD/.kube/kind.yaml"
python3 kube_backend.py setup
python3 scheduler.py verify
python3 scheduler.py run --dataset-size 1000 --iterations-per-mi 10
```

Gunakan path lokal milikmu saat membuka repository. Script PowerShell memakai lokasinya sendiri untuk masuk ke folder yang benar; tidak memerlukan path laptop pembuat proyek.

## Task dan sumber daya

Panjang task berasal dari [GoCJ dataset](../data/README.md), lalu dikalikan iterations-per-mi untuk menentukan jumlah iterasi hash. Skala default 10. Nilai MI bukan pengukuran instruksi CPU nyata dan bukan eksekusi pekerjaan asli Google.

Setiap pod memakai satu container non-root, request CPU 100m/RAM 32Mi, limit CPU 1/RAM 128Mi. Node dan pod berbagi hardware laptop; limit bukan reservasi core fisik. Image worker memakai tag python:3.12-slim; catat imageID jika membutuhkan reproduksi versi image.

Jangan menjalankan dua scheduler bersamaan pada pod yang sama. Jika pod diganti, UID yang berubah ditolak sebelum task berikutnya. Tidak ada pengalihan task otomatis. Run dengan task gagal keluar dengan exit code 1 dan tetap mencatat hasil. Timeout task satu jam; berhentinya kubectl tidak menjamin proses remote sudah berhenti, jadi periksa pod sebelum mengulang run timeout.

## Hasil dan pengukuran

### Menampilkan hasil tanpa menjalankan task ulang

Setiap run sudah menyimpan metrik dan report.txt. Untuk membaca kembali dari PowerShell, tanpa Docker atau WSL:

```powershell
# Hasil run terbaru
.\run-kubernetes.ps1 -Mode results

# Tabel seluruh 19 ukuran dataset dari hasil yang sudah tersimpan
.\run-kubernetes.ps1 -Mode results -AllDatasets

# Hasil seluruh task terbaru untuk dataset 1000
.\run-kubernetes.ps1 -Mode results -DatasetSize 1000

# Simpan tabel gabungan sebagai file teks
.\run-kubernetes.ps1 -Mode results -AllDatasets -ExportPath hasil-seluruh-dataset.txt
```

Mode results hanya membaca file lokal dan tidak memanggil Docker, WSL atau Kubernetes. Python Windows diperlukan. Tabel gabungan memilih run seluruh task terbaru per ukuran berdasarkan nama folder run; baris dapat berasal dari batch berbeda dan skala dicantumkan. Run subset tidak digunakan sebagai pengganti hasil seluruh dataset. Hasil gagal tetap ditandai GAGAL, ukuran yang belum tersedia ditandai BELUM ADA. Metrik hasil tersimpan tidak dihitung ulang.

Untuk membaca satu folder run tertentu: `python show_results.py --run runs/NAMA_FOLDER`. File ekspor teks dapat dimasukkan ke Git sebagai ringkasan; isi seluruh folder runs tetap perlu ditambahkan secara eksplisit jika ingin dipush.

Setiap run membuat folder `runs/<timestamp>/`:

| File | Isi |
|---|---|
| report.txt | Laporan rapi seperti output terminal |
| tasks.csv | Task, worker_index, pod, node, UID, checksum, waktu dan status |
| summary.json | Metrik, jumlah kegagalan, nama/ukuran dataset dan SHA-256 sumber |
| topology.json | Node dan placement pod hasil verifikasi API |
| plan.json | Pemetaan RR dan ukuran pekerjaan |

Makespan mencakup overhead kubectl. Waiting time diukur sampai pemanggilan kubectl task. Task CPU utilization membandingkan CPU time worker dengan kapasitas waktu empat limit CPU pod, bukan total utilisasi laptop. Jangan memakai run gagal sebagai pembanding kinerja karena waktu CPU pekerjaan gagal tidak diketahui.

Folder runs diabaikan Git secara default. Pilih hasil yang diperlukan untuk laporan secara terpisah setelah memeriksa isinya.

## Bukti demonstrasi

Dari PowerShell pada folder repository:

```powershell
.\run-kubernetes.ps1 -Mode inspect
.\run-kubernetes.ps1 -Mode verify
.\run-kubernetes.ps1
```

Mode inspect menampilkan node dan pod aktual, termasuk placement dua pod pada tiap worker. Ambil screenshot inspect dan laporan run sukses, serta file hasil dari run yang sama.

Pada profil kind, backend menjalankan kubectl melalui `docker exec soka-local-control-plane` menggunakan kubeconfig internal node. Ini tetap menghubungi API Kubernetes nyata dan menghindari masalah endpoint port localhost Docker Desktop pada WSL mirrored. Tidak menghapus cluster, tidak memakai API server teman dan tidak mematikan verifikasi TLS. Kubeconfig host tetap diekspor untuk akses eksternal bila port Docker dapat dijangkau.

## Struktur repository

```text
README.md
PUSH.md                    Langkah push mandiri ke GitHub tujuan
run-kubernetes.ps1         Menjalankan dari PowerShell
scheduler.py               RR, dispatch dan pencatatan hasil
kube_backend.py            Setup cluster, verifikasi dan kubectl exec
worker.py                  Komputasi hash nyata
kubernetes/
  kind.yaml                1 control-plane dan 2 worker
  install_kind.py          Installer kind dan kubectl lokal
data/
  GoCJ_Dataset_*.txt        19 dataset asli 100-1000 task
  manifest.json            Ukuran dan SHA-256 seluruh 22 file sumber
  GoCJ_DataSet_Monte_Carlo.xlsx  Workbook historis
  Original_DataSet.txt      Dataset original
  GoCJ Java Generator.txt   Generator historis
  README.md                Atribusi dataset
docs/
  alur-kubernetes.md       Diagram dan alur demonstrasi
tests/
  test_kubernetes.py       Pengujian kode
```

Tidak membutuhkan paket Python eksternal. Pengujian dari folder repository:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Unit test menggunakan API tiruan untuk validasi placement, kesiapan, identitas dan hasil. Bukti eksekusi nyata tetap berasal dari run cluster.

## Kelompok 5 - Institut Teknologi Sepuluh Nopember

| NRP | Nama |
|---|---|
| 5027241009 | Tasya Aulia Darmawan |
| 5027241043 | Azaria Raissa Maulidinnisa |
| 5027241090 | Tiara Fatimah Azzahra |
| 5027241104 | Afriza Tristan Calendra Rajasa |
| 5027201047 | Made Gde Krisna Wangsa |

## Referensi

- [Docker Desktop WSL 2](https://docs.docker.com/desktop/features/wsl/)
- [kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/)
- [Penempatan pod Kubernetes](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/)
- [GoCJ dataset](https://data.mendeley.com/datasets/b7bp6xhrcd/1)

## Jalur terdahulu

[Dokumentasi K3s dua laptop](../docs/K3S-DUA-LAPTOP.md) disimpan sebagai alternatif. Jalur aktif sekarang adalah satu laptop dengan kind. Deployment dua laptop sebelumnya belum berhasil diverifikasi.
