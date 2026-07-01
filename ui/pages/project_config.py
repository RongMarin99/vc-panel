from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QComboBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QMessageBox
)
from PyQt6.QtCore import Qt


class _AddDialog(QDialog):
    def __init__(self, registry, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.setWindowTitle("Add Project")
        self.setMinimumWidth(440)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("My Project")
        form.addRow("Name:", self._name)

        path_row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setPlaceholderText("/path/to/project")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self._path)
        path_row.addWidget(browse)
        form.addRow("Path:", path_row)
        layout.addLayout(form)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Version overrides (optional):"))

        self._combos: dict[str, QComboBox] = {}
        ver_form = QFormLayout()
        for name, mgr in self.registry.all().items():
            combo = QComboBox()
            combo.addItem("— (global)")
            for vi in mgr.list_installed():
                combo.addItem(vi.version)
            self._combos[name] = combo
            ver_form.addRow(f"{mgr.display_name}:", combo)
        layout.addLayout(ver_form)

        layout.addSpacing(8)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        p = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if p:
            self._path.setText(p)
            if not self._name.text():
                self._name.setText(Path(p).name)

    def result_data(self) -> dict:
        versions = {
            name: combo.currentText()
            for name, combo in self._combos.items()
            if combo.currentIndex() > 0
        }
        return {
            "name": self._name.text().strip(),
            "path": self._path.text().strip(),
            "versions": versions,
        }


class ProjectConfigPage(QWidget):
    def __init__(self, registry, config, db, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.config = config
        self.db = db
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)

        header = QHBoxLayout()
        vbox = QVBoxLayout()
        title = QLabel("Projects")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        vbox.addWidget(title)
        sub = QLabel("Per-project version overrides")
        sub.setStyleSheet("color: #8b949e; font-size: 13px; margin-top: 4px;")
        vbox.addWidget(sub)
        header.addLayout(vbox)
        header.addStretch()
        add_btn = QPushButton("+ Add Project")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._add)
        header.addWidget(add_btn)
        layout.addLayout(header)
        layout.addSpacing(20)

        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(["Name", "Path", "PHP", "Node", "Python", "Java", ".NET", ""])
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, 7):
            h.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

    def on_show(self):
        self._load()

    def _load(self):
        self._table.setRowCount(0)
        self._projects = self.db.list_projects()
        for proj in self._projects:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(proj["name"]))
            from PyQt6.QtGui import QColor
            path_item = QTableWidgetItem(proj["path"])
            path_item.setForeground(QColor("#8b949e"))
            self._table.setItem(row, 1, path_item)
            for col, tool in enumerate(["php", "node", "python", "java", "dotnet"], 2):
                ver = proj["versions"].get(tool, "—")
                item = QTableWidgetItem(ver)
                if ver != "—":
                    item.setForeground(QColor("#58a6ff"))
                self._table.setItem(row, col, item)
            # Delete button
            del_btn = QPushButton("✕")
            del_btn.setObjectName("danger")
            del_btn.setFixedSize(28, 28)
            del_btn.clicked.connect(lambda _, pid=proj["id"]: self._remove(pid))
            self._table.setCellWidget(row, 7, del_btn)

    def _add(self):
        dlg = _AddDialog(self.registry, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.result_data()
            if not data["name"] or not data["path"]:
                QMessageBox.warning(self, "Invalid", "Name and path are required.")
                return
            pid = self.db.add_project(data["name"], data["path"])
            for tool, ver in data["versions"].items():
                self.db.set_project_version(pid, tool, ver)
            self._load()

    def _remove(self, project_id: int):
        if QMessageBox.question(
            self, "Confirm", "Remove this project?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.db.remove_project(project_id)
            self._load()
