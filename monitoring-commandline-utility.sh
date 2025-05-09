#!/bin/bash
# Create & build by Arief (nocturnalismee)
# source code https://github.com/nocturnalismee/simple-monitor-utility

# Enable safer script execution
set -o errexit  # Exit immediately if a command exits with a non-zero status.
set -o pipefail # Return value of a pipeline is the status of the last command to exit with non-zero status
set -o nounset  # Treat unset variables as an error

# Trap to handle cleanup on exit
trap 'echo "Exiting..."; exit 1' SIGINT SIGTERM

# ////////////////////////////////////////// THEME FUNCTION //////////////////////////////////////////
# Additional color codes for theme
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BOLD='\033[1m'
UNDERLINE='\033[4m'
HEADER_BG='\033[44m'
FOOTER_BG='\033[45m'

#Header
print_header() {
  clear
  local terminal_width=$(tput cols)
  local header_text="Monitoring Commandline Utility"
  local date_text="Date: $(date)"
  local header_padding=$(( (terminal_width - ${#header_text}) / 2 ))
  local date_padding=$(( (terminal_width - ${#date_text}) / 2 ))
  echo -e "\033[1;32m\033[1m$(printf "%${header_padding}s%s" "" "$header_text")\033[0m"
  echo -e "\033[1;37m\033[1m$(printf "%${date_padding}s%s" "" "$date_text")\033[0m"
  printf "%${terminal_width}s\n" "" | tr ' ' '-'
  echo
}

# Footer
print_footer() {
  local terminal_width=$(tput cols)
  local footer_text="Complete"
  local footer_padding=$(( (terminal_width - ${#footer_text}) / 2 ))
  echo
  echo -e "\033[1;32m\033[1m$(printf "%${footer_padding}s%s" "" "$footer_text")\033[0m"
  printf "%${terminal_width}s\n" "" | tr ' ' '-'
}

 # Function to display text centered in a box
 print_centered_in_box() {
  local text="$1"
  local terminal_width=$(tput cols)
  local text_length=${#text}
  local padding=$(( (terminal_width - text_length - 4) / 2 ))
  local border="+$(printf -- '-%.0s' $(seq 1 $((terminal_width - 2))))+"
  local padding_spaces=$(printf ' %.0s' $(seq 1 $padding))
  echo -e "$border"
  echo -e "|${padding_spaces}${text}${padding_spaces}|"
  echo -e "$border"
 }

# ////////////////////////////////////////// END THEME FUNCTION //////////////////////////////////////////

# ////////////////////////////////////////// CMD COMBINATION FUNCTION ///////////////////////////////////////////////
# Disk Audit Functions
# Function to find files larger than 1GB, sorted by user then size (desc)
find_large_files() {
    print_header
    echo -e "${YELLOW}Mencari file backup atau lainnya dengan ukuran > 1GB at /home/*...${NC}"
    echo -e "${YELLOW}Mohon menunggu...${NC}"
    echo "-----------------------------------------"
    local results
    # Use find, du, sort. nice/ionice added for lower priority execution.
    results=$(nice ionice -c 3 find /home/* -path '/home/*/mail' -prune -o -type f -size +1G -exec du -sh {} + 2>/dev/null | nice ionice -c 3 sort -k2,2 -k1,1hr)
    clear
    if [ -z "$results" ]; then
        echo "No files found larger than 1GB."
    else
        echo -e "${RED}Size       | Direktori File${NC}"
        echo "-----------------------------------------"
        echo "$results" | while read -r line; do
            size=$(echo "$line" | awk '{print $1}')
            path=$(echo "$line" | awk '{$1=""; print $0}' | sed 's/^ *//')
            printf "%-10s | %s\n" "$size" "$path"
        done
    fi
    echo "-----------------------------------------"
    print_footer
    read -p "Press Enter to return to the menu..."
}

# Function to list email directories (/home/*/mail), sorted by user then size (desc)
check_email_usage() {
    print_header
    echo -e "${YELLOW}Listing disk usage for each email directory (/home/*/mail)...${NC}"
    echo -e "${YELLOW}Mohon menunggu...${NC}"
    echo "-------------------------------------------------------------"
    printf "%-15s | %s\n" "Size (GB)" "Directory"
    echo "----------------|--------------------------------------------"

    local threshold=10737418240 # 10 GiB

    # Use find, du, sort, awk. nice/ionice added.
    nice ionice -c 3 find /home/* -maxdepth 1 -type d -name 'mail' -exec du -sb {} + 2>/dev/null | \
    nice ionice -c 3 sort -k2,2 -k1,1nr | \
    awk -v threshold="$threshold" '
    BEGIN { found=0 }
    {
        bytes = $1;
        dir = ""; for(i=2; i<=NF; i++) { dir = dir $i (i==NF ? "" : " ") };
        gb = sprintf("%.2f", bytes / (1024*1024*1024));
        if (bytes > threshold) {
            printf "\033[0;31m%-15s | %s [>10G]\033[0m\n", gb, dir; # Red color
        } else {
            printf "%-15s | %s\n", gb, dir;
        }
        found=1;
    }
    END { exit !found }' # Exit with 0 if found, 1 otherwise

    if [ $? -ne 0 ]; then
        echo "No /home/*/mail directories found."
    fi

    echo "-------------------------------------------------------------"
   # echo -e "${GREEN}Email usage check complete.${NC}"
    print_footer
    read -p "Press Enter to return to the menu..."
}

# Function to find and optionally delete files of size 0 Kb
find_zero_size_files() {
    print_header
    echo -e "${YELLOW}Mencari file dengan ukuran 0 Kb di /home/*...${NC}"
    echo -e "${YELLOW}Mohon menunggu...${NC}"
    echo "-----------------------------------------"
    local results
    # Use find to locate files of size 0 Kb
    results=$(find /home/* -type f -size 0 2>/dev/null)
    if [ -z "$results" ]; then
        echo "Tidak ada file dengan ukuran 0 Kb ditemukan."
    else
        echo -e "${RED}File dengan ukuran 0 Kb ditemukan:${NC}"
        echo "Ukuran | File"
        echo "-------------------------"
        echo "$results" | while read -r file; do
            size=$(du -sh "$file" | awk '{print $1}')
            printf "%-7s | %s\n" "$size" "$file"
        done
        echo "-------------------------"
        read -p "Apakah Anda ingin menghapus file-file ini? (y/n): " choice
        if [[ "$choice" == "y" || "$choice" == "Y" ]]; then
            echo "$results" | xargs rm -f
            echo -e "${GREEN}File-file telah dihapus.${NC}"
        else
            echo -e "${YELLOW}Penghapusan dibatalkan.${NC}"
        fi
    fi
    echo "-----------------------------------------"
    # echo -e "${GREEN}Pencarian selesai.${NC}"
    print_footer
    read -p "Tekan Enter untuk kembali ke menu..."
}

# DDoS Mitigation Functions
# Function to track DDoS attacks by number of connections per IP
track_ddos_by_ip() {
    print_header
    echo -e "${YELLOW}Melacak serangan DDoS berdasarkan jumlah koneksi per IP...${NC}"
    echo "-----------------------------------------"
    netstat -ntu | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head
    echo "-----------------------------------------"
    print_footer
    read -p "Tekan Enter untuk kembali ke menu..."
}

# Function to check number of httpd connections per IP
check_httpd_connections() {
    print_header
    echo -e "${YELLOW}Memeriksa jumlah koneksi httpd per IP...${NC}"
    echo "-----------------------------------------"
    netstat -anp | grep ':80' | grep ESTABLISHED | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head
    echo "-----------------------------------------"
    print_footer
    read -p "Tekan Enter untuk kembali ke menu..."
}

# Function to check httpd processes with SYN_RECV status
check_syn_recv() {
    print_header
    echo -e "${YELLOW}Memeriksa proses httpd dengan status SYN_RECV...${NC}"
    echo "-----------------------------------------"
    netstat -n | grep 'SYN_RECV' | awk '{print $5}' | cut -d: -f1 | sort | uniq -c | sort -nr | head
    echo "-----------------------------------------"
    print_footer
    read -p "Tekan Enter untuk kembali ke menu..."
}

# Judol Audit Functions
# Function to search for judi scripts using local keyword file
find_judi_scripts() {
    print_header
    local keyword_file="/etc/judaylist.txt" # Path direktori keyword judi

    echo -e "${YELLOW}Searching for potential gambling scripts based on keywords in $keyword_file...${NC}"

    # Check if keyword file exists and is readable
    if [ ! -r "$keyword_file" ]; then
        echo -e "${RED}Error: Keyword file '$keyword_file' not found or not readable.${NC}"
        echo -e "${RED}Please ensure the file exists and has the correct permissions.${NC}"
        sleep 3
        return 1 # Return non-zero status
    fi

    # Check if keyword file is empty
    if [ ! -s "$keyword_file" ]; then
        echo -e "${RED}Warning: Keyword file '$keyword_file' is empty.${NC}"
        echo -e "${RED}No keywords to search for. Aborting search.${NC}"
        sleep 2
        return 1 # Return non-zero status
    fi

    # echo -e "${YELLOW}Included files: index.*${NC}"
    # echo -e "${YELLOW}Excluded Dirs: cache, tmp, spamcleaner, Scroller, checkout, .cache, .local, .npm, .node-gyp, node_modules${NC}"
    # echo -e "${YELLOW}Excluded Exts: js, map, tpl, ts, log, bak, old, swp, zip, tar, gz, bz2, xz, 7z, rar${NC}"
    # echo "-----------------------------------------"

    local results
    # Run grep using the local keyword file. nice/ionice added.
    results=$(nice ionice -c 3 grep -ilr \
        --include='index.*' \
        -f "$keyword_file" \
        --exclude-dir={cache,tmp,spamcleaner,Scroller,checkout,.cache,.local,.npm,.node-gyp,node_modules} \
        --exclude='*.{js,map,tpl,ts,log,bak,old,swp,zip,tar,gz,bz2,xz,7z,rar}' \
        /home/*/ 2>/dev/null)

    if [ -z "$results" ]; then
        echo "No potential judi script files found matching the criteria."
    else
        echo -e "${RED}Potential judi script files found:${NC}"
        # Sort the grep results alphabetically by path
        echo "$results" | sort
    fi

    echo "-----------------------------------------"

    # echo -e "${GREEN}Search complete.${NC}"
    print_footer
    read -p "Press Enter to return to the menu..."
}

# BACKDOOR SCAN FUNCTION
# Fungsi untuk melakukan scanning backdoor menggunakan file keyword
perform_scan() {
    print_header
    local keyword_file="/etc/bakdor-key.txt" # Path ke file keyword
    local username
    local website_dir
    found_any=false

    echo "Masukan username cpanel untuk scan file backdoor, tekan enter dan silahkan di tunggu beberapa saat."
    read -p "Username: " username
    if [[ -z "$username" ]]; then
        echo "Username tidak boleh kosong."
        return 1
    fi

    website_dir="/home/$username/"
    if [[ ! -d "$website_dir" ]]; then
        echo "Direktori $website_dir tidak ditemukan."
        return 1
    fi

    # Periksa apakah file keyword ada dan dapat dibaca
    if [[ ! -r "$keyword_file" ]]; then
        echo "File keyword '$keyword_file' tidak ditemukan atau tidak dapat dibaca."
        return 1
    fi

    # Gunakan grep dengan file keyword
    find "$website_dir" -type f | while read -r local_file; do
        if grep -qFf "$keyword_file" "$local_file"; then
            if [ "$found_any" = false ]; then
                echo "Potensi script backdoor ditemukan pada path direktori dibawah:"
                found_any=true
            fi
            echo " > $local_file"
        fi
    done

    if [ "$found_any" = false ]; then
        echo "Tidak ditemukan potensi script backdoor yang lainnya saat ini."
    fi
    print_footer
    read -p "Tekan Enter untuk kembali ke menu..."
}

# Function to validate user input
validate_input() {
    if ! [[ "$1" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Invalid input. Please enter a number.${NC}"
        return 1
    fi
    return 0
}

# ////////////////////////////////////////// END CMD FUNCTION ///////////////////////////////////////////////

# /////////////////////////////////////////// MENU FUNCTION ////////////////////////////////////////////////
# Function to display the Disk Audit menu
show_disk_audit_menu() {
    while true; do
        print_header
        echo -e "${YELLOW}${BOLD}Opsi Audit Disk Usage:${NC}"
        echo
        options=(
            "Audit File Backup/Arsip > 1GB"
            "Audit Disk Usage Mail"
            "Audit & Delete File 0 Kb"
            "Kembali ke Menu Utama"
        )
        select opt in "${options[@]}"
        do
            validate_input "$REPLY" || { sleep 1; continue; }
            case $REPLY in
                1)
                    find_large_files
                    ;;
                2)
                    check_email_usage
                    ;;
                3)
                    find_zero_size_files
                    ;;
                4)
                    return
                    ;;
                *)
                    echo -e "${RED}Invalid option $REPLY. Please try again.${NC}"
                    sleep 1
                    continue
                    ;;
            esac
        done
    done
}

# Function to display the DDoS mitigation menu
show_ddos_menu() {
    while true; do
        print_header
        echo -e "${YELLOW}${BOLD}Opsi Mitigasi DDOS:${NC}"
        echo
        options=(
            "Track DDoS by IP"
            "Check httpd Connections"
            "Check SYN_RECV Status"
            "Kembali ke Menu Utama"
        )
        select opt in "${options[@]}"
        do
            validate_input "$REPLY" || { sleep 1; continue; }
            case $REPLY in
                1)
                    track_ddos_by_ip
                    ;;
                2)
                    check_httpd_connections
                    ;;
                3)
                    check_syn_recv
                    ;;
                4)
                    return
                    ;;
                *)
                    echo -e "${RED}Invalid option $REPLY. Please try again.${NC}"
                    sleep 1
                    continue
                    ;;
            esac
        done
    done
}

# Function to display the Judol Audit menu
show_judol_audit_menu() {
    while true; do
        print_header
        echo -e "${YELLOW}${BOLD}Opsi Audit Judol:${NC}"
        echo
        options=(
            "Cari Script Judi"
            "Kembali ke Menu Utama"
        )
        select opt in "${options[@]}"
        do
            validate_input "$REPLY" || { sleep 1; continue; }
            case $REPLY in
                1)
                    find_judi_scripts
                    ;;
                2)
                    return
                    ;;
                *)
                    echo -e "${RED}Invalid option $REPLY. Please try again.${NC}"
                    sleep 1
                    continue
                    ;;
            esac
        done
    done
}

# Menu Utama Bash
while true; do
    print_header
    echo "Please choose an option:"
    echo
    echo -e "${GREEN}${BOLD}1) Audit Disk${NC}"
    echo -e "${GREEN}${BOLD}2) Audit Judol${NC}"
    echo -e "${GREEN}${BOLD}3) Mitigasi DDoS${NC}"
    echo -e "${GREEN}${BOLD}4) Mitigasi Backdoor (beta)${NC}"
    echo -e "${GREEN}${BOLD}5) EXIT${NC}"
    echo

    read -p "#? " REPLY
    validate_input "$REPLY" || { sleep 1; continue; }
    case $REPLY in
        1)
            show_disk_audit_menu
            ;;
        2)
            show_judol_audit_menu
            ;;
        3)
            show_ddos_menu
            ;;
        4)
            perform_scan
            ;;
        5)
            echo "Exiting."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option $REPLY. Please try again.${NC}"
            sleep 1
            continue
            ;;
    esac
# /////////////////////////////////////////// END MENU FUNCTION ////////////////////////////////////////////////
    # Use mktemp for temporary files if needed
    temp_file=$(mktemp)
done
