# Task Scheduling Heuristik - Kubernetes Dua Laptop

Implementasi **Round Robin (RR)** pada **K3s + Docker Engine native di Ubuntu WSL 2**, dengan dua laptop Windows fisik di jaringan Wi-Fi yang mengizinkan komunikasi antar-client. Seluruh dataset GoCJ sebelumnya tetap disertakan tanpa perubahan.

## Arsitektur aktif

```text
1 cluster K3s
+-- Laptop 1: soka-master
|   +-- Control-plane (juga menerima workload)
|   +-- rr-worker-0 dan rr-worker-1
|   +-- Job scheduler RR
|   +-- Web hasil pada NodePort 30080
+-- Laptop 2: soka-worker
    +-- rr-worker-2 dan rr-worker-3
```

Ada **dua node K3s dan empat pod komputasi**, dengan Job controller dan Deployment hasil sebagai workload tambahan. Pod bukan VM. WSL 2 memakai virtualisasi bawaan Windows, tetapi tidak membutuhkan VirtualBox atau VM yang dikelola lewat Hyper-V Manager.

**Status:** implementasi, Dockerfile, manifest dan pengujian kode tersedia. Deployment lintas dua laptop serta akses Wi-Fi kampus **belum diverifikasi**. Keberhasilan lab kind satu laptop sebelumnya tidak membuktikan topologi dua laptop ini sudah berjalan.

## Mulai dari sini

Ikuti [panduan lengkap K3s dua laptop](docs/K3S-DUA-LAPTOP.md) secara berurutan. Setiap langkah menjelaskan terminal dan laptop tempat perintah dijalankan.

1. Catat versi Windows/WSL dan IP Wi-Fi aktual kedua laptop.
2. Aktifkan WSL mirrored networking dan systemd tanpa menimpa konfigurasi lain.
3. Siapkan Docker Engine native di Ubuntu masing-masing; jangan mencampurnya dengan integrasi daemon Docker Desktop pada distro yang sama.
4. Buka firewall terbatas, lalu **uji TCP dan UDP dua arah**. Jika gagal, berhenti sebelum memasang/join K3s.
5. Pasang server K3s pada laptop 1 dan agent dengan versi sama pada laptop 2.
6. Build image, salin tar dan load image pada Docker Engine **kedua laptop**.
7. Buat empat worker, terapkan layanan hasil dan jalankan Job RR.
8. Akses hasil dari perangkat lain pada `http://IP_WIFI_LAPTOP_1:30080/`.

Wi-Fi kampus mungkin menerapkan isolasi client. Tidak ada konfigurasi aplikasi yang dapat menjamin akses jika kebijakan jaringan memblokir komunikasi tersebut. Netsh portproxy hanya meneruskan TCP dan tidak menggantikan kebutuhan UDP Flannel.

## Eksekusi setelah cluster siap

Di Ubuntu laptop 1, dari folder repository, dengan kubeconfig yang sudah disiapkan menurut panduan:

```bash
export KUBECONFIG="$PWD/.kube/k3s.yaml"
export SOKA_CLUSTER_MODE=k3s
export SOKA_KUBE_CONTEXT=default
python3 kube_backend.py setup
kubectl apply -f kubernetes/k3s/application.yaml
kubectl -n soka-heuristik rollout status deployment/rr-results --timeout=180s
python3 scripts/submit_experiment.py --dataset-size 100
```

Untuk seluruh 19 dataset asli (10.450 task total) secara berurutan:

```bash
python3 scripts/submit_experiment.py --all-datasets
```

PowerShell juga dapat mengirim Job setelah `.kube/k3s.yaml` tersedia di folder repository yang diakses melalui WSL:

```powershell
.\run-kubernetes.ps1 -Mode verify
.\run-kubernetes.ps1 -DatasetSize 1000
.\run-kubernetes.ps1 -AllDatasets
```

Default sekarang adalah profil **k3s**. Perintah tidak memasang K3s atau mengubah jaringan Windows secara otomatis. Jangan menjalankan lebih dari satu eksperimen pada empat pod yang sama.

## Alur algoritma dan task

```text
GoCJ -> pemetaan i % 4 -> empat antrean pod
     -> kubectl exec -> SHA-256 nyata dalam container
     -> checksum + waktu CPU/wall -> CSV/JSON/report.txt
     -> volume hasil -> web NodePort 30080
```

RR membagi task ke pod; Kubernetes menempatkan pod ke node. Kode tidak mengganti scheduler internal Kubernetes. Antrean tiap pod serial, antrean antar-pod paralel. Panjang GoCJ dikalikan skala iterasi untuk membentuk beban CPU; bukan pengukuran instruksi hardware atau eksekusi pekerjaan asli Google.

## Dataset dan hasil

[data/](data/README.md) memuat seluruh **22 file** sumber: 19 dataset 100-1000 task, workbook Monte Carlo, data original dan generator historis. Isi asli diperiksa dengan manifest SHA-256. Scheduler membaca TXT numerik; workbook/generator disimpan sebagai sumber historis.

Hasil Job disimpan pada PVC `rr-results`, di folder timestamp. `report.txt` memuat laporan rapi, `tasks.csv` mencatat pod/node/UID/checksum/status, `summary.json` memuat metrik serta hash dataset, `topology.json` menyimpan bukti pemeriksaan API, dan `plan.json` berisi pemetaan RR. Folder hasil bisa dibuka melalui layanan HTTP read-only pada NodePort 30080. Hanya hasil eksperimen yang boleh disimpan di volume web, bukan token atau kubeconfig.

Makespan termasuk overhead kubectl; waiting time sampai pemanggilan setiap task. CPU utilization membandingkan CPU time worker dengan kapasitas waktu empat limit CPU pod, bukan utilisasi seluruh laptop. Run gagal tidak layak dijadikan pembanding kinerja karena CPU time task gagal tidak diketahui.

## File utama

| File | Fungsi |
|---|---|
| [docs/K3S-DUA-LAPTOP.md](docs/K3S-DUA-LAPTOP.md) | Instalasi, jaringan, build, deploy, akses hasil dan troubleshooting |
| scripts/network_check.py | Uji TCP 18080 dan UDP 8472 antar-WSL |
| scripts/open-lab-firewall.ps1 | Aturan Defender dan firewall WSL yang dibatasi peer/subnet |
| scripts/install-k3s.sh | Instalasi server/agent native dengan Docker runtime |
| Dockerfile | Image Python, kubectl, seluruh dataset dan aplikasi |
| kube_backend.py | Verifikasi, setup worker dan kubectl exec |
| scheduler.py | RR, antrean dan pencatatan metrik |
| scripts/submit_experiment.py | Mengirim Job baru dan batch seluruh dataset |
| kubernetes/k3s/workers.yaml | Empat pod dengan dua pod per node |
| kubernetes/k3s/application.yaml | RBAC, PVC, Deployment web dan NodePort |
| kubernetes/k3s/job.yaml | Job statis eksperimen 100 task |
| results_server.py | Menampilkan file hasil melalui HTTP |
| [PUSH.md](PUSH.md) | Push sendiri ke repository GitHub tujuan |

Manifest worker juga dibentuk langsung oleh resources() pada backend. Bila image/tag diubah, samakan pada backend, manifest, Job dan kedua Docker Engine.

## Pengujian dan bukti

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Pengujian mencakup data asli, pemetaan RR, placement, identitas pod, profil K3s, service-account dispatch dan Job. Pengujian API memakai respons tiruan. Dua laptop, UDP jaringan kampus, build image dan volume hasil tetap harus diuji langsung mengikuti panduan.

Bukti penyerahan: dua perangkat fisik, dua Node Ready dengan IP Wi-Fi berbeda, empat pod komputasi pada node yang sesuai, Job Complete, laporan tanpa kegagalan dan halaman hasil yang dibuka dari perangkat lain. Dua objek Node saja tidak membuktikan dua laptop fisik.

Panduan lama satu laptop disimpan sebagai [arsip kind](docs/KIND-SATU-LAPTOP.md); gunakan `-ClusterMode kind` secara eksplisit bila memang ingin mode tersebut. Bukan jalur aktif dua laptop.

## Kelompok 5 - Institut Teknologi Sepuluh Nopember

| NRP | Nama |
|---|---|
| 5027241009 | Tasya Aulia Darmawan |
| 5027241043 | Azaria Raissa Maulidinnisa |
| 5027241090 | Tiara Fatimah Azzahra |
| 5027241104 | Afriza Tristan Calendra Rajasa |
| 5027201047 | Made Gde Krisna Wangsa |

## Referensi

- [K3s dengan Docker runtime](https://docs.k3s.io/advanced#using-docker-as-the-container-runtime)
- [K3s requirements](https://docs.k3s.io/installation/requirements)
- [WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking)
- [Docker Engine Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [GoCJ dataset](https://data.mendeley.com/datasets/b7bp6xhrcd/1)
