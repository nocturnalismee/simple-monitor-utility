#!/usr/bin/env python3
# Monitoring Commandline Utility
# Original by: Arief (nocturnalismee)
# Source: https://github.com/nocturnalismee/simple-monitor-utility
# Version : 2.0.2 (Final Optimized)

import os
import sys
import subprocess
import threading
import time
import logging
import shutil
import re
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────
VERSION = "2.0.2"
LOG_DIR = "/var/log/monitor-utility"
LOG_FILE = f"{LOG_DIR}/audit_{datetime.now().strftime('%Y%m%d')}.log"
KEYWORD_JUDI_URL = "https://raw.githubusercontent.com/nocturnalismee/simple-monitor-utility/main/judaylist.txt"
KEYWORD_BACKDOOR_URL = "https://raw.githubusercontent.com/nocturnalismee/simple-monitor-utility/main/bakdor-key.txt"

# Nama cache lokal di /tmp
CACHE_JUDI = "keywordjudi.txt"
CACHE_BACKDOOR = "patternbackdoor.txt"
CACHE_TTL = 86400 # 24 Jam dalam detik

LARGE_FILE_THRESHOLD = "+1G"
EMAIL_THRESHOLD_BYTES = 10 * 1024 * 1024 * 1024  # 10 GiB

EXCLUDE_DIRS = ["cache", "tmp", "spamcleaner", "Scroller", "checkout",
                ".cache", ".local", ".npm", ".node-gyp", "node_modules"]
EXCLUDE_EXTS = ["js", "map", "tpl", "ts", "log", "bak", "old", "swp",
                "zip", "tar", "gz", "bz2", "xz", "7z", "rar"]

# ─────────────────────────────────────────────
# WARNA ANSI
# ─────────────────────────────────────────────
class Color:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[0;31m"
    GREEN   = "\033[0;32m"
    YELLOW  = "\033[1;33m"
    CYAN    = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    WHITE   = "\033[1;37m"
    BOLD_GREEN = "\033[1;32m"
    DIM     = "\033[2m"

def colorize(text: str, color: str) -> str:
    return f"{color}{text}{Color.RESET}"

def strip_ansi(text: str) -> str:
    """Menghapus kode ANSI untuk perhitungan panjang string yang akurat."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
def setup_logging():
    """Setup logging ke file dan console."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(LOG_FILE),
            ]
        )
    except PermissionError:
        fallback_log = f"/tmp/monitor-utility_{datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(fallback_log)]
        )
        print(colorize(f"[!] Log disimpan ke fallback: {fallback_log}", Color.YELLOW))

def log(message: str, level: str = "info"):
    """Wrapper logging."""
    # Gunakan .lower() karena fungsi di logging module adalah lowercase (info, warning, error)
    log_func = getattr(logging, level.lower(), logging.info)
    log_func(message)

# ─────────────────────────────────────────────
# UI HELPER
# ─────────────────────────────────────────────
def get_terminal_width() -> int:
    return shutil.get_terminal_size(fallback=(80, 24)).columns

def print_centered(text: str, color: str = Color.BOLD_GREEN):
    width = get_terminal_width()
    clean_text = strip_ansi(text)
    padding = max(0, (width - len(clean_text)) // 2)
    print(" " * padding + colorize(text, color))

def print_separator(char: str = "─", color: str = Color.DIM):
    width = get_terminal_width()
    print(colorize(char * width, color))

def print_header():
    subprocess.run(['cls' if os.name == 'nt' else 'clear'], check=False)
    print_separator("═", Color.BOLD_GREEN)
    print_centered(f"  Monitoring Commandline Utility  v{VERSION}  ")
    print_centered(f"  {datetime.now().strftime('%A, %d %B %Y  %H:%M:%S')}  ", Color.DIM)
    print_separator("═", Color.BOLD_GREEN)
    print()

def print_footer(message: str = "Selesai"):
    print()
    print_separator()
    print_centered(f"[+] {message}", Color.BOLD_GREEN)
    print_separator()

def press_enter():
    input(colorize("\n  Tekan Enter untuk kembali ke menu...", Color.CYAN))

def confirm_action(prompt: str) -> bool:
    """Minta konfirmasi dengan mengetik 'ya' (bukan hanya y)."""
    print(colorize(f"\n[!] {prompt}", Color.YELLOW))
    answer = input(colorize("   Ketik 'ya' untuk konfirmasi: ", Color.RED)).strip().lower()
    return answer == "ya"

# ─────────────────────────────────────────────
# HELPER: FETCH & PREPROCESS KEYWORD
# ─────────────────────────────────────────────
def fetch_keyword_file(url: str, cache_name: str) -> Optional[str]:
    """Mengunduh keyword list dari GitHub dengan cache 24 jam."""
    cache_path = f"/tmp/{cache_name}"
    
    if os.path.exists(cache_path):
        file_age = time.time() - os.path.getmtime(cache_path)
        if file_age < CACHE_TTL:
            return cache_path
            
    try:
        print(colorize(f"  [*] Mengunduh keyword list dari GitHub...", Color.CYAN))
        req = urllib.request.Request(url, headers={'User-Agent': 'Monitor-Utility/2.0 (Linux)'})
        with urllib.request.urlopen(req, timeout=10) as response:
            with open(cache_path, 'wb') as f:
                f.write(response.read())
        print(colorize(f"  [+] Keyword list berhasil diunduh.", Color.GREEN))
        return cache_path
        
    except Exception as e:
        print(colorize(f"  [-] Gagal mengunduh dari GitHub: {e}", Color.RED))
        if os.path.exists(cache_path):
            print(colorize(f"  [!] Menggunakan cache lama (offline mode).", Color.YELLOW))
            return cache_path
        return None

def prepare_backdoor_patterns(raw_file: str, fixed_file: str, regex_file: str):
    """Memisahkan fixed string dan regex agar aman untuk grep."""
    fixed_strings = []
    regex_strings = []
    
    regex_detector = re.compile(r'\\[dswDSWbB]|\[[^\]]+\]|\{\d+\}|\{\d+,\d*\}|\||\^|\$')
    hex_detector = re.compile(r'^(\\x[0-9a-fA-F]{2})+$')

    with open(raw_file, 'r', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if hex_detector.match(line):
                fixed_strings.append(line)
                continue
                
            if line.count('[') != line.count(']') or line.count('(') != line.count(')'):
                fixed_strings.append(line)
                continue
                
            if regex_detector.search(line):
                regex_strings.append(line)
            else:
                fixed_strings.append(line)

    # Fallback agar file tidak kosong total (mencegah edge-case pada beberapa versi grep)
    if not fixed_strings: fixed_strings.append("IMPOSSIBLE_STRING_TO_MATCH_12345")
    if not regex_strings: regex_strings.append("^IMPOSSIBLE_REGEX_TO_MATCH_12345$")

    with open(fixed_file, 'w') as f:
        f.write('\n'.join(fixed_strings))
        
    with open(regex_file, 'w') as f:
        f.write('\n'.join(regex_strings))

# ─────────────────────────────────────────────
# LOADING ANIMATION
# ─────────────────────────────────────────────
class LoadingAnimation:
    def __init__(self, message: str = "Memproses"):
        self.message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._animate, daemon=True)

    def _animate(self):
        frames = ["|", "/", "-", "\\"]
        idx = 0
        while not self._stop_event.is_set():
            frame = colorize(frames[idx % len(frames)], Color.CYAN)
            print(f"\r  {frame}  {self.message}...", end="", flush=True)
            idx += 1
            time.sleep(0.1)

    def start(self):
        self._thread.start()

    def stop(self, done_message: str = "Selesai"):
        self._stop_event.set()
        self._thread.join()
        print(f"\r  {colorize('[+]', Color.BOLD_GREEN)}  {done_message}          ")

# ─────────────────────────────────────────────
# HELPER: COMMAND EXECUTION
# ─────────────────────────────────────────────
def run_command(args: list, timeout: int = 300) -> tuple[int, str, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timeout setelah {timeout} detik"
    except Exception as e:
        return -1, "", str(e)

def run_shell(command: str, timeout: int = 300) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        return f"[ERROR] {e}"

# ─────────────────────────────────────────────
# MENU 1: AUDIT DISK
# ─────────────────────────────────────────────
def find_large_files():
    print_header()
    print(colorize("  [AUDIT] File Backup/Arsip > 1GB", Color.BOLD))
    print(colorize("  Lokasi: /home/*\n", Color.DIM))

    anim = LoadingAnimation("Mencari file besar")
    anim.start()
    
    results = run_shell(
        f"find /home/* -path '/home/*/mail' -prune -o -type f -size {LARGE_FILE_THRESHOLD} -print0 2>/dev/null "
        "| xargs -0 du -sh 2>/dev/null | sort -k1,1hr"
    )
    anim.stop("Pencarian selesai")
    print_separator()

    if not results:
        print(colorize("  [+] Tidak ada file yang lebih besar dari 1GB.", Color.GREEN))
    else:
        print(colorize(f"  {'Ukuran':<12} {'Path'}", Color.WHITE))
        print_separator("-")
        lines = results.splitlines()
        for line in lines:
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                size, path = parts
                print(f"  {colorize(size, Color.YELLOW):<20} {path}")
        print_separator("-")
        print(colorize(f"  Total ditemukan: {len(lines)} file", Color.CYAN))
        log(f"find_large_files: {len(lines)} file ditemukan")

    print_footer()
    press_enter()

def check_email_usage():
    print_header()
    print(colorize("  [AUDIT] Disk Usage Email > 10GB", Color.BOLD))
    print(colorize("  Lokasi: /home/*/mail\n", Color.DIM))

    anim = LoadingAnimation("Menganalisa direktori mail")
    anim.start()
    results = run_shell(
        "find /home/* -maxdepth 1 -type d -name 'mail' -exec du -sb {} + 2>/dev/null | sort -k1,1nr"
    )
    anim.stop("Analisa selesai")
    print_separator()

    if not results:
        print(colorize("  [+] Tidak ada direktori /home/*/mail ditemukan.", Color.GREEN))
    else:
        print(colorize(f"  {'Ukuran (GB)':<18} {'Direktori'}", Color.WHITE))
        print_separator("-")
        flagged = 0
        for line in results.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) != 2: continue
            bytes_str, directory = parts
            try:
                total_bytes = int(bytes_str)
                gb = total_bytes / (1024 ** 3)
                if total_bytes > EMAIL_THRESHOLD_BYTES:
                    print(colorize(f"  {gb:<18.2f} {directory}  [!] >10GB", Color.RED))
                    flagged += 1
                    log(f"check_email_usage: {directory} = {gb:.2f}GB [FLAGGED]", "warning")
                else:
                    print(colorize(f"  {gb:<18.2f} {directory}", Color.DIM))
            except ValueError: continue

        print_separator("-")
        if flagged > 0:
            print(colorize(f"  [!] {flagged} direktori melebihi 10GB!", Color.RED))
        else:
            print(colorize("  [+] Semua direktori di bawah threshold 10GB.", Color.GREEN))

    print_footer()
    press_enter()

def find_zero_size_files():
    print_header()
    print(colorize("  [AUDIT] File Berukuran 0 KB", Color.BOLD))
    print(colorize("  Lokasi: /home/*\n", Color.DIM))

    anim = LoadingAnimation("Mencari file 0 KB")
    anim.start()

    exclude_args = []
    for d in EXCLUDE_DIRS:
        exclude_args.extend(["-path", f"*/{d}", "-prune", "-o"])

    cmd = ["find", "/home"] + exclude_args + ["-type", "f", "-size", "0", "-print"]
    returncode, stdout, stderr = run_command(cmd, timeout=300)
    anim.stop("Pencarian selesai")
    print_separator()

    if not stdout:
        print(colorize("  [+] Tidak ada file 0 KB ditemukan.", Color.GREEN))
        print_footer()
        press_enter()
        return

    files = [f for f in stdout.splitlines() if f.strip()]
    print(colorize(f"  Ditemukan {len(files)} file berukuran 0 KB:\n", Color.YELLOW))

    page_size = 20
    for i, filepath in enumerate(files):
        print(colorize(f"  [{i+1:>4}] ", Color.DIM) + filepath)
        if (i + 1) % page_size == 0 and (i + 1) < len(files):
            cont = input(colorize(f"\n  Tampilkan {page_size} file berikutnya? (y/n): ", Color.CYAN))
            if cont.lower() != 'y': break

    print_separator("-")
    log(f"find_zero_size_files: {len(files)} file ditemukan")

    if confirm_action(f"Hapus {len(files)} file ini secara PERMANEN?"):
        deleted, errors = 0, 0
        for filepath in files:
            try:
                p = Path(filepath)
                if p.exists() and not p.is_symlink() and p.stat().st_size == 0:
                    p.unlink()
                    deleted += 1
                    log(f"Deleted: {filepath}")
            except OSError as e:
                print(colorize(f"  [-] Gagal hapus {filepath}: {e}", Color.RED))
                errors += 1

        print(colorize(f"\n  [+] Berhasil dihapus: {deleted} file", Color.GREEN))
        if errors: print(colorize(f"  [-] Gagal dihapus: {errors} file", Color.RED))
    else:
        print(colorize("\n  Penghapusan dibatalkan.", Color.YELLOW))

    print_footer()
    press_enter()

def show_disk_audit_menu():
    show_submenu("Audit Disk Usage", [
        ("Audit File Backup/Arsip > 1GB", find_large_files),
        ("Audit Disk Usage Mail",         check_email_usage),
        ("Audit & Delete File 0 KB",      find_zero_size_files),
    ])

# ─────────────────────────────────────────────
# MENU 2: AUDIT JUDOL
# ─────────────────────────────────────────────
def find_judi_scripts():
    print_header()
    print(colorize("  [AUDIT] Script Judi / Gambling", Color.BOLD))
    print(colorize(f"  Source: {KEYWORD_JUDI_URL}\n", Color.DIM))

    keyword_file = fetch_keyword_file(KEYWORD_JUDI_URL, CACHE_JUDI)
    if not keyword_file:
        print(colorize("  [-] Tidak ada keyword list yang bisa digunakan.", Color.RED))
        press_enter()
        return
        
    if os.path.getsize(keyword_file) == 0:
        print(colorize(f"  [!] File keyword kosong.", Color.YELLOW))
        press_enter()
        return

    exclude_dir_args = [arg for d in EXCLUDE_DIRS for arg in ["--exclude-dir", d]]
    exclude_ext_args = [arg for ext in EXCLUDE_EXTS for arg in ["--exclude", f"*.{ext}"]]

    print(colorize("  Included files : index.*", Color.DIM))
    print(colorize(f"  Excluded dirs  : {', '.join(EXCLUDE_DIRS)}", Color.DIM))
    print(colorize(f"  Excluded exts  : {', '.join(EXCLUDE_EXTS)}", Color.DIM))
    print()

    anim = LoadingAnimation("Mencari script judi")
    anim.start()

    cmd = ["grep", "-i", "-l", "-r", "-F", "--include=index.*", f"-f{keyword_file}"] + exclude_dir_args + exclude_ext_args + ["/home/"]
    returncode, stdout, stderr = run_command(cmd, timeout=600)
    anim.stop("Pencarian selesai")
    print_separator()

    if not stdout:
        print(colorize("  [+] Tidak ada file script judi ditemukan.", Color.GREEN))
    else:
        found_files = stdout.splitlines()
        print(colorize(f"  [!] Ditemukan {len(found_files)} file potensial:\n", Color.RED))
        for filepath in found_files:
            print(colorize("  [*] ", Color.RED) + filepath)
        log(f"find_judi_scripts: {len(found_files)} file flagged", "warning")

    print_footer()
    press_enter()

def show_judol_audit_menu():
    show_submenu("Audit Judol", [("Cari Script Judi", find_judi_scripts)])

# ─────────────────────────────────────────────
# MENU 3: MITIGASI DDOS
# ─────────────────────────────────────────────
def track_ddos_by_ip():
    print_header()
    print(colorize("  [DDoS] Top IP berdasarkan jumlah koneksi", Color.BOLD))
    print_separator()
    results = run_shell("netstat -ntu 2>/dev/null | awk '{print $5}' | grep -oE '^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+' | sort | uniq -c | sort -rn | head -20")

    if not results:
        print(colorize("  Tidak ada data koneksi aktif.", Color.YELLOW))
    else:
        print(colorize(f"  {'Koneksi':<10} {'IP Address'}", Color.WHITE))
        print_separator("-")
        for line in results.splitlines():
            parts = line.split()
            if len(parts) == 2:
                count, ip = parts
                color = Color.RED if int(count) > 100 else Color.YELLOW if int(count) > 20 else Color.RESET
                print(f"  {colorize(count, color):<20} {ip}")
    print_footer()
    press_enter()

def check_httpd_connections():
    print_header()
    print(colorize("  [DDoS] Koneksi HTTPD per IP (port 80 ESTABLISHED)", Color.BOLD))
    print_separator()
    results = run_shell("netstat -anp 2>/dev/null | grep ':80' | grep ESTABLISHED | awk '{print $5}' | grep -oE '^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+' | sort | uniq -c | sort -rn | head -20")

    if not results:
        print(colorize("  Tidak ada koneksi ESTABLISHED di port 80.", Color.YELLOW))
    else:
        print(colorize(f"  {'Koneksi':<10} {'IP Address'}", Color.WHITE))
        print_separator("-")
        for line in results.splitlines():
            parts = line.split()
            if len(parts) == 2:
                count, ip = parts
                color = Color.RED if int(count) > 50 else Color.YELLOW if int(count) > 10 else Color.RESET
                print(f"  {colorize(count, color):<20} {ip}")
    print_footer()
    press_enter()

def check_syn_recv():
    print_header()
    print(colorize("  [DDoS] IP dengan status SYN_RECV (indikasi SYN Flood)", Color.BOLD))
    print_separator()
    results = run_shell("netstat -n 2>/dev/null | grep 'SYN_RECV' | awk '{print $5}' | grep -oE '^[0-9]+\\.[0-9]+\\.[0-9]+\\.[0-9]+' | sort | uniq -c | sort -rn | head -20")

    if not results:
        print(colorize("  [+] Tidak ada koneksi SYN_RECV ditemukan.", Color.GREEN))
    else:
        print(colorize(f"  [!] SYN_RECV terdeteksi!\n", Color.RED))
        print(colorize(f"  {'Count':<10} {'IP Address'}", Color.WHITE))
        print_separator("-")
        for line in results.splitlines():
            parts = line.split()
            if len(parts) == 2:
                print(f"  {colorize(parts[0], Color.RED):<20} {parts[1]}")
        log(f"check_syn_recv: SYN_RECV detected", "warning")
    print_footer()
    press_enter()

def show_ddos_menu():
    show_submenu("Mitigasi DDoS", [
        ("Track DDoS by IP",          track_ddos_by_ip),
        ("Check HTTPD Connections",   check_httpd_connections),
        ("Check SYN_RECV Status",     check_syn_recv),
    ])

# ─────────────────────────────────────────────
# MENU 4: MITIGASI BACKDOOR
# ─────────────────────────────────────────────
def perform_scan():
    print_header()
    print(colorize("  [BACKDOOR] Scanner Script Backdoor", Color.BOLD))
    print(colorize(f"  Source: {KEYWORD_BACKDOOR_URL}\n", Color.DIM))

    raw_keyword_file = fetch_keyword_file(KEYWORD_BACKDOOR_URL, CACHE_BACKDOOR)
    if not raw_keyword_file or os.path.getsize(raw_keyword_file) == 0:
        print(colorize("  [-] Keyword list tidak tersedia atau kosong.", Color.RED))
        press_enter()
        return

    fixed_file = f"{raw_keyword_file}.fixed"
    regex_file = f"{raw_keyword_file}.regex"
    
    # OPTIMASI: Cek cache pre-processor
    needs_processing = (
        not os.path.exists(fixed_file) or 
        not os.path.exists(regex_file) or 
        os.path.getmtime(fixed_file) < os.path.getmtime(raw_keyword_file)
    )

    if needs_processing:
        print(colorize("  [*] Menganalisa dan memisahkan pattern backdoor...", Color.CYAN))
        prepare_backdoor_patterns(raw_keyword_file, fixed_file, regex_file)
        print(colorize("  [+] Pattern berhasil dipisah dan disimpan.", Color.GREEN))
    else:
        print(colorize("  [+] Menggunakan pattern backdoor dari cache lokal.", Color.GREEN))

    username = input(colorize("  Masukkan username cPanel yang ingin di-scan: ", Color.CYAN)).strip()
    if not username or not re.match(r'^[a-zA-Z0-9_\-]{1,32}$', username):
        print(colorize("  [-] Username kosong atau tidak valid.", Color.RED))
        press_enter()
        return

    website_dir = f"/home/{username}/"
    if not os.path.isdir(website_dir):
        print(colorize(f"  [-] Direktori tidak ditemukan: {website_dir}", Color.RED))
        press_enter()
        return

    print(colorize(f"\n  Memulai scan pada: {website_dir}", Color.CYAN))
    anim = LoadingAnimation(f"Scanning /home/{username}")
    anim.start()

    # Scan Fixed Strings
    rc1, out1, _ = run_command(["grep", "-r", "-l", "-F", "--include=*.php", "-f", fixed_file, website_dir], timeout=600)
    # Scan Regex
    rc2, out2, _ = run_command(["grep", "-r", "-l", "-E", "--include=*.php", "-f", regex_file, website_dir], timeout=600)

    anim.stop("Scan selesai")
    print_separator()

    found_files = sorted(list(set((out1.splitlines() if out1 else []) + (out2.splitlines() if out2 else []))))

    if not found_files:
        print(colorize("  [+] Tidak ditemukan potensi script backdoor.", Color.GREEN))
    else:
        print(colorize(f"  [!] Ditemukan {len(found_files)} potensi backdoor:\n", Color.RED))
        for filepath in found_files:
            print(colorize("  [*] ", Color.RED) + filepath)
        log(f"perform_scan [{username}]: {len(found_files)} backdoor potensial", "warning")

        if input(colorize("\n  Simpan hasil ke file? (y/n): ", Color.CYAN)).strip().lower() == 'y':
            report_path = f"/tmp/backdoor_scan_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            try:
                with open(report_path, 'w') as f:
                    f.write(f"Backdoor Scan Report\nUsername : {username}\nWaktu    : {datetime.now()}\nDitemukan: {len(found_files)} file\n{'='*50}\n")
                    f.write('\n'.join(found_files))
                print(colorize(f"  [+] Laporan disimpan ke: {report_path}", Color.GREEN))
            except OSError as e:
                print(colorize(f"  [-] Gagal menyimpan laporan: {e}", Color.RED))

    print_footer()
    press_enter()

# ─────────────────────────────────────────────
# SUBMENU & MAIN MENU
# ─────────────────────────────────────────────
def show_submenu(title: str, menu_items: list):
    """
    Render submenu generik.
    menu_items: list of (label, function)
    """
    while True:
        print_header()
        print(colorize(f"  Opsi: {title}", Color.BOLD))
        print()

        for i, (label, _) in enumerate(menu_items, start=1):
            print(colorize(f"  {i})", Color.YELLOW) + f" {label}")

        back_num = len(menu_items) + 1
        print(colorize(f"  {back_num})", Color.DIM) + " Kembali ke Menu Utama")
        print()

        choice = input(colorize("  #? ", Color.CYAN)).strip()

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(menu_items):
                menu_items[idx - 1][1]()
                continue  # <--- PERBAIKAN: Lanjut ke loop berikutnya, skip pesan error
            elif idx == back_num:
                return
            else:
                print(colorize("  [-] Pilihan tidak valid.", Color.RED))
                time.sleep(1)
        else:
            print(colorize("  [-] Masukkan angka.", Color.RED))
            time.sleep(1)

def show_system_info():
    try:
        print(colorize(f"  Host   : {run_shell('hostname').strip()}", Color.DIM))
        print(colorize(f"  Uptime : {run_shell('uptime -p 2>/dev/null || uptime').strip()}", Color.DIM))
        print(colorize(f"  Load   : {run_shell('cat /proc/loadavg | awk \'{print $1,$2,$3}\'').strip()}", Color.DIM))
        print(colorize(f"  Disk / : {run_shell('df -h / | tail -1 | awk \'{print $3\"/\"$2\" (\"$5\" used)\"}\'').strip()}", Color.DIM))
        print()
    except Exception: pass

def main_menu():
    setup_logging()
    log(f"Session dimulai - PID {os.getpid()}")

    menu_items = [
        ("Audit Disk",              show_disk_audit_menu),
        ("Audit Judol",             show_judol_audit_menu),
        ("Mitigasi DDoS",           show_ddos_menu),
        ("Mitigasi Backdoor (beta)", perform_scan),
    ]

    while True:
        print_header()
        show_system_info()
        print(colorize("  Pilih opsi:", Color.BOLD))
        print()

        for i, (label, _) in enumerate(menu_items, start=1):
            print(colorize(f"  {i})", Color.YELLOW) + f" {label}")

        print(colorize(f"  {len(menu_items)+1})", Color.RED) + " EXIT")
        print()

        choice = input(colorize("  #? ", Color.CYAN)).strip()

        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(menu_items):
                menu_items[idx - 1][1]()
                continue  # <--- PERBAIKAN: Lanjut ke loop berikutnya, skip pesan error
            elif idx == len(menu_items) + 1:
                log("Session berakhir")
                print(colorize("\n  Sampai jumpa!\n", Color.BOLD_GREEN))
                sys.exit(0)
            else:
                print(colorize("  [-] Pilihan tidak valid.", Color.RED))
                time.sleep(1)
        else:
            print(colorize("  [-] Masukkan angka.", Color.RED))
            time.sleep(1)

if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("ERROR: Python 3.9+ diperlukan.")
        sys.exit(1)
    main_menu()
