import tempfile
from pathlib import Path

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal

from utils.updater import check_update, download_installer, apply_update, CURRENT_VERSION
import ui.theme as theme

_SPINNER = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]


class _CheckThread(QThread):
    found = pyqtSignal(str, str)

    def run(self):
        version, url = check_update()
        if version:
            self.found.emit(version, url)


class _DownloadThread(QThread):
    progress = pyqtSignal(int, int)
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
        self._url     = ""
        self._version = ""
        self._dest: Path | None = None
        self._spin_i  = 0
        self._build()
        self._start_check()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 12, 0)
        layout.setSpacing(12)

        self._icon = QLabel("⬆")
        self._icon.setStyleSheet("font-size:15px; background:transparent;")
        layout.addWidget(self._icon)

        self._msg = QLabel("")
        self._msg.setStyleSheet("font-size:13px; font-weight:600; background:transparent;")
        layout.addWidget(self._msg)

        layout.addStretch()

        # Action button (Update Now → Restart to Update)
        self._action_btn = QPushButton("⬇  Update Now")
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setFixedHeight(28)
        self._action_btn.clicked.connect(self._start_download)
        layout.addWidget(self._action_btn)

        # Dismiss
        self._dismiss_btn = QPushButton("✕")
        self._dismiss_btn.setFixedSize(28, 28)
        self._dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_btn.setStyleSheet(
            "QPushButton { background:transparent; border:none; font-size:14px; }"
        )
        self._dismiss_btn.clicked.connect(self.hide)
        layout.addWidget(self._dismiss_btn)

        # Spinner timer
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(100)
        self._spin_timer.timeout.connect(self._tick_spinner)

    def _apply_style(self, color_key: str = "blue"):
        C = theme.current_colors()
        c = C[color_key]
        self.setStyleSheet(
            f"QFrame {{ background:{c}18; border-bottom:1px solid {c}44; }}"
        )
        self._msg.setStyleSheet(
            f"font-size:13px; font-weight:600; color:{C['text']}; background:transparent;"
        )
        self._action_btn.setStyleSheet(
            f"QPushButton {{ background:{c}; color:#fff; border:none;"
            f" border-radius:5px; padding:0 14px; font-size:12px; font-weight:600; }}"
            f"QPushButton:hover {{ background:{c}dd; }}"
            f"QPushButton:disabled {{ background:{c}66; color:#fff; }}"
        )

    # ── Check ─────────────────────────────────────────────────────────────────

    def _start_check(self):
        self._check_thread = _CheckThread(self)
        self._check_thread.found.connect(self._on_found)
        self._check_thread.start()

    def _on_found(self, version: str, url: str):
        self._version = version
        self._url     = url
        self._msg.setText(f"VC {version} is available  (you have {CURRENT_VERSION})")
        self._action_btn.setText("⬇  Update Now")
        self._action_btn.setEnabled(True)
        self._action_btn.clicked.disconnect()
        self._action_btn.clicked.connect(self._start_download)
        self._apply_style("blue")
        self.setVisible(True)

    # ── Download ──────────────────────────────────────────────────────────────

    def _start_download(self):
        if not self._url:
            return

        self._dest = Path(tempfile.gettempdir()) / f"VC-Setup-{self._version}.exe"

        # Switch to loading state — spinner only, no big progress bar
        self._action_btn.setEnabled(False)
        self._action_btn.setText("⣾  Downloading…")
        self._msg.setText(f"Downloading VC {self._version} in background…")
        self._dismiss_btn.setEnabled(False)
        self._spin_timer.start()

        self._dl_thread = _DownloadThread(self._url, self._dest)
        self._dl_thread.progress.connect(self._on_progress)
        self._dl_thread.done.connect(self._on_done)
        self._dl_thread.error.connect(self._on_error)
        self._dl_thread.start()

    def _tick_spinner(self):
        self._spin_i = (self._spin_i + 1) % len(_SPINNER)
        done_mb = getattr(self, "_done_mb", 0)
        total_mb = getattr(self, "_total_mb", 0)
        if total_mb > 0:
            self._action_btn.setText(
                f"{_SPINNER[self._spin_i]}  {done_mb:.0f} / {total_mb:.0f} MB"
            )
        else:
            self._action_btn.setText(f"{_SPINNER[self._spin_i]}  Downloading…")

    def _on_progress(self, done: int, total: int):
        self._done_mb  = done  / 1_048_576
        self._total_mb = total / 1_048_576

    def _on_done(self, ok: bool):
        self._spin_timer.stop()
        self._dismiss_btn.setEnabled(True)

        if ok and self._dest and self._dest.exists():
            self._msg.setText(
                f"VC {self._version} is ready to install."
            )
            self._action_btn.setText("🔄  Restart to Update")
            self._action_btn.setEnabled(True)
            self._action_btn.clicked.disconnect()
            self._action_btn.clicked.connect(self._do_apply)
            self._apply_style("green")
        else:
            self._on_error("Download incomplete.")

    def _on_error(self, msg: str):
        self._spin_timer.stop()
        self._dismiss_btn.setEnabled(True)
        self._msg.setText(f"Update failed — {msg}")
        self._action_btn.setText("↗  Open in Browser")
        self._action_btn.setEnabled(True)
        self._action_btn.clicked.disconnect()
        self._action_btn.clicked.connect(
            lambda: __import__("webbrowser").open(self._url)
        )
        self._apply_style("red")

    def _do_apply(self):
        self._msg.setText("Applying update… VC will restart automatically.")
        self._action_btn.setEnabled(False)
        QTimer.singleShot(800, lambda: apply_update(self._dest))
