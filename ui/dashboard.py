"""Dashboard panel for JARVIS.

Displays live system metrics, hardware overview, and recent activity logs.
"""

from __future__ import annotations

import time
import platform
import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QScrollArea,
    QFrame,
)

from ui.components.metric_card import MetricCard
from app.config import get_settings


class DashboardPanel(QWidget):
    """Futuristic, live system dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._setup_timer()
        # Delay first metric fetch so the window appears instantly
        from PySide6.QtCore import QTimer
        QTimer.singleShot(800, self.update_metrics)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Welcome Header
        header_layout = QHBoxLayout()
        header_text = QVBoxLayout()
        title = QLabel("SYSTEM COMMAND DASHBOARD")
        title.setStyleSheet("color: #F8FAFC; font-size: 20px; font-weight: 800; letter-spacing: 1.5px;")
        subtitle = QLabel("Real-time laptop monitoring, hardware telemetry, and operational state")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 13px;")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header_layout.addLayout(header_text)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("⚡ Refresh Telemetry")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284C7;
                color: #FFFFFF;
            }
        """)
        self.btn_refresh.clicked.connect(self.update_metrics)
        header_layout.addWidget(self.btn_refresh)
        layout.addLayout(header_layout)

        # Top Metric Cards Grid
        grid = QGridLayout()
        grid.setSpacing(14)

        self.card_cpu = MetricCard("CPU Usage", "0%", "Logical Cores: --", "#00D2FF")
        self.card_ram = MetricCard("RAM Memory", "0%", "Used: -- / Total: --", "#10B981")
        self.card_disk = MetricCard("Disk Storage", "-- GB Free", "Storage Anchor: C:\\", "#F59E0B")
        self.card_battery = MetricCard("Battery Status", "--%", "Power: --", "#8B5CF6")

        grid.addWidget(self.card_cpu, 0, 0)
        grid.addWidget(self.card_ram, 0, 1)
        grid.addWidget(self.card_disk, 0, 2)
        grid.addWidget(self.card_battery, 0, 3)
        layout.addLayout(grid)

        # Host System Specs Section
        specs_frame = QFrame()
        specs_frame.setStyleSheet("""
            QFrame {
                background-color: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        specs_layout = QVBoxLayout(specs_frame)
        specs_title = QLabel("LAPTOP HARDWARE & OS ENVIRONMENT")
        specs_title.setStyleSheet("color: #38BDF8; font-size: 12px; font-weight: bold; letter-spacing: 1px;")
        specs_layout.addWidget(specs_title)

        self.lbl_system_details = QLabel("Gathering system information...")
        self.lbl_system_details.setStyleSheet("color: #CBD5E1; font-size: 12px; line-height: 1.6;")
        specs_layout.addWidget(self.lbl_system_details)
        layout.addWidget(specs_frame)

        # Live Activity / Security Feed
        log_frame = QFrame()
        log_frame.setStyleSheet("""
            QFrame {
                background-color: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        log_layout = QVBoxLayout(log_frame)
        log_title = QLabel("ACTIVITY & AUDIT LOG FEED")
        log_title.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold; letter-spacing: 1px;")
        log_layout.addWidget(log_title)

        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("""
            QTextEdit {
                background-color: #020617;
                border: 1px solid #1E293B;
                border-radius: 6px;
                color: #A7F3D0;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 11px;
                padding: 8px;
            }
        """)
        log_layout.addWidget(self.log_viewer)
        layout.addWidget(log_frame, 1)

    def _setup_timer(self):
        """Update metrics every 2.5 seconds."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(2500)

    def update_metrics(self):
        """Query real-time hardware telemetry from psutil."""
        try:
            # CPU
            cpu_pct = psutil.cpu_percent(interval=None)
            cpu_count = psutil.cpu_count(logical=True)
            self.card_cpu.set_value(f"{cpu_pct:.1f}%", f"Active Cores: {cpu_count}")

            # RAM
            ram = psutil.virtual_memory()
            used_gb = ram.used / (1024 ** 3)
            total_gb = ram.total / (1024 ** 3)
            self.card_ram.set_value(f"{ram.percent:.1f}%", f"{used_gb:.1f} GB / {total_gb:.1f} GB")

            # Disk
            settings = get_settings()
            anchor = str(settings.jarvis_data_dir.anchor or "C:\\")
            disk = psutil.disk_usage(anchor)
            free_gb = disk.free / (1024 ** 3)
            total_disk_gb = disk.total / (1024 ** 3)
            self.card_disk.set_value(f"{free_gb:.1f} GB Free", f"Total: {total_disk_gb:.1f} GB ({disk.percent}% used)")

            # Battery
            battery = psutil.sensors_battery()
            if battery is not None:
                charging_str = "Plugged In" if battery.power_plugged else "On Battery"
                self.card_battery.set_value(f"{battery.percent:.0f}%", charging_str)
            else:
                self.card_battery.set_value("Desktop / AC", "No battery sensor")

            # System specs overview
            boot_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
            specs = (
                f"<b>Node / Computer Name:</b> {platform.node()}  |  "
                f"<b>Operating System:</b> Windows {platform.release()} (Build {platform.version()})<br>"
                f"<b>Processor:</b> {platform.processor() or 'x86_64 Architecture'}  |  "
                f"<b>System Booted:</b> {boot_time}  |  "
                f"<b>Active Processes:</b> {len(psutil.pids())}"
            )
            self.lbl_system_details.setText(specs)

        except Exception as e:
            self.lbl_system_details.setText(f"<span style='color: #EF4444;'>Telemetry error: {e}</span>")

    def append_log(self, text: str):
        """Append log message to the dashboard viewer."""
        self.log_viewer.append(text)
