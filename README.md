# Monitoring Commandline Utility

Utility Python command-line untuk audit dasar shared-hosting/Linux: audit disk, pencarian indikator konten judi dan backdoor, serta triage koneksi jaringan.

> Hasil scanner adalah indikator investigasi, bukan bukti kompromi atau dasar penghapusan/blokir otomatis.

## Kebutuhan

- Linux dan Python 3.9 atau lebih baru.
- Perintah `grep`, `find`, `du`, `sort`, `xargs`, `awk`, `df`, dan `ss`.
- Akses baca ke target scan, biasanya `/home`.
- Akses tulis ke `/var/log/monitor-utility` dan `/var/cache/monitor-utility` bila dijalankan sebagai root.

Jalankan sebagai root hanya bila memang diperlukan untuk membaca seluruh akun hosting. Penghapusan file 0 KB bersifat permanen dan membutuhkan konfirmasi `ya`.

## Instalasi dan menjalankan

Salin `mcu.py` dan README ini ke server. Validasi syntax sebelum penggunaan pertama:

```bash
python3 -m py_compile mcu.py
python3 mcu.py
```

`py_compile` hanya pemeriksaan syntax; tidak wajib dijalankan setiap kali. Untuk pemeriksaan dan eksekusi sekaligus:

```bash
python3 -m py_compile mcu.py && python3 mcu.py
```

## Lokasi data lokal

| Lokasi | Isi | Permission |
| --- | --- | --- |
| `/var/log/monitor-utility/` | audit log harian | akses tulis proses |
| `/var/cache/monitor-utility/` | keyword cache, SHA-256, pola, laporan | `0700` |
| `$HOME/.cache/monitor-utility/` | fallback cache jika `/var/cache` tidak tersedia | `0700` |

File cache/laporan dibuat dengan mode `0600`.

## Menu

### 1. Audit Disk

- **Audit File Backup/Arsip > 1GB**: menampilkan file besar pada `/home`, kecuali subtree mail.
- **Audit Disk Usage Mail**: menghitung ukuran `/home/*/mail` dan menandai yang lebih dari 10 GiB.
- **Audit & Delete File 0 KB**: menampilkan file kosong di `/home`; penghapusan hanya berjalan setelah konfirmasi `ya`.

Direktori cache/dependency serta ekstensi arsip dan log dikecualikan sesuai `EXCLUDE_DIRS` dan `EXCLUDE_EXTS` di `mcu.py`.

### 2. Audit Judol

Tiga target scan tersedia:

1. seluruh `/home`;
2. satu username cPanel;
3. direktori custom dari operator.

Scan memeriksa `index.*`, PHP/PHTML, INC, HTML, dan HTM. Hasil menunjukkan file yang mengandung keyword dari `judaylist.txt`; selalu periksa konteks file sebelum melakukan tindakan.

### 3. Mitigasi DDoS

- **Track DDoS by IP**: IP peer berdasarkan jumlah socket TCP/UDP aktif.
- **Check HTTPD Connections**: koneksi `ESTABLISHED` ke port lokal 80 dan 443.
- **Check SYN_RECV Status**: peer yang berada pada status `SYN_RECV`.

Menu ini memakai `ss` dan mendukung IPv4/IPv6. Jumlah socket bukan packet rate, bandwidth, atau atribusi akun/proses. Untuk insiden nyata, ambil packet capture dan korelasikan socket/proses sebelum memblokir trafik.

### 4. Mitigasi Backdoor (beta)

Masukkan username cPanel untuk memindai PHP pada `/home/<username>/`. Keyword dari `bakdor-key.txt` dipisahkan menjadi fixed string dan extended regular expression. Regex invalid tidak diteruskan ke `grep -E`, sehingga error pattern tidak menghasilkan laporan bersih palsu.

Laporan opsional disimpan di direktori cache privat dengan nama acak.

## Keyword remote dan pin SHA-256

Keyword judol/backdoor diunduh melalui HTTPS dari GitHub. Saat nilai pin masih `None`, aplikasi memakai **trust on first use (TOFU)**:

1. download pertama diterima dan SHA-256 disimpan pada cache privat;
2. perubahan isi file remote berikutnya ditolak;
3. cache tervalidasi lama tetap dipakai sampai administrator menyetujui update.

Setelah mengubah keyword di GitHub, commit dan review terlebih dahulu. Hitung hash dari konten raw yang benar-benar akan diunduh script:

```bash
curl -fsSL https://raw.githubusercontent.com/nocturnalismee/simple-monitor-utility/main/judaylist.txt | sha256sum
curl -fsSL https://raw.githubusercontent.com/nocturnalismee/simple-monitor-utility/main/bakdor-key.txt | sha256sum
```

Masukkan hash 64 karakter dari output tersebut ke konfigurasi:

```python
KEYWORD_JUDI_SHA256: Optional[str] = "sha256-judaylist-64-karakter"
KEYWORD_BACKDOOR_SHA256: Optional[str] = "sha256-bakdor-key-64-karakter"
```

Jangan mengganti `Optional[str]`; yang diganti hanya nilai `None` di sisi kanan. Jika hanya mengubah list judol, cukup perbarui `KEYWORD_JUDI_SHA256`.

Jangan menghapus sidecar `.sha256` hanya agar update diterima. Review perubahan, hitung hash baru, perbarui pin di source, lalu lakukan validasi syntax lagi.

## Operasional aman

1. Uji perubahan di staging atau satu akun cPanel lebih dahulu.
2. Menu 2 dan 4 hanya deteksi awal; buka dan nilai file yang terdeteksi secara manual.
3. Untuk anomali jaringan, simpan bukti packet/socket. Jangan menyimpulkan pemilik akun atau memblokir IP hanya dari jumlah koneksi.
4. Sebelum menggunakan hapus file 0 KB, review daftarnya dan pastikan aplikasi tidak membutuhkannya.
5. Simpan perubahan source dan nilai SHA-256 pada change record.

## Troubleshooting

| Gejala | Tindakan |
| --- | --- |
| `ss` tidak ditemukan | Instal paket `iproute2` pada distribusi terkait. |
| Keyword tidak dapat diunduh | Periksa DNS/egress HTTPS; cache tervalidasi lama masih dapat dipakai. |
| `SHA-256 ... tidak sesuai` | Review update remote, hitung hash baru, lalu perbarui pin secara sadar. |
| `grep` atau `find` gagal | Baca pesan error dan audit log; jangan menganggap hasil scan bersih. |
| Cache aman tidak tersedia | Periksa ownership/permission `/var/cache/monitor-utility` atau gunakan fallback `$HOME/.cache/monitor-utility`. |

## Batasan

- Tidak melakukan remediasi otomatis selain hapus file 0 KB yang dikonfirmasi operator.
- Tidak membuktikan file yang terdeteksi adalah malware.
- Tidak menggantikan telemetry PPS/BPS, firewall, packet capture, atau atribusi proses saat investigasi DDoS.
- Signature list tetap perlu direview agar false positive dan false negative terkendali.
