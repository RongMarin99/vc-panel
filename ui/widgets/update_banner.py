import tempfile
from pathlib import Path

from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from utils.updater import check_update, download_installer, apply_update, CURRENT_VERSION
import ui.theme as theme


class _CheckThread(QThread):
    found = pyqtSignal(str, str)   # (version, installer_url)

    def run(self):
        version, url = check_update()
        if version:
            self.found.emit(version, url)


class _DownloadThread(QThread):
    progress = pyqtSignal(int, int)  # (downloaded, total)
    done     = pyqtSignal(bool)
    error    = pyqtSignal(str)

    def __init__(self, url: str, dest: Path):
        super().__init__()
        self._url  = url
        self._dest = dest

    def run(self):
        try:
            ok = download_installer(
                self._url, self._dest,
                progress_cb=lambda d, t: self.progress.emit(d, t),
            )
            self.done.emit(ok)
        except Exception as e:
            self.error.emit(str(e))


class UpdateBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self._url      = ""
        self._version  = ""
        self._dest: Path | None = None
        self._build()
        self._start_check()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self.setFixedHeight(44)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        # ── Row 1: message + buttons ─────────────────────────────────────────
        self._row1 = QFrame()
        self._row1.setFixedHeight(44)
        row = QHBoxLayout(self._row1)
        row.setContentsMargins(20, 0, 12, 0)
        row.setSpacing(12)

        QLabel("⬆", self._row1).setStyleSheet("font-size:16px; background:transparent;")
        row.addWidget(QLabel("⬆"))

        self._msg = QLabel("")
        self._msg.setStyleSheet("font-size:13px; font-weight:600; background:transparent;")
        row.addWidget(self._msg)
        row.addStretch()

        self._update_btn = QPushButton("⬇  Update Now")
        self._update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_btn.setFixedHeight(28)
        self._update_btn.clicked.connect(self._start_download)
        row.addWidget(self._update_btn)

        dismiss = QPushButton("✕")
        dismiss.setFixedSize(28, 28)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(
            "QPushButton { background:transparent; border:none; font-size:14px; }"
        )
        dismiss.clicked.connect(self.hide)
        row.addWidget(dismiss)
        self._outer.addWidget(self._row1)

        # ── Row 2: download progress (hidden until download starts) ──────────
        self._row2 = QFrame()
        self._row2.setFixedHeight(36)
        self._row2.setVisible(False)
        prow = QHBoxLayout(self._row2)
        prow.setContentsMargins(20, 4, 20, 4)
        prow.setSpacing(12)

        self._dl_label = QLabel("Downloading…")
        self._dl_label.setStyleSheet("font-size:12px; background:transparent;")
        prow.addWidget(self._dl_label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        prow.addWidget(self._bar)

        self._pct_label = QLabel("0%")
        self._pct_label.setFixedWidth(36)
        self._pct_label.setStyleSheet("font-size:12px; background:transparent;")
        prow.addWidget(self._pct_label)
        self._outer.addWidget(self._row2)

    def _apply_style(self):
        C = theme.current_colors()
        self.setStyleSheet(
            f"QFrame {{ background:{C['blue']}18; border-bottom:1px solid {C['blue']}44; }}"
        )
        self._msg.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{C['text']}; background:transparent;"
        )
        self._update_btn.setStyleSheet(
            f"QPushButton {{ background:{C['blue']}; color:#fff; border:none;"
            f" border-radius:5px; padding:0 14px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{C['blue']}dd; }}"
        )

    # ── Update check ──────────────────────────────────────────────────────────

    def _start_check(self):
        self._check_thread = _CheckThread(self)
        self._check_thread.found.connect(self._on_found)
        self._check_thread.start()

    def _on_found(self, version: str, url: str):
        self._version = version
        self._url     = url
        self._msg.setText(
            f"VC {version} available  —  you have {CURRENT_VERSION}"
        )
        self._apply_style()
        self.setVisible(True)

    # ── Download + apply ──────────────────────────────────────────────────────

    def _start_download(self):
        if not self._url:
            return

        # Prepare temp path
        tmp_dir  = Path(tempfile.gettempdir())
        self._dest = tmp_dir / f"VC-Setup-{self._version}.exe"

        # Switch UI to download mode
        self._update_btn.setEnabled(False)
        self._update_btn.setText("Downloading…")
        self._row2.setVisible(True)
        self.setFixedHeight(80)

        self._dl_thread = _DownloadThread(self._url, self._dest)
        self._dl_thread.progress.connect(self._on_progress)
        self._dl_thread.done.connect(self._on_download_done)
        self._dl_thread.error.connect(self._on_download_error)
        self._dl_thread.start()

    def _on_progress(self, done: int, total: int):
        pct = int(done / total * 100)
        self._bar.setValue(pct)
        self._pct_label.setText(f"{pct}%")
        mb = done / 1_048_576
        self._dl_label.setText(f"Downloading  {mb:.1f} MB…")

    def _on_download_done(self, ok: bool):
        if ok and self._dest and self._dest.exists():
            self._dl_label.setText("Installing… VC will restart automatically.")
            self._bar.setValue(100)
            self._pct_label.setText("100%")
            # Small delay so user sees the message, then apply
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1200, lambda: apply_update(self._dest))
        else:
            self._on_download_error("Download incomplete.")

    def _on_download_error(self, msg: str):
        import webbrowser
        self._dl_label.setText(f"Download failed — opening browser instead.")
        self._bar.setVisible(False)
        self._pct_label.setVisible(False)
        self._update_btn.setText("⬇  Update Now")
        self._update_btn.setEnabled(True)
        webbrowser.open(self._url)
