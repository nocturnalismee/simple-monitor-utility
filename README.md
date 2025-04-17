# Simple Monitoring Utility Tool

Script bash ini adalah tool simple untuk memantau dan mengelola server dengan berbagai fitur seperti audit disk, audit judol, dan mitigasi DDoS.

## Fitur

- **Audit Disk**: Memeriksa file backup/arsip yang lebih besar dari 1GB, Audit penggunaan disk untuk direktori mail, dan menghapus file berukuran 0 Kb untuk direktory home user.
- **Audit Judol**: Mencari script judi berdasarkan file keyword lokal.
- **Mitigasi DDoS**: Melacak serangan DDoS berdasarkan jumlah koneksi per IP, memeriksa koneksi httpd per IP, dan memeriksa status SYN_RECV.

## Penggunaan

1. Jalankan script dengan perintah `./monitor-utility.sh`.
2. Pilih opsi yang diinginkan dari menu yang tersedia.

## Persyaratan

- Bash
- Akses root (untuk beberapa fitur)

## Instalasi

1. Clone repository ini.
2. Pastikan script memiliki izin eksekusi: `chmod +x monitor-utility.sh`.

## Kontribusi

Silakan buat pull request untuk perbaikan atau fitur baru.

## Informasi lainnya
Perlu diingat script bash ini masih beta dan akan terus dicoba lakukan pengembangan dan penambahan tool. 😊
