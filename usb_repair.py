import ctypes
import os
import shutil
import string
import struct
import sys
from PyQt6.QtCore import QPointF, Qt, QThread, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# --- AlphaTheta CDJ-1500X Pro DJ Hardware Theme ---
CDJ1500X_THEME = """
QMainWindow {
    background-color: #0E1013;
}
QWidget {
    color: #E2E8F0;
    font-family: "Segoe UI", Roboto, Helvetica, sans-serif;
    font-size: 12px;
}
QPushButton {
    background-color: #1A1D24;
    color: #F8FAFC;
    border: 1px solid #2A2F3D;
    border-radius: 4px;
    padding: 6px 10px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #242936;
    border-color: #00CC44;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #0F1218;
}
QPushButton:disabled {
    background-color: #15181F;
    color: #4A5568;
    border-color: #1E222B;
}
QPushButton#PrimaryButton {
    background-color: #00CC44;
    border: none;
    font-size: 13px;
    font-weight: bold;
    color: #FFFFFF;
}
QPushButton#PrimaryButton:hover {
    background-color: #00B33B;
}
QPushButton#PrimaryButton:pressed {
    background-color: #009933;
}
QPushButton#PrimaryButton:disabled {
    background-color: #1A1D24;
    color: #4A5568;
    border: 1px solid #2A2F3D;
}
QComboBox {
    background-color: #15181F;
    border: 1px solid #2A2F3D;
    border-radius: 4px;
    padding: 6px 10px;
    color: #FFFFFF;
}
QComboBox::drop-down {
    border: 0px;
}
QComboBox QAbstractItemView {
    background-color: #15181F;
    color: #FFFFFF;
    selection-background-color: #00CC44;
    border: 1px solid #2A2F3D;
}
QProgressBar {
    border: 1px solid #2A2F3D;
    border-radius: 4px;
    background-color: #15181F;
    text-align: center;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 11px;
}
QProgressBar::chunk {
    background-color: #00CC44;
    border-radius: 3px;
}
"""


def create_play_icon() -> QIcon:
  pixmap = QPixmap(32, 32)
  pixmap.fill(Qt.GlobalColor.transparent)
  painter = QPainter(pixmap)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)

  painter.setBrush(QBrush(QColor("#FFFFFF")))
  painter.setPen(Qt.PenStyle.NoPen)
  triangle = QPolygonF(
      [QPointF(11.0, 9.0), QPointF(11.0, 23.0), QPointF(23.0, 16.0)]
  )
  painter.drawPolygon(triangle)
  painter.end()
  return QIcon(pixmap)


def create_eject_icon() -> QIcon:
  pixmap = QPixmap(32, 32)
  pixmap.fill(Qt.GlobalColor.transparent)
  painter = QPainter(pixmap)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)

  painter.setPen(QPen(QColor("#0088FF"), 2))
  arrow = QPolygonF(
      [QPointF(16.0, 6.0), QPointF(9.0, 15.0), QPointF(23.0, 15.0)]
  )
  painter.setBrush(QBrush(QColor("#0088FF")))
  painter.drawPolygon(arrow)

  painter.setBrush(Qt.BrushStyle.NoBrush)
  painter.drawRect(8, 20, 16, 4)
  painter.end()
  return QIcon(pixmap)


def create_app_icon() -> QIcon:
  pixmap = QPixmap(64, 64)
  pixmap.fill(Qt.GlobalColor.transparent)
  painter = QPainter(pixmap)
  painter.setRenderHint(QPainter.RenderHint.Antialiasing)

  painter.setBrush(QBrush(QColor("#0E1013")))
  painter.setPen(QColor("#0088FF"))
  painter.drawRoundedRect(4, 4, 56, 56, 10, 10)

  painter.setBrush(QBrush(QColor("#1A1D24")))
  painter.setPen(Qt.PenStyle.NoPen)
  painter.drawRect(8, 8, 48, 26)

  painter.setBrush(QBrush(QColor("#FF6600")))
  painter.drawRoundedRect(12, 14, 24, 4, 2, 2)
  painter.setBrush(QBrush(QColor("#00CC44")))
  painter.drawRoundedRect(12, 22, 18, 4, 2, 2)

  painter.end()
  return QIcon(pixmap)


def get_windows_drive_label(drive_letter: str) -> str:
  if os.name != "nt":
    return ""
  try:
    kernel32 = ctypes.windll.kernel32
    volume_name_buf = ctypes.create_unicode_buffer(261)
    if kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(drive_letter),
        volume_name_buf,
        ctypes.sizeof(volume_name_buf),
        None,
        None,
        None,
        None,
        0,
    ):
      return volume_name_buf.value
  except Exception:
    pass
  return ""


class RepairWorker(QThread):
  progress = pyqtSignal(int, str)
  finished = pyqtSignal(str)
  error = pyqtSignal(str)

  def __init__(self, usb_root: str):
    super().__init__()
    self.usb_root = usb_root

  def run(self):
    try:
      self.progress.emit(10, "Initializing CDJ Link & mounting export.pdb...")
      usb_path = os.path.normpath(self.usb_root)
      pdb_path = os.path.join(usb_path, "PIONEER", "rekordbox", "export.pdb")

      if not os.path.exists(pdb_path):
        self.error.emit(f"export.pdb not found in {usb_path}")
        return

      backup_path = pdb_path + ".bak"
      self.progress.emit(25, "Backing up database to export.pdb.bak...")
      shutil.copy2(pdb_path, backup_path)

      self.progress.emit(40, "Reading media database stream...")
      with open(pdb_path, "rb") as f:
        data_bytes = bytearray(f.read())

      if len(data_bytes) < 32:
        self.error.emit("PDB file is too small.")
        return

      page_size = struct.unpack_from("<I", data_bytes, 4)[0]
      if page_size == 0:
        self.error.emit("PDB zero page size.")
        return

      total_pages = len(data_bytes) // page_size
      num_tables = struct.unpack_from("<I", data_bytes, 8)[0]
      next_unused = struct.unpack_from("<I", data_bytes, 0x0C)[0]

      self.progress.emit(60, "Analyzing player tables & structure...")
      live_data_pages = set()
      for p in range(1, total_pages):
        off = p * page_size
        if off + 40 > len(data_bytes):
          break
        stored_idx = struct.unpack_from("<I", data_bytes, off + 4)[0]
        if stored_idx == 0 or data_bytes[off + 0x1B] == 0x64:
          continue
        if struct.unpack_from("<H", data_bytes, off + 0x1E)[0] == 0:
          continue
        live_data_pages.add(stored_idx)

      # 1. Torn Growth Pages & Truncated Table Chains[cite: 1]
      garbage_ec_pages = []
      for i in range(num_tables):
        toff = 0x1C + i * 16
        if toff + 16 > len(data_bytes):
          break
        ec = struct.unpack_from("<I", data_bytes, toff + 4)[0]
        if ec == 0 or ec in live_data_pages:
          continue
        off = ec * page_size
        if off + page_size <= len(data_bytes) and any(
            b != 0 for b in data_bytes[off : off + page_size]
        ):
          garbage_ec_pages.append(ec)

      truncate_to = None
      if (
          total_pages > next_unused
          and next_unused > 0
          and (next_unused * page_size < len(data_bytes))
      ):
        if any(b != 0 for b in data_bytes[next_unused * page_size :]):
          truncate_to = next_unused

      # Truncated Table Chains Detection[cite: 1]
      truncated_chains = []
      for i in range(num_tables):
        toff = 0x1C + i * 16
        if toff + 16 > len(data_bytes):
          break
        tt = struct.unpack_from("<I", data_bytes, toff)[0]
        first = struct.unpack_from("<I", data_bytes, toff + 8)[0]
        last = struct.unpack_from("<I", data_bytes, toff + 12)[0]
        if first == 0 or last < total_pages:
          continue

        seen = set()
        real_last = None
        cur = first
        for _ in range(total_pages + 1):
          if cur >= total_pages or cur in seen:
            break
          seen.add(cur)
          real_last = cur
          if cur == last:
            break
          off = cur * page_size
          if off + 0x10 > len(data_bytes):
            break
          nxt = struct.unpack_from("<I", data_bytes, off + 0x0C)[0]
          if nxt == 0:
            break
          cur = nxt

        if real_last is None or real_last == last:
          continue

        off = real_last * page_size
        if off + page_size > len(data_bytes):
          continue
        used_s = struct.unpack_from("<H", data_bytes, off + 0x1E)[0]
        if used_s == 0:
          continue

        real_next = struct.unpack_from("<I", data_bytes, off + 0x0C)[0]
        corrected_ec = real_next if real_next > real_last else total_pages
        truncated_chains.append((tt, real_last, corrected_ec))

      # 2. Sentinel u5 & Flags & B-Trees[cite: 1]
      sentinel_u5_pages, wrong_flags_pages, stale_btree_pages = [], [], []
      for p in range(1, total_pages):
        off = p * page_size
        if off + 0x24 > len(data_bytes):
          break
        stored_idx = struct.unpack_from("<I", data_bytes, off + 4)[0]
        if stored_idx == 0:
          continue
        flags = data_bytes[off + 0x1B]
        used_s = struct.unpack_from("<H", data_bytes, off + 0x1E)[0]

        if used_s > 0:
          if struct.unpack_from("<H", data_bytes, off + 0x20)[0] == 0x1FFF:
            sentinel_u5_pages.append(p)
          table_type = struct.unpack_from("<I", data_bytes, off + 8)[0]
          expected_valid = (
              (flags in (0x24, 0x34))
              if table_type in (0, 7, 19)
              else (flags == 0x24)
          )
          if not expected_valid:
            wrong_flags_pages.append((p, table_type))

        if flags == 0x64:
          if (
              struct.unpack_from("<H", data_bytes, off + 0x38)[0] == 0
              and struct.unpack_from("<H", data_bytes, off + 0x26)[0] != 0
          ):
            stale_btree_pages.append(p)

      self.progress.emit(75, "Applying hardware-level corrective repairs...")

      for ec in garbage_ec_pages:
        off = ec * page_size
        if off + page_size <= len(data_bytes):
          data_bytes[off : off + page_size] = b"\x00" * page_size

      if truncate_to is not None:
        new_len = truncate_to * page_size
        if new_len < len(data_bytes):
          del data_bytes[new_len:]

      # Apply Truncated Table Chain Fixes[cite: 1]
      for tt, corrected_last, corrected_ec in truncated_chains:
        for i in range(num_tables):
          toff = 0x1C + i * 16
          if toff + 16 > len(data_bytes):
            break
          if struct.unpack_from("<I", data_bytes, toff)[0] == tt:
            struct.pack_into("<I", data_bytes, toff + 4, corrected_ec)
            struct.pack_into("<I", data_bytes, toff + 12, corrected_last)
            break

      for p in sentinel_u5_pages:
        off = p * page_size
        if off + 0x24 <= len(data_bytes):
          nrs = data_bytes[off + 0x18]
          struct.pack_into("<H", data_bytes, off + 0x20, max(1, nrs))
          struct.pack_into("<H", data_bytes, off + 0x22, 0)

      for p, tt in wrong_flags_pages:
        off = p * page_size
        if off + 0x20 <= len(data_bytes):
          data_bytes[off + 0x1B] = 0x34 if tt in (0, 7, 19) else 0x24

      for p in stale_btree_pages:
        off = p * page_size
        if off + page_size <= len(data_bytes):
          struct.pack_into("<H", data_bytes, off + 0x38, 0)
          struct.pack_into("<H", data_bytes, off + 0x3A, 0x1FFF)
          struct.pack_into("<H", data_bytes, off + 0x26, 0)

      self.progress.emit(90, "Recomputing seqdb index & saving...")
      max_seq = 0
      for p in range(1, len(data_bytes) // page_size):
        off = p * page_size
        if off + 0x14 <= len(data_bytes):
          seq = struct.unpack_from("<I", data_bytes, off + 0x10)[0]
          if seq > max_seq:
            max_seq = seq

      new_seqdb = max(struct.unpack_from("<I", data_bytes, 0x14)[0], max_seq + 1)
      struct.pack_into("<I", data_bytes, 0x14, new_seqdb)

      with open(pdb_path, "wb") as f:
        f.write(data_bytes)

      self.progress.emit(100, "Ready!")
      self.finished.emit(
          "CDJ-1500X: export.pdb database successfully repaired & synced (Backup"
          " saved as export.pdb.bak)[cite: 1, 2]."
      )

    except Exception as e:
      self.error.emit(str(e))


class RekordboxLibraryRepairWindow(QMainWindow):

  def __init__(self):
    super().__init__()
    self.setWindowIcon(create_app_icon())
    self.init_ui()
    self.detect_drives()

  def init_ui(self):
    self.setWindowTitle("Rekordbox Library Repair")
    self.setFixedSize(390, 150)

    central = QWidget()
    self.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(8)

    # Selection row with CDJ Eject icon replacing refresh
    sel_layout = QHBoxLayout()
    sel_layout.setSpacing(6)
    self.drive_combo = QComboBox()
    self.drive_combo.currentIndexChanged.connect(self.on_drive_selected)

    refresh_btn = QPushButton(create_eject_icon(), "")
    refresh_btn.setFixedWidth(36)
    refresh_btn.setToolTip("Eject / Refresh Drives")
    refresh_btn.clicked.connect(self.detect_drives)

    browse_btn = QPushButton("📂")
    browse_btn.setFixedWidth(36)
    browse_btn.setToolTip("Browse Folder")
    browse_btn.clicked.connect(self.browse_folder)

    sel_layout.addWidget(self.drive_combo, 1)
    sel_layout.addWidget(refresh_btn)
    sel_layout.addWidget(browse_btn)
    layout.addLayout(sel_layout)

    # Progress bar
    self.progress_bar = QProgressBar()
    self.progress_bar.setValue(0)
    self.progress_bar.setFixedHeight(20)
    layout.addWidget(self.progress_bar)

    # Single Play button filling the bottom layout row entirely
    self.repair_btn = QPushButton(create_play_icon(), " Play")
    self.repair_btn.setObjectName("PrimaryButton")
    self.repair_btn.setEnabled(False)
    self.repair_btn.setFixedHeight(34)
    self.repair_btn.clicked.connect(self.run_repair)
    layout.addWidget(self.repair_btn)

  def detect_drives(self):
    self.drive_combo.clear()
    self.drive_combo.addItem("-- Select USB / Folder --", "")

    detected = []
    if os.name == "nt":
      for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
          pioneer_check = os.path.join(root, "PIONEER", "rekordbox", "export.pdb")
          vol = get_windows_drive_label(root)
          if os.path.exists(pioneer_check):
            label = f"[{letter}:] {vol}" if vol else f"[{letter}:] USB Device"
          else:
            label = f"[{letter}:] {vol}" if vol else f"[{letter}:]"
          detected.append((label, root))
    else:
      for base in ["/Volumes", "/media", "/mnt"]:
        if os.path.exists(base):
          try:
            for entry in os.listdir(base):
              full = os.path.join(base, entry)
              if os.path.isdir(full):
                detected.append((f"Mount: {entry}", full))
          except Exception:
            pass

    for label, path in detected:
      self.drive_combo.addItem(label, path)

  def browse_folder(self):
    dir_path = QFileDialog.getExistingDirectory(self, "Select Folder")
    if dir_path:
      for i in range(self.drive_combo.count()):
        if self.drive_combo.itemData(i) == dir_path:
          self.drive_combo.setCurrentIndex(i)
          return
      self.drive_combo.addItem(
          f"Folder: {os.path.basename(dir_path)}", dir_path
      )
      self.drive_combo.setCurrentIndex(self.drive_combo.count() - 1)

  def on_drive_selected(self, index):
    path = self.drive_combo.itemData(index)
    if path and os.path.isdir(path):
      self.current_root = path
      self.repair_btn.setEnabled(True)
    else:
      self.repair_btn.setEnabled(False)

  def run_repair(self):
    self.repair_btn.setEnabled(False)
    self.progress_bar.setValue(0)

    self.worker = RepairWorker(self.current_root)
    self.worker.progress.connect(
        lambda v, m: (
            self.progress_bar.setValue(v),
            self.progress_bar.setFormat(m),
        )
    )
    self.worker.finished.connect(self.handle_success)
    self.worker.error.connect(self.handle_error)
    self.worker.start()

  def handle_success(self, msg):
    self.repair_btn.setEnabled(True)
    self.progress_bar.setFormat("Ready")
    QMessageBox.information(self, "CDJ-1500X Status", msg)

  def handle_error(self, err):
    self.repair_btn.setEnabled(True)
    self.progress_bar.setValue(0)
    self.progress_bar.setFormat("Error")
    QMessageBox.critical(self, "CDJ-1500X Error", err)


if __name__ == "__main__":
  app = QApplication(sys.argv)
  app.setStyleSheet(CDJ1500X_THEME)
  window = RekordboxLibraryRepairWindow()
  window.show()
  sys.exit(app.exec())
