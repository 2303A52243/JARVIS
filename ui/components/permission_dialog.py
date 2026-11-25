"""Permission & Confirmation Modal Dialog for JARVIS."""

from typing import Any, Dict
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QFrame,
)


class PermissionDialog(QDialog):
    """Modal prompt asking for explicit user approval before executing sensitive operations."""

    def __init__(self, action_name: str, message: str, details: Dict[str, Any] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("JARVIS — Security Authorization Required")
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0F172A;
                color: #F8FAFC;
                border: 2px solid #EF4444;
                border-radius: 10px;
            }
            QLabel {
                color: #E2E8F0;
                font-size: 13px;
            }
            QPushButton {
                padding: 8px 18px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header with warning badge
        header_layout = QHBoxLayout()
        badge = QLabel("⚠️ ACTION APPROVAL REQUIRED")
        badge.setStyleSheet("color: #EF4444; font-weight: 800; font-size: 14px; letter-spacing: 0.5px;")
        header_layout.addWidget(badge)
        layout.addLayout(header_layout)

        # Action Title
        self.lbl_action = QLabel(f"<b>Requested Action:</b> <span style='color: #38BDF8;'>{action_name}</span>")
        layout.addWidget(self.lbl_action)

        # Description / Reason
        self.lbl_message = QLabel(message)
        self.lbl_message.setWordWrap(True)
        layout.addWidget(self.lbl_message)

        # Details box if details provided
        if details:
            details_box = QTextEdit()
            details_box.setReadOnly(True)
            details_text = "\n".join(f"{k}: {v}" for k, v in details.items())
            details_box.setPlainText(details_text)
            details_box.setMaximumHeight(90)
            details_box.setStyleSheet("""
                QTextEdit {
                    background-color: #020617;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    color: #94A3B8;
                    font-family: Consolas, monospace;
                    font-size: 11px;
                }
            """)
            layout.addWidget(details_box)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_deny = QPushButton("Deny Action (Cancel)")
        self.btn_deny.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #F1F5F9;
                border: 1px solid #475569;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.btn_deny.clicked.connect(self.reject)

        self.btn_approve = QPushButton("Approve & Execute")
        self.btn_approve.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: #FFFFFF;
                border: 1px solid #DC2626;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        self.btn_approve.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_deny)
        btn_layout.addWidget(self.btn_approve)
        layout.addLayout(btn_layout)
