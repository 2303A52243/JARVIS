"""Metric card component for system and activity stats."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout


class MetricCard(QFrame):
    """Modern dark-themed stat card with glowing accent."""

    def __init__(self, title: str, value: str = "--", subtitle: str = "", accent_color: str = "#00D2FF", parent=None):
        super().__init__(parent)
        self.accent_color = accent_color

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #111827;
                border: 1px solid #1F2937;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                padding: 10px;
            }}
            QFrame:hover {{
                border-color: {accent_color};
                background-color: #162032;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: bold; letter-spacing: 1px;")

        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"color: #F9FAFB; font-size: 22px; font-weight: 800;")

        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setStyleSheet("color: #6B7280; font-size: 11px;")

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addWidget(self.lbl_subtitle)

    def set_value(self, value: str, subtitle: str = ""):
        self.lbl_value.setText(value)
        if subtitle:
            self.lbl_subtitle.setText(subtitle)
