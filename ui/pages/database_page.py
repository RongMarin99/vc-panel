from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

import ui.theme as theme
from ui.widgets.progress_dialog import DownloadProgressDialog
from providers.mysql import MySQLService
from providers.postgresql import PostgreSQLService
from providers.redis import RedisService
from providers.mongodb import MongoDBService
from providers.base_service import BaseService, ServiceInfo

MONO = QFont("Cascadia Code")
MONO.setStyleHint(QFont.StyleHint.Monospace)
MONO.setPointSize(12)

_STATUS_COLOR = {
    "running":   "#1a7f37",
    "stopped":   "#cf222e",
    "not_found": "#6e7681",
}
_STATUS_TEXT = {
    "running":   "● Running",
    "stopped":   "◼ Stopped",
    "not_found": "○ Not Found",
}


def _make_btn(label: str, kind: str) -> QPushButton:
    C = theme.current_colors()
    btn = QPushButton(label)
    base = "border-radius:5px; font-size:12px; font-weight:600; padding:4px 0;"
    if kind == "install":
        ss = f"background:transparent; color:{C['blue']}; border:2px solid {C['blue']};"
        hv = f"background:{C['blue']}18;"
    elif kind == "use":
        ss = f"background:{C['blue']}; color:#ffffff; border:none;"
        hv = f"background:{C['blue']}dd;"
    elif kind == "green":
        ss = "background:#1a7f37; color:#fff; border:none;"
        hv = "background:#1c8c3d;"
    elif kind == "danger":
        ss = f"background:transparent; color:{C['red']}; border:1.5px solid {C['red']}; font-weight:normal;"
        hv = f"background:{C['red']}15;"
    elif kind == "outline":
        ss = f"background:transparent; color:{C['text2']}; border:1.5px solid {C['border']}; font-weight:normal;"
        hv = f"background:{C['hover']};"
    else:
        ss = hv = ""
    btn.setStyleSheet(
        f"QPushButton {{ {base} {ss} }}"
        f"QPushButton:hover {{ {hv} }}"
        f"QPushButton:disabled {{ opacity:0.4; }}"
    )
    return btn


# ── Fetch thread ──────────────────────────────────────────────────────────────

class _FetchThread(QThread):
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, service):
        super().__init__()
        self._svc = service

    def run(self):
        try:
            self.done.emit(self._svc.list_remote())
        except Exception as e:
            self.error.emit(str(e))


class _InfoThread(QThread):
    done = pyqtSignal(object)  # ServiceInfo

    def __init__(self, service):
        super().__init__()
        self._svc = service

    def run(self):
        try:
            self.done.emit(self._svc.info())
        except Exception:
            from providers.base_service import ServiceInfo
            self.done.emit(ServiceInfo("not_found", None, self._svc.default_port, None, None))


class _ActionThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, fn, label: str):
        super().__init__()
        self._fn = fn
        self._label = label

    def run(self):
        try:
            ok = self._fn()
            self.finished.emit(ok, self._label)
        except Exception as e:
            self.finished.emit(False, str(e))


# ── Per-DB Tab ────────────────────────────────────────────────────────────────

class DBVersionTab(QWidget):
    def __init__(self, service: BaseService, parent=None):
        super().__init__(parent)
        self._svc = service
        self._versions = []
        self._info: ServiceInfo | None = None
        self._build()

    def _build(self):
        C = theme.current_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(0)

        # ── Service status panel ──────────────────────────────────────────────
        self._status_panel = QFrame()
        self._status_panel.setObjectName("card")
        sp_layout = QHBoxLayout(self._status_panel)
        sp_layout.setContentsMargins(16, 12, 16, 12)
        sp_layout.setSpacing(24)

        # Status
        col1 = QVBoxLayout()
        col1.addWidget(self._mklabel("SERVICE STATUS", small=True))
        self._status_lbl = QLabel("Scanning…")
        self._status_lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{C['text3']};")
        col1.addWidget(self._status_lbl)
        sp_layout.addLayout(col1)

        # Version
        col2 = QVBoxLayout()
        col2.addWidget(self._mklabel("SYSTEM VERSION", small=True))
        self._ver_lbl = QLabel("—")
        self._ver_lbl.setFont(MONO)
        self._ver_lbl.setStyleSheet(f"font-size:14px; font-weight:700; color:{C['blue']};")
        col2.addWidget(self._ver_lbl)
        sp_layout.addLayout(col2)

        # Port
        col3 = QVBoxLayout()
        col3.addWidget(self._mklabel("PORT", small=True))
        self._port_lbl = QLabel(str(self._svc.default_port))
        self._port_lbl.setFont(MONO)
        self._port_lbl.setStyleSheet("font-size:14px; font-weight:700;")
        col3.addWidget(self._port_lbl)
        sp_layout.addLayout(col3)

        sp_layout.addStretch()

        # Action buttons
        self._start_btn = _make_btn("▶ Start", "green")
        self._start_btn.setFixedHeight(32)
        self._start_btn.setMinimumWidth(80)
        self._start_btn.setEnabled(False)
        self._start_btn.clicked.connect(self._start_sys)
        sp_layout.addWidget(self._start_btn)

        self._stop_btn = _make_btn("■ Stop", "danger")
        self._stop_btn.setFixedHeight(32)
        self._stop_btn.setMinimumWidth(80)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_sys)
        sp_layout.addWidget(self._stop_btn)

        self._port_btn = _make_btn("⚙ Port", "outline")
        self._port_btn.setFixedHeight(32)
        self._port_btn.setMinimumWidth(80)
        self._port_btn.setEnabled(False)
        self._port_btn.clicked.connect(self._change_port)
        sp_layout.addWidget(self._port_btn)

        layout.addWidget(self._status_panel)
        layout.addSpacing(16)

        # ── Version table ─────────────────────────────────────────────────────
        bar = QHBoxLayout()
        active_lbl = QLabel("Available Versions")
        active_lbl.setStyleSheet("font-size:13px; font-weight:600;")
        bar.addWidget(active_lbl)
        bar.addStretch()
        self._refresh_btn = QPushButton("↻  Refresh")
        self._refresh_btn.clicked.connect(self._load)
        bar.addWidget(self._refresh_btn)
        layout.addLayout(bar)
        layout.addSpacing(8)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Version", "Status", "Released", "Actions"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(3, 200)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(44)
        layout.addWidget(self._table)

    def _mklabel(self, text: str, small=False) -> QLabel:
        lbl = QLabel(text)
        C = theme.current_colors()
        if small:
            lbl.setStyleSheet(
                f"font-size:10px; font-weight:600; color:{C['text3']};"
                " letter-spacing:0.8px; text-transform:uppercase;"
            )
        return lbl

    def refresh(self):
        self._load_info()
        if not self._versions:
            self._load()
        else:
            self._refresh_rows()

    def _load_info(self):
        self._status_lbl.setText("Scanning…")
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._port_btn.setEnabled(False)
        self._info_thread = _InfoThread(self._svc)
        self._info_thread.done.connect(self._on_info)
        self._info_thread.start()

    def _on_info(self, info: ServiceInfo):
        self._info = info
        C = theme.current_colors()
        color = _STATUS_COLOR.get(info.status, C["text3"])
        text  = _STATUS_TEXT.get(info.status, "Unknown")
        self._status_lbl.setText(text)
        self._status_lbl.setStyleSheet(f"font-size:13px; font-weight:600; color:{color};")
        self._ver_lbl.setText(info.version or "—")
        self._port_lbl.setText(str(info.port))

        has_svc = bool(info.service_key)
        self._start_btn.setEnabled(has_svc and info.status == "stopped")
        self._stop_btn.setEnabled(has_svc and info.status == "running")
        self._port_btn.setEnabled(bool(info.config_path))

    def _start_sys(self):
        self._run_svc_action(self._svc.start, "start")

    def _stop_sys(self):
        self._run_svc_action(self._svc.stop, "stop")

    def _run_svc_action(self, fn, label: str):
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._action_thread = _ActionThread(fn, label)
        self._action_thread.finished.connect(self._on_svc_action_done)
        self._action_thread.start()

    def _on_svc_action_done(self, ok: bool, label: str):
        if not ok:
            QMessageBox.warning(self, "Error",
                f"Failed to {label} {self._svc.display_name}.\n"
                "Try running VC as Administrator.")
        self._load_info()

    def _change_port(self):
        from ui.pages.db_port_dialog import DBPortDialog
        port = self._info.port if self._info else self._svc.default_port
        dlg = DBPortDialog(self._svc.display_name, port, self)
        if dlg.exec() == dlg.DialogCode.Accepted and dlg.selected_port():
            ok = self._svc.set_port(dlg.selected_port())
            if ok:
                self._load_info()
            else:
                QMessageBox.warning(self, "Error",
                    "Could not write config file.\nRun VC as Administrator.")

    def _load(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Loading…")
        self._ft = _FetchThread(self._svc)
        self._ft.done.connect(self._on_fetched)
        self._ft.error.connect(lambda e: (
            self._refresh_btn.setEnabled(True),
            self._refresh_btn.setText("↻  Refresh"),
            QMessageBox.warning(self, "Error", e),
        ))
        self._ft.start()

    def _on_fetched(self, versions):
        self._versions = versions
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText("↻  Refresh")
        self._populate(versions)

    def _populate(self, versions):
        self._table.setRowCount(0)
        for vi in versions:
            row = self._table.rowCount()
            self._table.insertRow(row)

            v_item = QTableWidgetItem(vi.version)
            v_item.setFont(MONO)
            if vi.active:
                v_item.setForeground(QColor("#3fb950"))
            self._table.setItem(row, 0, v_item)

            if vi.active:
                s, c = "● Running", "#3fb950"
            elif vi.installed:
                s, c = "Installed", "#58a6ff"
            else:
                s, c = "—", "#6e7681"
            s_item = QTableWidgetItem(s)
            s_item.setForeground(QColor(c))
            self._table.setItem(row, 1, s_item)

            d_item = QTableWidgetItem(vi.release_date or "—")
            d_item.setForeground(QColor("#8b949e"))
            self._table.setItem(row, 2, d_item)

            self._table.setCellWidget(row, 3, self._action_widget(vi))

    def _action_widget(self, vi) -> QWidget:
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        sp = (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        if vi.installed:
            if vi.active:
                stop = _make_btn("Stop", "danger")
                stop.setSizePolicy(*sp)
                stop.clicked.connect(lambda _, v=vi.version: self._stop_vc(v))
                layout.addWidget(stop, 1)
            else:
                start = _make_btn("Start", "green")
                start.setSizePolicy(*sp)
                start.clicked.connect(lambda _, v=vi.version: self._start_vc(v))
                layout.addWidget(start, 1)

            remove = _make_btn("Remove", "danger")
            remove.setSizePolicy(*sp)
            remove.clicked.connect(lambda _, v=vi.version: self._remove(v))
            layout.addWidget(remove, 1)
        else:
            install = _make_btn("Install", "install")
            install.setSizePolicy(*sp)
            install.clicked.connect(lambda _, v=vi.version: self._install(v))
            layout.addWidget(install, 1)
        return w

    def _install(self, version: str):
        dlg = DownloadProgressDialog(self._svc, version, self)
        dlg.exec()
        self._load()
        self._load_info()

    def _remove(self, version: str):
        if QMessageBox.question(
            self, "Confirm", f"Remove {self._svc.display_name} {version}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._svc.uninstall_vc(version)
            self._load()
            self._load_info()

    def _start_vc(self, version: str):
        ok = self._svc.start_vc(version)
        if not ok:
            QMessageBox.warning(self, "Error",
                f"Could not start {self._svc.display_name} {version}.\n"
                "Service may not be registered. Run VC as Administrator.")
        self._refresh_rows()

    def _stop_vc(self, version: str):
        self._svc.stop_vc(version)
        self._refresh_rows()

    def _refresh_rows(self):
        from providers._svc_win import sc_query
        for row in range(self._table.rowCount()):
            ver = self._table.item(row, 0).text()
            svc_name = self._svc._vc_svc(ver)  # noqa: protected
            is_running = sc_query(svc_name) == "running"
            dest = self._svc.versions_root / ver
            is_inst = (dest / ".vc_managed").exists()

            if is_running:
                s, c = "● Running", "#3fb950"
                self._table.item(row, 0).setForeground(QColor(c))
            elif is_inst:
                s, c = "Installed", "#58a6ff"
                self._table.item(row, 0).setForeground(QColor("#e6edf3"))
            else:
                s, c = "—", "#6e7681"
                self._table.item(row, 0).setForeground(QColor("#e6edf3"))

            self._table.item(row, 1).setText(s)
            self._table.item(row, 1).setForeground(QColor(c))

            from core.base_manager import VersionInfo
            vi = VersionInfo(version=ver, installed=is_inst, active=is_running)
            self._table.setCellWidget(row, 3, self._action_widget(vi))


# ── Main page ─────────────────────────────────────────────────────────────────

class DatabasePage(QWidget):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._services: list[BaseService] = [
            MySQLService(config),
            PostgreSQLService(config),
            RedisService(config),
            MongoDBService(config),
        ]
        self._tabs: dict[str, DBVersionTab] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        title = QLabel("Databases")
        title.setStyleSheet("font-size:24px; font-weight:700;")
        layout.addWidget(title)
        sub = QLabel("Install and manage local database services")
        sub.setStyleSheet("color:#8b949e; font-size:13px; margin-top:4px; margin-bottom:24px;")
        layout.addWidget(sub)

        self._tab_widget = QTabWidget()
        for svc in self._services:
            tab = DBVersionTab(svc)
            self._tabs[svc.name] = tab
            self._tab_widget.addTab(tab, f"{svc.icon}  {svc.display_name}")
        layout.addWidget(self._tab_widget)

    def on_show(self):
        for tab in self._tabs.values():
            tab.refresh()
