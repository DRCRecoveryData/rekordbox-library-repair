# 💽 Rekordbox Library Repair

<img width="400" height="230" alt="Screenshot 2026-08-08 004122" src="https://github.com/user-attachments/assets/e39690b0-d5f3-4c52-8694-b052995b565c" />
<img width="392" height="182" alt="Screenshot 2026-08-08 204847" src="https://github.com/user-attachments/assets/3d32af1b-707f-4fbb-8557-f713f0101504" />


A minimalist, professional desktop utility to automatically diagnose and repair corrupted Rekordbox `export.pdb` USB databases.

## ✨ Features
* **AlphaTheta DJ Hardware Aesthetic**: Sleek dark-mode interface built with PyQt6, featuring hardware-styled controls, an eject button, and green LED indicator elements.
* **Automatic Safety Backup**: Instantly creates an `export.pdb.bak` backup file right beside your database before running any corrections.
* **Comprehensive Automated Repairs**: Fixes common database corruption vectors including torn growth pages, sentinel page flags, and index sequencing mismatches.
* **Real Volume Detection**: Automatically reads Windows drive names and local paths to locate your Rekordbox export files instantly.

## 🛠️ Requirements & Installation
Make sure you have Python 3 and PyQt6 installed on your system:

```bash
pip install PyQt6

```

Run the application:

```bash
python usb_repair.py

```

## 🚀 How to Use

1. Launch the utility.
2. Select your target Rekordbox USB drive or backup folder from the dropdown menu (or click the folder icon to browse manually).
3. Click the **Play** button to automatically back up, scan, and repair your library library structure.
