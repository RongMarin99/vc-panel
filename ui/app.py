from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget

from ui.sidebar import Sidebar
from ui.pages.dashboard import DashboardPage
from ui.pages.version_manager import VersionManagerPage
from ui.pages.project_config import ProjectConfigPage
from ui.pages.settings import SettingsPage
from ui.pages.about import AboutPage
import ui.theme as theme
from core.registry import Registry
from storage.config import Config
from storage.db import Database
from utils.path_manager import add_to_path


class MainWindow(QMainWindow):
    def __init__(self, config: Config, db: Database):
        super().__init__()
        self.config = config
        self.db = db
        self.registry = Registry(config)
        add_to_path(config.shims_dir)
        self._build()

    def _build(self):
        self.setWindowTitle("VC — Version Controller")
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

        self.stack = QStackedWidget()
        main.addWidget(self.stack)

        self.pages = {
            "dashboard": DashboardPage(self.registry, self.config),
            "versions":  VersionManagerPage(self.registry, self.config),
            "projects":  ProjectConfigPage(self.registry, self.config, self.db),
            "settings":  SettingsPage(self.config),
            "about":     AboutPage(),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self._navigate("dashboard")
        self.sidebar.set_active("dashboard")

    def _navigate(self, page_id: str):
        if page_id in self.pages:
            self.stack.setCurrentWidget(self.pages[page_id])
            self.pages[page_id].on_show()
