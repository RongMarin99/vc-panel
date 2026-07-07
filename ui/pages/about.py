import webbrowser

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QTabWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont

import ui.theme as theme
from utils.resource_path import resource_path
from utils.updater import check_update, CURRENT_VERSION, RELEASES_URL

ASSETS   = resource_path("assets")
REPO_URL = "https://github.com/RongMarin99/vc-panel"


# ── helpers ──────────────────────────────────────────────────────────────────

def _card(layout_margins=(24, 24, 24, 24)) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(*layout_margins)
    lay.setSpacing(0)
    return f, lay


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    C = theme.current_colors()
    line.setStyleSheet(f"color:{C['border']};")
    return line


# ── Update check thread ───────────────────────────────────────────────────────

class _CheckThread(QThread):
    result = pyqtSignal(str, str)   # (latest_version, url) — empty strings = up to date
    error  = pyqtSignal(str)

    def run(self):
        try:
            v, url = check_update()
            self.result.emit(v or "", url or "")
        except Exception as e:
            self.error.emit(str(e))


# ── Tab: About Us ─────────────────────────────────────────────────────────────

class _AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        C = theme.current_colors()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(20)
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # Logo + name
        logo_row = QHBoxLayout()
        icon_path = ASSETS / "icon.png"
        if icon_path.exists():
            px = QPixmap(str(icon_path)).scaled(
                64, 64, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            logo = QLabel()
            logo.setPixmap(px)
            logo.setFixedSize(64, 64)
            logo_row.addWidget(logo)
            logo_row.addSpacing(16)

        name_col = QVBoxLayout()
        app_name = QLabel("VC — Version Controller")
        app_name.setStyleSheet("font-size:22px; font-weight:700;")
        name_col.addWidget(app_name)
        ver_lbl = QLabel(f"Version {CURRENT_VERSION}  ·  Open Source  ·  Free")
        ver_lbl.setStyleSheet(f"font-size:12px; color:{C['text2']};")
        name_col.addWidget(ver_lbl)
        logo_row.addLayout(name_col)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        # Description card
        card, cl = _card()
        desc = QLabel(
            "VC is a lightweight, open-source version manager for developers on Windows, macOS, and Linux.\n\n"
            "Manage PHP, Node.js, Python, Java, .NET, Go, and Rust — all from one clean interface.\n\n"
            "Switch between versions instantly, manage per-project overrides, "
            "configure PHP extensions, and keep your environment consistent across machines."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size:13px; line-height:1.6; color:{C['text']};")
        cl.addWidget(desc)
        layout.addWidget(card)

        # Features card
        card2, cl2 = _card()
        feat_title = QLabel("Features")
        feat_title.setStyleSheet("font-size:14px; font-weight:700; margin-bottom:12px;")
        cl2.addWidget(feat_title)
        features = [
            ("🔀", "Multi-language version switching — PHP, Node, Python, Java, .NET, Go, Rust"),
            ("🗄", "Database management — MySQL, PostgreSQL, Redis, MongoDB install & service control"),
            ("📦", "Per-project version overrides"),
            ("⚙",  "PHP extensions manager — enable/disable per version"),
            ("📄", "PHP INI settings — upload size, memory, execution time"),
            ("⚡", "System PATH management — add shims with one click"),
            ("🌙", "Light & Dark theme"),
            ("🔔", "Auto update notifications"),
            ("🚀", "Run at startup + minimize to tray"),
        ]
        for icon, text in features:
            row = QHBoxLayout()
            row.setSpacing(10)
            i = QLabel(icon)
            i.setFixedWidth(22)
            i.setStyleSheet("font-size:15px;")
            row.addWidget(i)
            t = QLabel(text)
            t.setStyleSheet(f"font-size:12px; color:{C['text']};")
            row.addWidget(t, 1)
            cl2.addSpacing(6)
            cl2.addLayout(row)
        layout.addWidget(card2)

        # Links card
        card3, cl3 = _card()
        links_title = QLabel("Links")
        links_title.setStyleSheet("font-size:14px; font-weight:700; margin-bottom:12px;")
        cl3.addWidget(links_title)

        def _link_btn(label: str, url: str) -> QPushButton:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background:transparent; color:{C['blue']}; border:none;"
                f" font-size:13px; text-align:left; padding:2px 0; }}"
                f"QPushButton:hover {{ text-decoration:underline; }}"
            )
            b.clicked.connect(lambda: webbrowser.open(url))
            return b

        cl3.addWidget(_link_btn("🌐  GitHub — Source code & issues", REPO_URL))
        cl3.addSpacing(6)
        cl3.addWidget(_link_btn("📥  Releases — Download latest version", f"{REPO_URL}/releases"))
        cl3.addSpacing(6)
        cl3.addWidget(_link_btn("🐛  Report a bug", f"{REPO_URL}/issues"))
        layout.addWidget(card3)

        # Credits card
        card4, cl4 = _card()
        cred_title = QLabel("Built with")
        cred_title.setStyleSheet("font-size:14px; font-weight:700; margin-bottom:10px;")
        cl4.addWidget(cred_title)
        tech = QLabel("Python 3.13  ·  PyQt6  ·  cx_Freeze  ·  Requests  ·  Packaging")
        tech.setStyleSheet(f"font-size:12px; color:{C['text2']};")
        cl4.addWidget(tech)
        cl4.addSpacing(6)
        author = QLabel("Developed by  RONG MARIN")
        author.setStyleSheet(f"font-size:12px; color:{C['text2']};")
        cl4.addWidget(author)
        layout.addWidget(card4)

        layout.addStretch()


# ── Tab: Check for Update ─────────────────────────────────────────────────────

class _UpdateTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        C = theme.current_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # Current version card
        card, cl = _card()
        cl.setSpacing(10)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Current version"))
        row1.addStretch()
        cur = QLabel(CURRENT_VERSION)
        cur.setStyleSheet(
            f"font-family:monospace; font-size:14px; font-weight:700; color:{C['blue']};"
        )
        row1.addWidget(cur)
        cl.addLayout(row1)
        cl.addWidget(_divider())

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Latest version"))
        row2.addStretch()
        self._latest_lbl = QLabel("—")
        self._latest_lbl.setStyleSheet(
            f"font-family:monospace; font-size:14px; font-weight:700; color:{C['text2']};"
        )
        row2.addWidget(self._latest_lbl)
        cl.addLayout(row2)
        layout.addWidget(card)

        # Status card
        self._status_card, self._status_cl = _card()
        self._status_icon = QLabel("🔍")
        self._status_icon.setStyleSheet("font-size:32px;")
        self._status_icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._status_cl.addWidget(self._status_icon)
        self._status_cl.addSpacing(10)
        self._status_msg = QLabel("Click below to check for updates")
        self._status_msg.setStyleSheet(f"font-size:13px; color:{C['text2']};")
        self._status_msg.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._status_msg.setWordWrap(True)
        self._status_cl.addWidget(self._status_msg)
        layout.addWidget(self._status_card)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._check_btn = QPushButton("Check for Updates")
        self._check_btn.setFixedHeight(38)
        self._check_btn.setMinimumWidth(160)
        self._check_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._check_btn.setStyleSheet(
            f"QPushButton {{ background:{C['blue']}; color:#fff; border:none;"
            f" border-radius:6px; font-size:13px; font-weight:600; padding:0 20px; }}"
            f"QPushButton:hover {{ background:{C['blue']}dd; }}"
            f"QPushButton:disabled {{ background:{C['hover']}; color:{C['text3']}; }}"
        )
        self._check_btn.clicked.connect(self._check)
        btn_row.addWidget(self._check_btn)

        self._dl_btn = QPushButton("Download Update")
        self._dl_btn.setFixedHeight(38)
        self._dl_btn.setMinimumWidth(160)
        self._dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dl_btn.setVisible(False)
        self._dl_btn.setStyleSheet(
            f"QPushButton {{ background:#1a7f37; color:#fff; border:none;"
            f" border-radius:6px; font-size:13px; font-weight:600; padding:0 20px; }}"
            f"QPushButton:hover {{ background:#1c8c3d; }}"
        )
        self._dl_btn.clicked.connect(self._open_download)
        btn_row.addWidget(self._dl_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        self._url = ""

    def _check(self):
        C = theme.current_colors()
        self._check_btn.setEnabled(False)
        self._check_btn.setText("Checking…")
        self._dl_btn.setVisible(False)
        self._status_icon.setText("🔍")
        self._status_msg.setText("Connecting to GitHub…")
        self._status_msg.setStyleSheet(f"font-size:13px; color:{C['text2']};")

        self._thread = _CheckThread(self)
        self._thread.result.connect(self._on_result)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    def _on_result(self, version: str, url: str):
        C = theme.current_colors()
        self._check_btn.setEnabled(True)
        self._check_btn.setText("Check for Updates")
        if version:
            self._url = url
            self._latest_lbl.setText(version)
            self._latest_lbl.setStyleSheet(
                f"font-family:monospace; font-size:14px; font-weight:700; color:#1a7f37;"
            )
            self._status_icon.setText("⬆")
            self._status_msg.setText(
                f"Version {version} is available!\n"
                f"You are currently on {CURRENT_VERSION}."
            )
            self._status_msg.setStyleSheet(f"font-size:13px; color:#1a7f37; font-weight:600;")
            self._dl_btn.setVisible(True)
        else:
            self._latest_lbl.setText(CURRENT_VERSION)
            self._latest_lbl.setStyleSheet(
                f"font-family:monospace; font-size:14px; font-weight:700; color:{C['green']};"
            )
            self._status_icon.setText("✅")
            self._status_msg.setText("You are on the latest version.")
            self._status_msg.setStyleSheet(
                f"font-size:13px; color:{C['green']}; font-weight:600;"
            )

    def _open_download(self):
        if self._url:
            webbrowser.open(self._url)

    def _on_error(self, msg: str):
        C = theme.current_colors()
        self._check_btn.setEnabled(True)
        self._check_btn.setText("Check for Updates")
        self._status_icon.setText("⚠")
        self._status_msg.setText(f"Could not reach update server.\n{msg}")
        self._status_msg.setStyleSheet(f"font-size:12px; color:{C['red']};")


# ── Tab: Donate ───────────────────────────────────────────────────────────────

class _DonateTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        C = theme.current_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(340)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 28, 28, 28)
        cl.setSpacing(0)
        cl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        coffee = QLabel("☕")
        coffee.setStyleSheet("font-size:36px;")
        coffee.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cl.addWidget(coffee)
        cl.addSpacing(8)

        heading = QLabel("Buy me a coffee")
        heading.setStyleSheet("font-size:18px; font-weight:700;")
        heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cl.addWidget(heading)
        cl.addSpacing(4)

        tagline = QLabel("Scan with ABA Pay to support development")
        tagline.setStyleSheet(f"color:{C['text2']}; font-size:12px;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        tagline.setWordWrap(True)
        cl.addWidget(tagline)
        cl.addSpacing(24)

        qr_path = ASSETS / "qr_abapay.jpg"
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        qr_label.setFixedSize(220, 220)
        qr_label.setStyleSheet(
            "border:1px solid #d0d7de; border-radius:12px; background:#ffffff; padding:8px;"
        )
        if qr_path.exists():
            px = QPixmap(str(qr_path)).scaled(
                204, 204,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            qr_label.setPixmap(px)
        else:
            qr_label.setText("Place qr_abapay.jpg\nin assets/ folder")
            qr_label.setStyleSheet(
                qr_label.styleSheet() +
                "color:#8b949e; font-size:12px; qproperty-alignment:AlignCenter;"
            )
        cl.addWidget(qr_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        cl.addSpacing(20)

        name = QLabel("RONG MARIN")
        name.setStyleSheet(
            f"font-size:15px; font-weight:700; letter-spacing:1.5px; color:{C['blue']};"
        )
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cl.addWidget(name)
        cl.addSpacing(4)

        badge = QLabel("ABA Pay  ·  KHQR")
        badge.setStyleSheet(f"font-size:11px; color:{C['text2']}; letter-spacing:0.5px;")
        badge.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cl.addWidget(badge)

        layout.addWidget(card)


# ── Main page ─────────────────────────────────────────────────────────────────

class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        title = QLabel("About")
        title.setStyleSheet("font-size:24px; font-weight:700;")
        layout.addWidget(title)
        sub = QLabel("VC — Version Controller  ·  Open source & free")
        sub.setStyleSheet("color:#8b949e; font-size:13px; margin-top:4px;")
        layout.addWidget(sub)
        layout.addSpacing(24)

        tabs = QTabWidget()
        tabs.addTab(_AboutTab(),  "ℹ  About")
        tabs.addTab(_UpdateTab(), "🔔  Check for Update")
        tabs.addTab(_DonateTab(), "☕  Donate")
        layout.addWidget(tabs)

    def on_show(self):
        pass
