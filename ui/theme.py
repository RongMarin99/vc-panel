from PyQt6.QtWidgets import QApplication

SIDEBAR_W = 220

_DARK = {
    "bg":       "#0d1117",
    "surface":  "#161b22",
    "card":     "#21262d",
    "hover":    "#30363d",
    "border":   "#30363d",
    "border2":  "#484f58",
    "text":     "#e6edf3",
    "text2":    "#8b949e",
    "text3":    "#6e7681",
    "blue":     "#58a6ff",
    "green":    "#3fb950",
    "yellow":   "#d29922",
    "red":      "#f85149",
    "input_bg": "#21262d",
}

_LIGHT = {
    "bg":       "#f6f8fa",
    "surface":  "#ffffff",
    "card":     "#ffffff",
    "hover":    "#eaeef2",
    "border":   "#d0d7de",
    "border2":  "#afb8c1",
    "text":     "#1f2328",
    "text2":    "#656d76",
    "text3":    "#9198a1",
    "blue":     "#0969da",
    "green":    "#1a7f37",
    "yellow":   "#9a6700",
    "red":      "#d1242f",
    "input_bg": "#f6f8fa",
}


def _make(C: dict) -> str:
    return f"""
* {{
    font-family: 'Segoe UI', -apple-system, sans-serif;
    font-size: 13px;
}}
QMainWindow, QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
}}
#sidebar {{
    background-color: {C['surface']};
    border-right: 1px solid {C['border']};
}}
QPushButton#nav_btn {{
    background: transparent;
    color: {C['text2']};
    text-align: left;
    padding: 9px 14px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    margin: 1px 8px;
}}
QPushButton#nav_btn:hover {{
    background-color: {C['hover']};
    color: {C['text']};
}}
QPushButton#nav_btn[active="true"] {{
    background-color: {C['blue']}22;
    color: {C['blue']};
    font-weight: 600;
}}
QFrame#card {{
    background-color: {C['card']};
    border: 1px solid {C['border']};
    border-radius: 8px;
}}
QPushButton {{
    background-color: {C['hover']};
    color: {C['text']};
    border: 1px solid {C['border']};
    padding: 5px 14px;
    border-radius: 6px;
}}
QPushButton:hover {{
    background-color: {C['border']};
}}
QPushButton:disabled {{
    color: {C['text3']};
    background-color: {C['hover']};
}}
QPushButton#primary {{
    background-color: {C['blue']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background-color: {C['blue']};
}}
QPushButton#install {{
    background-color: transparent;
    color: {C['blue']};
    border: 1.5px solid {C['blue']};
    font-weight: 600;
    border-radius: 6px;
}}
QPushButton#install:hover {{
    background-color: {C['blue']}18;
}}
QPushButton#danger {{
    background-color: transparent;
    color: {C['red']};
    border: 1px solid {C['red']};
}}
QPushButton#danger:hover {{
    background-color: {C['red']}22;
}}
QPushButton#theme_active {{
    background-color: {C['blue']};
    color: #ffffff;
    border: none;
    border-radius: 5px;
}}
QPushButton#theme_inactive {{
    background-color: transparent;
    color: {C['text2']};
    border: 1px solid {C['border']};
    border-radius: 5px;
}}
QPushButton#theme_inactive:hover {{
    background-color: {C['hover']};
    color: {C['text']};
}}
QTableWidget {{
    background-color: {C['surface']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    gridline-color: {C['border']};
    selection-background-color: {C['blue']}22;
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 8px;
    border: none;
    color: {C['text']};
}}
QTableWidget::item:selected {{
    background-color: {C['blue']}22;
    color: {C['text']};
}}
QHeaderView::section {{
    background-color: {C['card']};
    color: {C['text2']};
    padding: 7px 8px;
    border: none;
    border-bottom: 1px solid {C['border']};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}}
QTabWidget::pane {{
    border: 1px solid {C['border']};
    border-radius: 6px;
    background-color: {C['surface']};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {C['text2']};
    padding: 8px 18px;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {C['text']};
    border-bottom-color: {C['blue']};
}}
QTabBar::tab:hover {{
    color: {C['text']};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C['border2']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QLineEdit {{
    background-color: {C['input_bg']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 6px 10px;
}}
QLineEdit:focus {{
    border-color: {C['blue']};
}}
QLineEdit:read-only {{
    color: {C['text2']};
}}
QComboBox {{
    background-color: {C['input_bg']};
    color: {C['text']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 6px 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {C['card']};
    border: 1px solid {C['border']};
    selection-background-color: {C['hover']};
    color: {C['text']};
}}
QProgressBar {{
    background-color: {C['hover']};
    border: none;
    border-radius: 4px;
    height: 6px;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {C['blue']};
    border-radius: 4px;
}}
QDialog {{
    background-color: {C['surface']};
}}
QMessageBox {{
    background-color: {C['surface']};
}}
QLabel {{
    color: {C['text']};
}}
"""


DARK  = _make(_DARK)
LIGHT = _make(_LIGHT)

_current = "light"


def current_colors() -> dict:
    return _LIGHT if _current == "light" else _DARK


def apply(name: str):
    global _current
    _current = name
    app = QApplication.instance()
    if app:
        app.setStyleSheet(LIGHT if name == "light" else DARK)


def current() -> str:
    return _current
