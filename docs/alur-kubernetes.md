# Alur Sistem K3s Dua Laptop

Lihat [panduan langkah demi langkah](K3S-DUA-LAPTOP.md) untuk perintah lengkap dan [README](../README.md) untuk ringkasan tugas.

```mermaid
flowchart TD
    N["Wi-Fi: TCP/UDP antar-client harus diizinkan"] --> L1["Laptop 1: Ubuntu WSL mirrored + Docker Engine"]
    N --> L2["Laptop 2: Ubuntu WSL mirrored + Docker Engine"]
    L1 --> M["soka-master: control-plane + workload"]
    L2 --> W["soka-worker"]
    M --> P0["rr-worker-0"]
    M --> P1["rr-worker-1"]
    W --> P2["rr-worker-2"]
    W --> P3["rr-worker-3"]
    M --> J["Job: controller Round Robin"]
    J --> P0
    J --> P1
    J --> P2
    J --> P3
    J --> V["PVC hasil pada master"]
    V --> S["Deployment web read-only"]
    S --> H["Service NodePort 30080"]
    H --> B["Browser perangkat lain di Wi-Fi"]
```

## Persiapan (sekali sebelum eksperimen)

1. Pastikan versi Windows mendukung WSL mirrored networking, systemd aktif dan Docker Engine native tersedia pada masing-masing Ubuntu.
2. Buka hanya port yang diperlukan dengan cakupan IP peer/subnet yang jelas.
3. Jalankan uji TCP dan UDP 8472 dalam dua arah. Jangan lanjut bila Wi-Fi memblokir komunikasi.
4. Pasang server K3s pada laptop 1 dan agent versi sama pada laptop 2, menggunakan runtime Docker.
5. Label host1 untuk master dan host2 untuk agent. Master menerima workload juga.
6. Build satu image aplikasi, transfer tar dan load pada Engine kedua laptop.
7. Terapkan empat worker, RBAC, PVC, Deployment web dan NodePort.

## Eksekusi (setiap run)

```mermaid
sequenceDiagram
    participant U as Pengguna Ubuntu laptop 1
    participant A as Kubernetes API
    participant J as Job controller RR
    participant P as Empat pod worker
    participant V as PVC hasil
    participant H as Web NodePort
    U->>A: Submit Job dengan dataset GoCJ terpilih
    A->>J: Jalankan image lokal di master
    J->>A: Verifikasi dua node dan empat pod
    J->>J: Baca data asli, petakan task i ke i mod 4
    loop Antrean tiap pod serial, empat antrean paralel
        J->>A: Periksa UID pod tetap sama
        J->>P: kubectl exec menjalankan hash CPU
        P-->>J: Waktu CPU/wall, checksum dan status
    end
    J->>V: Tulis report.txt, CSV, JSON dan topologi
    J-->>A: Job Complete jika tidak ada task gagal
    H->>V: Baca volume hasil
    U->>H: Browser melalui IP Wi-Fi laptop 1:30080
```

RR membagi task ke pod; Kubernetes menempatkan pod ke node. Untuk 100 task tiap pod memperoleh 25 task, tetapi durasi tidak harus sama karena bobot GoCJ berbeda-beda. Input tetap dataset sebelumnya, bukan data sintetis yang dibuat ulang. Nilai dataset diskalakan menjadi iterasi hash dan bukan pengukuran instruksi hardware.

## Bukti dan batasan

Catat dua node dengan IP berbeda, dua pod RR pada setiap node, Job Complete, hasil tanpa kegagalan dan akses halaman dari perangkat lain. Verifikasi juga HTTP antarpod lintas node sesuai panduan. Node Ready saja belum cukup untuk membuktikan jaringan pod berfungsi.

Pod bukan VM. Dua objek Node tidak otomatis membuktikan dua perangkat fisik; sertakan bukti kedua laptop. Runtime menggunakan Docker Engine dalam WSL, sementara WSL 2 sendiri tetap memakai virtualisasi bawaan Windows. Deployment lintas laptop dan kebijakan jaringan kampus harus diuji langsung; pengujian unit tidak menggantikannya.
