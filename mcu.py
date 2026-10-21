#!/usr/bin/env python3
# Monitoring Commandline Utility
# Original by: Arief (nocturnalismee)
# Source: https://github.com/nocturnalismee/simple-monitor-utility
# Version : 2.0.3 (Hardened & Production-Ready)

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
VERSION = "2.0.3"
LOG_DIR = "/var/log/monitor-utility"
LOG_FILE = f"{LOG_DIR}/audit_{datetime.now().strftime('%Y%m%d')}.log"
KEYWORD_JUDI_URL = "https://raw.githubusercontent.com/nocturnalismee/simple-monitor-utility/main/judaylist.txt"
KEYWORD_BACKDOOR_URL = "https://raw.githubusercontent.com/nocturnalismee/simple-monitor-utility/main/bakdor-key.txt"

# Set digest berikut bila ingin mewajibkan versi signature tertentu. Nilai None
# memakai trust-on-first-use (TOFU): signature pertama dicatat dan perubahan
# berikutnya ditolak sampai administrator memperbarui pin secara sadar
# (gunakan menu "Refresh Signature" untuk mereset pin).
KEYWORD_JUDI_SHA256: Optional[str] = None
KEYWORD_BACKDOOR_SHA256: Optional[str] = None

# Cache disimpan pada direktori privat, bukan /tmp yang dapat ditulis semua user.
CACHE_DIR = Path("/var/cache/monitor-utility")
CACHE_JUDI = "keywordjudi.txt"
CACHE_BACKDOOR = "patternbackdoor.txt"
CACHE_TTL = 86400  # 24 Jam dalam detik

LARGE_FILE_THRESHOLD = "+1G"
EMAIL_THRESHOLD_BYTES = 10 * 1024 * 1024 * 1024  # 10 GiB

# Ekstensi web yang relevan untuk audit konten.
WEB_SCAN_GLOBS = ["index.*", "*.php", "*.phtml", "*.php3", "*.php4", "*.php5",
                  "*.php7", "*.php8", "*.inc", "*.html", "*.htm"]

EXCLUDE_DIRS = ["cache", "tmp", "spamcleaner", "Scroller", "checkout",
                ".cache", ".local", ".npm", ".node-gyp", "node_modules",
                "mail"]
EXCLUDE_EXTS = ["js", "map", "tpl", "ts", "log", "bak", "old", "swp",
                "zip", "tar", "gz", "bz2", "xz", "7z", "rar"]

# Timeout default untuk operasi panjang (scan backdoor, audit file).
SCAN_TIMEOUT = 1800  # 30 menit
DEFAULT_TIMEOUT = 300

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

def pad_color(text: str, width: int, color: str) -> str:
    """Rata-kiri berdasarkan panjang teks ASLI (tanpa karakter ANSI)."""
    return colorize(text, color) + " " * max(0, width - len(text))

# ─────────────────────────────────────────────
# LOGGING SETUP
# ─────────────────────────────────────────────
def setup_logging():
    """Setup logging dengan fallback berjenjang agar tidak pernah crash."""
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO, format=fmt,
            handlers=[logging.FileHandler(LOG_FILE)]
        )
        return
    except OSError:
        pass

    try:
        fallback_log = get_private_cache_dir() / f"monitor-utility_{datetime.now():%Y%m%d}.log"
        logging.basicConfig(
            level=logging.INFO, format=fmt,
            handlers=[logging.FileHandler(str(fallback_log))]
        )
        print(colorize(f"[!] Log disimpan ke fallback: {fallback_log}", Color.YELLOW))
    except OSError as error:
        logging.basicConfig(
            level=logging.INFO, format=fmt,
            handlers=[logging.NullHandler()]
        )
        print(colorize(f"[!] Logging dinonaktifkan: {error}", Color.YELLOW))

def log(message: str, level: str = "info"):
    """Wrapper logging. Gunakan huruf kecil (info, warning, error, dll)."""
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
# HELPER: CACHE & FILE SYSTEM
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
    """Menulis file dengan permission 0600 melalui replace atomik."""
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


def create_secure_report(username: str, found_files: list) -> str:
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
                f"Backdoor Scan Report\n"
                f"Username : {username}\n"
                f"Waktu    : {datetime.now()}\n"
                f"Ditemukan: {len(found_files)} file\n"
                f"{'=' * 50}\n"
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

# ─────────────────────────────────────────────
# HELPER: FETCH KEYWORD DARI GITHUB
# ─────────────────────────────────────────────
def read_cached_digest(digest_path: Path) -> Optional[str]:
    if not is_regular_file(digest_path):
        return None
    try:
        digest = digest_path.read_text(encoding="ascii").strip().lower()
        return digest if re.fullmatch(r"[0-9a-f]{64}", digest) else None
    except OSError:
        return None


def cache_matches_digest(cache_path: Path, digest: Optional[str],
                         expected_sha256: Optional[str]) -> bool:
    """Memeriksa isi cache, sidecar digest, dan optional pin konfigurasi."""
    if not digest or not is_regular_file(cache_path):
        return False
    try:
        if hashlib.sha256(cache_path.read_bytes()).hexdigest() != digest:
            return False
        return not expected_sha256 or digest == expected_sha256.lower()
    except OSError:
        return False


def fetch_keyword_file(url: str, cache_name: str,
                       expected_sha256: Optional[str] = None) -> Optional[str]:
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

    # Cache valid dan belum kadaluarsa -> langsung pakai
    if cache_valid and time.time() - cache_path.stat().st_mtime < CACHE_TTL:
        return str(cache_path)

    # Download dari GitHub
    try:
        print(colorize("  [*] Mengunduh keyword list dari GitHub...", Color.CYAN))
        request = urllib.request.Request(
            url, headers={"User-Agent": f"Monitor-Utility/{VERSION} (Linux)"}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read(10 * 1024 * 1024 + 1)

        if not payload or len(payload) > 10 * 1024 * 1024:
            raise ValueError("Ukuran keyword list tidak valid")

        received_digest = hashlib.sha256(payload).hexdigest()
        required_digest = (
            expected_sha256.lower() if expected_sha256 else cached_digest
        )

        # PENTING: digest mismatch BUKAN kondisi offline. Jangan fallback diam-diam.
        if required_digest and received_digest != required_digest:
            raise ValueError(
                "Signature di GitHub berubah, pin SHA-256 lokal masih lama. "
                "Gunakan menu 'Refresh Signature' untuk memperbarui."
            )

        atomic_write(cache_path, payload)
        atomic_write(digest_path, f"{received_digest}\n".encode("ascii"))
        print(colorize("  [+] Keyword list berhasil diunduh dan diverifikasi.", Color.GREEN))
        return str(cache_path)

    except ValueError as error:
        # Digest mismatch - signature berubah, jangan fallback diam-diam
        print(colorize(f"  [-] {error}", Color.RED))
        log(f"fetch_keyword_file: digest mismatch {url} ({error})", "error")
        return None

    except Exception as error:
        # Network error / timeout / dll - OK fallback ke cache jika valid
        print(colorize(f"  [-] Gagal mengunduh dari GitHub: {error}", Color.RED))
        if cache_valid:
            print(colorize("  [!] Jaringan gagal - memakai cache tervalidasi.", Color.YELLOW))
            return str(cache_path)
        return None


def inspect_remote_signature(url: str, cache_name: str) -> None:
    """Menampilkan SHA-256 remote tanpa mengganti cache atau pin yang ada."""
    try:
        cache_dir = get_private_cache_dir()
        cached_digest = read_cached_digest(cache_dir / f"{cache_name}.sha256")
        request = urllib.request.Request(
            url, headers={"User-Agent": f"Monitor-Utility/{VERSION} (Linux)"}
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read(10 * 1024 * 1024 + 1)
        if not payload or len(payload) > 10 * 1024 * 1024:
            raise ValueError("Ukuran keyword list tidak valid")

        remote_digest = hashlib.sha256(payload).hexdigest()
        print(colorize(f"  {cache_name}", Color.WHITE))
        print(f"    Remote SHA-256 : {remote_digest}")
        if cached_digest:
            status = "SAMA" if remote_digest == cached_digest else "BERUBAH - review sebelum memperbarui pin"
            color = Color.GREEN if remote_digest == cached_digest else Color.YELLOW
            print(colorize(f"    Cache SHA-256  : {cached_digest} [{status}]", color))
        else:
            print(colorize("    Cache SHA-256  : belum ada", Color.YELLOW))
    except Exception as error:
        print(colorize(f"  [-] Gagal memeriksa {cache_name}: {error}", Color.RED))
        log(f"inspect_remote_signature gagal untuk {url}: {error}", "error")


def refresh_signatures():
    """Memeriksa hash signature remote tanpa melemahkan cache/pin lokal."""
    print_header()
    print(colorize("  [SIGNATURE] Periksa update SHA-256 remote", Color.BOLD))
    print(colorize("  Cache dan pin lokal tidak akan diubah.\n", Color.DIM))

    if KEYWORD_JUDI_SHA256 or KEYWORD_BACKDOOR_SHA256:
        print(colorize("  [!] Ada pin hard-coded. Bila remote berubah, review hash di bawah", Color.YELLOW))
        print(colorize("      lalu perbarui KEYWORD_*_SHA256 di source dan deploy ulang.", Color.YELLOW))
        print()

    inspect_remote_signature(KEYWORD_JUDI_URL, CACHE_JUDI)
    print()
    inspect_remote_signature(KEYWORD_BACKDOOR_URL, CACHE_BACKDOOR)

    log("refresh_signatures: hash remote diperiksa tanpa mengubah cache", "info")
    print_footer("Pemeriksaan selesai")
    press_enter()

# ─────────────────────────────────────────────
# HELPER: PREPROCESS BACKDOOR PATTERNS
# ─────────────────────────────────────────────
# Escape yang dikenal GNU grep ERE. Selain ini (mis. \d, \x, \u) grep
# memperlakukannya sebagai huruf biasa -> harus dinormalisasi.
ERE_KNOWN_ESCAPES = set("\\.^$*+?()[]{}|/wWbBsS<>`'-")
ERE_METACHAR = re.compile(r'[.^$*+?()\[\]{}|\\]')
HEX_LITERAL = re.compile(r'^(\\x[0-9a-fA-F]{2})+$')


def normalize_ere(pattern: str) -> str:
    """
    Normalisasi pattern agar sesuai kemampuan GNU grep ERE:
      \\d -> [0-9]      (grep TIDAK mendukung \\d; dianggap huruf 'd' literal)
      \\D -> [^0-9]
      \\x, \\u, dll -> \\\\x  (agar cocok dengan backslash literal di source PHP)
    Penggantian hanya dilakukan DI LUAR bracket expression, dan '\\[' dianggap
    kurung literal (bukan pembuka bracket).
    """
    out: list[str] = []
    i, n, in_bracket = 0, len(pattern), False

    while i < n:
        char = pattern[i]

        if char == "\\" and i + 1 < n:
            nxt = pattern[i + 1]
            if not in_bracket and nxt == "d":
                out.append("[0-9]"); i += 2; continue
            if not in_bracket and nxt == "D":
                out.append("[^0-9]"); i += 2; continue
            if nxt not in ERE_KNOWN_ESCAPES:
                out.append("\\\\"); out.append(nxt); i += 2; continue
            out.append(char); out.append(nxt); i += 2; continue

        if char == "[" and not in_bracket:
            in_bracket = True; out.append(char); i += 1; continue
        if char == "]" and in_bracket:
            in_bracket = False
        out.append(char); i += 1

    return "".join(out)


def is_valid_ere(pattern: str, timeout: int = 5) -> bool:
    """Memastikan pola diterima grep -E. rc 0/1 = valid, rc 2 = invalid."""
    try:
        result = subprocess.run(
            ["grep", "-E", "-q", "-e", pattern, "/dev/null"],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        return result.returncode in (0, 1)
    except (subprocess.TimeoutExpired, OSError):
        return False


def prepare_backdoor_patterns(raw_file: str, fixed_file: str,
                              regex_file: str) -> tuple[int, int]:
    """
    Klasifikasi tiap pattern dengan validasi nyata ke grep (bukan heuristik).
    Urutan keputusan:
      1. komentar / baris kosong      -> dibuang
      2. hex literal murni (\\xNN..)  -> -F  (memang dimaksudkan sebagai teks)
      3. tanpa metachar sama sekali   -> -F  (cepat, tanpa spawn subprocess)
      4. normalisasi \\d, lalu uji grep -E:
           valid   -> -E
           invalid -> -F  (aman, tidak akan membuat grep crash)
    """
    fixed_strings: list[str] = []
    regex_strings: list[str] = []

    with open(raw_file, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if HEX_LITERAL.match(line) or not ERE_METACHAR.search(line):
                fixed_strings.append(line)
                continue

            normalized = normalize_ere(line)
            if is_valid_ere(normalized):
                regex_strings.append(normalized)
            else:
                fixed_strings.append(line)

    # Jaga-jaga agar file pattern tidak kosong total.
    if not fixed_strings:
        fixed_strings.append("IMPOSSIBLE_STRING_TO_MATCH_12345")
    if not regex_strings:
        regex_strings.append("^IMPOSSIBLE_REGEX_TO_MATCH_12345$")

    atomic_write(Path(fixed_file), ("\n".join(fixed_strings) + "\n").encode("utf-8"))
    atomic_write(Path(regex_file), ("\n".join(regex_strings) + "\n").encode("utf-8"))
    return len(fixed_strings), len(regex_strings)

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
def run_command(args: list, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str, str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timeout setelah {timeout} detik"
    except Exception as e:
        return -1, "", str(e)


def run_shell(command: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    try:
        result = subprocess.run(command, shell=True, capture_output=True,
                                text=True, timeout=timeout)
        return result.stdout.strip()
    except Exception as e:
        return f"[ERROR] {e}"


def run_shell_checked(command: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, str, str]:
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
        print("  " + pad_color("Ukuran", 14, Color.WHITE) + "Path")
        print_separator("-")
        lines = results.splitlines()
        for line in lines:
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                size, path = parts
                print("  " + pad_color(size, 14, Color.YELLOW) + path)
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
        print("  " + pad_color("Ukuran (GB)", 18, Color.WHITE) + "Direktori")
        print_separator("-")
        flagged = 0
        for line in results.splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) != 2:
                continue
            bytes_str, directory = parts
            try:
                total_bytes = int(bytes_str)
                gb = total_bytes / (1024 ** 3)
                if total_bytes > EMAIL_THRESHOLD_BYTES:
                    print("  " + pad_color(f"{gb:.2f}", 18, Color.RED)
                          + directory + colorize("  [!] >10GB", Color.RED))
                    flagged += 1
                    log(f"check_email_usage: {directory} = {gb:.2f}GB [FLAGGED]", "warning")
                else:
                    print("  " + pad_color(f"{gb:.2f}", 18, Color.DIM) + directory)
            except ValueError:
                continue

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
    returncode, stdout, stderr = run_command(cmd, timeout=DEFAULT_TIMEOUT)
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
            if cont.lower() != 'y':
                break

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
        if errors:
            print(colorize(f"  [-] Gagal dihapus: {errors} file", Color.RED))
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
    """Fungsi inti untuk menjalankan scan judi pada direktori target."""
    print_header()
    print(colorize(f"  [AUDIT] Script Judi - {scan_title}", Color.BOLD))
    print(colorize(f"  Target: {target_dir}", Color.DIM))
    print(colorize(f"  Source: {KEYWORD_JUDI_URL}\n", Color.DIM))

    keyword_file = fetch_keyword_file(KEYWORD_JUDI_URL, CACHE_JUDI, KEYWORD_JUDI_SHA256)

    if not keyword_file:
        print(colorize("  [-] Tidak ada keyword list yang bisa digunakan.", Color.RED))
        press_enter()
        return

    if os.path.getsize(keyword_file) == 0:
        print(colorize("  [!] File keyword kosong.", Color.YELLOW))
        press_enter()
        return

    exclude_dir_args = [a for d in EXCLUDE_DIRS for a in ("--exclude-dir", d)]
    exclude_ext_args = [a for ext in EXCLUDE_EXTS for a in ("--exclude", f"*.{ext}")]

    print(colorize(f"  Included files : {', '.join(WEB_SCAN_GLOBS)}", Color.DIM))
    print(colorize(f"  Excluded dirs  : {', '.join(EXCLUDE_DIRS)}", Color.DIM))
    print(colorize(f"  Excluded exts  : {', '.join(EXCLUDE_EXTS)}", Color.DIM))
    print()

    anim = LoadingAnimation(f"Scanning {target_dir}")
    anim.start()

    include_args = [a for g in WEB_SCAN_GLOBS for a in ("--include", g)]
    cmd = (["grep", "-i", "-l", "-r", "-F", "-f", keyword_file]
           + include_args + exclude_dir_args + exclude_ext_args + [target_dir])

    returncode, stdout, stderr = run_command(cmd, timeout=SCAN_TIMEOUT)
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
        ("Cari Konten Judi by Username cPanel",          scan_judi_by_username),
        ("Cari Konten Judi by custom Direktory",         scan_judi_custom_dir),
    ])

# ─────────────────────────────────────────────
# MENU 3: MITIGASI DDOS
# ─────────────────────────────────────────────
# Nama state persis seperti yang dicetak ss (bukan keyword filternya).
SS_STATES = {
    "ESTAB", "SYN-SENT", "SYN-RECV", "FIN-WAIT-1", "FIN-WAIT-2",
    "TIME-WAIT", "CLOSE", "CLOSE-WAIT", "LAST-ACK", "LISTEN",
    "CLOSING", "UNCONN",
}

# Abaikan loopback agar "Top IP" tidak didominasi proses internal server.
IGNORE_LOOPBACK = True


def split_socket_endpoint(endpoint: str) -> tuple[Optional[str], Optional[int]]:
    """Mengurai endpoint ss untuk IPv4 maupun IPv6."""
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


def is_noise_ip(ip: str) -> bool:
    if not IGNORE_LOOPBACK:
        return False
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def get_ss_connections(state: Optional[str] = None
                       ) -> tuple[Optional[list[tuple[str, int, str, int]]], str]:
    """
    Baca socket TCP/UDP via `ss`. None menandakan command gagal.

    PENTING: `ss ... state <X>` MENGHILANGKAN kolom State sehingga jumlah kolom
    berubah dari 6 menjadi 5 dan indeks posisi bergeser. Karena itu ss dipanggil
    TANPA filter, lalu state disaring di Python. Parser di bawah juga tidak
    bergantung pada posisi kolom (tahan terhadap -p / perubahan layout iproute2).
    """
    returncode, stdout, stderr = run_command(["ss", "-H", "-n", "-t", "-u"], timeout=30)
    if returncode != 0:
        return None, stderr or f"exit code {returncode}"

    # `ss` menampilkan ESTAB, sedangkan pemanggil lebih mudah memakai
    # istilah ESTABLISHED. State lain memakai nama yang sama seperti output ss.
    wanted = {"ESTABLISHED": "ESTAB"}.get(state.upper(), state.upper()) if state else None
    connections: list[tuple[str, int, str, int]] = []

    for line in stdout.splitlines():
        fields = line.split()
        if not fields:
            continue

        row_state: Optional[str] = None
        endpoints: list[tuple[str, int]] = []

        for token in fields:
            host, port = split_socket_endpoint(token)
            if host is not None and port is not None:
                endpoints.append((host, port))
            elif row_state is None and token.upper() in SS_STATES:
                row_state = token.upper()

        if len(endpoints) < 2:
            continue

        (local_ip, local_port), (peer_ip, peer_port) = endpoints[-2], endpoints[-1]

        if wanted and row_state != wanted:
            continue
        if is_noise_ip(peer_ip):
            continue

        connections.append((local_ip, local_port, peer_ip, peer_port))

    return connections, ""


def print_connection_counts(counts: dict[str, int], warning: int, critical: int) -> None:
    if not counts:
        print(colorize("  Tidak ada koneksi yang dapat diatribusikan ke IP klien.", Color.YELLOW))
        return
    print("  " + pad_color("Koneksi", 12, Color.WHITE) + "IP Address")
    print_separator("-")
    for ip, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:20]:
        color = Color.RED if count > critical else Color.YELLOW if count > warning else Color.RESET
        print("  " + pad_color(str(count), 12, color) + ip)


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
        ("Track DDoS by IP",        track_ddos_by_ip),
        ("Check HTTPD Connections", check_httpd_connections),
        ("Check SYN_RECV Status",   check_syn_recv),
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

    # Cek cache pre-processor
    needs_processing = (
        not os.path.exists(fixed_file)
        or not os.path.exists(regex_file)
        or os.path.getmtime(fixed_file) < os.path.getmtime(raw_keyword_file)
    )

    if needs_processing:
        print(colorize("  [*] Menganalisa dan memisahkan pattern backdoor...", Color.CYAN))
        try:
            n_fixed, n_regex = prepare_backdoor_patterns(raw_keyword_file, fixed_file, regex_file)
        except (OSError, subprocess.SubprocessError) as error:
            print(colorize(f"  [-] Gagal menyiapkan pattern backdoor: {error}", Color.RED))
            log(f"prepare_backdoor_patterns gagal: {error}", "error")
            press_enter()
            return
        print(colorize(f"  [+] {n_fixed} literal + {n_regex} regex siap dipakai.", Color.GREEN))
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

    include_args     = [a for g in WEB_SCAN_GLOBS for a in ("--include", g)]
    exclude_dir_args = [a for d in EXCLUDE_DIRS   for a in ("--exclude-dir", d)]
    grep_base = ["grep", "-r", "-l"] + include_args + exclude_dir_args

    # Scan Fixed Strings
    rc1, out1, err1 = run_command(
        grep_base + ["-F", "-f", fixed_file, website_dir], timeout=SCAN_TIMEOUT
    )
    # Scan Regex
    rc2, out2, err2 = run_command(
        grep_base + ["-E", "-f", regex_file, website_dir], timeout=SCAN_TIMEOUT
    )

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

    found_files = sorted(list(set(
        (out1.splitlines() if out1 else []) + (out2.splitlines() if out2 else [])
    )))

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
    """Render submenu generik."""
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
                continue  # skip pesan error
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
        hostname = run_shell('hostname').strip()
        uptime = run_shell('uptime -p 2>/dev/null || uptime').strip()
        load = run_shell("cat /proc/loadavg | awk '{print $1,$2,$3}'").strip()
        disk_cmd = "df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\" used)\"}'"
        disk = run_shell(disk_cmd).strip()

        print(colorize(f"  Host   : {hostname}", Color.DIM))
        print(colorize(f"  Uptime : {uptime}", Color.DIM))
        print(colorize(f"  Load   : {load}", Color.DIM))
        print(colorize(f"  Disk / : {disk}", Color.DIM))
        print()
    except Exception:
        pass


def main_menu():
    setup_logging()
    log(f"Session dimulai - PID {os.getpid()}")

    menu_items = [
        ("Audit Disk",               show_disk_audit_menu),
        ("Audit Judol",              show_judol_audit_menu),
        ("Mitigasi DDoS",            show_ddos_menu),
        ("Mitigasi Backdoor (beta)", perform_scan),
        ("Check Signature Update",   refresh_signatures),
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
                continue  # skip pesan error
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
    try:
        main_menu()
    except KeyboardInterrupt:
        print(colorize("\n\n  [!] Dibatalkan oleh user (Ctrl+C).", Color.YELLOW))
        log("Session diinterupsi oleh KeyboardInterrupt", "warning")
        sys.exit(130)
