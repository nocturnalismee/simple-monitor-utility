# 💻 Monitoring Commandline Utility 💻

Script Bash ini adalah alat sederhana untuk memantau dan mengelola server dengan berbagai fitur seperti audit disk, audit judol, mitigasi DDoS, dan mitigasi backdoor.

## ✨ Fitur Utama

- **🗄️ Audit Disk**:
  - Memeriksa file backup/arsip yang lebih besar dari 1GB.
  - Audit penggunaan disk untuk direktori mail.
  - Menghapus file berukuran 0 Kb di direktori home user.
- **🔍 Audit Judol**:
  - Mencari script judi berdasarkan file keyword lokal. (Berinama dan simpan keyword anda di `/etc/judaylist.txt` ).
- **🛡️ Mitigasi DDoS**:
  - Melacak serangan DDoS berdasarkan jumlah koneksi per IP.
  - Memeriksa koneksi httpd per IP.
  - Memeriksa status SYN_RECV.
- **🛡️ Mitigasi File Backdoor (Beta)**:
  - Memindai file pada direktori website `/home/username/*` untuk potensi script backdoor. keyword atau pattern simpan di local `patterns=("string or pattern in here" "etc")`

## 🚀 Cara Penggunaan

1. Jalankan script dengan perintah:
   ```bash
   ./monitor-utility.sh
   ```
2. Pilih opsi yang diinginkan dari menu yang tersedia.

## 📋 Persyaratan

- **Bash**: Pastikan Bash terinstal di sistem Anda.
- **Akses Root**: Diperlukan untuk beberapa fitur.

## ⚙️ Instalasi

1. Clone repository ini:
   ```bash
   git clone <repository-url>
   ```
2. Pastikan script memiliki izin eksekusi:
   ```bash
   chmod +x monitor-utility.sh
   ```

## Catatan
- ❗Perlu diingat script bash ini masih beta dan akan terus dicoba lakukan pengembangan dan penambahan tool. 😊
- ❗Baru dicoba test pada server cloudlinux dengan panel WHM/cPanel.


## 🤝 Kontribusi

Kami menyambut kontribusi dari komunitas. Silakan buat pull request untuk perbaikan atau fitur baru.

## 📄 Lisensi

Proyek ini dilisensikan di bawah lisensi MIT. Lihat file LICENSE untuk detail lebih lanjut.
