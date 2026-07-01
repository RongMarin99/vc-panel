import sys
import os

# Python 3.8+ on Windows changed DLL search behavior — Qt6 DLLs must be registered explicitly
if sys.platform == "win32":
    import importlib.util
    _spec = importlib.util.find_spec("PyQt6")
    if _spec and _spec.origin:
        _qt6_bin = os.path.join(os.path.dirname(_spec.origin), "Qt6", "bin")
        if os.path.isdir(_qt6_bin):
            os.add_dll_directory(_qt6_bin)

from PyQt6.QtWidgets import QApplication, QStyleFactory

from ui.app import MainWindow
from storage.config import Config
from storage.db import Database
import ui.theme as theme


def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setApplicationName("VC")
    app.setApplicationDisplayName("VC — Version Controller")
    app.setApplicationVersion("0.1.0")

    config = Config()
    db = Database(config.db_path)

    saved_theme = config.get("theme", "light")
    theme.apply(saved_theme)

    window = MainWindow(config=config, db=db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
