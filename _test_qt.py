import sys
import os
if sys.platform == "win32" and getattr(sys, "frozen", False):
    qt6_bin = os.path.join(sys._MEIPASS, "PyQt6", "Qt6", "bin")
    if os.path.isdir(qt6_bin):
        os.add_dll_directory(qt6_bin)
from PyQt6.QtWidgets import QApplication, QLabel, QStyleFactory
app = QApplication(sys.argv)
app.setStyle(QStyleFactory.create("Fusion"))
lbl = QLabel("Hello")
lbl.show()
sys.exit(app.exec())
