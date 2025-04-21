# Create & build by Arief (nocturnalismee)
# source https://github.com/nocturnalismee/simple-monitor-utility
import os
import subprocess

def loading_animation(duration=3):
    import time
    import sys
    animation = "|/-\\"
    idx = 0
    end_time = time.time() + duration
    while time.time() < end_time:
        print(f"\rLoading {animation[idx % len(animation)]}", end="")
        idx += 1
        time.sleep(0.1)
    print("\rDone!     ")

# Fungsi untuk menampilkan teks dengan warna hijau dan tebal

def print_green_bold_text(text):
    terminal_width = os.get_terminal_size().columns
    text_length = len(text)
    padding = (terminal_width - text_length) // 2
    print(" " * padding + "\033[1;32m" + text + "\033[0m")

# Memperbarui fungsi print_header untuk menggunakan teks hijau dan tebal

def print_header():
    os.system('cls' if os.name == 'nt' else 'clear')
    print_green_bold_text("Monitoring Commandline Utility")

# Fungsi untuk menampilkan footer

def print_footer():
    print_green_bold_text("Selesai")

# Fungsi untuk mencari file besar

def find_large_files():
    print_header()
    print("Mencari file backup atau lainnya dengan ukuran > 1GB at /home/*...")
    loading_animation()
    print("Mohon menunggu...")
    print("-----------------------------------------")
    results = subprocess.getoutput("find /home/* -path '/home/*/mail' -prune -o -type f -size +1G -exec du -sh {} + 2>/dev/null | sort -k2,2 -k1,1hr")
    if not results:
        print("No files found larger than 1GB.")
    else:
        print("Ukuran (GB) | Direktori/File")
        print("-----------------------------------------")
        for line in results.splitlines():
            size, path = line.split(maxsplit=1)
            print(f"{size:<10} | {path}")
    print("-----------------------------------------")
    print("Search complete.")
    print_footer()
    input("Press Enter to return to the menu...")

# Fungsi untuk memeriksa penggunaan email

def check_email_usage():
    print_header()
    print("Listing disk usage for each email directory (/home/*/mail) lebih dari 10G...")
    loading_animation()
    print("Mohon menunggu...")
    print("-------------------------------------------------------------")
    print("Size (GB)       | Directory")
    print("----------------|--------------------------------------------")

    threshold = 10737418240  # 10 GiB

    results = subprocess.getoutput("find /home/* -maxdepth 1 -type d -name 'mail' -exec du -sb {} + 2>/dev/null | sort -k2,2 -k1,1nr")
    if not results:
        print("No /home/*/mail directories found.")
    else:
        for line in results.splitlines():
            bytes, dir = line.split(maxsplit=1)
            gb = float(bytes) / (1024*1024*1024)
            if int(bytes) > threshold:
                print(f"\033[0;31m{gb:<15.2f} | {dir} [>10G]\033[0m")  # Red color
    print("-------------------------------------------------------------")
    print("Email usage check complete.")
    print_footer()
    input("Press Enter to return to the menu...")

# Fungsi untuk mencari dan menghapus file berukuran 0 Kb

def find_zero_size_files():
    print_header()
    print("Mencari file dengan ukuran 0 Kb di /home/*...")
    print("Mohon menunggu...")
    print("-----------------------------------------")
    results = subprocess.getoutput("find /home/* -type f -size 0 2>/dev/null")
    if not results:
        print("Tidak ada file dengan ukuran 0 Kb ditemukan.")
    else:
        print("File dengan ukuran 0 Kb ditemukan:")
        print("Ukuran | File")
        print("-------------------------")
        for file in results.splitlines():
            size = subprocess.getoutput(f"du -sh {file} | awk '{{print $1}}'")
            print(f"{size:<7} | {file}")
        print("-------------------------")
        choice = input("Apakah Anda ingin menghapus file-file ini? (y/n): ")
        if choice.lower() == 'y':
            subprocess.run(f"echo '{results}' | xargs rm -f", shell=True)
            print("File-file telah dihapus.")
        else:
            print("Penghapusan dibatalkan.")
    print("-----------------------------------------")
    print("Pencarian selesai.")
    print_footer()
    input("Tekan Enter untuk kembali ke menu...")

# Fungsi untuk menampilkan menu audit disk

def show_disk_audit_menu():
    while True:
        print_header()
        print("Opsi Audit Disk Usage:")
        print("1) Audit File Backup/Arsip > 1GB")
        print("2) Audit Disk Usage Mail")
        print("3) Audit & Delete File 0 Kb")
        print("4) Kembali ke Menu Utama")

        choice = input("#? ")
        if choice == '1':
            find_large_files()
        elif choice == '2':
            check_email_usage()
        elif choice == '3':
            find_zero_size_files()
        elif choice == '4':
            return
        else:
            print("Invalid option. Please try again.")

# Fungsi untuk melacak serangan DDoS berdasarkan jumlah koneksi per IP

def track_ddos_by_ip():
    print_header()
    print("Melacak serangan DDoS berdasarkan jumlah koneksi per IP...")
    print("-----------------------------------------")
    results = subprocess.getoutput("netstat -ntu | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head")
    print(results)
    print("-----------------------------------------")
    print_footer()
    input("Tekan Enter untuk kembali ke menu...")

# Fungsi untuk memeriksa jumlah koneksi httpd per IP

def check_httpd_connections():
    print_header()
    print("Memeriksa jumlah koneksi httpd per IP...")
    print("-----------------------------------------")
    results = subprocess.getoutput("netstat -anp | grep ':80' | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head")
    print(results)
    print("-----------------------------------------")
    print_footer()
    input("Tekan Enter untuk kembali ke menu...")

# Fungsi untuk memeriksa proses httpd dengan status SYN_RECV

def check_syn_recv():
    print_header()
    print("Memeriksa proses httpd dengan status SYN_RECV...")
    print("-----------------------------------------")
    results = subprocess.getoutput("netstat -n | grep 'SYN_RECV' | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head")
    print(results)
    print("-----------------------------------------")
    print_footer()
    input("Tekan Enter untuk kembali ke menu...")

# Fungsi untuk menampilkan menu mitigasi DDoS

def show_ddos_menu():
    while True:
        print_header()
        print("Opsi Mitigasi DDOS:")
        print("1) Track DDoS by IP")
        print("2) Check httpd Connections")
        print("3) Check SYN_RECV Status")
        print("4) Kembali ke Menu Utama")

        choice = input("#? ")
        if choice == '1':
            track_ddos_by_ip()
        elif choice == '2':
            check_httpd_connections()
        elif choice == '3':
            check_syn_recv()
        elif choice == '4':
            return
        else:
            print("Invalid option. Please try again.")

# Fungsi untuk mencari script judi

def find_judi_scripts():
    print_header()
    keyword_file = "/etc/judaylist.txt"
    print(f"Searching for potential gambling scripts based on keywords in {keyword_file}...")

    if not os.path.isfile(keyword_file) or not os.access(keyword_file, os.R_OK):
        print(f"Error: Keyword file '{keyword_file}' not found or not readable.")
        print("Please ensure the file exists and has the correct permissions.")
        input("Press Enter to return to the menu...")
        return

    if os.path.getsize(keyword_file) == 0:
        print(f"Warning: Keyword file '{keyword_file}' is empty.")
        print("No keywords to search for. Aborting search.")
        input("Press Enter to return to the menu...")
        return

    print("Included files: index.*")
    print("Excluded Dirs: cache, tmp, spamcleaner, Scroller, checkout, .cache, .local, .npm, .node-gyp, node_modules")
    print("Excluded Exts: js, map, tpl, ts, log, bak, old, swp, zip, tar, gz, bz2, xz, 7z, rar")
    print("-----------------------------------------")

    results = subprocess.getoutput(
        "grep -ilr --include='index.*' -f {keyword_file} --exclude-dir={cache,tmp,spamcleaner,Scroller,checkout,.cache,.local,.npm,.node-gyp,node_modules} --exclude='*.{js,map,tpl,ts,log,bak,old,swp,zip,tar,gz,bz2,xz,7z,rar}' /home/* 2>/dev/null"
    )

    if not results:
        print("No potential judi script files found matching the criteria.")
    else:
        print("Potential judi script files found:")
        for line in results.splitlines():
            print(line)

    print("-----------------------------------------")
    print("Search complete.")
    print_footer()
    input("Press Enter to return to the menu...")

# Fungsi untuk menampilkan menu audit judol

def show_judol_audit_menu():
    while True:
        print_header()
        print("Opsi Audit Judol:")
        print("1) Cari Script Judi")
        print("2) Kembali ke Menu Utama")

        choice = input("#? ")
        if choice == '1':
            find_judi_scripts()
        elif choice == '2':
            return
        else:
            print("Invalid option. Please try again.")

# Fungsi untuk melakukan scanning backdoor menggunakan file keyword

def perform_scan():
    print_header()
    keyword_file = "/etc/bakdor-key.txt"
    username = input("Masukan username cpanel untuk scan file backdoor, tekan enter dan silahkan di tunggu beberapa saat.\nUsername: ")
    if not username:
        print("Username tidak boleh kosong.")
        return

    website_dir = f"/home/{username}/"
    if not os.path.isdir(website_dir):
        print(f"Direktori {website_dir} tidak ditemukan.")
        return

    if not os.path.isfile(keyword_file) or not os.access(keyword_file, os.R_OK):
        print(f"File keyword '{keyword_file}' tidak ditemukan atau tidak dapat dibaca.")
        return

    found_any = False
    results = subprocess.getoutput(f"find {website_dir} -type f")
    for local_file in results.splitlines():
        if subprocess.getoutput(f"grep -qFf {keyword_file} {local_file}"):
            if not found_any:
                print("Potensi script backdoor ditemukan pada path direktori dibawah:")
                found_any = True
            print(f" > {local_file}")

    if not found_any:
        print("Tidak ditemukan potensi script backdoor yang lainnya saat ini.")
    print_footer()
    input("Tekan Enter untuk kembali ke menu...")

# Memperbarui menu utama untuk memasukkan submenu audit judol

def main_menu():
    while True:
        print_header()
        print("\033[1;32mPlease choose an option:\033[0m")
        print("\033[1;33m1) Audit Disk\033[0m")
        print("\033[1;33m2) Audit Judol\033[0m")
        print("\033[1;33m3) Mitigasi DDoS\033[0m")
        print("\033[1;33m4) Mitigasi Backdoor (beta)\033[0m")
        print("\033[1;33m5) EXIT\033[0m")

        choice = input("#? ")
        if choice == '1':
            show_disk_audit_menu()
        elif choice == '2':
            show_judol_audit_menu()
        elif choice == '3':
            show_ddos_menu()
        elif choice == '4':
            perform_scan()
        elif choice == '5':
            print("Exiting.")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main_menu() 
