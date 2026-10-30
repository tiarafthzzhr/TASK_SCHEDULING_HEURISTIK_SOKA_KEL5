# Alur Aktif: Kubernetes Satu Laptop

```mermaid
flowchart TD
    W["Ubuntu WSL 2 + Docker Engine"] --> K["Cluster kind: soka-local"]
    K --> C["Control-plane"]
    K --> N1["Worker node 1"]
    K --> N2["Worker node 2"]
    N1 --> P0["rr-worker-0"]
    N1 --> P1["rr-worker-1"]
    N2 --> P2["rr-worker-2"]
    N2 --> P3["rr-worker-3"]
    D["Dataset GoCJ asli"] --> R["Scheduler Round Robin: i mod 4"]
    R --> P0
    R --> P1
    R --> P2
    R --> P3
    P0 --> O["CSV, JSON dan report.txt lokal"]
    P1 --> O
    P2 --> O
    P3 --> O
```

1. Hentikan agent K3s percobaan pada laptopmu dan pastikan Docker Engine aktif.
2. Setup kind membuat satu control-plane, dua worker node dan empat pod.
3. Verifikasi membaca status, UID pod dan placement aktual melalui kubectl di container control-plane. Jalur kind memakai docker exec agar tidak tergantung port API yang dipublikasikan ke Windows/WSL.
4. Baca dataset GoCJ yang dipilih, kemudian bagi task bergiliran ke empat pod.
5. Eksekusi hash CPU nyata melalui kubectl exec, serial per pod dan paralel antarpod.
6. Simpan metrik dan checksum ke folder runs, lalu kumpulkan screenshot node/pod serta report.txt.

Node kind adalah container di satu laptop; pod bukan VM. Ini tidak membuktikan dua host fisik. Total tiga node mencakup satu control-plane dan dua worker. Mode ini tidak memerlukan server teman, portproxy atau NodePort. Seluruh dataset sebelumnya tetap tersedia.

Perintah lengkap ada di [README](../README.md). Jalur [K3s dua laptop](K3S-DUA-LAPTOP.md) hanya alternatif sebelumnya.
