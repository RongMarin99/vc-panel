from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont

ASSETS = Path(__file__).parent.parent.parent / "assets"


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.setSpacing(0)

        title = QLabel("About & Support")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        outer.addWidget(title)

        sub = QLabel("VC — Version Controller  ·  v0.1.0")
        sub.setStyleSheet("color: #8b949e; font-size: 13px; margin-top: 4px;")
        outer.addWidget(sub)

        outer.addSpacing(32)

        # Center card
        center_row = QHBoxLayout()
        center_row.addStretch()

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(340)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(0)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Coffee emoji + heading
        coffee = QLabel("☕")
        coffee.setStyleSheet("font-size: 36px;")
        coffee.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(coffee)
        card_layout.addSpacing(8)

        heading = QLabel("Buy me a coffee")
        heading.setStyleSheet("font-size: 18px; font-weight: 700;")
        heading.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(heading)
        card_layout.addSpacing(4)

        tagline = QLabel("Scan with ABA Pay to support development")
        tagline.setStyleSheet("color: #8b949e; font-size: 12px;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        tagline.setWordWrap(True)
        card_layout.addWidget(tagline)
        card_layout.addSpacing(24)

        # QR code image
        qr_path = ASSETS / "qr_abapay.jpg"
        qr_label = QLabel()
        qr_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        qr_label.setFixedSize(220, 220)
        qr_label.setStyleSheet(
            "border: 1px solid #d0d7de; border-radius: 12px; "
            "background: #ffffff; padding: 8px;"
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
                "color: #8b949e; font-size: 12px; qproperty-alignment: AlignCenter;"
            )

        card_layout.addWidget(qr_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        card_layout.addSpacing(20)

        # Name
        name = QLabel("RONG MARIN")
        name.setStyleSheet(
            "font-size: 15px; font-weight: 700; letter-spacing: 1.5px; color: #1f6feb;"
        )
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(name)
        card_layout.addSpacing(4)

        badge = QLabel("ABA Pay  ·  KHQR")
        badge.setStyleSheet("font-size: 11px; color: #8b949e; letter-spacing: 0.5px;")
        badge.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(badge)

        center_row.addWidget(card)
        center_row.addStretch()
        outer.addLayout(center_row)
        outer.addStretch()

    def on_show(self):
        pass
