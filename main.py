import sys
import os

# Register Qt6 DLLs — works in both dev and PyInstaller frozen exe
if sys.platform == "win32":
    if getattr(sys, "frozen", False):
        _base = os.path.dirname(sys.executable)
        # cx_Freeze: packages under lib/, Qt6 DLLs directly in lib/PyQt6/Qt6/
        for _p in [
            os.path.join(_base, "lib", "PyQt6", "Qt6"),
            os.path.join(_base, "lib", "PyQt6", "Qt6", "bin"),
            os.path.join(_base, "PyQt6", "Qt6", "bin"),
            _base,
        ]:
            if os.path.isdir(_p):
                os.add_dll_directory(_p)
    else:
        import importlib.util
        _spec = importlib.util.find_spec("PyQt6")
        _qt6_bin = (
            os.path.join(os.path.dirname(_spec.origin), "Qt6", "bin")
            if _spec and _spec.origin else ""
        )
        if _qt6_bin and os.path.isdir(_qt6_bin):
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
    app.setApplicationVersion("0.1.2")

    config = Config()
    db = Database(config.db_path)

    saved_theme = config.get("theme", "light")
    theme.apply(saved_theme)

    window = MainWindow(config=config, db=db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
