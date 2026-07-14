"""Tools page: install and manage global CLI tools (pnpm, bun, deno, uv, yarn, composer)."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QScrollArea, QMessageBox, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.theme import current_colors
from ui.widgets.progress_dialog import DownloadProgressDialog
from providers.global_tools import (
    PnpmTool, BunTool, DenoTool, UvTool, YarnTool, ComposerTool,
    ToolVersion,
)


def _action_btn(text: str, obj_name: str = "") -> QPushButton:
    btn = QPushButton(text)
    if obj_name:
        btn.setObjectName(obj_name)
    btn.setFixedHeight(28)
    btn.setMinimumWidth(btn.fontMetrics().horizontalAdvance(text) + 28)
    btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    return btn


class _VersionRow(QFrame):
    def __init__(self, vi: ToolVersion, on_install, on_use, on_remove, parent=None):
        super().__init__(parent)
        C = current_colors()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet(
            f"QFrame {{ border-bottom:1px solid {C['border']}; }}"
            f"QFrame:hover {{ background:{C['hover']}; }}"
        )
        self.setFixedHeight(44)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(0)

        # Version
        ver = QLabel(f"v{vi.version}")
        ver.setFont(QFont("Consolas", 12))
        ver.setFixedWidth(96)
        row.addWidget(ver)

        # Status badge
        if vi.active:
            badge = QLabel("● Active")
            badge.setStyleSheet(
                f"background:{C['green']}22; color:{C['green']};"
                "border-radius:3px; padding:1px 8px; font-size:11px;"
            )
        elif vi.installed:
            badge = QLabel("✓ Installed")
            badge.setStyleSheet(
                f"background:{C['blue']}22; color:{C['blue']};"
                "border-radius:3px; padding:1px 8px; font-size:11px;"
            )
        else:
            badge = QLabel("—")
            badge.setStyleSheet(f"color:{C['text3']}; font-size:11px;")
        badge.setFixedWidth(98)
        row.addWidget(badge)

        # Release date
        date = QLabel(vi.release_date)
        date.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        date.setFixedWidth(96)
        row.addWidget(date)

        row.addStretch()

        # Action buttons
        if vi.installed:
            if not vi.active:
                use_btn = _action_btn("Use")
                use_btn.clicked.connect(lambda: on_use(vi.version))
                row.addWidget(use_btn)
                row.addSpacing(6)
            rm_btn = _action_btn("Remove", "danger")
            rm_btn.clicked.connect(lambda: on_remove(vi.version))
            row.addWidget(rm_btn)
        else:
            inst_btn = _action_btn("Install", "install")
            inst_btn.clicked.connect(lambda: on_install(vi.version))
            row.addWidget(inst_btn)

        row.addSpacing(4)


class _ToolTab(QWidget):
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self._tool = tool
        self._build()
        self._load()

    def _build(self):
        C = current_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Tool info card ──────────────────────────────────────────────────
        info_card = QWidget()
        info_card.setStyleSheet(
            f"background:{C['surface']}; border-bottom:1px solid {C['border']};"
        )
        info_card.setFixedHeight(72)
        card_lay = QVBoxLayout(info_card)
        card_lay.setContentsMargins(20, 10, 20, 10)
        card_lay.setSpacing(4)

        top = QHBoxLayout()
        name_lbl = QLabel(f"{self._tool.icon}  {self._tool.display_name}")
        name_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        top.addWidget(name_lbl)
        top.addSpacing(16)

        self._sys_lbl = QLabel()
        self._sys_lbl.setStyleSheet(f"color:{C['text3']}; font-size:12px;")
        top.addWidget(self._sys_lbl)
        top.addStretch()

        self._active_badge = QLabel()
        self._active_badge.setStyleSheet(
            f"background:{C['green']}22; color:{C['green']};"
            "padding:2px 10px; border-radius:4px; font-size:12px;"
        )
        self._active_badge.setVisible(False)
        top.addWidget(self._active_badge)
        card_lay.addLayout(top)

        desc_lbl = QLabel(self._tool.description)
        desc_lbl.setStyleSheet(f"color:{C['text2']}; font-size:11px;")
        card_lay.addWidget(desc_lbl)
        layout.addWidget(info_card)

        # ── Column headers ──────────────────────────────────────────────────
        col_header = QWidget()
        col_header.setStyleSheet(
            f"background:{C['card']}; border-bottom:1px solid {C['border']};"
        )
        col_header.setFixedHeight(30)
        ch_lay = QHBoxLayout(col_header)
        ch_lay.setContentsMargins(12, 0, 12, 0)
        ch_lay.setSpacing(0)
        for text, width in (("VERSION", 96), ("STATUS", 98), ("RELEASED", 96)):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color:{C['text3']}; font-size:10px; font-weight:600; letter-spacing:0.5px;"
            )
            lbl.setFixedWidth(width)
            ch_lay.addWidget(lbl)
        ch_lay.addStretch()
        layout.addWidget(col_header)

        # ── Scroll area for version rows ────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch()
        scroll.setWidget(self._rows_container)
        layout.addWidget(scroll)

        # ── Bottom info bar ─────────────────────────────────────────────────
        bar = QLabel(
            "💡  Shims written to ~/.vc/shims — already on PATH when VC is running. "
            "Restart your terminal after first install."
        )
        bar.setStyleSheet(
            f"background:{C['surface']}; color:{C['blue']}; font-size:11px;"
            f"padding:5px 16px; border-top:1px solid {C['border']};"
        )
        bar.setWordWrap(True)
        layout.addWidget(bar)

    def _load(self):
        C = current_colors()

        sys_ver = self._tool.detect_system()
        self._sys_lbl.setText(f"System: v{sys_ver}" if sys_ver else "System: not found")

        active = self._tool.current()
        if active:
            self._active_badge.setText(f"Active: v{active}")
            self._active_badge.setVisible(True)
        else:
            self._active_badge.setVisible(False)

        # Rebuild version rows (keep the trailing stretch at index -1)
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for vi in self._tool.list_versions():
            row = _VersionRow(vi,
                              on_install=self._do_install,
                              on_use=self._do_use,
                              on_remove=self._do_remove)
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)

    def _do_install(self, version: str):
        dlg = DownloadProgressDialog(self._tool, version, self)
        dlg.exec()
        self._load()

    def _do_use(self, version: str):
        if not self._tool.use(version):
            QMessageBox.warning(self, "Error",
                                f"Could not activate {self._tool.display_name} {version}.")
        self._load()

    def _do_remove(self, version: str):
        reply = QMessageBox.question(
            self, "Remove",
            f"Remove {self._tool.display_name} {version}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._tool.uninstall(version)
            self._load()

    def refresh(self):
        self._load()


class ToolsPage(QWidget):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._tools = [
            PnpmTool(config),
            BunTool(config),
            DenoTool(config),
            UvTool(config),
            YarnTool(config),
            ComposerTool(config),
        ]
        self._tabs: dict[str, _ToolTab] = {}
        self._build()

    def _build(self):
        C = current_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Page header
        header = QWidget()
        header.setStyleSheet(
            f"background:{C['surface']}; border-bottom:1px solid {C['border']};"
        )
        header.setFixedHeight(52)
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(24, 0, 24, 0)
        title = QLabel("🛠  Global Tools")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        hlay.addWidget(title)
        hlay.addStretch()
        refresh_btn = QPushButton("↺  Refresh")
        refresh_btn.setFixedHeight(30)
        refresh_btn.setMinimumWidth(88)
        refresh_btn.clicked.connect(self._refresh_current)
        hlay.addWidget(refresh_btn)
        layout.addWidget(header)

        self._tab_widget = QTabWidget()
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tab_widget)

        for tool in self._tools:
            tab = _ToolTab(tool)
            self._tabs[tool.name] = tab
            self._tab_widget.addTab(tab, f"{tool.icon}  {tool.display_name}")

    def _current_tab(self) -> _ToolTab | None:
        idx = self._tab_widget.currentIndex()
        if 0 <= idx < len(self._tools):
            return self._tabs[self._tools[idx].name]
        return None

    def _refresh_current(self):
        tab = self._current_tab()
        if tab:
            tab.refresh()

    def _on_tab_changed(self, idx: int):
        if 0 <= idx < len(self._tools):
            self._tabs[self._tools[idx].name].refresh()

    def on_show(self):
        self._refresh_current()
