from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QSystemTrayIcon, QMenu,
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PyQt6.QtCore import Qt

from ui.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.version_manager import VersionManagerPage
from ui.pages.project_config import ProjectConfigPage
from ui.pages.settings import SettingsPage
from ui.pages.about import AboutPage
from ui.pages.database_page import DatabasePage
import ui.theme as theme
from core.registry import Registry
from storage.config import Config
from storage.db import Database
from utils.path_manager import add_to_path
from ui.widgets.update_banner import UpdateBanner


def _load_icon() -> QIcon:
    from utils.resource_path import resource_path
    for name in ("icon.ico", "icon.png"):
        p = resource_path("assets", name)
        if p.exists():
            return QIcon(str(p))
    # fallback: programmatic blue circle
    px = QPixmap(32, 32)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#0d1b3e"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 30, 30)
    p.setPen(QColor("white"))
    font = QFont()
    font.setBold(True)
    font.setPixelSize(16)
    p.setFont(font)
    p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "VC")
    p.end()
    return QIcon(px)


class MainWindow(QMainWindow):
    def __init__(self, config: Config, db: Database):
        super().__init__()
        self.config = config
        self.db = db
        self.registry = Registry(config)
        add_to_path(config.shims_dir)
        self._build()
        self._build_tray()

    def _build(self):
        self.setWindowTitle("VC — Version Controller")
        self.setWindowIcon(_load_icon())
        self.setMinimumSize(980, 640)
        self.resize(1100, 700)

        central = QWidget()
        self.setCentralWidget(central)
        main = QHBoxLayout(central)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.page_changed.connect(self._navigate)
        main.addWidget(self.sidebar)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._update_banner = UpdateBanner()
        right_layout.addWidget(self._update_banner)

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack)
        main.addWidget(right)

        self.pages = {
            "dashboard": DashboardPage(self.registry, self.config),
            "versions":  VersionManagerPage(self.registry, self.config),
            "databases": DatabasePage(self.config),
            "projects":  ProjectConfigPage(self.registry, self.config, self.db),
            "settings":  SettingsPage(self.config),
            "about":     AboutPage(),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self._navigate("dashboard")
        self.sidebar.set_active("dashboard")

    def _build_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(_load_icon())
        self._tray.setToolTip("VC — Version Controller")

        menu = QMenu()
        show_action = QAction("Show VC", self)
        show_action.triggered.connect(self._show_from_tray)
        menu.addAction(show_action)
        menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)

        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit(self):
        self._tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def closeEvent(self, event):
        minimize = self.config.get("minimize_to_tray", "true") == "true"
        if minimize and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "VC — Version Controller",
                "Running in background. Right-click the tray icon to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )
        else:
            self._tray.hide()
            event.accept()

    def _navigate(self, page_id: str):
        if page_id in self.pages:
            self.stack.setCurrentWidget(self.pages[page_id])
            self.pages[page_id].on_show()
