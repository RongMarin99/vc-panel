from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QScrollArea, QWidget, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

import ui.theme as theme


def _normalize(val: str) -> str:
    """php_curl.dll → curl,  php_curl → curl,  curl → curl"""
    v = val.strip().strip('"').strip("'").lower()
    if v.startswith("php_"):
        v = v[4:]
    if v.endswith(".dll"):
        v = v[:-4]
    return v


def _read_extensions(php_ini: Path) -> tuple[dict[str, str], set[str]]:
    """
    Returns:
        available: { canonical_name → original_line_value }  (all extension= lines seen in ini)
        enabled:   { canonical_name }  (uncommented ones)
    """
    available: dict[str, str] = {}
    enabled: set[str] = set()
    if not php_ini.exists():
        return available, enabled
    for line in php_ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        commented = stripped.startswith(";")
        raw = stripped.lstrip(";").strip()
        if raw.lower().startswith("extension="):
            val = raw[10:]
            canonical = _normalize(val)
            if canonical:
                available[canonical] = val.strip()
                if not commented:
                    enabled.add(canonical)
    return available, enabled


def _read_ext_dir(ext_dir: Path) -> dict[str, str]:
    """Returns { canonical_name → filename } for all php_*.dll in ext/."""
    result: dict[str, str] = {}
    if ext_dir.exists():
        for f in sorted(ext_dir.glob("php_*.dll"), key=lambda x: x.name.lower()):
            canonical = _normalize(f.name)
            result[canonical] = f.name
    return result


def _save_extensions(php_ini: Path, enabled_set: set[str], available: dict[str, str]):
    if not php_ini.exists():
        return
    lines = php_ini.read_text(encoding="utf-8", errors="ignore").splitlines(keepends=True)
    new_lines: list[str] = []
    processed: set[str] = set()

    for line in lines:
        stripped = line.strip()
        commented = stripped.startswith(";")
        raw = stripped.lstrip(";").strip()
        if raw.lower().startswith("extension="):
            val = raw[10:]
            canonical = _normalize(val)
            if not canonical:
                new_lines.append(line)
                continue
            processed.add(canonical)
            orig_val = available.get(canonical, canonical)
            if canonical in enabled_set:
                new_lines.append(f"extension={orig_val}\n")
            else:
                new_lines.append(f";extension={orig_val}\n")
        else:
            new_lines.append(line if line.endswith("\n") else line + "\n")

    # Append newly enabled extensions not previously in the file
    for ext in sorted(enabled_set):
        if ext not in processed:
            new_lines.append(f"extension={ext}\n")

    php_ini.write_text("".join(new_lines), encoding="utf-8")


class PHPExtensionsDialog(QDialog):
    def __init__(self, version: str, install_path: Path, parent=None):
        super().__init__(parent)
        self.version = version
        self.php_ini = install_path / "php.ini"
        self.ext_dir = install_path / "ext"

        self.setWindowTitle(f"PHP {version} — Extensions")
        self.setMinimumSize(480, 560)
        self.resize(520, 620)

        self._ini_available: dict[str, str] = {}
        self._enabled: set[str] = set()
        self._ext_available: dict[str, str] = {}
        self._all_items: list[tuple[str, str]] = []  # [(canonical, dll_filename)]

        self._build()
        self._load()

    def _build(self):
        C = theme.current_colors()
        self.setStyleSheet(f"background:{C['bg']}; color:{C['text']}; font-size:13px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        # Header
        title = QLabel(f"PHP {self.version} Extensions")
        title.setStyleSheet("font-size:18px; font-weight:700;")
        layout.addWidget(title)

        ini_label = QLabel(str(self.php_ini))
        ini_label.setStyleSheet(f"font-size:11px; color:{C['text2']}; font-family:monospace;")
        ini_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(ini_label)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search extensions…")
        self._search.setStyleSheet(
            f"background:{C['input_bg']}; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:6px; padding:6px 10px; font-size:13px;"
        )
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        # Count label
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"font-size:12px; color:{C['text2']};")
        layout.addWidget(self._count_lbl)

        # List
        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget {{ background:{C['card']}; border:1px solid {C['border']};"
            f" border-radius:8px; padding:4px; }}"
            f"QListWidget::item {{ padding:6px 8px; border-radius:4px; }}"
            f"QListWidget::item:hover {{ background:{C['hover']}; }}"
        )
        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

        # Footer
        footer = QHBoxLayout()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"font-size:12px; color:{C['text2']};")
        footer.addWidget(self._status_lbl)
        footer.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:transparent; color:{C['text']}; border:1px solid {C['border']};"
            f" border-radius:5px; padding:6px 18px; font-size:13px; }}"
            f"QPushButton:hover {{ background:{C['hover']}; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            f"QPushButton {{ background:{C['blue']}; color:#fff; border:none;"
            f" border-radius:5px; padding:6px 22px; font-size:13px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C['blue']}dd; }}"
        )
        save_btn.clicked.connect(self._save)
        footer.addWidget(save_btn)

        layout.addLayout(footer)

    def _load(self):
        self._ini_available, self._enabled = _read_extensions(self.php_ini)
        self._ext_available = _read_ext_dir(self.ext_dir)

        # Merge: ini-known + disk-known
        all_names: set[str] = set(self._ini_available) | set(self._ext_available)
        self._all_items = sorted(
            [(n, self._ext_available.get(n, f"php_{n}.dll")) for n in all_names],
            key=lambda x: x[0],
        )
        self._populate(self._all_items)
        self._update_count()

    def _populate(self, items: list[tuple[str, str]]):
        self._list.blockSignals(True)
        self._list.clear()
        for canonical, dll_name in items:
            text = f"{canonical}  ({dll_name})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, canonical)
            checked = canonical in self._enabled
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            C = theme.current_colors()
            item.setForeground(QColor(C["green"] if checked else C["text2"]))
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _filter(self, text: str):
        q = text.lower()
        filtered = [(n, d) for n, d in self._all_items if q in n or q in d.lower()]
        self._populate(filtered)
        self._count_lbl.setText(f"{len(filtered)} of {len(self._all_items)} shown")

    def _on_item_changed(self, item: QListWidgetItem):
        canonical = item.data(Qt.ItemDataRole.UserRole)
        C = theme.current_colors()
        if item.checkState() == Qt.CheckState.Checked:
            self._enabled.add(canonical)
            item.setForeground(QColor(C["green"]))
        else:
            self._enabled.discard(canonical)
            item.setForeground(QColor(C["text2"]))
        self._update_count()

    def _update_count(self):
        total = len(self._all_items)
        enabled = len(self._enabled)
        C = theme.current_colors()
        self._count_lbl.setText(f"{enabled} of {total} extensions enabled")
        self._status_lbl.setText(f"{enabled} enabled")

    def _save(self):
        _save_extensions(self.php_ini, self._enabled, self._ini_available)
        self.accept()
