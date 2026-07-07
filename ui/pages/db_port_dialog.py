from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox,
    QPushButton, QFrame,
)
from PyQt6.QtCore import Qt
import ui.theme as theme


class DBPortDialog(QDialog):
    def __init__(self, service_name: str, current_port: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Change {service_name} Port")
        self.setFixedWidth(360)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._port: int | None = None
        self._build(service_name, current_port)

    def _build(self, service_name: str, current_port: int):
        C = theme.current_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(f"Change {service_name} Port")
        title.setStyleSheet("font-size:16px; font-weight:700;")
        layout.addWidget(title)

        desc = QLabel(
            f"Current port: <b>{current_port}</b><br>"
            "Changes take effect after restarting the service."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"font-size:12px; color:{C['text2']};")
        layout.addWidget(desc)

        # Divider
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']};")
        layout.addWidget(sep)

        # Port input
        row = QHBoxLayout()
        row.addWidget(QLabel("New port:"))
        self._spin = QSpinBox()
        self._spin.setRange(1, 65535)
        self._spin.setValue(current_port)
        self._spin.setFixedWidth(100)
        self._spin.setStyleSheet(
            f"QSpinBox {{ background:{C['input_bg']}; color:{C['text']};"
            f" border:1px solid {C['border']}; border-radius:5px;"
            f" padding:4px 8px; font-size:14px; }}"
        )
        row.addWidget(self._spin)
        row.addStretch()
        layout.addLayout(row)

        # Common presets
        preset_row = QHBoxLayout()
        preset_lbl = QLabel("Quick select:")
        preset_lbl.setStyleSheet(f"font-size:11px; color:{C['text3']};")
        preset_row.addWidget(preset_lbl)
        for port in [current_port, 3306, 5432, 6379, 27017, 3307, 5433]:
            if port == current_port:
                continue
            b = QPushButton(str(port))
            b.setFixedHeight(24)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background:{C['hover']}; color:{C['text2']};"
                f" border:1px solid {C['border']}; border-radius:4px;"
                f" font-size:11px; padding:0 6px; }}"
                f"QPushButton:hover {{ color:{C['text']}; }}"
            )
            b.clicked.connect(lambda _, p=port: self._spin.setValue(p))
            preset_row.addWidget(b)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)

        save = QPushButton("Save & Restart")
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setStyleSheet(
            f"QPushButton {{ background:{C['blue']}; color:#fff; border:none;"
            f" border-radius:6px; font-size:13px; font-weight:600; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:{C['blue']}dd; }}"
        )
        save.clicked.connect(self._save)
        btn_row.addWidget(save)
        layout.addLayout(btn_row)

    def _save(self):
        self._port = self._spin.value()
        self.accept()

    def selected_port(self) -> int | None:
        return self._port
