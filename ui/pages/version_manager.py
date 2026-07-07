from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont

import ui.theme as theme
from ui.widgets.progress_dialog import DownloadProgressDialog
from ui.pages.php_extensions_dialog import PHPExtensionsDialog
from ui.pages.php_settings_dialog import PHPSettingsDialog

TOOL_ICONS = {"php": "🐘", "node": "⬢", "python": "🐍", "java": "☕", "dotnet": "🔷", "go": "🐹", "rust": "🦀"}
MONO = QFont("Cascadia Code")
MONO.setStyleHint(QFont.StyleHint.Monospace)
MONO.setPointSize(12)


def _make_btn(label: str, kind: str) -> QPushButton:
    """Inline-styled button — bypasses QSS cascade so text is always visible."""
    btn = QPushButton(label)
    C = theme.current_colors()
    base = "border-radius:5px; font-size:12px; font-weight:600; padding:4px 0px;"
    if kind == "install":
        ss = f"background:transparent; color:{C['blue']}; border:2px solid {C['blue']};"
        hover = f"background:{C['blue']}18;"
    elif kind == "use":
        ss = f"background:{C['blue']}; color:#ffffff; border:none;"
        hover = f"background:{C['blue']}dd;"
    elif kind == "danger":
        ss = f"background:transparent; color:{C['red']}; border:1.5px solid {C['red']}; font-weight:normal;"
        hover = f"background:{C['red']}15;"
    elif kind == "ext":
        ss = f"background:transparent; color:{C['green']}; border:1.5px solid {C['green']}; font-weight:normal;"
        hover = f"background:{C['green']}15;"
    else:
        ss = hover = ""
    btn.setStyleSheet(
        f"QPushButton {{ {base} {ss} }}"
        f"QPushButton:hover {{ {hover} }}"
    )
    return btn


class _FetchThread(QThread):
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

    def run(self):
        try:
            self.done.emit(self.manager.list_remote())
        except Exception as e:
            self.error.emit(str(e))


class ToolTab(QWidget):
    def __init__(self, name: str, manager, parent=None):
        super().__init__(parent)
        self.name = name
        self.manager = manager
        self._versions = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)

        bar = QHBoxLayout()
        self._active_lbl = QLabel("Active: —")
        self._active_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")
        bar.addWidget(self._active_lbl)
        bar.addStretch()
        self._refresh_btn = QPushButton("↻  Refresh")
        self._refresh_btn.clicked.connect(self._load_remote)
        bar.addWidget(self._refresh_btn)
        layout.addLayout(bar)
        layout.addSpacing(10)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Version", "Status", "Released", "Actions"])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(3, 290 if self.name == "php" else 170)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(46)
        self._table.verticalHeader().setMinimumSectionSize(46)
        layout.addWidget(self._table)

        self._update_active_label()

    def _update_active_label(self):
        cur = self.manager.current()
        if cur:
            self._active_lbl.setText(f"Active: {cur}")
            self._active_lbl.setStyleSheet("color: #3fb950; font-size: 12px;")
        else:
            self._active_lbl.setText("Active: none")
            self._active_lbl.setStyleSheet("color: #8b949e; font-size: 12px;")

    def _load_remote(self):
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText("Loading…")
        self._ft = _FetchThread(self.manager)
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
        current = self.manager.current()
        for vi in versions:
            row = self._table.rowCount()
            self._table.insertRow(row)

            v_item = QTableWidgetItem(vi.version)
            v_item.setFont(MONO)
            if vi.active:
                v_item.setForeground(QColor("#3fb950"))
            self._table.setItem(row, 0, v_item)

            if vi.active:
                status, color = "● Active", "#3fb950"
            elif vi.installed:
                status, color = "Installed", "#58a6ff"
            else:
                status, color = "—", "#6e7681"
            s_item = QTableWidgetItem(status)
            s_item.setForeground(QColor(color))
            self._table.setItem(row, 1, s_item)

            d_item = QTableWidgetItem(vi.release_date or "—")
            d_item.setForeground(QColor("#8b949e"))
            self._table.setItem(row, 2, d_item)

            self._table.setCellWidget(row, 3, self._action_widget(vi.version, vi.installed, vi.active))

    def _action_widget(self, version: str, installed: bool, active: bool) -> QWidget:
        w = QWidget()
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QHBoxLayout(w)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)
        _sp = (QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if installed:
            if not active:
                u = _make_btn("Use", "use")
                u.setSizePolicy(*_sp)
                u.clicked.connect(lambda _, v=version: self._use(v))
                layout.addWidget(u, 1)
            if self.name == "php":
                e = _make_btn("Ext", "ext")
                e.setSizePolicy(*_sp)
                e.clicked.connect(lambda _, v=version: self._open_extensions(v))
                layout.addWidget(e, 1)
                s = _make_btn("INI", "ext")
                s.setSizePolicy(*_sp)
                s.clicked.connect(lambda _, v=version: self._open_settings(v))
                layout.addWidget(s, 1)
            d = _make_btn("Remove", "danger")
            d.setSizePolicy(*_sp)
            d.clicked.connect(lambda _, v=version: self._uninstall(v))
            layout.addWidget(d, 1)
        else:
            i = _make_btn("Install", "install")
            i.setSizePolicy(*_sp)
            i.clicked.connect(lambda _, v=version: self._install(v))
            layout.addWidget(i, 1)
        return w

    def _install(self, version: str):
        dlg = DownloadProgressDialog(self.manager, version, self)
        dlg.exec()
        self._refresh_rows()

    def _use(self, version: str):
        self.manager.use(version)
        self._update_active_label()
        self._refresh_rows()
        QMessageBox.information(
            self, "Version switched",
            f"{self.manager.display_name} {version} is now active.\n\n"
            "Open a new terminal for changes to take effect.\n\n"
            "If NVM, Laragon, or another version manager is active, "
            "its PATH entries may override VC. Disable them or run VC as Administrator.",
        )

    def _uninstall(self, version: str):
        if QMessageBox.question(
            self, "Confirm", f"Remove {self.name} {version}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.manager.uninstall(version)
            self._update_active_label()
            self._refresh_rows()

    def _open_extensions(self, version: str):
        install_path = self.manager.install_path(version)
        PHPExtensionsDialog(version, install_path, self).exec()

    def _open_settings(self, version: str):
        install_path = self.manager.install_path(version)
        PHPSettingsDialog(version, install_path, self).exec()

    def _refresh_rows(self):
        installed = {v.version for v in self.manager.list_installed()}
        current = self.manager.current()
        for row in range(self._table.rowCount()):
            ver = self._table.item(row, 0).text()
            is_inst = ver in installed
            is_act = ver == current
            if is_act:
                s, c = "● Active", "#3fb950"
                self._table.item(row, 0).setForeground(QColor(c))
            elif is_inst:
                s, c = "Installed", "#58a6ff"
                self._table.item(row, 0).setForeground(QColor("#e6edf3"))
            else:
                s, c = "—", "#6e7681"
                self._table.item(row, 0).setForeground(QColor("#e6edf3"))
            self._table.item(row, 1).setText(s)
            self._table.item(row, 1).setForeground(QColor(c))
            self._table.setCellWidget(row, 3, self._action_widget(ver, is_inst, is_act))

    def refresh(self):
        self._update_active_label()
        if not self._versions:
            installed = self.manager.list_installed()
            if installed:
                self._populate(installed)
            self._load_remote()
        else:
            self._refresh_rows()


class VersionManagerPage(QWidget):
    def __init__(self, registry, config, parent=None):
        super().__init__(parent)
        self.registry = registry
        self._tabs: dict[str, ToolTab] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)

        title = QLabel("Version Manager")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        sub = QLabel("Install, remove, and switch between versions")
        sub.setStyleSheet("color: #8b949e; font-size: 13px; margin-top: 4px; margin-bottom: 20px;")
        layout.addWidget(sub)

        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        for name, mgr in self.registry.all().items():
            tab = ToolTab(name, mgr)
            self._tabs[name] = tab
            self._tab_widget.addTab(tab, f"{TOOL_ICONS.get(name, '📦')}  {mgr.display_name}")

    def on_show(self):
        for tab in self._tabs.values():
            tab.refresh()
