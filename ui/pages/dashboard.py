import re
import shutil
import subprocess
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame
)

TOOL_ICONS = {
    "php":    "🐘",
    "node":   "⬢",
    "python": "🐍",
    "java":   "☕",
    "dotnet": "🔷",
}

_SYS_CMDS = {
    "php":    (["php",    "--version"],  r"PHP (\d+\.\d+\.\d+)"),
    "node":   (["node",   "--version"],  r"v?(\d+\.\d+\.\d+)"),
    "python": (["python", "--version"],  r"Python (\d+\.\d+\.\d+)"),
    "java":   (["java",   "-version"],   r'"(\d+[\.\d]*)"'),
    "dotnet": (["dotnet", "--version"],  r"(\d+\.\d+\.\d+)"),
}


def _system_version(tool: str) -> str | None:
    args, pattern = _SYS_CMDS[tool]
    exe = shutil.which(args[0])
    if not exe:
        return None
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        out = subprocess.run(
            [exe] + args[1:], capture_output=True, text=True, timeout=3,
            creationflags=flags,
        )
        # java -version writes to stderr; everything else uses stdout
        text = out.stderr + out.stdout
        m = re.search(pattern, text)
        return m.group(1) if m else None
    except Exception:
        return None


class ToolCard(QFrame):
    def __init__(self, name: str, manager, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumWidth(230)
        self.setMaximumWidth(310)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(0)

        # Header
        header = QHBoxLayout()
        icon = QLabel(TOOL_ICONS.get(name, "📦"))
        icon.setStyleSheet("font-size: 20px;")
        header.addWidget(icon)
        title = QLabel(f"  {manager.display_name}")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)
        layout.addSpacing(14)

        # Managed (VC) version
        managed = manager.current()
        vc_row = QHBoxLayout()
        vc_label = QLabel("Managed")
        vc_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #8b949e; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        vc_row.addWidget(vc_label)
        vc_row.addStretch()
        layout.addLayout(vc_row)
        layout.addSpacing(4)

        if managed:
            ver_lbl = QLabel(managed)
            ver_lbl.setStyleSheet(
                "font-family: 'Cascadia Code', Consolas, monospace; "
                "font-size: 20px; font-weight: 700; color: #0969da;"
            )
            layout.addWidget(ver_lbl)
            badge = QLabel("● Active")
            badge.setStyleSheet("color: #1a7f37; font-size: 12px;")
            layout.addWidget(badge)
        else:
            none_lbl = QLabel("Not set")
            none_lbl.setStyleSheet("font-size: 13px; color: #9198a1;")
            layout.addWidget(none_lbl)

        layout.addSpacing(14)

        # System (PATH) version
        sys_row = QHBoxLayout()
        sys_label = QLabel("System (PATH)")
        sys_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #8b949e; "
            "text-transform: uppercase; letter-spacing: 0.5px;"
        )
        sys_row.addWidget(sys_label)
        sys_row.addStretch()
        layout.addLayout(sys_row)
        layout.addSpacing(4)

        sys_ver = _system_version(name)
        sys_lbl = QLabel(sys_ver if sys_ver else "Not found")
        if sys_ver:
            sys_lbl.setStyleSheet(
                "font-family: 'Cascadia Code', Consolas, monospace; "
                "font-size: 14px; font-weight: 600; color: #656d76;"
            )
        else:
            sys_lbl.setStyleSheet("font-size: 13px; color: #9198a1;")
        layout.addWidget(sys_lbl)

        layout.addSpacing(14)

        # Installed count
        installed = manager.list_installed()
        count = QLabel(
            f"{len(installed)} version{'s' if len(installed) != 1 else ''} installed"
        )
        count.setStyleSheet("color: #8b949e; font-size: 12px;")
        layout.addWidget(count)
        layout.addStretch()


class DashboardPage(QWidget):
    def __init__(self, registry, config, parent=None):
        super().__init__(parent)
        self.registry = registry
        self.config = config
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        sub = QLabel("Active environments at a glance")
        sub.setStyleSheet("color: #8b949e; font-size: 13px; margin-top: 4px;")
        layout.addWidget(sub)

        layout.addSpacing(24)

        self._cards_grid = QGridLayout()
        self._cards_grid.setSpacing(16)
        layout.addLayout(self._cards_grid)

        layout.addStretch()

        shims_bar = QFrame()
        shims_bar.setObjectName("card")
        bar_layout = QHBoxLayout(shims_bar)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        bar_layout.addWidget(QLabel("⚡"))
        shims_path = QLabel(f"Shims: {self.config.shims_dir}")
        shims_path.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px; color: #8b949e;"
        )
        bar_layout.addWidget(shims_path)
        bar_layout.addStretch()
        layout.addWidget(shims_bar)

    def on_show(self):
        while self._cards_grid.count():
            item = self._cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, (name, mgr) in enumerate(self.registry.all().items()):
            row, col = divmod(i, 3)
            self._cards_grid.addWidget(ToolCard(name, mgr), row, col)
