# 💻 Monitoring Commandline Utility 💻

This Bash script is a simple tool for monitoring and managing servers with various features such as disk audit, gambling script audit, DDoS mitigation, and backdoor mitigation.

## ✨ Main Features

- **🗄️ Disk Audit**:
  - Check backup/archive files larger than 1GB.
  - Audit disk usage for mail directories.
  - Delete files sized 0 Kb in the user's home directory.
- **🔍 Gambling Script Audit**:
  - Search for gambling scripts in the website directory `/home/*/`.
  - Create and save your keywords in `/etc/judaylist.txt`.
- **🛡️ DDoS Mitigation**:
  - Track DDoS attacks based on the number of connections per IP.
  - Check httpd connections per IP.
  - Check SYN_RECV status.
- **🛡️ Backdoor File Mitigation (Beta)**:
  - Scan files in the website directory `/home/*/` for potential backdoor scripts.
  - Create & save keywords or patterns locally in `/etc/bakdor-key.txt`.

## 🚀 Usage

1. Run the script with the command:
   ```bash
   ./monitoring-commandline-utility.sh
   ```
2. Select the desired option from the available menu.

## 📋 Requirements

- **Bash**: Ensure Bash is installed on your system.
- **Root Access**: Required for some features.

## ⚙️ Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/nocturnalismee/simple-monitor-utility.git
   ```
2. Ensure the script has execution permissions:
   ```bash
   chmod +x monitoring-commandline-utility.sh
   or
   chmod 777 monitoring-commandline-utility.sh
   ```
## Notes

- ❗Please note that this Bash script is still in beta and will continue to be developed and expanded with additional tools. 😊
- ❗Tested only on CloudLinux servers with WHM/cPanel panel.

## 🤝 Contributions

We welcome contributions from the community. Please create a pull request for improvements or new features. 🤗

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for more details.
