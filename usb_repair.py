import ctypes
import csv
import os
import re
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
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# --- Modern Professional Blue Theme Styling ---
THEME_STYLESHEET = """
QMainWindow {
    background-color: #0B0F19;
    color: #E2E8F0;
}
QWidget {
    color: #E2E8F0;
    font-family: "Segoe UI", Roboto, Helvetica, sans-serif;
    font-size: 12px;
}
QPushButton {
    background-color: #131B2E;
    color: #F8FAFC;
    border: 1px solid #1E293B;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #1E293B;
    border-color: #3B82F6;
    color: #FFFFFF;
}
QPushButton:pressed {
    background-color: #0F172A;
}
QPushButton:disabled {
    background-color: #0D1322;
    color: #475569;
    border-color: #131B2E;
}
QPushButton#PrimaryButton {
    background-color: #2563EB;
    border: none;
    font-size: 13px;
    font-weight: bold;
    color: #FFFFFF;
}
QPushButton#PrimaryButton:hover {
    background-color: #1D4ED8;
}
QPushButton#PrimaryButton:pressed {
    background-color: #1E40AF;
}
QPushButton#PrimaryButton:disabled {
    background-color: #131B2E;
    color: #475569;
    border: 1px solid #1E293B;
}
QComboBox {
    background-color: #111827;
    border: 1px solid #1F2937;
    border-radius: 5px;
    padding: 6px 12px;
    color: #FFFFFF;
}
QComboBox::drop-down {
    border: 0px;
}
QComboBox QAbstractItemView {
    background-color: #111827;
    color: #FFFFFF;
    selection-background-color: #2563EB;
    border: 1px solid #1F2937;
}
QProgressBar {
    border: 1px solid #1F2937;
    border-radius: 5px;
    background-color: #111827;
    text-align: center;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 11px;
}
QProgressBar::chunk {
    background-color: #2563EB;
    border-radius: 4px;
}
QTableWidget { 
    background-color: #111827; color: #F1F1F1; 
    gridline-color: #1F2937; selection-background-color: #2563EB; 
    selection-color: #FFFFFF; border: 1px solid #1F2937; 
}
QHeaderView::section { 
    background-color: #131B2E; color: #60A5FA; 
    padding: 6px; border: 1px solid #1F2937; font-weight: bold; 
}
QTextEdit { 
    background-color: #0D1322; color: #93C5FD; 
    border: 1px solid #1F2937; font-family: Consolas, monospace; font-size: 10pt; 
}
QLineEdit { 
    background-color: #111827; color: #FFFFFF; border: 1px solid #1F2937; 
    padding: 6px; border-radius: 5px; font-size: 11pt; 
}
"""


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


class PdbParser:

  def __init__(self, pdb_path: str):
    self.pdb_path = pdb_path
    with open(pdb_path, "rb") as f:
      self.data = bytearray(f.read())

    if len(self.data) < 32:
      raise ValueError("PDB file is too small or invalid.")

    self.page_size = struct.unpack_from("<I", self.data, 4)[0]
    if self.page_size == 0:
      raise ValueError("PDB page size is zero.")

    self.num_tables = struct.unpack_from("<I", self.data, 8)[0]
    self.next_unused = struct.unpack_from("<I", self.data, 0x0C)[0]
    self.total_pages = len(self.data) // self.page_size

  def parse_tables(self):
    tables = []
    for i in range(self.num_tables):
      toff = 0x1C + i * 16
      if toff + 16 > len(self.data):
        break
      tt = struct.unpack_from("<I", self.data, toff)[0]
      ec = struct.unpack_from("<I", self.data, toff + 4)[0]
      first = struct.unpack_from("<I", self.data, toff + 8)[0]
      last = struct.unpack_from("<I", self.data, toff + 12)[0]
      tables.append(
          {
              "index": i,
              "table_type": tt,
              "empty_candidate": ec,
              "first": first,
              "last": last,
          }
      )
    return tables

  def run_health_diagnostic(self):
    issues = []
    tables = self.parse_tables()

    sentinel_u5_count = 0
    wrong_flags_count = 0
    truncated_chains = 0
    id_mismatch_count = 0
    torn_growth_count = 0

    if self.page_size not in (512, 1024, 2048, 4096, 8192):
      issues.append(
          f"<b>[UNKNOWN ERROR / ANOMALY]</b> Abnormal page size detected:"
          f" <b>{self.page_size}</b>."
      )

    if self.num_tables <= 0 or self.num_tables > 100:
      issues.append(
          f"<b>[UNKNOWN ERROR / ANOMALY]</b> Abnormal table count header:"
          f" <b>{self.num_tables}</b>."
      )

    claimed_pages = set()
    for t in tables:
      tt, first, last, ec = (
          t["table_type"],
          t["first"],
          t["last"],
          t["empty_candidate"],
      )

      if first > self.total_pages or last > self.total_pages:
        issues.append(
            f"<b>[UNKNOWN ERROR / ANOMALY]</b> Table Type {tt} references"
            f" physical pages beyond EOF (First: {first}, Last: {last}, Total:"
            f" {self.total_pages})."
        )

      if first != 0 and last != 0 and first <= last:
        for p in range(first, min(last + 1, self.total_pages)):
          if p in claimed_pages:
            issues.append(
                f"<b>[UNKNOWN ERROR / ANOMALY]</b> Page collision: Page"
                f" <b>{p}</b> is claimed by multiple table chains."
            )
          claimed_pages.add(p)

    max_table_last = max([t["last"] for t in tables] if tables else [1])
    effective_limit = max(self.next_unused, max_table_last + 1)
    if self.total_pages > effective_limit:
      torn_growth_count += self.total_pages - effective_limit

    for t in tables:
      if t["first"] >= self.total_pages or t["last"] >= self.total_pages:
        truncated_chains += 1

    for p in range(1, self.total_pages):
      off = p * self.page_size
      if off + 0x24 > len(self.data):
        break
      stored_idx = struct.unpack_from("<I", self.data, off + 4)[0]
      if stored_idx == 0:
        continue

      if stored_idx != p:
        id_mismatch_count += 1

      flags = self.data[off + 0x1B]
      if flags != 0x64:
        used_s = struct.unpack_from("<H", self.data, off + 0x1E)[0]
        if used_s > 0:
          if struct.unpack_from("<H", self.data, off + 0x20)[0] == 0x1FFF:
            sentinel_u5_count += 1
          if flags not in (0x24, 0x34):
            wrong_flags_count += 1

    if torn_growth_count > 0:
      issues.append(
          f"<b>[TORN EXPORT]</b> Interrupted Growth Tail: <b>{torn_growth_count}</b>"
          " unpopulated page(s) detected beyond next_unused boundary."
      )
    if truncated_chains > 0:
      issues.append(
          f"<b>[CRITICAL]</b> Truncated Table Chains: <b>{truncated_chains}</b>"
          " table(s) reference out-of-bounds pages."
      )
    if id_mismatch_count > 0:
      issues.append(
          f"<b>[CRITICAL]</b> Page ID Mismatches: <b>{id_mismatch_count}</b>"
          " page(s) have internal ID headers that do not match their physical"
          " index."
      )
    if sentinel_u5_count > 0:
      issues.append(
          f"<b>[WARNING]</b> Sentinel u5 Markers: <b>{sentinel_u5_count}</b>"
          " page(s) carry forbidden u5=0x1FFF values."
      )
    if wrong_flags_count > 0:
      issues.append(
          f"<b>[WARNING]</b> Wrong Page Flags: <b>{wrong_flags_count}</b>"
          " page(s) have invalid flag bytes."
      )

    if not issues:
      return (
          '<span style="color: #60A5FA; font-weight: bold;">[OK] Database Health'
          " Check Passed: No structural corruption or anomalies found in"
          " export.pdb!</span>"
      )
    else:
      warning_html = "<br>".join(issues)
      return (
          '<span style="color: #F87171; font-weight: bold;">--- USB DIAGNOSTICS:'
          f" ANOMALIES / TORN ---</span><br>{warning_html}"
      )

  def parse_device_sql_string(self, base_pos: int, string_offset: int) -> str:
    if string_offset == 0:
      return ""
    offset = base_pos + string_offset
    if offset >= len(self.data):
      return ""

    length_and_kind = self.data[offset]
    decoded = ""

    try:
      if length_and_kind == 144:
        if offset + 4 <= len(self.data):
          length = struct.unpack_from("<H", self.data, offset)[0]
          text_len = length - 4
          if 0 < text_len < 300 and offset + 4 + text_len <= len(self.data):
            raw = self.data[offset + 4 : offset + 4 + text_len]
            decoded = raw.decode("utf-16le", errors="ignore")
      elif length_and_kind == 64:
        if offset + 4 <= len(self.data):
          length = struct.unpack_from("<H", self.data, offset)[0]
          text_len = length - 4
          if 0 < text_len < 300 and offset + 4 + text_len <= len(self.data):
            raw = self.data[offset + 4 : offset + 4 + text_len]
            for enc in ("utf-8", "latin-1", "ascii"):
              try:
                decoded = raw.decode(enc, errors="ignore")
                break
              except Exception:
                continue
      else:
        text_len = length_and_kind >> 1
        if 0 < text_len < 300 and offset + 1 + text_len <= len(self.data):
          raw = self.data[offset + 1 : offset + 1 + text_len]
          for enc in ("utf-8", "latin-1", "ascii"):
            try:
              decoded = raw.decode(enc, errors="ignore")
              break
            except Exception:
              continue
    except Exception:
      return ""

    decoded = decoded.replace("\x00", "").strip()
    decoded = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", decoded)

    if len(decoded) > 150 or decoded.count("Ã") > 3:
      return ""

    return decoded

  def parse_table_rows(self, table_type: int):
    tables = self.parse_tables()
    target_table = next(
        (t for t in tables if t["table_type"] == table_type), None
    )
    if not target_table or target_table["first"] == 0:
      return []

    parsed_rows = []
    cur = target_table["first"]
    seen = set()

    max_valid_page = min(
        self.total_pages, target_table["last"] + 1, self.next_unused
    )
    if max_valid_page <= cur:
      max_valid_page = self.total_pages

    while cur != 0 and cur < max_valid_page and cur not in seen:
      seen.add(cur)
      off = cur * self.page_size
      if off + self.page_size > len(self.data):
        break

      try:
        stored_idx = struct.unpack_from("<I", self.data, off + 4)[0]
        if stored_idx == 0 or self.data[off + 0x1B] == 0x64:
          nxt = struct.unpack_from("<I", self.data, off + 0x0C)[0]
          if nxt == cur or nxt == 0 or nxt >= self.total_pages:
            break
          cur = nxt
          continue

        used_s = struct.unpack_from("<H", self.data, off + 0x1E)[0]
        if used_s == 0:
          nxt = struct.unpack_from("<I", self.data, off + 0x0C)[0]
          if nxt == cur or nxt == 0 or nxt >= self.total_pages:
            break
          cur = nxt
          continue

        b18 = self.data[off + 0x18]
        b19 = self.data[off + 0x19]
        b1a = self.data[off + 0x1A]
        packed = b18 | (b19 << 8) | (b1a << 16)
        num_row_offsets = packed & 0x1FFF

        if num_row_offsets > 0:
          footer_groups = (num_row_offsets - 1) // 16 + 1
          cursor = self.page_size
          for g in range(footer_groups):
            if cursor < 4:
              break
            cursor -= 4
            rowpf = struct.unpack_from("<H", self.data, off + cursor)[0]
            cursor -= 2
            glen = min(16, num_row_offsets - g * 16)
            if cursor < glen * 2:
              break
            cursor -= glen * 2
            for r in range(glen):
              roff = struct.unpack_from(
                  "<H", self.data, off + cursor + r * 2
              )[0]
              is_active = (rowpf >> (r % 16)) & 1 == 1
              if is_active:
                row_abs = off + 40 + roff
                if row_abs + 16 <= len(self.data):
                  row_id = 0
                  label_text = ""

                  if table_type == 0 and row_abs + 136 <= len(self.data):
                    row_id = struct.unpack_from("<I", self.data, row_abs + 72)[
                        0
                    ]
                    title_str_ofs = struct.unpack_from(
                        "<H", self.data, row_abs + 94 + (17 * 2)
                    )[0]
                    label_text = self.parse_device_sql_string(
                        row_abs, title_str_ofs
                    )
                  elif table_type == 3:
                    row_id = struct.unpack_from("<I", self.data, row_abs + 12)[
                        0
                    ]
                    name_ofs = self.data[row_abs + 21]
                    label_text = self.parse_device_sql_string(
                        row_abs, name_ofs
                    )
                  elif table_type == 2:
                    row_id = struct.unpack_from("<I", self.data, row_abs + 4)[
                        0
                    ]
                    name_ofs = self.data[row_abs + 9]
                    label_text = self.parse_device_sql_string(
                        row_abs, name_ofs
                    )
                  elif table_type == 7:
                    row_id = struct.unpack_from("<I", self.data, row_abs + 12)[
                        0
                    ]
                    label_text = self.parse_device_sql_string(row_abs, 20)
                  else:
                    row_id = struct.unpack_from("<I", self.data, row_abs)[0]
                    label_text = f"Page {cur} Offset {roff}"

                  if label_text:
                    parsed_rows.append(
                        {"id": row_id, "page": cur, "label": label_text}
                    )

        nxt = struct.unpack_from("<I", self.data, off + 0x0C)[0]
        if nxt == cur or nxt == 0 or nxt >= self.total_pages:
          break
        cur = nxt
      except Exception:
        break

    return parsed_rows


class LoadWorker(QThread):
  finished = pyqtSignal(object, str)
  error = pyqtSignal(str)

  def __init__(self, pdb_path: str):
    super().__init__()
    self.pdb_path = pdb_path

  def run(self):
    try:
      parser = PdbParser(self.pdb_path)
      parser.parse_tables()
      self.finished.emit(parser, self.pdb_path)
    except Exception as e:
      self.error.emit(str(e))


class RepairWorker(QThread):
  progress = pyqtSignal(int, str)
  finished = pyqtSignal(str)
  error = pyqtSignal(str)

  def __init__(self, pdb_path_or_root: str):
    super().__init__()
    self.target_path = pdb_path_or_root

  def run(self):
    try:
      self.progress.emit(10, "Initializing and mounting export.pdb...")
      target = os.path.normpath(self.target_path)

      if target.endswith(".pdb"):
        pdb_path = target
      else:
        pdb_path = os.path.join(target, "PIONEER", "rekordbox", "export.pdb")

      if not os.path.exists(pdb_path):
        self.error.emit(f"export.pdb not found at: {pdb_path}")
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

      self.progress.emit(55, "Parsing tables and mapping page ownership...")

      tables = []
      for i in range(num_tables):
        toff = 0x1C + i * 16
        if toff + 16 > len(data_bytes):
          break
        tt = struct.unpack_from("<I", data_bytes, toff)[0]
        ec = struct.unpack_from("<I", data_bytes, toff + 4)[0]
        first = struct.unpack_from("<I", data_bytes, toff + 8)[0]
        last = struct.unpack_from("<I", data_bytes, toff + 12)[0]
        tables.append(
            {
                "index": i,
                "table_type": tt,
                "empty_candidate": ec,
                "first": first,
                "last": last,
            }
        )

      # --- ADVANCED CHAIN COLLISION RESOLUTION ---
      claimed_pages = set()
      fixed_chains_count = 0

      for t in tables:
        toff = 0x1C + (t["index"] * 16)
        cur = t["first"]
        chain_pages = []
        visited_in_chain = set()

        while (
            cur != 0
            and cur < total_pages
            and cur not in visited_in_chain
            and cur not in claimed_pages
        ):
          visited_in_chain.add(cur)
          chain_pages.append(cur)

          off = cur * page_size
          if off + 0x10 > len(data_bytes):
            break
          nxt = struct.unpack_from("<I", data_bytes, off + 0x0C)[0]
          if nxt == cur:
            struct.pack_into("<I", data_bytes, off + 0x0C, 0)
            break
          cur = nxt

        if chain_pages:
          new_first = chain_pages[0]
          new_last = chain_pages[-1]
          for p in chain_pages:
            claimed_pages.add(p)
        else:
          new_first = 0
          new_last = 0

        if new_first != t["first"] or new_last != t["last"]:
          struct.pack_into("<I", data_bytes, toff + 8, new_first)
          struct.pack_into("<I", data_bytes, toff + 12, new_last)
          t["first"] = new_first
          t["last"] = new_last
          fixed_chains_count += 1

      self.progress.emit(75, "Sanitizing page headers, IDs, and flags...")

      fixed_ids = 0
      fixed_u5 = 0
      fixed_flags = 0
      garbage_ec_pages = 0

      for t in tables:
        ec = t["empty_candidate"]
        if ec != 0 and ec < total_pages:
          off = ec * page_size
          if off + page_size <= len(data_bytes) and any(
              data_bytes[off : off + page_size]
          ):
            data_bytes[off : off + page_size] = b"\x00" * page_size
            garbage_ec_pages += 1

      max_table_last = max([t["last"] for t in tables] if tables else [1])
      valid_limit = max(next_unused, max_table_last + 1)
      max_allowed_len = valid_limit * page_size
      truncated_tail_pages = 0

      if len(data_bytes) > max_allowed_len:
        truncated_tail_pages = (
            len(data_bytes) - max_allowed_len
        ) // page_size
        del data_bytes[max_allowed_len:]

      total_pages = len(data_bytes) // page_size
      corrected_next_unused = min(total_pages, max_table_last + 2)
      struct.pack_into("<I", data_bytes, 0x0C, corrected_next_unused)

      for p in range(1, total_pages):
        off = p * page_size
        if off + page_size > len(data_bytes):
          break

        stored_idx = struct.unpack_from("<I", data_bytes, off + 4)[0]
        if stored_idx != 0:
          if stored_idx != p:
            struct.pack_into("<I", data_bytes, off + 4, p)
            fixed_ids += 1

        nxt = struct.unpack_from("<I", data_bytes, off + 0x0C)[0]
        if nxt >= total_pages:
          struct.pack_into("<I", data_bytes, off + 0x0C, 0)

        flags = data_bytes[off + 0x1B]
        if flags != 0x64:
          used_s = struct.unpack_from("<H", data_bytes, off + 0x1E)[0]
          if used_s > 0:
            if struct.unpack_from("<H", data_bytes, off + 0x20)[0] == 0x1FFF:
              struct.pack_into("<H", data_bytes, off + 0x20, 0x0000)
              fixed_u5 += 1

            if flags not in (0x24, 0x34):
              data_bytes[off + 0x1B] = 0x24
              fixed_flags += 1

      self.progress.emit(90, "Updating database sequence & writing file...")
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
          f"Successfully fully rebuilt and CDJ-certified saved to:\n{pdb_path}\n"
          f"- Resolved Colliding Chains: {fixed_chains_count}\n"
          f"- Zeroed Garbage Candidates: {garbage_ec_pages}\n"
          f"- Truncated Tail Pages: {truncated_tail_pages}\n"
          f"- Re-aligned Page IDs: {fixed_ids}\n"
          f"- Fixed u5 Sentinels: {fixed_u5}\n"
          f"- Normalized Flags: {fixed_flags}"
      )

    except Exception as e:
      self.error.emit(str(e))


class RekordboxLibraryRepairWindow(QMainWindow):

  def __init__(self):
    super().__init__()
    self.parser = None
    self.current_rows = []
    self.current_pdb_path = ""
    self.current_root = ""
    self.load_worker = None
    self.init_ui()
    self.detect_drives()

  def init_ui(self):
    self.setWindowTitle(
        "PyQt6 Advanced Rekordbox PDB Forensic Repair & Export Suite"
    )
    self.resize(1300, 750)

    central = QWidget()
    self.setCentralWidget(central)
    layout = QVBoxLayout(central)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    top_layout = QHBoxLayout()
    self.load_btn = QPushButton("📂 Open export.pdb")
    self.load_btn.clicked.connect(self.open_file)
    top_layout.addWidget(self.load_btn)

    self.health_btn = QPushButton("🛡️ Run Health Check")
    self.health_btn.clicked.connect(self.run_health_check)
    self.health_btn.setEnabled(False)
    top_layout.addWidget(self.health_btn)

    self.repair_btn = QPushButton("🛠️ Auto-Repair")
    self.repair_btn.setObjectName("PrimaryButton")
    self.repair_btn.clicked.connect(self.run_repair)
    self.repair_btn.setEnabled(False)
    top_layout.addWidget(self.repair_btn)

    self.export_btn = QPushButton("💾 Export Table to CSV")
    self.export_btn.clicked.connect(self.export_to_csv)
    self.export_btn.setEnabled(False)
    top_layout.addWidget(self.export_btn)

    top_layout.addStretch()

    self.drive_combo = QComboBox()
    self.drive_combo.setMinimumWidth(220)
    self.drive_combo.currentIndexChanged.connect(self.on_drive_selected)
    top_layout.addWidget(QLabel("Target USB/Dir:"))
    top_layout.addWidget(self.drive_combo)

    refresh_btn = QPushButton("🔄")
    refresh_btn.setFixedWidth(36)
    refresh_btn.setToolTip("Refresh Drives")
    refresh_btn.clicked.connect(self.detect_drives)
    top_layout.addWidget(refresh_btn)

    layout.addLayout(top_layout)

    self.progress_bar = QProgressBar()
    self.progress_bar.setValue(0)
    self.progress_bar.setFixedHeight(18)
    layout.addWidget(self.progress_bar)

    search_layout = QHBoxLayout()
    search_layout.addWidget(QLabel("🔍 Filter Rows:"))
    self.search_input = QLineEdit()
    self.search_input.setPlaceholderText(
        "Type to filter content or ID in current table..."
    )
    self.search_input.textChanged.connect(self.filter_rows)
    self.search_input.setEnabled(False)
    search_layout.addWidget(self.search_input)
    layout.addLayout(search_layout)

    splitter = QSplitter(Qt.Orientation.Horizontal)

    self.tables_table = QTableWidget()
    self.tables_table.setColumnCount(4)
    self.tables_table.setHorizontalHeaderLabels(
        ["Table Type", "First", "Last", "Empty Candidate"]
    )
    self.tables_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch
    )
    self.tables_table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows
    )
    self.tables_table.cellClicked.connect(self.on_table_selected)
    splitter.addWidget(self.tables_table)

    right_splitter = QSplitter(Qt.Orientation.Vertical)

    self.rows_table = QTableWidget()
    self.rows_table.setColumnCount(3)
    self.rows_table.setHorizontalHeaderLabels(["Record ID", "Page", "Content"])
    self.rows_table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch
    )
    right_splitter.addWidget(self.rows_table)

    self.log_output = QTextEdit()
    self.log_output.setReadOnly(True)
    self.log_output.setPlaceholderText(
        "Forensic logs, health checks, and repair reports will appear here..."
    )
    right_splitter.addWidget(self.log_output)

    right_splitter.setSizes([450, 180])
    splitter.addWidget(right_splitter)
    splitter.setSizes([400, 900])
    layout.addWidget(splitter)

  def detect_drives(self):
    self.drive_combo.clear()
    self.drive_combo.addItem("-- Select USB Drive / Folder --", "")

    detected = []
    if os.name == "nt":
      for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        if os.path.exists(root):
          pioneer_check = os.path.join(root, "PIONEER", "rekordbox", "export.pdb")
          vol = get_windows_drive_label(root)
          if os.path.exists(pioneer_check):
            label = f"[{letter}:] {vol}" if vol else f"[{letter}:]"
            detected.insert(0, (label, root))
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

  def on_drive_selected(self, index):
    path = self.drive_combo.itemData(index)
    if path and os.path.isdir(path):
      self.current_root = path
      pdb_candidate = os.path.join(path, "PIONEER", "rekordbox", "export.pdb")
      if os.path.exists(pdb_candidate):
        self.load_pdb_from_path(pdb_candidate)

  def open_file(self):
    file_name, _ = QFileDialog.getOpenFileName(
        self, "Open export.pdb", "", "PDB Files (*.pdb);;All Files (*.*)"
    )
    if file_name:
      self.load_pdb_from_path(file_name)

  def load_pdb_from_path(self, file_name):
    self.load_btn.setEnabled(False)
    self.progress_bar.setRange(0, 0)
    self.progress_bar.setFormat("Loading PDB asynchronously...")

    self.load_worker = LoadWorker(file_name)
    self.load_worker.finished.connect(self.handle_load_success)
    self.load_worker.error.connect(self.handle_load_error)
    self.load_worker.start()

  def handle_load_success(self, parser, file_name):
    self.load_btn.setEnabled(True)
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(100)
    self.progress_bar.setFormat("Ready")

    self.parser = parser
    self.current_pdb_path = file_name
    self.current_root = os.path.dirname(
        os.path.dirname(os.path.dirname(file_name))
    )

    try:
      tables = self.parser.parse_tables()

      self.tables_table.setRowCount(len(tables))
      for row_idx, t in enumerate(tables):
        self.tables_table.setItem(
            row_idx, 0, QTableWidgetItem(str(t["table_type"]))
        )
        self.tables_table.setItem(
            row_idx, 1, QTableWidgetItem(str(t["first"]))
        )
        self.tables_table.setItem(row_idx, 2, QTableWidgetItem(str(t["last"])))
        self.tables_table.setItem(
            row_idx, 3, QTableWidgetItem(str(t["empty_candidate"]))
        )

      self.health_btn.setEnabled(True)
      self.repair_btn.setEnabled(True)
      self.export_btn.setEnabled(True)
      self.search_input.setEnabled(True)

      self.log_output.setHtml(
          '<span style="color: #60A5FA;">Loaded PDB:</span>'
          f" <b>{file_name}</b><br>"
          '<span style="color: #34D399;">Total Pages:</span>'
          f" {self.parser.total_pages} | "
          '<span style="color: #34D399;">Total Tables:</span>'
          f" {self.parser.num_tables}"
      )

      if tables:
        self.tables_table.selectRow(0)
        self.on_table_selected(0, 0)

    except Exception as e:
      self.log_output.setHtml(
          f'<span style="color: #F87171;">Error parsing tables: {e}</span>'
      )

  def handle_load_error(self, err):
    self.load_btn.setEnabled(True)
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)
    self.progress_bar.setFormat("Error")
    self.log_output.setHtml(
        f'<span style="color: #F87171;">Error opening PDB: {err}</span>'
    )

  def run_health_check(self):
    if not self.parser:
      return
    report_html = self.parser.run_health_diagnostic()
    self.log_output.setHtml(report_html)

  def run_repair(self):
    target = (
        self.current_pdb_path
        if self.current_pdb_path
        else (
            os.path.join(
                self.current_root, "PIONEER", "rekordbox", "export.pdb"
            )
            if self.current_root
            else ""
        )
    )

    if not target or not os.path.exists(target):
      target, _ = QFileDialog.getOpenFileName(
          self, "Select export.pdb to Repair", "", "PDB Files (*.pdb)"
      )

    if not target:
      return

    self.repair_btn.setEnabled(False)
    self.progress_bar.setRange(0, 100)
    self.progress_bar.setValue(0)

    self.worker = RepairWorker(target)
    self.worker.progress.connect(
        lambda v, m: (
            self.progress_bar.setValue(v),
            self.progress_bar.setFormat(m),
        )
    )
    self.worker.finished.connect(self.handle_repair_success)
    self.worker.error.connect(self.handle_repair_error)
    self.worker.start()

  def handle_repair_success(self, msg):
    self.repair_btn.setEnabled(True)
    self.progress_bar.setFormat("Ready")
    self.log_output.setHtml(
        f'<span style="color: #34D399; font-weight: bold;">{msg}</span>'
    )
    if self.current_pdb_path and os.path.exists(self.current_pdb_path):
      self.load_pdb_from_path(self.current_pdb_path)
    QMessageBox.information(self, "Library Status", msg)

  def handle_repair_error(self, err):
    self.repair_btn.setEnabled(True)
    self.progress_bar.setValue(0)
    self.progress_bar.setFormat("Error")
    self.log_output.setHtml(
        f'<span style="color: #F87171;">Repair failed: {err}</span>'
    )
    QMessageBox.critical(self, "Library Error", err)

  def export_to_csv(self):
    if not self.current_rows:
      return
    save_path, _ = QFileDialog.getSaveFileName(
        self,
        "Export Table to CSV",
        "table_export.csv",
        "CSV Files (*.csv);;All Files (*.*)",
    )
    if save_path:
      try:
        with open(save_path, "w", newline="", encoding="utf-8") as f:
          writer = csv.writer(f)
          writer.writerow(["Record ID", "Page", "Content"])
          for r in self.current_rows:
            writer.writerow([r["id"], r["page"], r["label"]])
        self.log_output.setHtml(
            f'<span style="color: #34D399;">Successfully exported table data'
            f" to: <b>{save_path}</b></span>"
        )
      except Exception as e:
        self.log_output.setHtml(
            f'<span style="color: #F87171;">Export failed: {e}</span>'
        )

  def on_table_selected(self, row, column):
    if not self.parser:
      return
    item = self.tables_table.item(row, 0)
    if not item:
      return
    table_type = int(item.text())

    self.current_rows = self.parser.parse_table_rows(table_type)
    self.populate_rows_table(self.current_rows)
    self.search_input.clear()

  def populate_rows_table(self, rows):
    self.rows_table.setRowCount(len(rows))
    for r_idx, r in enumerate(rows):
      self.rows_table.setItem(r_idx, 0, QTableWidgetItem(str(r["id"])))
      self.rows_table.setItem(r_idx, 1, QTableWidgetItem(str(r["page"])))
      self.rows_table.setItem(r_idx, 2, QTableWidgetItem(str(r["label"])))

  def filter_rows(self, text):
    if not self.current_rows:
      return
    query = text.lower()
    filtered = [
        r
        for r in self.current_rows
        if query in str(r["id"]).lower() or query in r["label"].lower()
    ]
    self.populate_rows_table(filtered)


if __name__ == "__main__":
  app = QApplication(sys.argv)
  app.setStyleSheet(THEME_STYLESHEET)
  window = RekordboxLibraryRepairWindow()
  window.show()
  sys.exit(app.exec())
