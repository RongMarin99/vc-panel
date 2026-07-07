import re
import shutil
import subprocess
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea, QPushButton,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

TOOL_ICONS = {
    "php":    "🐘",
    "node":   "⬢",
    "python": "🐍",
    "java":   "☕",
    "dotnet": "🔷",
    "go":     "🐹",
    "rust":   "🦀",
}

_SYS_CMDS = {
    "php":    (["php",    "--version"],  r"PHP (\d+\.\d+\.\d+)"),
    "node":   (["node",   "--version"],  r"v?(\d+\.\d+\.\d+)"),
    "python": (["python", "--version"],  r"Python (\d+\.\d+\.\d+)"),
    "java":   (["java",   "-version"],   r'"(\d+[\.\d]*)"'),
    "dotnet": (["dotnet", "--version"],  r"(\d+\.\d+\.\d+)"),
    "go":     (["go",     "version"],    r"go(\d+\.\d+(?:\.\d+)?)"),
    "rust":   (["rustc",  "--version"],  r"rustc (\d+\.\d+\.\d+)"),
}

_STATUS_COLOR = {
    "running":   "#1a7f37",
    "stopped":   "#cf222e",
    "not_found": "#6e7681",
}
_STATUS_TEXT = {
    "running":   "● Running",
    "stopped":   "◼ Stopped",
    "not_found": "○ Not Installed",
}


def _system_version(tool: str) -> str | None:
    args, pattern = _SYS_CMDS[tool]
    exe = shutil.which(args[0])
    if not exe:
        return None
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        out = subprocess.run(
            [exe] + args[1:], capture_output=True, text=True, timeout=3,
            creationflags=flags,
        )
        text = out.stderr + out.stdout
        m = re.search(pattern, text)
        return m.group(1) if m else None
    except Exception:
        return None


# ── Language card ─────────────────────────────────────────────────────────────

class ToolCard(QFrame):
    def __init__(self, name: str, manager, parent=None):
        super().__init__(parent)
        self._name = name
        self._manager = manager
        self.setObjectName("card")
        self.setMinimumWidth(230)
        self.setMaximumWidth(310)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(0)

        header = QHBoxLayout()
        icon = QLabel(TOOL_ICONS.get(name, "📦"))
        icon.setStyleSheet("font-size: 20px;")
        header.addWidget(icon)
        title = QLabel(f"  {manager.display_name}")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        layout.addSpacing(14)

        managed = manager.current()
        vc_row = QHBoxLayout()
        vc_label = QLabel("Managed")
        vc_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #8b949e; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        vc_row.addWidget(vc_label)
        vc_row.addStretch()
        layout.addLayout(vc_row)
        layout.addSpacing(4)

        if managed:
            ver_lbl = QLabel(managed)
            ver_lbl.setStyleSheet(
                "font-family: 'Cascadia Code', Consolas, monospace; "
                "font-size: 20px; font-weight: 700; color: #0969da;"
            )
            layout.addWidget(ver_lbl)
            badge = QLabel("● Active")
            badge.setStyleSheet("color: #1a7f37; font-size: 12px;")
            layout.addWidget(badge)
        else:
            none_lbl = QLabel("Not set")
            none_lbl.setStyleSheet("font-size: 13px; color: #9198a1;")
            layout.addWidget(none_lbl)

        layout.addSpacing(14)

        sys_row = QHBoxLayout()
        sys_label = QLabel("System (PATH)")
        sys_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #8b949e; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        sys_row.addWidget(sys_label)
        sys_row.addStretch()
        layout.addLayout(sys_row)
        layout.addSpacing(4)

        sys_ver = _system_version(name)
        sys_lbl = QLabel(sys_ver if sys_ver else "Not found")
        if sys_ver:
            sys_lbl.setStyleSheet(
                "font-family: 'Cascadia Code', Consolas, monospace; "
                "font-size: 14px; font-weight: 600; color: #656d76;"
            )
        else:
            sys_lbl.setStyleSheet("font-size: 13px; color: #9198a1;")
        layout.addWidget(sys_lbl)

        layout.addSpacing(14)

        installed = manager.list_installed()
        count = QLabel(
            f"{len(installed)} version{'s' if len(installed) != 1 else ''} installed"
        )
        count.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(count)
        layout.addStretch()

    def _show_context_menu(self, pos):
        if self._name != "php":
            return
        version = self._manager.current()
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)

        ext_action = menu.addAction("⚙  Extensions")
        ext_action.setEnabled(bool(version))
        settings_action = menu.addAction("📄  Settings  (upload size, limits)")
        settings_action.setEnabled(bool(version))

        if not version:
            menu.addSeparator()
            note = menu.addAction("No active PHP version")
            note.setEnabled(False)

        action = menu.exec(self.mapToGlobal(pos))
        if not action or not version:
            return

        install_path = self._manager.install_path(version)
        if action == ext_action:
            from ui.pages.php_extensions_dialog import PHPExtensionsDialog
            PHPExtensionsDialog(version, install_path, self).exec()
        elif action == settings_action:
            from ui.pages.php_settings_dialog import PHPSettingsDialog
            PHPSettingsDialog(version, install_path, self).exec()


# ── Database card (compact dashboard widget) ──────────────────────────────────

class _DBScanThread(QThread):
    done = pyqtSignal(list)

    def __init__(self, services):
        super().__init__()
        self._services = services

    def run(self):
        result = []
        for svc in self._services:
            try:
                result.append((svc, svc.info()))
            except Exception:
                from providers.base_service import ServiceInfo
                result.append((svc, ServiceInfo("not_found", None, svc.default_port, None, None)))
        self.done.emit(result)


class _SvcActionThread(QThread):
    finished = pyqtSignal()

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self._fn()
        except Exception:
            pass
        self.finished.emit()


class DBCard(QFrame):
    action_done = pyqtSignal()

    def __init__(self, service, info, parent=None):
        super().__init__(parent)
        self._svc = service
        self._info = info
        self.setObjectName("card")
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(0)

        header = QHBoxLayout()
        icon = QLabel(self._svc.icon)
        icon.setStyleSheet("font-size:18px;")
        header.addWidget(icon)
        name = QLabel(f"  {self._svc.display_name}")
        name.setStyleSheet("font-size:14px; font-weight:700;")
        header.addWidget(name)
        header.addStretch()
        layout.addLayout(header)
        layout.addSpacing(8)

        color = _STATUS_COLOR.get(self._info.status, "#6e7681")
        text  = _STATUS_TEXT.get(self._info.status, "Unknown")
        status = QLabel(text)
        status.setStyleSheet(f"color:{color}; font-size:12px; font-weight:600;")
        layout.addWidget(status)
        layout.addSpacing(10)

        port_row = QHBoxLayout()
        port_key = QLabel("PORT")
        port_key.setStyleSheet("font-size:10px; color:#8b949e; font-weight:600; letter-spacing:0.5px;")
        port_row.addWidget(port_key)
        port_row.addStretch()
        port_val = QLabel(str(self._info.port))
        port_val.setStyleSheet("font-family:Consolas,monospace; font-size:12px; font-weight:600;")
        port_row.addWidget(port_val)
        layout.addLayout(port_row)
        layout.addSpacing(12)

        has_svc = bool(self._info.service_key)
        if has_svc:
            btn_row = QHBoxLayout()
            btn_row.setSpacing(6)
            if self._info.status == "running":
                btn = QPushButton("Stop")
                btn.setFixedHeight(26)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton { background:transparent; color:#cf222e;"
                    " border:1px solid #cf222e; border-radius:4px;"
                    " font-size:11px; padding:0 10px; }"
                    "QPushButton:hover { background:#cf222e15; }"
                )
                btn.clicked.connect(lambda: self._do(self._svc.stop))
                btn_row.addWidget(btn)
            else:
                btn = QPushButton("Start")
                btn.setFixedHeight(26)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    "QPushButton { background:#1a7f37; color:#fff; border:none;"
                    " border-radius:4px; font-size:11px; padding:0 10px; }"
                    "QPushButton:hover { background:#1c8c3d; }"
                )
                btn.clicked.connect(lambda: self._do(self._svc.start))
                btn_row.addWidget(btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)
        elif self._info.status == "not_found":
            note = QLabel("Not installed")
            note.setStyleSheet("font-size:11px; color:#6e7681; font-style:italic;")
            layout.addWidget(note)

        layout.addStretch()

    def _do(self, fn):
        self._thread = _SvcActionThread(fn)
        self._thread.finished.connect(self.action_done.emit)
        self._thread.start()


# ── Dashboard page ────────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    def __init__(self, registry, config, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.config = config
        self._db_services = []
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        sub = QLabel("Active environments at a glance")
        sub.setStyleSheet("color: #8b949e; font-size: 13px; margin-top: 4px;")
        layout.addWidget(sub)
        layout.addSpacing(28)

        # ── Languages ─────────────────────────────────────────────────────────
        layout.addWidget(self._section_header("Languages", "🔧"))
        layout.addSpacing(12)
        self._lang_grid = QGridLayout()
        self._lang_grid.setSpacing(16)
        layout.addLayout(self._lang_grid)
        layout.addSpacing(32)

        # ── Databases ─────────────────────────────────────────────────────────
        db_row = QHBoxLayout()
        db_row.addWidget(self._section_header("Databases", "🗄"))
        db_row.addStretch()
        self._db_refresh_btn = QPushButton("↻")
        self._db_refresh_btn.setFixedSize(28, 28)
        self._db_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._db_refresh_btn.setToolTip("Refresh database status")
        self._db_refresh_btn.clicked.connect(self._scan_dbs)
        db_row.addWidget(self._db_refresh_btn)
        layout.addLayout(db_row)
        layout.addSpacing(12)

        self._db_grid = QGridLayout()
        self._db_grid.setSpacing(16)
        layout.addLayout(self._db_grid)
        layout.addSpacing(28)

        # Shims bar
        shims_bar = QFrame()
        shims_bar.setObjectName("card")
        bar_layout = QHBoxLayout(shims_bar)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        bar_layout.addWidget(QLabel("⚡"))
        shims_path = QLabel(f"Shims: {self.config.shims_dir}")
        shims_path.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px; color: #8b949e;"
        )
        bar_layout.addWidget(shims_path)
        bar_layout.addStretch()
        layout.addWidget(shims_bar)

        layout.addStretch()

    def _section_header(self, text: str, icon: str) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size:15px;")
        row.addWidget(icon_lbl)
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size:15px; font-weight:700;")
        row.addWidget(lbl)
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#30363d;")
        row.addWidget(sep, 1)
        return w

    def on_show(self):
        # Rebuild language cards
        while self._lang_grid.count():
            item = self._lang_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (name, mgr) in enumerate(self.registry.all().items()):
            row, col = divmod(i, 3)
            self._lang_grid.addWidget(ToolCard(name, mgr), row, col)

        # Lazy-init DB services
        if not self._db_services:
            from providers.mysql import MySQLService
            from providers.postgresql import PostgreSQLService
            from providers.redis import RedisService
            from providers.mongodb import MongoDBService
            self._db_services = [
                MySQLService(self.config),
                PostgreSQLService(self.config),
                RedisService(self.config),
                MongoDBService(self.config),
            ]

        self._scan_dbs()

    def _scan_dbs(self):
        self._db_refresh_btn.setEnabled(False)
        # Show placeholders
        while self._db_grid.count():
            item = self._db_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, svc in enumerate(self._db_services):
            ph = QFrame()
            ph.setObjectName("card")
            ph.setMinimumWidth(200)
            ph.setMaximumWidth(300)
            ph_layout = QVBoxLayout(ph)
            ph_layout.setContentsMargins(16, 14, 16, 14)
            lbl = QLabel(f"{svc.icon}  {svc.display_name}")
            lbl.setStyleSheet("font-size:13px; font-weight:600;")
            ph_layout.addWidget(lbl)
            scanning = QLabel("Scanning…")
            scanning.setStyleSheet("color:#8b949e; font-size:12px;")
            ph_layout.addWidget(scanning)
            row, col = divmod(i, 4)
            self._db_grid.addWidget(ph, row, col)

        self._db_scan_thread = _DBScanThread(self._db_services)
        self._db_scan_thread.done.connect(self._on_db_scanned)
        self._db_scan_thread.start()

    def _on_db_scanned(self, results):
        self._db_refresh_btn.setEnabled(True)
        while self._db_grid.count():
            item = self._db_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (svc, info) in enumerate(results):
            card = DBCard(svc, info)
            card.action_done.connect(self._scan_dbs)
            row, col = divmod(i, 4)
            self._db_grid.addWidget(card, row, col)
