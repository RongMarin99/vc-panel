from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout
)
from PyQt6.QtCore import QThread, pyqtSignal


class _Worker(QThread):
    progress = pyqtSignal(int, int)
    done = pyqtSignal(bool)
    error = pyqtSignal(str)

    def __init__(self, manager, version: str):
        super().__init__()
        self.manager = manager
        self.version = version

    def run(self):
        try:
            ok = self.manager.install(
                self.version,
                progress_callback=lambda d, t: self.progress.emit(d, t),
            )
            self.done.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class DownloadProgressDialog(QDialog):
    def __init__(self, manager, version: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Installing {manager.display_name} {version}")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._build(manager.display_name, version)
        self._worker = _Worker(manager, version)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _build(self, name: str, version: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self.title = QLabel(f"Installing {name} {version}…")
        self.title.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(self.title)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        layout.addWidget(self.bar)

        self.detail = QLabel("Connecting…")
        self.detail.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(self.detail)

        layout.addSpacing(8)
        row = QHBoxLayout()
        row.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setEnabled(False)
        self.close_btn.clicked.connect(self.accept)
        row.addWidget(self.close_btn)
        layout.addLayout(row)

    def _on_progress(self, downloaded: int, total: int):
        self.bar.setValue(int(downloaded / total * 100))
        self.detail.setText(f"{self._fmt(downloaded)} / {self._fmt(total)}")

    def _on_done(self, ok: bool):
        self.bar.setValue(100)
        if ok:
            self.title.setText("Installation complete!")
            self.title.setStyleSheet("font-size: 14px; font-weight: 600; color: #3fb950;")
            self.detail.setText("Done.")
        else:
            self._fail("Installation failed.")

    def _on_error(self, msg: str):
        self._fail(msg)

    def _fail(self, msg: str):
        self.title.setText("Installation failed")
        self.title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f85149;")
        self.detail.setText(msg)
        self.close_btn.setEnabled(True)

    @staticmethod
    def _fmt(b: int) -> str:
        if b >= 1024 * 1024:
            return f"{b / 1048576:.1f} MB"
        return f"{b / 1024:.0f} KB"
