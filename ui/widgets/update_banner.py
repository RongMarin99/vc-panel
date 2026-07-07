import webbrowser

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from utils.updater import check_update, CURRENT_VERSION
import ui.theme as theme


class _CheckThread(QThread):
    found = pyqtSignal(str, str)   # (version, url)

    def run(self):
        version, url = check_update()
        if version:
            self.found.emit(version, url)


class UpdateBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self._url = ""
        self._build()
        self._start_check()

    def _build(self):
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 12, 0)
        layout.setSpacing(12)

        self._icon = QLabel("⬆")
        self._icon.setStyleSheet("font-size:16px; background:transparent;")
        layout.addWidget(self._icon)

        self._msg = QLabel("")
        self._msg.setStyleSheet("font-size:13px; font-weight:600; background:transparent;")
        layout.addWidget(self._msg)

        layout.addStretch()

        self._dl_btn = QPushButton("Download Update")
        self._dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dl_btn.setFixedHeight(28)
        self._dl_btn.clicked.connect(self._download)
        layout.addWidget(self._dl_btn)

        dismiss = QPushButton("✕")
        dismiss.setFixedSize(28, 28)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(
            "QPushButton { background:transparent; border:none; font-size:14px; }"
            "QPushButton:hover { opacity: 0.7; }"
        )
        dismiss.clicked.connect(self.hide)
        layout.addWidget(dismiss)

    def _apply_style(self):
        C = theme.current_colors()
        self.setStyleSheet(
            f"QFrame {{ background:{C['blue']}18; border-bottom:1px solid {C['blue']}44; }}"
        )
        self._msg.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{C['text']}; background:transparent;"
        )
        self._dl_btn.setStyleSheet(
            f"QPushButton {{ background:{C['blue']}; color:#fff; border:none;"
            f" border-radius:5px; padding:0 14px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C['blue']}dd; }}"
        )

    def _start_check(self):
        self._thread = _CheckThread(self)
        self._thread.found.connect(self._on_found)
        self._thread.start()

    def _on_found(self, version: str, url: str):
        self._url = url
        self._msg.setText(
            f"VC {version} is available  (you have {CURRENT_VERSION})"
        )
        self._apply_style()
        self.setVisible(True)

    def _download(self):
        if self._url:
            webbrowser.open(self._url)
