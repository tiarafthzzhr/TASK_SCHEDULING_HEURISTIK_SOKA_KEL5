# Push sendiri ke repository Kubernetes

Folder ini mandiri dan hanya berisi implementasi Kubernetes. Repository Git baru dibuat **di dalam folder ini**, sehingga riwayat dan file proyek induk tidak ikut push.

## 1. Masuk ke folder yang benar

Pada workspace saat ini:

```powershell
cd "C:\Users\TIARA F.A\soka-taskscheduling1\TASK_SCHEDULING_HEURISTIK_SOKA_KEL5"
Get-Location
```

Boleh juga menyalin folder ini ke lokasi lain dahulu. Sesuaikan perintah cd dengan lokasi tersebut.

## 2. Buat Git baru dan commit

Jalankan hanya dari folder tersebut:

```powershell
git init -b main
git add .
git status
git diff --cached --stat
git commit -m "Implementasi heuristik Round Robin pada Kubernetes lokal"
```

Periksa bahwa yang staged hanya file Kubernetes, dataset, dokumentasi dan test. File hasil run, binary kind, cache dan kredensial diabaikan oleh .gitignore. Tidak perlu menjalankan git add dari folder proyek induk.

## 3. Pasang tujuan yang benar

Untuk Git baru yang belum memiliki remote:

```powershell
git remote add origin https://github.com/tiarafthzzhr/TASK_SCHEDULING_HEURISTIK_SOKA_KEL5.git
git remote -v
```

Jika origin sudah ada, periksa alamatnya. Bila salah, ubah dengan:

```powershell
git remote set-url origin https://github.com/tiarafthzzhr/TASK_SCHEDULING_HEURISTIK_SOKA_KEL5.git
```

## 4. Push

```powershell
git push -u origin main
```

Login melalui browser jika diminta. Ini mengirim commit dari repository baru di folder ini. Jika muncul rejected/fetch first karena repository tujuan sudah berisi commit, jangan gunakan --force. Periksa isi remote terlebih dahulu agar file di GitHub tidak tertimpa; kirim errornya untuk menentukan langkah penggabungan yang sesuai.

Setelah push berhasil, buka repository tujuan dan pastikan README serta scheduler Kubernetes tampil.
