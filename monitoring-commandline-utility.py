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
import hashlib
import stat
import tempfile
import ipaddress
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

# Set digest berikut bila ingin mewajibkan versi signature tertentu. Nilai None
# memakai trust-on-first-use (TOFU): signature pertama dicatat dan perubahan
# berikutnya ditolak sampai administrator memperbarui pin secara sadar.
KEYWORD_JUDI_SHA256: Optional[str] = None
KEYWORD_BACKDOOR_SHA256: Optional[str] = None

# Cache disimpan pada direktori privat, bukan /tmp yang dapat ditulis semua user.
CACHE_DIR = Path("/var/cache/monitor-utility")
CACHE_JUDI = "keywordjudi.txt"
CACHE_BACKDOOR = "patternbackdoor.txt"
CACHE_TTL = 86400 # 24 Jam dalam detik

# Ekstensi web yang relevan untuk audit konten. Menu Judol tetap tidak memindai
# arsip, log, dependency, maupun aset statis yang sudah dikecualikan.
WEB_SCAN_GLOBS = ["index.*", "*.php", "*.phtml", "*.php3", "*.php4", "*.php5",
                  "*.php7", "*.php8", "*.inc", "*.html", "*.htm"]

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
        fallback_log = get_private_cache_dir() / f"monitor-utility_{datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(str(fallback_log))]
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
def get_private_cache_dir() -> Path:
    """Mengembalikan direktori cache yang dimiliki proses dan tidak world-writable."""
    candidates = [CACHE_DIR, Path.home() / ".cache" / "monitor-utility"]
    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                continue
            if info.st_uid != os.geteuid():
                continue
            os.chmod(directory, 0o700)
            return directory
        except OSError:
            continue
    raise OSError("Tidak dapat membuat direktori cache privat")


def is_regular_file(path: Path) -> bool:
    """Memastikan path adalah file biasa, tanpa mengikuti symlink."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def atomic_write(path: Path, content: bytes) -> None:
    """Menulis file dengan permission 0600 melalui replace atomik di direktori privat."""
    descriptor, temp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def create_secure_report(username: str, found_files: list[str]) -> str:
    """Menyimpan laporan dengan nama acak di direktori privat, bukan /tmp."""
    cache_dir = get_private_cache_dir()
    descriptor, report_path = tempfile.mkstemp(
        prefix=f"backdoor_scan_{username}_",
        suffix=".txt",
        dir=cache_dir,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                f"Backdoor Scan Report\nUsername : {username}\nWaktu    : {datetime.now()}\n"
                f"Ditemukan: {len(found_files)} file\n{'=' * 50}\n"
            )
            handle.write("\n".join(found_files))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(report_path, 0o600)
        return report_path
    except Exception:
        try:
            os.unlink(report_path)
        except OSError:
            pass
        raise


def read_cached_digest(digest_path: Path) -> Optional[str]:
    if not is_regular_file(digest_path):
        return None
    try:
        digest = digest_path.read_text(encoding="ascii").strip().lower()
        return digest if re.fullmatch(r"[0-9a-f]{64}", digest) else None
    except OSError:
        return None


def cache_matches_digest(cache_path: Path, digest: Optional[str], expected_sha256: Optional[str]) -> bool:
    """Memeriksa isi cache, sidecar digest, dan optional pin konfigurasi."""
    if not digest or not is_regular_file(cache_path):
        return False
    try:
        if hashlib.sha256(cache_path.read_bytes()).hexdigest() != digest:
            return False
        return not expected_sha256 or digest == expected_sha256.lower()
    except OSError:
        return False


def fetch_keyword_file(url: str, cache_name: str, expected_sha256: Optional[str] = None) -> Optional[str]:
    """Mengunduh signature list secara aman, dengan cache 24 jam dan pin SHA-256."""
    if Path(cache_name).name != cache_name:
        raise ValueError("Nama cache tidak valid")

    try:
        cache_dir = get_private_cache_dir()
    except OSError as error:
        print(colorize(f"  [-] Cache aman tidak tersedia: {error}", Color.RED))
        return None

    cache_path = cache_dir / cache_name
    digest_path = cache_dir / f"{cache_name}.sha256"
    cached_digest = read_cached_digest(digest_path)
    cache_valid = cache_matches_digest(cache_path, cached_digest, expected_sha256)
    if cache_valid and time.time() - cache_path.stat().st_mtime < CACHE_TTL:
        return str(cache_path)

    try:
        print(colorize("  [*] Mengunduh keyword list dari GitHub...", Color.CYAN))
        request = urllib.request.Request(url, headers={"User-Agent": f"Monitor-Utility/{VERSION} (Linux)"})
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read(10 * 1024 * 1024 + 1)
        if not payload or len(payload) > 10 * 1024 * 1024:
            raise ValueError("Ukuran keyword list tidak valid")

        received_digest = hashlib.sha256(payload).hexdigest()
        required_digest = expected_sha256.lower() if expected_sha256 else cached_digest
        if required_digest and received_digest != required_digest:
            raise ValueError("SHA-256 keyword list tidak sesuai dengan pin cache")

        atomic_write(cache_path, payload)
        atomic_write(digest_path, f"{received_digest}\n".encode("ascii"))
        print(colorize("  [+] Keyword list berhasil diunduh dan diverifikasi.", Color.GREEN))
        return str(cache_path)
    except Exception as error:
        print(colorize(f"  [-] Gagal mengunduh atau memverifikasi GitHub: {error}", Color.RED))
        if cache_valid:
            print(colorize("  [!] Menggunakan cache tervalidasi (offline mode).", Color.YELLOW))
            return str(cache_path)
        return None


def is_valid_ere(pattern: str) -> bool:
    """Memastikan pola dapat diproses oleh grep -E sebelum dipakai untuk scan."""
    result = subprocess.run(
        ["grep", "-E", "-q", "-e", pattern, "/dev/null"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode in (0, 1)


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
                
            if regex_detector.search(line) and is_valid_ere(line):
                regex_strings.append(line)
            else:
                fixed_strings.append(line)

    # Fallback agar file tidak kosong total (mencegah edge-case pada beberapa versi grep)
    if not fixed_strings: fixed_strings.append("IMPOSSIBLE_STRING_TO_MATCH_12345")
    if not regex_strings: regex_strings.append("^IMPOSSIBLE_REGEX_TO_MATCH_12345$")

    atomic_write(Path(fixed_file), ('\n'.join(fixed_strings) + '\n').encode("utf-8"))
    atomic_write(Path(regex_file), ('\n'.join(regex_strings) + '\n').encode("utf-8"))

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


def run_shell_checked(command: str, timeout: int = 300) -> tuple[int, str, str]:
    """Menjalankan pipeline shell dengan pipefail agar error tidak tersembunyi."""
    return run_command(["bash", "-o", "pipefail", "-c", command], timeout=timeout)


def show_scan_error(action: str, returncode: int, stderr: str) -> None:
    """Menampilkan error command agar kegagalan tidak dianggap sebagai hasil bersih."""
    detail = stderr or f"exit code {returncode}"
    print(colorize(f"  [-] {action} gagal: {detail}", Color.RED))
    log(f"{action} gagal (rc={returncode}): {detail}", "error")

# ─────────────────────────────────────────────
# MENU 1: AUDIT DISK
# ─────────────────────────────────────────────
def find_large_files():
    print_header()
    print(colorize("  [AUDIT] File Backup/Arsip > 1GB", Color.BOLD))
    print(colorize("  Lokasi: /home/*\n", Color.DIM))

    anim = LoadingAnimation("Mencari file besar")
    anim.start()
    
    returncode, results, stderr = run_shell_checked(
        f"find /home/* -path '/home/*/mail' -prune -o -type f -size {LARGE_FILE_THRESHOLD} -print0 2>/dev/null "
        "| xargs -0 du -sh 2>/dev/null | sort -k1,1hr"
    )
    anim.stop("Pencarian selesai")
    print_separator()

    if returncode != 0:
        show_scan_error("Pencarian file besar", returncode, stderr)
        print_footer("Pencarian gagal")
        press_enter()
        return

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
    returncode, results, stderr = run_shell_checked(
        "find /home/* -maxdepth 1 -type d -name 'mail' -exec du -sb {} + 2>/dev/null | sort -k1,1nr"
    )
    anim.stop("Analisa selesai")
    print_separator()

    if returncode != 0:
        show_scan_error("Analisa disk usage email", returncode, stderr)
        print_footer("Analisa gagal")
        press_enter()
        return

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

    if returncode != 0:
        show_scan_error("Pencarian file 0 KB", returncode, stderr)
        print_footer("Pencarian gagal")
        press_enter()
        return

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
def execute_judi_scan(target_dir: str, scan_title: str):
    """
    Fungsi inti untuk menjalankan scan judi pada direktori target.
    """
    print_header()
    print(colorize(f"  [AUDIT] Script Judi - {scan_title}", Color.BOLD))
    print(colorize(f"  Target: {target_dir}", Color.DIM))
    print(colorize(f"  Source: {KEYWORD_JUDI_URL}\n", Color.DIM))

    # Fetch dari GitHub / Cache
    keyword_file = fetch_keyword_file(KEYWORD_JUDI_URL, CACHE_JUDI, KEYWORD_JUDI_SHA256)
    
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

    print(colorize(f"  Included files : {', '.join(WEB_SCAN_GLOBS)}", Color.DIM))
    print(colorize(f"  Excluded dirs  : {', '.join(EXCLUDE_DIRS)}", Color.DIM))
    print(colorize(f"  Excluded exts  : {', '.join(EXCLUDE_EXTS)}", Color.DIM))
    print()

    anim = LoadingAnimation(f"Scanning {target_dir}")
    anim.start()

    # Command grep dengan target direktori dinamis
    include_args = [arg for pattern in WEB_SCAN_GLOBS for arg in ["--include", pattern]]
    cmd = ["grep", "-i", "-l", "-r", "-F", "-f", keyword_file] + include_args + exclude_dir_args + exclude_ext_args + [target_dir]

    returncode, stdout, stderr = run_command(cmd, timeout=600)
    anim.stop("Pencarian selesai")
    print_separator()

    if returncode not in (0, 1):
        show_scan_error("Scan konten judi", returncode, stderr)
        print_footer("Scan gagal")
        press_enter()
        return

    if not stdout:
        print(colorize("  [+] Tidak ada file script judi ditemukan.", Color.GREEN))
    else:
        found_files = stdout.splitlines()
        print(colorize(f"  [!] Ditemukan {len(found_files)} file potensial:\n", Color.RED))
        for filepath in found_files:
            print(colorize("  [*] ", Color.RED) + filepath)
        log(f"find_judi_scripts [{scan_title}]: {len(found_files)} file flagged", "warning")

    print_footer()
    press_enter()

def scan_judi_all():
    """Opsi 1: Scan seluruh /home"""
    execute_judi_scan("/home/", "Semua Direktori /home")

def scan_judi_by_username():
    """Opsi 2: Scan berdasarkan username cPanel"""
    print_header()
    print(colorize("  [AUDIT] Script Judi by Username", Color.BOLD))
    username = input(colorize("  Masukkan username cPanel: ", Color.CYAN)).strip()
    
    if not username:
        print(colorize("  [-] Username tidak boleh kosong.", Color.RED))
        press_enter()
        return
        
    if not re.match(r'^[a-zA-Z0-9_\-]{1,32}$', username):
        print(colorize("  [-] Username tidak valid.", Color.RED))
        press_enter()
        return

    target_dir = f"/home/{username}/"
    if not os.path.isdir(target_dir):
        print(colorize(f"  [-] Direktori tidak ditemukan: {target_dir}", Color.RED))
        press_enter()
        return

    execute_judi_scan(target_dir, f"User: {username}")

def scan_judi_custom_dir():
    """Opsi 3: Scan direktori custom"""
    print_header()
    print(colorize("  [AUDIT] Script Judi Custom Direktori", Color.BOLD))
    target_dir = input(colorize("  Masukkan path direktori (contoh: /home/user/public_html): ", Color.CYAN)).strip()
    
    if not target_dir:
        print(colorize("  [-] Path tidak boleh kosong.", Color.RED))
        press_enter()
        return
    
    # Normalisasi path agar diakhiri slash untuk grep
    if not target_dir.endswith('/'):
        target_dir += '/'
        
    if not os.path.isdir(target_dir):
        print(colorize(f"  [-] Direktori tidak ditemukan atau bukan folder: {target_dir}", Color.RED))
        press_enter()
        return

    execute_judi_scan(target_dir, "Custom Direktori")

def show_judol_audit_menu():
    show_submenu("Audit Judol", [
        ("Cari Konten Judi ( Opsi All Direktori /home)", scan_judi_all),
        ("Cari Konten Judi by Username cPanel", scan_judi_by_username),
        ("Cari Konten Judi by custom Direktory", scan_judi_custom_dir),
    ])

# ─────────────────────────────────────────────
# MENU 3: MITIGASI DDOS
# ─────────────────────────────────────────────
def split_socket_endpoint(endpoint: str) -> tuple[Optional[str], Optional[int]]:
    """Mengurai endpoint ss untuk IPv4 maupun IPv6 tanpa mengandalkan grep."""
    if endpoint in ("*", "*:*", "[::]:*"):
        return None, None
    if endpoint.startswith("["):
        host, separator, port = endpoint[1:].partition("]:")
    else:
        host, separator, port = endpoint.rpartition(":")
    if not separator:
        return None, None
    try:
        ipaddress.ip_address(host)
        return host, int(port)
    except ValueError:
        return None, None


def get_ss_connections(state: Optional[str] = None) -> tuple[Optional[list[tuple[str, int, str, int]]], str]:
    """Membaca socket TCP/UDP dari ss; None menandakan command gagal."""
    args = ["ss", "-H", "-n", "-t", "-u"]
    if state:
        args.extend(["state", state])
    returncode, stdout, stderr = run_command(args, timeout=30)
    if returncode != 0:
        return None, stderr or f"exit code {returncode}"

    connections = []
    for line in stdout.splitlines():
        fields = line.split()
        if len(fields) < 6:
            continue
        local_ip, local_port = split_socket_endpoint(fields[4])
        peer_ip, peer_port = split_socket_endpoint(fields[5])
        if local_ip and peer_ip and local_port is not None and peer_port is not None:
            connections.append((local_ip, local_port, peer_ip, peer_port))
    return connections, ""


def print_connection_counts(counts: dict[str, int], warning: int, critical: int) -> None:
    if not counts:
        print(colorize("  Tidak ada koneksi yang dapat diatribusikan ke IP klien.", Color.YELLOW))
        return
    print(colorize(f"  {'Koneksi':<10} {'IP Address'}", Color.WHITE))
    print_separator("-")
    for ip, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:20]:
        color = Color.RED if count > critical else Color.YELLOW if count > warning else Color.RESET
        print(f"  {colorize(str(count), color):<20} {ip}")


def track_ddos_by_ip():
    print_header()
    print(colorize("  [DDoS] Top IP berdasarkan socket TCP/UDP aktif", Color.BOLD))
    print(colorize("  Catatan: jumlah socket bukan packet rate/bandwidth.", Color.DIM))
    print_separator()
    connections, error = get_ss_connections()
    if connections is None:
        show_scan_error("Pembacaan socket dengan ss", -1, error)
    else:
        counts: dict[str, int] = {}
        for _, _, peer_ip, _ in connections:
            counts[peer_ip] = counts.get(peer_ip, 0) + 1
        print_connection_counts(counts, warning=20, critical=100)
    print_footer()
    press_enter()


def check_httpd_connections():
    print_header()
    print(colorize("  [DDoS] Koneksi HTTP/HTTPS ESTABLISHED per IP", Color.BOLD))
    print(colorize("  Port lokal: 80 dan 443; IPv4 serta IPv6 didukung.", Color.DIM))
    print_separator()
    connections, error = get_ss_connections("established")
    if connections is None:
        show_scan_error("Pembacaan koneksi HTTP/HTTPS", -1, error)
    else:
        counts: dict[str, int] = {}
        for _, local_port, peer_ip, _ in connections:
            if local_port in (80, 443):
                counts[peer_ip] = counts.get(peer_ip, 0) + 1
        print_connection_counts(counts, warning=10, critical=50)
    print_footer()
    press_enter()


def check_syn_recv():
    print_header()
    print(colorize("  [DDoS] IP dengan status SYN_RECV (indikasi SYN Flood)", Color.BOLD))
    print_separator()
    connections, error = get_ss_connections("syn-recv")
    if connections is None:
        show_scan_error("Pembacaan koneksi SYN_RECV", -1, error)
    else:
        counts: dict[str, int] = {}
        for _, _, peer_ip, _ in connections:
            counts[peer_ip] = counts.get(peer_ip, 0) + 1
        if counts:
            print(colorize("  [!] SYN_RECV terdeteksi!\n", Color.RED))
            print_connection_counts(counts, warning=0, critical=0)
            log("check_syn_recv: SYN_RECV detected", "warning")
        else:
            print(colorize("  [+] Tidak ada koneksi SYN_RECV ditemukan.", Color.GREEN))
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

    raw_keyword_file = fetch_keyword_file(KEYWORD_BACKDOOR_URL, CACHE_BACKDOOR, KEYWORD_BACKDOOR_SHA256)
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
        try:
            prepare_backdoor_patterns(raw_keyword_file, fixed_file, regex_file)
        except (OSError, subprocess.SubprocessError) as error:
            print(colorize(f"  [-] Gagal menyiapkan pattern backdoor: {error}", Color.RED))
            log(f"prepare_backdoor_patterns gagal: {error}", "error")
            press_enter()
            return
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
    rc1, out1, err1 = run_command(["grep", "-r", "-l", "-F", "--include=*.php", "-f", fixed_file, website_dir], timeout=600)
    # Scan Regex
    rc2, out2, err2 = run_command(["grep", "-r", "-l", "-E", "--include=*.php", "-f", regex_file, website_dir], timeout=600)

    anim.stop("Scan selesai")
    print_separator()

    if rc1 not in (0, 1) or rc2 not in (0, 1):
        if rc1 not in (0, 1):
            show_scan_error("Scan fixed-string backdoor", rc1, err1)
        if rc2 not in (0, 1):
            show_scan_error("Scan regex backdoor", rc2, err2)
        print_footer("Scan gagal atau tidak lengkap")
        press_enter()
        return

    found_files = sorted(list(set((out1.splitlines() if out1 else []) + (out2.splitlines() if out2 else []))))

    if not found_files:
        print(colorize("  [+] Tidak ditemukan potensi script backdoor.", Color.GREEN))
    else:
        print(colorize(f"  [!] Ditemukan {len(found_files)} potensi backdoor:\n", Color.RED))
        for filepath in found_files:
            print(colorize("  [*] ", Color.RED) + filepath)
        log(f"perform_scan [{username}]: {len(found_files)} backdoor potensial", "warning")

        if input(colorize("\n  Simpan hasil ke file? (y/n): ", Color.CYAN)).strip().lower() == 'y':
            try:
                report_path = create_secure_report(username, found_files)
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
