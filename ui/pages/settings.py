import sys
import platform

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QMessageBox, QSizePolicy, QScrollArea
)
from PyQt6.QtCore import Qt

import ui.theme as theme
from utils.startup import is_startup_enabled, set_startup


def _card() -> QFrame:
    f = QFrame()
    f.setObjectName("card")
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        "font-size: 11px; font-weight: 600; color: #8b949e; "
        "letter-spacing: 1px; margin-bottom: 6px;"
    )
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #d0d7de; margin: 0px;")
    return line


class SettingsPage(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._theme_btns: dict[str, QPushButton] = {}
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        sub = QLabel("Appearance, paths and system")
        sub.setStyleSheet("color: #8b949e; font-size: 13px; margin-top: 4px;")
        layout.addWidget(sub)
        layout.addSpacing(28)

        # ── Appearance ───────────────────────────────────────
        layout.addWidget(_section_label("Appearance"))
        card = _card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 18, 20, 18)
        cl.setSpacing(12)

        row = QHBoxLayout()
        lbl = QLabel("Theme")
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        row.addWidget(lbl)
        row.addStretch()

        for name, icon, label in [("light", "☀", "Light"), ("dark", "🌙", "Dark")]:
            btn = QPushButton(f"{icon}  {label}")
            btn.setFixedSize(110, 34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, n=name: self._switch_theme(n))
            self._theme_btns[name] = btn
            row.addWidget(btn)

        cl.addLayout(row)
        layout.addWidget(card)
        layout.addSpacing(20)

        # ── Paths ─────────────────────────────────────────────
        layout.addWidget(_section_label("Paths"))
        card2 = _card()
        cl2 = QVBoxLayout(card2)
        cl2.setContentsMargins(7, 0, 15, 0)
        cl2.setSpacing(0)

        paths = [
            ("Home",     str(self.config.home)),
            ("Versions", str(self.config.versions_dir)),
            ("Shims",    str(self.config.shims_dir)),
            ("Config",   str(self.config.config_file)),
            ("Database", str(self.config.db_path)),
        ]
        C = theme.current_colors()
        for i, (key, val) in enumerate(paths):
            row = QHBoxLayout()
            row.setContentsMargins(20, 12, 20, 12)
            k = QLabel(key)
            k.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {C['text2']};")
            k.setFixedWidth(70)
            row.addWidget(k)
            v = QLabel(val)
            v.setStyleSheet(
                f"font-family: 'Cascadia Code', Consolas, monospace; "
                f"font-size: 12px; color: {C['text']};"
            )
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            v.setWordWrap(False)
            row.addWidget(v, 1)
            cl2.addLayout(row)
            if i < len(paths) - 1:
                cl2.addWidget(_divider())

        layout.addWidget(card2)
        layout.addSpacing(20)

        # ── PATH Management (Windows only) ────────────────────
        if sys.platform == "win32":
            layout.addWidget(_section_label("PATH Management"))
            card3 = _card()
            cl3 = QVBoxLayout(card3)
            cl3.setContentsMargins(20, 18, 20, 18)
            cl3.setSpacing(14)

            top = QHBoxLayout()
            top.setSpacing(12)

            icon_lbl = QLabel("⚡")
            icon_lbl.setStyleSheet("font-size: 22px;")
            icon_lbl.setFixedWidth(30)
            top.addWidget(icon_lbl)

            txt = QVBoxLayout()
            txt.setSpacing(3)
            heading = QLabel("Add VC Shims to System PATH")
            heading.setStyleSheet("font-size: 13px; font-weight: 700;")
            txt.addWidget(heading)
            desc = QLabel(
                "Ensures VC-managed versions take priority over NVM, Laragon, "
                "or any system-level version manager. Requires Administrator."
            )
            desc.setWordWrap(True)
            desc.setStyleSheet("font-size: 12px; color: #8b949e;")
            txt.addWidget(desc)
            top.addLayout(txt, 1)

            cl3.addLayout(top)

            # Status + button row
            bottom = QHBoxLayout()
            bottom.setSpacing(12)

            self._path_status = QLabel()
            self._path_status.setStyleSheet(
                "font-size: 12px; font-weight: 600; padding: 4px 12px; "
                "border-radius: 12px;"
            )
            bottom.addWidget(self._path_status)
            bottom.addStretch()

            add_btn = QPushButton("Add to System PATH")
            add_btn.setFixedHeight(34)
            add_btn.setMinimumWidth(160)
            add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            add_btn.setStyleSheet(
                "QPushButton { background: #0969da; color: #ffffff; border: none; "
                "border-radius: 6px; font-size: 13px; font-weight: 600; padding: 0 16px; }"
                "QPushButton:hover { background: #0860ca; }"
            )
            add_btn.clicked.connect(self._add_to_system_path)
            bottom.addWidget(add_btn)

            cl3.addLayout(bottom)
            layout.addWidget(card3)
            layout.addSpacing(20)

        # ── Startup & Tray ───────────────────────────────────
        layout.addWidget(_section_label("Startup & Background"))
        card5 = _card()
        cl5 = QVBoxLayout(card5)
        cl5.setContentsMargins(20, 4, 20, 4)
        cl5.setSpacing(0)

        self._startup_btn = self._toggle_row(
            cl5,
            "Run at startup",
            "Launch VC automatically when Windows starts",
            is_startup_enabled(),
            self._toggle_startup,
        )
        cl5.addWidget(_divider())
        self._tray_btn = self._toggle_row(
            cl5,
            "Minimize to tray on close",
            "Keep VC running in the background when the window is closed",
            self.config.get("minimize_to_tray", "true") == "true",
            self._toggle_tray,
        )
        layout.addWidget(card5)
        layout.addSpacing(20)

        # ── System ────────────────────────────────────────────
        layout.addWidget(_section_label("System"))
        card4 = _card()
        cl4 = QVBoxLayout(card4)
        cl4.setContentsMargins(20, 4, 20, 4)
        cl4.setSpacing(0)

        sys_info = [
            ("Platform", f"{sys.platform}  ·  {platform.machine()}"),
            ("Python",   sys.version.split()[0]),
            ("VC",       "0.1.2"),
        ]
        for i, (key, val) in enumerate(sys_info):
            row = QHBoxLayout()
            row.setContentsMargins(0, 12, 0, 12)
            k = QLabel(key)
            k.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {C['text2']};")
            k.setFixedWidth(70)
            row.addWidget(k)
            v = QLabel(val)
            v.setStyleSheet(f"font-size: 12px; color: {C['text']};")
            row.addWidget(v, 1)
            cl4.addLayout(row)
            if i < len(sys_info) - 1:
                cl4.addWidget(_divider())

        layout.addWidget(card4)
        layout.addStretch()

    # ── helpers ──────────────────────────────────────────────

    def _switch_theme(self, name: str):
        theme.apply(name)
        self.config.set("theme", name)
        self._update_theme_buttons()

    def _update_theme_buttons(self):
        current = theme.current()
        for name, btn in self._theme_btns.items():
            if name == current:
                btn.setObjectName("theme_active")
            else:
                btn.setObjectName("theme_inactive")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _sys_path_contains_shims(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                0, winreg.KEY_READ,
            )
            val, _ = winreg.QueryValueEx(key, "Path")
            winreg.CloseKey(key)
            return str(self.config.shims_dir).lower() in val.lower()
        except Exception:
            return False

    def _update_path_status(self):
        if not hasattr(self, "_path_status"):
            return
        if self._sys_path_contains_shims():
            self._path_status.setText("✔  In System PATH")
            self._path_status.setStyleSheet(
                "font-size: 12px; font-weight: 600; padding: 4px 12px; "
                "border-radius: 12px; background: #dafbe1; color: #1a7f37;"
            )
        else:
            self._path_status.setText("✘  Not in System PATH")
            self._path_status.setStyleSheet(
                "font-size: 12px; font-weight: 600; padding: 4px 12px; "
                "border-radius: 12px; background: #ffebe9; color: #d1242f;"
            )

    def _add_to_system_path(self):
        import ctypes
        shims = str(self.config.shims_dir).replace("'", "\\'")
        ps_cmd = (
            f"$p=[Environment]::GetEnvironmentVariable('Path','Machine');"
            f"if($p -notlike '*{shims}*'){{"
            f"[Environment]::SetEnvironmentVariable('Path','{shims};'+$p,'Machine')"
            f"}}"
        )
        QMessageBox.information(
            self, "Admin required",
            "A UAC prompt will appear.\n"
            "Click Yes to add VC shims to System PATH.\n\n"
            "After accepting, open a new terminal.",
        )
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell",
            f"-NoProfile -Command \"{ps_cmd}\"",
            None, 1,
        )
        self._update_path_status()

    def _toggle_row(self, parent_layout, label: str, hint: str,
                    initial: bool, callback) -> QPushButton:
        row = QHBoxLayout()
        row.setContentsMargins(0, 12, 0, 12)

        col = QVBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        col.addWidget(lbl)
        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet("font-size: 12px; color: #8b949e;")
        col.addWidget(hint_lbl)
        row.addLayout(col, 1)

        btn = QPushButton()
        btn.setFixedSize(64, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(True)
        btn.setChecked(initial)
        self._apply_toggle_style(btn)
        btn.toggled.connect(lambda checked, cb=callback, b=btn: (cb(checked), self._apply_toggle_style(b)))
        row.addWidget(btn)

        parent_layout.addLayout(row)
        return btn

    def _apply_toggle_style(self, btn: QPushButton):
        if btn.isChecked():
            btn.setText("ON")
            btn.setStyleSheet(
                "QPushButton { background: #1a7f37; color: #fff; border: none; "
                "border-radius: 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #1c8c3d; }"
            )
        else:
            btn.setText("OFF")
            btn.setStyleSheet(
                "QPushButton { background: #d0d7de; color: #57606a; border: none; "
                "border-radius: 14px; font-size: 11px; font-weight: 700; }"
                "QPushButton:hover { background: #b8c0c8; }"
            )

    def _toggle_startup(self, enabled: bool):
        set_startup(enabled)

    def _toggle_tray(self, enabled: bool):
        self.config.set("minimize_to_tray", "true" if enabled else "false")

    def on_show(self):
        self._update_theme_buttons()
        self._update_path_status()
        # Sync startup toggle with actual registry state
        if hasattr(self, "_startup_btn"):
            self._startup_btn.blockSignals(True)
            self._startup_btn.setChecked(is_startup_enabled())
            self._apply_toggle_style(self._startup_btn)
            self._startup_btn.blockSignals(False)
