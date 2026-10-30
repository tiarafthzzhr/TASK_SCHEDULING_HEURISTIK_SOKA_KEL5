# Kubernetes Dua Laptop: K3s + Docker Engine dalam WSL 2

Panduan ini mengganti arsitektur kind satu laptop menjadi **dua laptop Windows fisik**. K3s berjalan sebagai service Linux di Ubuntu WSL, memakai **Docker Engine native di setiap distro** melalui opsi --docker. Tidak memakai VirtualBox atau VM yang dibuat lewat Hyper-V Manager. WSL 2 sendiri tetap menggunakan virtualisasi bawaan Windows; jangan menonaktifkan komponen virtualisasi yang dibutuhkannya.

**Status:** kode, Dockerfile, manifest dan panduan sudah disiapkan. Deployment dua laptop belum terverifikasi. Keberhasilan kind sebelumnya bukan bukti K3s dua laptop ini.

## Arsitektur akhir

```text
Wi-Fi kampus yang mengizinkan komunikasi antar-client
|
+-- Laptop 1: Windows -> Ubuntu WSL 2 mirrored -> Docker Engine
|   +-- K3s soka-master (control-plane sekaligus node workload)
|       +-- rr-worker-0 dan rr-worker-1
|       +-- Job scheduler Round Robin
|       +-- Deployment hasil HTTP -> NodePort 30080
|
+-- Laptop 2: Windows -> Ubuntu WSL 2 mirrored -> Docker Engine
    +-- K3s soka-worker
        +-- rr-worker-2 dan rr-worker-3
```

Total dua node K3s dan empat pod komputasi. Job controller serta pod web adalah workload tambahan, bukan empat worker RR. Pod bukan VM. Data asli GoCJ 100-1000 task tetap dibawa lengkap.

## A. Persiapan kedua laptop

### A1. Catat IP dan versi

Di PowerShell **masing-masing laptop**:

```powershell
winver
wsl --version
wsl -l -v
ipconfig
```

Panduan mirrored membutuhkan Windows 11 22H2+ dan WSL terbaru. Catat IPv4 Wi-Fi laptop 1 sebagai SERVER_IP, laptop 2 sebagai AGENT_IP, serta subnet Wi-Fi sebenarnya. Jangan memakai alamat NAT WSL atau adapter Host-only. IP 10.4.x.x berikut harus diisi dari hasil aktual, bukan diambil dari percakapan sebelumnya.

Kedua laptop harus bisa berkomunikasi melalui jaringan kampus. Berada pada SSID sama tidak menjamin client-to-client diizinkan. Jika kampus memblokirnya, berhenti dan minta jalur lab yang diizinkan administrator; membuka firewall laptop tidak dapat mengatasi isolasi access point.

### A2. Aktifkan mirrored networking

Di PowerShell tiap laptop:

```powershell
notepad "$env:USERPROFILE\.wslconfig"
```

Tambahkan/gabungkan pengaturan berikut; **jangan menimpa pengaturan lain atau membuat bagian wsl2 ganda**:

```ini
[wsl2]
networkingMode=mirrored
firewall=true
dnsTunneling=true
```

Di Ubuntu, edit `/etc/wsl.conf` dengan `sudo nano /etc/wsl.conf` dan tambahkan pada bagian boot yang sudah ada:

```ini
[boot]
systemd=true
```

Simpan pekerjaan WSL lain dahulu. Di PowerShell:

```powershell
wsl --shutdown
wsl -d Ubuntu
```

Shutdown menghentikan semua distro WSL dan bisa mengganggu Docker Desktop yang sedang digunakan. Setelah masuk Ubuntu:

```bash
ps -p 1 -o comm=
ip -br addr
```

PID 1 harus systemd dan IP Wi-Fi yang dipilih harus muncul pada interface mirrored dalam WSL. Jika tidak, jangan lanjut instalasi.

### A3. Docker Engine native, bukan shared daemon Docker Desktop

Untuk rancangan K3s ini, pilih satu runtime: **Docker Engine di Ubuntu WSL masing-masing laptop**. Matikan integrasi Docker Desktop untuk distro Ubuntu tersebut sebelum menambahkan Engine native. Jangan menjalankan Desktop integration dan Engine native pada distro yang sama. Docker Desktop tidak perlu dihapus dan workload lain tidak perlu dihapus.

Jika Engine native belum terpasang dan tidak ada paket Docker lain yang konflik, jalankan di Ubuntu kedua laptop:

```bash
sudo apt-get update
sudo apt-get install -y docker.io ca-certificates curl git python3
sudo systemctl enable --now docker
sudo docker info
```

Jika sudah memakai paket docker-ce dari sumber resmi Docker, pertahankan instalasi itu; tidak perlu menambahkan docker.io. Lihat [instalasi Docker Engine Ubuntu](https://docs.docker.com/engine/install/ubuntu/) bila ada konflik paket.

`sudo docker info` harus menunjukkan Engine native Ubuntu, bukan Docker Desktop. Gunakan sudo untuk build/load sehingga tidak perlu mengubah keanggotaan grup. K3s service memakai socket Docker distro ini.

### A4. Ambil kode dan buka firewall terbatas

Di Ubuntu pada kedua laptop:

```bash
git clone https://github.com/tiarafthzzhr/TASK_SCHEDULING_HEURISTIK_SOKA_KEL5.git
cd TASK_SCHEDULING_HEURISTIK_SOKA_KEL5
```

Jika clone sudah ada, gunakan folder tersebut dan ambil commit terbaru setelah perubahan ini dipush sendiri. Jangan clone ke folder Git yang sudah berisi repository. File baru dalam panduan ini harus sudah tersedia di kedua laptop.

Di **PowerShell Administrator**, masuk folder repository Windows yang memuat script, lalu pada laptop 1:

```powershell
.\scripts\open-lab-firewall.ps1 -PeerIP "IP_WIFI_LAPTOP_2" -ClientSubnet "SUBNET_WIFI_DALAM_CIDR"
```

Pada laptop 2, PeerIP adalah IP Wi-Fi laptop 1. Ganti placeholder dengan IPv4/CIDR aktual. Jika repository berada di filesystem Linux, salin script melalui File Explorer dari `\\wsl.localhost\Ubuntu\home\<user>\...` ke folder Windows dahulu, atau buka script tersebut melalui path UNC.

Script membuat aturan Defender dan firewall WSL/Hyper-V. Port cluster dibatasi ke IP peer; NodePort dibatasi ke subnet client yang kamu berikan. Firewall tetap aktif.

| Port | Tujuan |
|---|---|
| TCP 6443 | Agent dan controller mengakses API server laptop 1 |
| UDP 8472 | Flannel VXLAN antarnode, dua arah |
| TCP 10250 | Kubelet/metrics antarnode |
| TCP 18080 | Pemeriksaan jaringan sementara |
| TCP 30080 | Halaman hasil untuk client pada subnet yang diizinkan |

Jangan membuka UDP 8472 ke internet. Jangan mengganti seluruh kebijakan firewall menjadi Allow.

### A5. Uji TCP dan UDP sebelum instal K3s

Di terminal Ubuntu **kedua laptop**:

```bash
python3 scripts/network_check.py serve
```

Biarkan terminal ini berjalan. Pada terminal Ubuntu kedua di laptop 1:

```bash
python3 scripts/network_check.py check IP_WIFI_LAPTOP_2
```

Pada terminal Ubuntu kedua di laptop 2:

```bash
python3 scripts/network_check.py check IP_WIFI_LAPTOP_1
```

Keduanya harus PASS TCP 18080 dan UDP 8472. Ping saja tidak cukup. Jika gagal, perbaiki routing/firewall atau minta bantuan pengelola Wi-Fi; jangan lanjut join. Setelah keduanya PASS, hentikan **dua server pengujian** dengan Ctrl+C supaya UDP 8472 tersedia untuk Flannel.

### Tentang netsh portproxy

Pada mirrored mode, forwarding NAT tidak diperlukan. `netsh portproxy` hanya mendukung TCP, sehingga **bukan solusi lengkap untuk cluster Flannel VXLAN**.

Untuk aplikasi HTTP saja pada WSL NAT, pola forwarding yang valid adalah berikut pada PowerShell Admin, dengan alamat yang sudah diverifikasi:

```powershell
$taskWifiIP = "IP_WIFI_LAPTOP_INI"
$taskWslIP = "IP_ETHERNET_WSL_YANG_BENAR"
netsh interface portproxy add v4tov4 listenaddress=$taskWifiIP listenport=30080 connectaddress=$taskWslIP connectport=30080
netsh interface portproxy show all
```

Ini hanya contoh jalur HTTP alternatif; jangan menerapkannya pada rancangan mirrored tanpa kebutuhan. Jangan menganggap forwarding 6443/30080 membuat UDP dan jaringan pod bekerja. Koneksi antar-laptop pada panduan utama selalu menggunakan IP Wi-Fi peer.

## B. Instal cluster lintas laptop

### B1. Server pada laptop 1

Di Ubuntu laptop 1, dari folder repository:

```bash
sudo bash scripts/install-k3s.sh server IP_WIFI_LAPTOP_1
```

Script memeriksa systemd, IP yang benar-benar ada di WSL, serta Engine native, kemudian memasang K3s server dengan --docker, node IP Wi-Fi, TLS SAN, interface Flannel dan label `soka.lab/host=host1`. Node bernama soka-master. Script menolak menimpa instalasi K3s yang sudah ada.

Catat versi yang terpasang dan baca token **secara privat**:

```bash
sudo k3s --version
sudo cat /var/lib/rancher/k3s/server/node-token
```

Jangan kirim token ke chat publik/GitHub. Gunakan versi persis dari baris pertama, misalnya pola `vX.Y.Z+k3sN`, pada laptop 2.

### B2. Agent pada laptop 2

Di Ubuntu laptop 2:

```bash
sudo env INSTALL_K3S_VERSION='VERSI_PERSIS_DARI_SERVER' bash scripts/install-k3s.sh agent IP_WIFI_LAPTOP_2 IP_WIFI_LAPTOP_1
```

Saat diminta, paste token server. Input tidak ditampilkan. Node agent bernama soka-worker, diberi label `soka.lab/host=host2`, dan memakai --docker serta interface Wi-Fi mirrored.

### B3. Kubeconfig controller dan verifikasi

Di Ubuntu laptop 1, dari folder repository:

```bash
mkdir -p .kube
sudo cat /etc/rancher/k3s/k3s.yaml > .kube/k3s.yaml
chmod 600 .kube/k3s.yaml
export KUBECONFIG="$PWD/.kube/k3s.yaml"
export SOKA_CLUSTER_MODE=k3s
export SOKA_KUBE_CONTEXT=default
```

Set alamat API secara eksplisit ke IP Wi-Fi laptop 1:

```bash
kubectl config set-cluster default --server=https://IP_WIFI_LAPTOP_1:6443
kubectl get nodes -o wide
kubectl get nodes -L soka.lab/host
```

Harus terlihat **soka-master dan soka-worker Ready**, dengan dua Internal-IP Wi-Fi berbeda serta label host1/host2. Server juga menjalankan workload; K3s default tidak memberi taint NoSchedule pada server. Jika ada taint dari instalasi lain, tinjau dulu sebelum menempatkan pod.

Kubeconfig ini memberi akses admin. Sudah diabaikan Git; jangan salin ke image atau folder hasil web. Ekspor ulang ketiga environment variable pada terminal Ubuntu baru.

## C. Build dan distribusikan image tanpa Docker Hub

### C1. Build di laptop 1

Dockerfile sudah tersedia dan memuat Python, kubectl, scheduler, worker, server hasil dan seluruh dataset. Tidak memakai main.py yang tidak ada.

Di Ubuntu laptop 1:

```bash
KUBE_VERSION=$(sudo k3s --version | head -n 1 | awk '{print $3}' | cut -d+ -f1)
sudo docker build --build-arg KUBECTL_VERSION="$KUBE_VERSION" -t soka-task-scheduler:v1 .
sudo docker save -o soka-task-scheduler-v1.tar soka-task-scheduler:v1
sudo chown "$(id -u):$(id -g)" soka-task-scheduler-v1.tar
sha256sum soka-task-scheduler-v1.tar
```

Kubectl image disesuaikan dengan versi Kubernetes server untuk menghindari version skew. Dockerfile memeriksa checksum kubectl. Base image dan unduhan tool tetap membutuhkan internet, tetapi image aplikasi tidak dipush ke registry publik.

### C2. Load pada laptop 2 juga

Salin tar ke laptop 2 melalui saluran transfer file yang tersedia/diizinkan, lalu di Ubuntu laptop 2:

```bash
sha256sum soka-task-scheduler-v1.tar
sudo docker load -i soka-task-scheduler-v1.tar
sudo docker image inspect soka-task-scheduler:v1 --format '{{.Id}}'
```

Cocokkan checksum tar dan image ID dengan laptop 1. Karena kedua K3s memakai --docker, image harus ada pada **Docker Engine native kedua laptop**. Tidak memakai `k3s ctr images import` pada jalur Docker ini.

Untuk mode containerd lain, padanannya adalah `docker save ... | sudo k3s ctr images import -` pada **setiap node**. Untuk kind/k3d lokal, padanannya `kind load docker-image IMAGE --name CLUSTER` atau `k3d image import IMAGE -c CLUSTER`. Jangan mencampur ketiga cara runtime tersebut pada cluster yang sama.

## D. Deploy worker, Job dan layanan hasil

Semua perintah controller berikut di Ubuntu laptop 1, dengan tiga environment variable pada B3 masih aktif.

### D1. Buat empat pod worker dan penempatan dua per node

```bash
python3 kube_backend.py setup
kubectl -n soka-heuristik get pods -l app=rr-worker -o wide
```

Pada profil K3s, setup tidak membuat kind; hanya memverifikasi dua node berlabel, menerapkan empat pod dari manifest yang dibentuk `resources()`, menunggu Ready dan memeriksa nodeName aktual. Image worker adalah soka-task-scheduler:v1 dengan imagePullPolicy Never. Jika image belum diload pada laptop 2, perbaiki ErrImageNeverPull di node tersebut.

### D2. Deploy penyimpanan, RBAC dan web hasil

```bash
kubectl apply -f kubernetes/k3s/application.yaml
kubectl -n soka-heuristik rollout status deployment/rr-results --timeout=180s
kubectl -n soka-heuristik get pvc,pods,svc -o wide
```

Manifest memuat service account controller, izin baca nodes/pods dan exec, PVC local-path, Deployment HTTP dan Service NodePort 30080 -> container 8000. Web server berjalan nyata; Service tidak menunjuk port kosong.

Job dan web hasil ditempatkan pada host1 agar berbagi PVC local-path di node yang sama. Worker CPU tidak membutuhkan volume. Web hanya membaca volume hasil dan tidak menerima service-account token.

### D3. Jalankan dataset yang sama dalam Job

Pilihan manifest statis untuk run pertama (100 task):

```bash
kubectl apply -f kubernetes/k3s/job.yaml
kubectl -n soka-heuristik logs -f job/rr-experiment
kubectl -n soka-heuristik get job rr-experiment
```

Job sekali jalan sesuai aplikasi batch. backoffLimit=0 mencegah retry otomatis eksperimen gagal. Manifest Job yang sudah selesai tidak menjalankan ulang ketika di-apply lagi.

Untuk run baru dengan nama unik, gunakan helper (jangan dijalankan bersamaan dengan Job di atas):

```bash
python3 scripts/submit_experiment.py --dataset-size 1000
```

Untuk seluruh 19 dataset asli secara berurutan:

```bash
python3 scripts/submit_experiment.py --all-datasets
```

Helper menolak Job lain yang masih aktif, menunggu setiap run selesai, dan menghentikan rangkaian ketika Job gagal. Semua 22 file sumber dataset masih tersedia dan SHA-256 dicatat. Beban hash diturunkan dari panjang GoCJ; bukan pengukuran instruksi hardware asli.

### D4. Akses dari perangkat lain di Wi-Fi kampus

Buka browser pada laptop/perangkat lain:

```text
http://IP_WIFI_LAPTOP_1:30080/
```

Halaman menampilkan direktori hasil. Pilih folder timestamp lalu report.txt, summary.json atau tasks.csv. Sebelum Job pertama selesai, halaman dapat kosong. Mengakses halaman tidak otomatis memulai eksperimen.

Service tidak memiliki login; folder hasil hanya boleh berisi keluaran eksperimen yang memang hendak dibagikan pada subnet lab. Jangan menaruh token/kubeconfig di sana. Firewall membatasi client pada subnet yang ditentukan. Jangan menganggap Wi-Fi kampus pasti mengizinkan akses; jika tes HTTP gagal, tinjau kebijakan jaringan bersama administrator.

### D5. Verifikasi jaringan pod dan bukti

```bash
kubectl get nodes -o wide
kubectl -n soka-heuristik get pods -o wide
kubectl -n soka-heuristik get jobs
kubectl -n soka-heuristik get svc rr-results
kubectl -n soka-heuristik logs job/rr-experiment
```

Node Ready saja belum membuktikan komunikasi pod lintas node. Di laptop 1, ambil IP pod hasil lalu uji HTTP dari worker pada laptop 2 melalui jaringan pod:

```bash
RESULT_IP=$(kubectl -n soka-heuristik get pods -l app=rr-results -o jsonpath='{.items[0].status.podIP}')
kubectl -n soka-heuristik exec rr-worker-2 -- python3 -c "import urllib.request; print(urllib.request.urlopen('http://${RESULT_IP}:8000/', timeout=5).status)"
```

Harus mendapat HTTP 200. Sertakan screenshot kedua laptop, dua node dengan IP berbeda, empat worker pada node yang tepat, Job Complete, laporan task tanpa kegagalan, dan halaman NodePort yang dibuka dari perangkat lain. Bukti fisik tidak dapat disimpulkan hanya dari dua objek Node API. Pod tetap bukan VM.

## Troubleshooting singkat

- Tes UDP gagal: cek mirrored mode, firewall kedua sisi dan isolasi Wi-Fi; jangan mengganti dengan TCP portproxy.
- API connection refused: pastikan K3s server aktif dan IP tujuan benar (`sudo systemctl status k3s`).
- Node NotReady: lihat `sudo journalctl -u k3s` atau `sudo journalctl -u k3s-agent`; periksa Flannel/CNI dan IP.
- ErrImageNeverPull: load image dengan tag yang sama pada Docker Engine node yang disebut pod.
- Permission denied pada PVC: periksa fsGroup/izin volume; jangan me-mount kubeconfig admin ke pod.
- Pod Pending: periksa selector host1/host2, taint, CPU/RAM dan local-path storage class.
- Job Failed: baca logs dan events sebelum mengulang. Menghentikan client kubectl tidak menjamin task remote ikut berhenti.

## Referensi resmi

- [WSL networking dan mirrored mode](https://learn.microsoft.com/en-us/windows/wsl/networking)
- [K3s requirements dan port](https://docs.k3s.io/installation/requirements)
- [K3s menggunakan Docker runtime](https://docs.k3s.io/advanced#using-docker-as-the-container-runtime)
- [K3s cluster access](https://docs.k3s.io/cluster-access)
- [Docker Engine Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
