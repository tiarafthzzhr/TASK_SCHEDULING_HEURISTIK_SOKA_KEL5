> Arsip jalur satu laptop. Untuk dua laptop gunakan [panduan K3s](K3S-DUA-LAPTOP.md).

# Task Scheduling Heuristik - Kelompok 5

Implementasi **Round Robin (RR)** pada Kubernetes lokal memakai **Docker Desktop + Ubuntu WSL 2 + kind**. Task CPU benar-benar dijalankan dalam empat pod Python pada satu laptop.

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

1. Docker Desktop menyediakan container node melalui backend WSL 2.
2. kind membuat cluster dan Kubernetes menempatkan dua pod pada setiap worker node melalui nodeSelector.
3. Scheduler memeriksa node Ready, pod Running/Ready, node aktual dan UID pod.
4. Dataset GoCJ dibaca dan task dipetakan menggunakan `worker_index = task_index % 4`.
5. Controller Python mengirim task melalui kubectl exec. Antrean setiap pod serial, empat antrean berjalan paralel.
6. Worker menjalankan SHA-256 berulang, lalu mengembalikan checksum, CPU time dan wall time.
7. Scheduler menyimpan hasil dan menampilkan tabel ringkasan.

Kubernetes menempatkan pod; RR proyek membagi task ke pod. Ini bukan penggantian scheduler internal Kubernetes. Lihat [diagram dan alur demonstrasi](../docs/alur-kubernetes.md).

## Persiapan pertama

Prasyarat: Docker Desktop aktif dengan WSL 2 based engine, integrasi distro Ubuntu aktif, Python 3.10+ tersedia di Ubuntu. Kubernetes bawaan Docker Desktop tidak perlu diaktifkan. Seluruh perintah Python/kubectl memakai Ubuntu WSL yang sama, bukan kubeconfig Windows.

Buka PowerShell pada folder repository yang berisi file ini, lalu jalankan:

```powershell
.\run-kubernetes.ps1 -ClusterMode kind -Mode setup
```

Installer mengunduh kind v0.33.0 dan kubectl v1.37.0 dengan pemeriksaan SHA-256 ke `.tools/kubernetes-bin/`, tanpa sudo. Setup awal membutuhkan internet untuk image Kubernetes dan Python. Setup tidak menghapus cluster yang sudah ada. Jika layout cluster berbeda, proses dihentikan sebelum menerapkan resource.

Jika kubectl Linux belum tersedia, ikuti [panduan instalasi kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/).

## Menjalankan task

Docker Desktop harus tetap aktif. Dari PowerShell pada folder repository:

```powershell
# Verifikasi topologi
.\run-kubernetes.ps1 -ClusterMode kind -Mode verify

# Lihat rencana delapan task, tanpa eksekusi
.\run-kubernetes.ps1 -ClusterMode kind -Mode plan -Tasks 8

# Jalankan seluruh dataset 100 task
.\run-kubernetes.ps1 -ClusterMode kind
```

Seluruh dataset lama disertakan: 19 ukuran dari 100 sampai 1000 task (kelipatan 50). Workbook Monte Carlo, dataset original dan generator historis juga dibawa tanpa perubahan. Default menjalankan seluruh 100 task, bukan hanya 20 task contoh.

```powershell
# Seluruh 1000 task dari file dataset 1000, bukan potongan dataset 100
.\run-kubernetes.ps1 -ClusterMode kind -DatasetSize 1000

# Semua 19 dataset dijalankan berurutan (10.450 task total)
.\run-kubernetes.ps1 -ClusterMode kind -AllDatasets

# Contoh kecil: hanya 20 task pertama dataset 100
.\run-kubernetes.ps1 -ClusterMode kind -DatasetSize 100 -Tasks 20
```

Setiap dataset menghasilkan folder run terpisah. Rangkaian berhenti jika satu run gagal. Eksekusi seluruh dataset dapat memerlukan waktu lama; tidak dijalankan otomatis saat penyalinan file.

Jika script diblokir PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-kubernetes.ps1 -ClusterMode kind
```

Alternatif dari Ubuntu WSL, setelah masuk folder repository:

```bash
python3 kubernetes/install_kind.py
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

Dari PowerShell:

```powershell
wsl -d Ubuntu --cd "$PWD" -- ./.tools/kubernetes-bin/kubectl --context kind-soka-local get nodes -o wide
wsl -d Ubuntu --cd "$PWD" -- ./.tools/kubernetes-bin/kubectl --context kind-soka-local -n soka-heuristik get pods -o wide
```

Ambil screenshot dua worker node Ready, empat pod Running dengan dua pod per worker, dan laporan scheduler yang menunjukkan status BERHASIL. Sertakan file hasil dari run yang sama serta penjelasan bahwa pod bukan VM.

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
