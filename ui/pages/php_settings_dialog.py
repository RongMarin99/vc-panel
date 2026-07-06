from pathlib import Path
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QFrame,
)
from PyQt6.QtCore import Qt

import ui.theme as theme


_SETTINGS = [
    ("upload_max_filesize", "Upload Max File Size",
     "Max size of a single uploaded file"),
    ("post_max_size",       "POST Max Size",
     "Max size of entire POST body — must be ≥ upload_max_filesize"),
    ("memory_limit",        "Memory Limit",
     "Max memory a PHP script may consume"),
    ("max_execution_time",  "Max Execution Time",
     "Max seconds a script may run (0 = unlimited)"),
]

_SIZE_KEYS  = {"upload_max_filesize", "post_max_size", "memory_limit"}
_TIME_KEYS  = {"max_execution_time"}


def _read_ini_value(php_ini: Path, key: str) -> str:
    if not php_ini.exists():
        return ""
    pattern = re.compile(r"^\s*" + re.escape(key) + r"\s*=\s*(.+)$", re.IGNORECASE)
    for line in php_ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pattern.match(line.strip())
        if m:
            return m.group(1).strip()
    return ""


def _write_ini_value(php_ini: Path, key: str, value: str):
    if not php_ini.exists():
        return
    lines = php_ini.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    pattern = re.compile(r"^(\s*;?\s*)" + re.escape(key) + r"\s*=", re.IGNORECASE)
    new_lines = []
    replaced = False
    for line in lines:
        if pattern.match(line) and not replaced:
            new_lines.append(f"{key} = {value}\n")
            replaced = True
        else:
            new_lines.append(line if line.endswith("\n") else line + "\n")
    if not replaced:
        new_lines.append(f"{key} = {value}\n")
    php_ini.write_text("".join(new_lines), encoding="utf-8")


def _parse_size(value: str) -> tuple[str, str]:
    """'128M' → ('128', 'M'),  '2G' → ('2', 'G'),  '256' → ('256', 'M')"""
    value = value.strip()
    m = re.match(r"^(\d+)\s*([KkMmGg]?)$", value)
    if m:
        num, unit = m.group(1), m.group(2).upper() or "M"
        return num, unit
    return value, "M"


class _SizeRow(QHBoxLayout):
    def __init__(self, key: str, label: str, hint: str, current: str, C: dict):
        super().__init__()
        self._key = key

        col = QVBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text']};")
        col.addWidget(lbl)
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(f"font-size:11px; color:{C['text2']};")
        col.addWidget(hint_lbl)
        self.addLayout(col)
        self.addStretch()

        num, unit = _parse_size(current)

        self._input = QLineEdit(num)
        self._input.setFixedWidth(80)
        self._input.setStyleSheet(
            f"background:{C['input_bg']}; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:5px; padding:5px 8px; font-size:13px;"
        )
        self.addWidget(self._input)

        self._unit = QComboBox()
        self._unit.addItems(["K", "M", "G"])
        self._unit.setCurrentText(unit if unit in ("K", "M", "G") else "M")
        self._unit.setFixedWidth(60)
        self._unit.setStyleSheet(
            f"background:{C['input_bg']}; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:5px; padding:4px; font-size:13px;"
        )
        self.addWidget(self._unit)

    def value(self) -> str:
        return f"{self._input.text().strip()}{self._unit.currentText()}"


class _TimeRow(QHBoxLayout):
    def __init__(self, key: str, label: str, hint: str, current: str, C: dict):
        super().__init__()
        self._key = key

        col = QVBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text']};")
        col.addWidget(lbl)
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(f"font-size:11px; color:{C['text2']};")
        col.addWidget(hint_lbl)
        self.addLayout(col)
        self.addStretch()

        self._input = QLineEdit(current or "30")
        self._input.setFixedWidth(80)
        self._input.setStyleSheet(
            f"background:{C['input_bg']}; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:5px; padding:5px 8px; font-size:13px;"
        )
        self.addWidget(self._input)

        sec = QLabel("sec")
        sec.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        self.addWidget(sec)

    def value(self) -> str:
        return self._input.text().strip()


class PHPSettingsDialog(QDialog):
    def __init__(self, version: str, install_path: Path, parent=None):
        super().__init__(parent)
        self.version = version
        self.php_ini = install_path / "php.ini"
        self.setWindowTitle(f"PHP {version} — Settings")
        self.setMinimumWidth(480)
        self.setFixedHeight(380)
        self._rows: list = []
        self._build()

    def _build(self):
        C = theme.current_colors()
        self.setStyleSheet(f"background:{C['bg']}; color:{C['text']}; font-size:13px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)

        title = QLabel(f"PHP {self.version} — Settings")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        layout.addWidget(title)

        ini_lbl = QLabel(str(self.php_ini))
        ini_lbl.setStyleSheet(f"font-size:11px; color:{C['text2']}; font-family:monospace;")
        ini_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(ini_lbl)
        layout.addSpacing(18)

        for key, label, hint in _SETTINGS:
            current = _read_ini_value(self.php_ini, key)
            if key in _SIZE_KEYS:
                row = _SizeRow(key, label, hint, current, C)
            else:
                row = _TimeRow(key, label, hint, current, C)
            row._key = key
            self._rows.append(row)
            layout.addLayout(row)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color:{C['border']};")
            layout.addSpacing(10)
            layout.addWidget(sep)
            layout.addSpacing(10)

        layout.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:5px; padding:6px 18px; font-size:13px; }}"
            f"QPushButton:hover {{ background:{C['hover']}; }}"
        )
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)

        save = QPushButton("Save")
        save.setStyleSheet(
            f"QPushButton {{ background:{C['blue']}; color:#fff; border:none;"
            f" border-radius:5px; padding:6px 22px; font-size:13px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C['blue']}dd; }}"
        )
        save.clicked.connect(self._save)
        footer.addWidget(save)

        layout.addLayout(footer)

    def _save(self):
        for row in self._rows:
            val = row.value()
            if val:
                _write_ini_value(self.php_ini, row._key, val)
        self.accept()
