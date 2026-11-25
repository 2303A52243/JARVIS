"""System & Application Control Panel for JARVIS."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMessageBox,
)

from system.application_manager import list_installed_apps, launch_app, terminate_app, is_app_running

BTN = "background:#1E293B;color:#38BDF8;border:1px solid #0284C7;border-radius:6px;padding:7px 14px;font-weight:bold;"
IN = "background:#0B0F19;color:#E2E8F0;border:1px solid #1F2937;border-radius:6px;padding:6px 10px;font-size:12px;"


class SystemPanel(QWidget):
    """Application discovery and process control panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apps = []
        self._init_ui()
        self.refresh_apps()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("📱 APPLICATION & PROCESS MANAGER")
        title.setStyleSheet("color:#00F0FF;font-size:18px;font-weight:900;letter-spacing:1px;")
        layout.addWidget(title)

        # Search bar
        bar = QHBoxLayout()
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("Filter applications by name (e.g. Chrome, Notepad, VS Code)...")
        self.search_in.setStyleSheet(IN)
        self.search_in.textChanged.connect(self._filter_apps)
        bar.addWidget(self.search_in, 1)

        self.btn_refresh = QPushButton("🔄 Refresh Apps")
        self.btn_refresh.setStyleSheet(BTN)
        self.btn_refresh.clicked.connect(self.refresh_apps)
        bar.addWidget(self.btn_refresh)
        layout.addLayout(bar)

        # App list
        self.app_list = QListWidget()
        self.app_list.setStyleSheet("""
            QListWidget {
                background: #050B14;
                border: 1px solid #0F2A4A;
                border-radius: 8px;
                color: #E2E8F0;
                font-size: 13px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px 12px;
                border-bottom: 1px solid #0D1B2A;
            }
            QListWidget::item:selected {
                background: #1E3A8A;
                color: #00F0FF;
            }
        """)
        layout.addWidget(self.app_list, 1)

        # Actions
        act_bar = QHBoxLayout()
        self.btn_launch = QPushButton("🚀 Launch App")
        self.btn_launch.setStyleSheet("background:#0284C7;color:#FFFFFF;border:none;border-radius:6px;padding:8px 20px;font-weight:bold;")
        self.btn_launch.clicked.connect(self._launch_selected)
        act_bar.addWidget(self.btn_launch)

        self.btn_close = QPushButton("🛑 Terminate App")
        self.btn_close.setStyleSheet("background:#7F1D1D;color:#FCA5A5;border:1px solid #DC2626;border-radius:6px;padding:8px 16px;font-weight:bold;")
        self.btn_close.clicked.connect(self._close_selected)
        act_bar.addWidget(self.btn_close)

        act_bar.addStretch()
        layout.addLayout(act_bar)

    def refresh_apps(self):
        self._apps = list_installed_apps()
        self._filter_apps()

    def _filter_apps(self):
        q = self.search_in.text().lower().strip()
        self.app_list.clear()
        for a in self._apps:
            name = a.get("name", "")
            if not q or q in name.lower():
                item = QListWidgetItem(f"📱 {name}")
                item.setData(Qt.UserRole, name)
                self.app_list.addItem(item)

    def _selected_name(self) -> str | None:
        item = self.app_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _launch_selected(self):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Select App", "Please select an application to launch.")
            return
        try:
            res = launch_app(name)
            QMessageBox.information(self, "App Launched", str(res))
        except Exception as e:
            QMessageBox.critical(self, "Launch Error", str(e))

    def _close_selected(self):
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, "Select App", "Please select an application to terminate.")
            return
        if QMessageBox.question(self, "Confirm Close", f"Are you sure you want to close {name}?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                res = terminate_app(name)
                QMessageBox.information(self, "App Terminated", str(res))
            except Exception as e:
                QMessageBox.critical(self, "Termination Error", str(e))
