from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget

from providers.apache import ApacheService
from providers.nginx import NginxService
from providers.traefik import TraefikService
from ui.pages.database_page import DBVersionTab


class WebServerPage(QWidget):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._services = [
            ApacheService(config),
            NginxService(config),
            TraefikService(config),
        ]
        self._tabs: dict[str, DBVersionTab] = {}
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        title = QLabel("Web Servers")
        title.setStyleSheet("font-size:24px; font-weight:700;")
        layout.addWidget(title)
        sub = QLabel("Install and manage web server and reverse proxy services")
        sub.setStyleSheet("color:#8b949e; font-size:13px; margin-top:4px; margin-bottom:24px;")
        layout.addWidget(sub)

        self._tab_widget = QTabWidget()
        for svc in self._services:
            tab = DBVersionTab(svc)
            self._tabs[svc.name] = tab
            self._tab_widget.addTab(tab, f"{svc.icon}  {svc.display_name}")
        layout.addWidget(self._tab_widget)

    def on_show(self):
        for tab in self._tabs.values():
            tab.refresh()
