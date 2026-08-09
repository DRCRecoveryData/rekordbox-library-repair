# 💽 Rekordbox Library Repair

### Before
<p align="center">
  <img width="1920" height="1033" alt="Screenshot 2026-08-09 212439" src="https://github.com/user-attachments/assets/31ff98d8-3345-4b9b-9fed-774a2a0dfa77" />
</p>

### After
<p align="center">
  <img width="1920" height="1033" alt="Screenshot 2026-08-09 212400" src="https://github.com/user-attachments/assets/724e5d78-d60b-421d-b3e2-78956420e65c" />
</p>

### Preview
<p align="center">
  <img width="1920" height="1033" alt="image" src="https://github.com/user-attachments/assets/72026c23-4344-4b6b-8f38-f6f02d1c7008" />
</p>


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
