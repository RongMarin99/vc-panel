from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

NAV_ITEMS = [
    ("dashboard", "Dashboard", "🏠"),
    ("versions",  "Versions",  "📦"),
    ("projects",  "Projects",  "📁"),
    ("settings",  "Settings",  "⚙"),
    ("about",     "Support ☕", ""),
]


class Sidebar(QWidget):
    page_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._buttons: dict[str, QPushButton] = {}
        self._active: str | None = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel("  VC")
        logo.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        logo.setStyleSheet("color: #58a6ff; padding: 22px 16px 4px;")
        layout.addWidget(logo)

        tagline = QLabel("  Version Controller")
        tagline.setStyleSheet("color: #6e7681; font-size: 11px; padding: 0 16px 16px;")
        layout.addWidget(tagline)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #30363d;")
        layout.addWidget(sep)
        layout.addSpacing(8)

        for page_id, label, icon in NAV_ITEMS:
            btn = QPushButton(f"  {icon}   {label}")
            btn.setObjectName("nav_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(38)
            btn.clicked.connect(lambda _, p=page_id: self._on_click(p))
            layout.addWidget(btn)
            self._buttons[page_id] = btn

        layout.addStretch()

        ver = QLabel("  v0.1.0")
        ver.setStyleSheet("color: #6e7681; font-size: 11px; padding: 12px 16px;")
        layout.addWidget(ver)

    def _on_click(self, page_id: str):
        self.set_active(page_id)
        self.page_changed.emit(page_id)

    def set_active(self, page_id: str):
        if self._active and self._active in self._buttons:
            btn = self._buttons[self._active]
            btn.setProperty("active", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._active = page_id
        if page_id in self._buttons:
            btn = self._buttons[page_id]
            btn.setProperty("active", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
