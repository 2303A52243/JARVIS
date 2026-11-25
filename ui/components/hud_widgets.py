"""Custom Sree Industries Holographic HUD Widgets for JARVIS.

Provides authentic cybernetic HUD building blocks matching the JARVIS OS aesthetic:
- HudFrame: Chamfered dark-translucent panel with neon corner brackets & tech header
- WaveformGraphWidget: Live scrolling area, dual-trace, and spectrum bar graphs
- CircularDriveGauge: Segmented circular disk storage ring
- DigitalClockWeatherWidget: Live digital clock + async local weather telemetry
- JarvisOsBadgeWidget: Top-center JARVIS OS identity & status badge
- SreeBottomBanner: Bottom-center glowing SREE INDUSTRIES emblem
"""

from __future__ import annotations

import math
import time
import platform
from collections import deque
from typing import Deque, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QLinearGradient,
    QFont,
    QPainterPath,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)


class HudFrame(QFrame):
    """Cybernetic HUD container with chamfered corners, neon brackets, and tech header."""

    def __init__(self, title: str = "", tag: str = "", parent=None):
        super().__init__(parent)
        self._title = title.upper()
        self._tag = tag.upper()
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.inner_layout = QVBoxLayout(self)
        self.inner_layout.setContentsMargins(10, 26 if title else 10, 10, 8)
        self.inner_layout.setSpacing(6)

    def set_tag(self, tag: str) -> None:
        self._tag = tag.upper()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cut = 9.0

        # Chamfered octagonal path
        poly = QPolygonF([
            QPointF(cut, 1),
            QPointF(w - 1, 1),
            QPointF(w - 1, h - cut),
            QPointF(w - cut, h - 1),
            QPointF(1, h - 1),
            QPointF(1, cut),
        ])

        # Translucent dark cyber backdrop
        painter.setBrush(QColor(4, 15, 30, 210))
        painter.setPen(QPen(QColor(0, 180, 230, 110), 1.0))
        painter.drawPolygon(poly)

        # Glowing corner brackets
        painter.setPen(QPen(QColor(0, 240, 255, 220), 1.8))
        b = 12.0
        # Top-left chamfer accent
        painter.drawLine(QPointF(1, cut + b), QPointF(1, cut))
        painter.drawLine(QPointF(1, cut), QPointF(cut, 1))
        painter.drawLine(QPointF(cut, 1), QPointF(cut + b, 1))

        # Top-right accent
        painter.drawLine(QPointF(w - b - 4, 1), QPointF(w - 1, 1))
        painter.drawLine(QPointF(w - 1, 1), QPointF(w - 1, b))

        # Bottom-right chamfer accent
        painter.drawLine(QPointF(w - 1, h - cut - b), QPointF(w - 1, h - cut))
        painter.drawLine(QPointF(w - 1, h - cut), QPointF(w - cut, h - 1))
        painter.drawLine(QPointF(w - cut, h - 1), QPointF(w - cut - b, h - 1))

        # Bottom-left accent
        painter.drawLine(QPointF(1, h - b), QPointF(1, h - 1))
        painter.drawLine(QPointF(1, h - 1), QPointF(b, h - 1))

        # Header strip & title
        if self._title:
            painter.setBrush(QColor(0, 140, 210, 35))
            painter.setPen(Qt.NoPen)
            painter.drawRect(QRectF(10, 4, w - 20, 18))

            painter.setPen(QPen(QColor(0, 220, 255, 130), 1.0))
            painter.drawLine(QPointF(10, 22), QPointF(w - 10, 22))

            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(QColor(0, 240, 255, 235))
            painter.drawText(QRectF(14, 4, max(60.0, w * 0.58), 18), Qt.AlignVCenter | Qt.AlignLeft, f"▪ {self._title}")

            if self._tag:
                painter.setFont(QFont("Consolas", 8, QFont.Bold))
                painter.setPen(QColor(125, 211, 252, 220))
                painter.drawText(QRectF(w * 0.52, 4, max(40.0, w * 0.48 - 14), 18), Qt.AlignVCenter | Qt.AlignRight, self._tag)


class WaveformGraphWidget(QWidget):
    """Real-time glowing cyan telemetry waveform / equalizer graph."""

    def __init__(
        self,
        mode: str = "area",
        max_points: int = 48,
        primary_color: QColor = QColor(0, 240, 255),
        secondary_color: QColor = QColor(56, 189, 248),
        min_height: int = 58,
        parent=None,
    ):
        super().__init__(parent)
        self.mode = mode  # "area", "dual", "bars"
        self.max_points = max_points
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.setMinimumHeight(min_height)

        self.data1: Deque[float] = deque([0.0] * max_points, maxlen=max_points)
        self.data2: Deque[float] = deque([0.0] * max_points, maxlen=max_points)
        self._max_scale = 100.0
        self._label_overlay = ""

    def push_value(self, v1: float, v2: Optional[float] = None, max_scale: float = 100.0, overlay: str = "") -> None:
        self._max_scale = max(1.0, max_scale)
        self.data1.append(max(0.0, v1))
        if v2 is not None:
            self.data2.append(max(0.0, v2))
        if overlay:
            self._label_overlay = overlay
        self.update()

    def set_bars(self, values: List[float], max_scale: float = 100.0) -> None:
        self._max_scale = max(1.0, max_scale)
        self.data1 = deque(values[-self.max_points:], maxlen=self.max_points)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        if w < 20 or h < 16:
            return

        # Subtle background & tech grid
        painter.fillRect(0, 0, w, h, QColor(2, 10, 22, 180))
        grid_pen = QPen(QColor(0, 180, 230, 35), 1.0, Qt.DotLine)
        painter.setPen(grid_pen)
        for frac in (0.25, 0.5, 0.75):
            y = h * frac
            painter.drawLine(QPointF(0, y), QPointF(w, y))
        for i in range(1, 6):
            x = (w / 6.0) * i
            painter.drawLine(QPointF(x, 0), QPointF(x, h))

        painter.setPen(QPen(QColor(0, 180, 230, 70), 1.0))
        painter.drawRect(0, 0, w - 1, h - 1)

        if self.mode == "bars":
            vals = list(self.data1)
            n = max(1, len(vals))
            bar_slot = w / n
            bar_w = max(2.0, bar_slot * 0.65)
            for i, val in enumerate(vals):
                ratio = min(1.0, val / self._max_scale)
                bh = max(2.0, ratio * (h - 6))
                x = i * bar_slot + (bar_slot - bar_w) / 2.0
                y = h - 3 - bh

                grad = QLinearGradient(x, y, x, h - 3)
                grad.setColorAt(0.0, QColor(210, 250, 255, 240))
                grad.setColorAt(0.4, self.primary_color)
                grad.setColorAt(1.0, QColor(2, 100, 160, 140))
                painter.fillRect(QRectF(x, y, bar_w, bh), QBrush(grad))
        else:
            self._draw_trace(painter, list(self.data1), self.primary_color, fill=True, w=w, h=h)
            if self.mode == "dual":
                self._draw_trace(painter, list(self.data2), self.secondary_color, fill=False, w=w, h=h)

        if self._label_overlay:
            painter.setFont(QFont("Consolas", 8, QFont.Bold))
            painter.setPen(QColor(220, 248, 255, 220))
            painter.drawText(QRectF(6, 2, w - 12, 16), Qt.AlignRight | Qt.AlignTop, self._label_overlay)

    def _draw_trace(self, painter: QPainter, vals: List[float], color: QColor, fill: bool, w: float, h: float):
        if len(vals) < 2:
            return

        step_x = w / (len(vals) - 1)
        points: List[QPointF] = []
        for i, val in enumerate(vals):
            ratio = min(1.0, val / self._max_scale)
            x = i * step_x
            y = (h - 4) - ratio * (h - 10)
            points.append(QPointF(x, y))

        if fill:
            area_path = QPainterPath()
            area_path.moveTo(0, h - 2)
            for pt in points:
                area_path.lineTo(pt)
            area_path.lineTo(w, h - 2)
            area_path.closeSubpath()

            grad = QLinearGradient(0, 0, 0, h)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), 110))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 10))
            painter.fillPath(area_path, QBrush(grad))

        line_path = QPainterPath()
        line_path.moveTo(points[0])
        for pt in points[1:]:
            line_path.lineTo(pt)

        painter.setPen(QPen(color, 1.6))
        painter.drawPath(line_path)


class CircularDriveGauge(QWidget):
    """Segmented circular disk storage ring matching Sree HUD."""

    def __init__(self, drive_name: str = "C:\\", parent=None):
        super().__init__(parent)
        self.drive_name = drive_name
        self.percent = 0.0
        self.free_gb = 0.0
        self.total_gb = 0.0
        self.setMinimumSize(130, 82)

    def set_usage(self, drive_name: str, percent: float, free_gb: float, total_gb: float) -> None:
        self.drive_name = drive_name
        self.percent = max(0.0, min(100.0, percent))
        self.free_gb = free_gb
        self.total_gb = total_gb
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        r = min(h - 10, 68) / 2.0
        cx, cy = r + 10.0, h / 2.0
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        # Track arc
        painter.setPen(QPen(QColor(15, 50, 80, 180), 5.0))
        painter.drawArc(rect, 0, 360 * 16)

        # Progress arc
        span = int((self.percent / 100.0) * 360 * 16)
        arc_color = QColor(245, 158, 11) if self.percent > 85 else QColor(0, 240, 255)
        painter.setPen(QPen(arc_color, 5.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, -span)

        # Center percentage
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor(225, 250, 255))
        painter.drawText(rect, Qt.AlignCenter, f"{self.percent:.0f}%")

        # Right side drive details
        tx = cx + r + 12.0
        tw = max(40.0, w - tx - 4.0)
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor(0, 240, 255))
        painter.drawText(QRectF(tx, 10, tw, 18), Qt.AlignLeft | Qt.AlignVCenter, f"DRIVE {self.drive_name}")

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor(180, 225, 245))
        used_gb = max(0.0, self.total_gb - self.free_gb)
        painter.drawText(QRectF(tx, 28, tw, 16), Qt.AlignLeft | Qt.AlignVCenter, f"USED : {used_gb:.0f} GB")
        painter.drawText(QRectF(tx, 44, tw, 16), Qt.AlignLeft | Qt.AlignVCenter, f"FREE : {self.free_gb:.0f} GB")
        painter.drawText(QRectF(tx, 60, tw, 16), Qt.AlignLeft | Qt.AlignVCenter, f"TOTAL: {self.total_gb:.0f} GB")


class _WeatherWorker(QThread):
    """Non-blocking background worker to fetch local weather once."""
    fetched = Signal(dict)

    def run(self):
        try:
            import requests
            r = requests.get("https://wttr.in/?format=j1", timeout=4)
            if r.status_code == 200:
                data = r.json()
                curr = data["current_condition"][0]
                area = data.get("nearest_area", [{}])[0]
                city = area.get("areaName", [{}])[0].get("value", "Local Sector")
                country = area.get("country", [{}])[0].get("value", "")
                weather_list = data.get("weather", [])
                forecast = []
                for day in weather_list[:3]:
                    forecast.append({
                        "date": day.get("date", ""),
                        "max": day.get("maxtempC", "--"),
                        "min": day.get("mintempC", "--"),
                    })
                self.fetched.emit({
                    "city": f"{city}, {country}".strip(", "),
                    "temp_c": curr.get("temp_C", "--"),
                    "feels_like": curr.get("FeelsLikeC", "--"),
                    "desc": curr.get("weatherDesc", [{}])[0].get("value", "Nominal"),
                    "humidity": curr.get("humidity", "--"),
                    "wind_kmph": curr.get("windspeedKmph", "--"),
                    "forecast": forecast,
                })
        except Exception:
            pass


class DigitalClockWeatherWidget(QWidget):
    """Right-panel Sree Digital Clock & Local Weather/Environment display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._weather = {
            "city": f"{platform.node()} // LOCAL",
            "temp_c": "28",
            "feels_like": "29",
            "desc": "Clear / Standby",
            "humidity": "45",
            "wind_kmph": "8",
            "forecast": [],
        }
        self._init_ui()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        # Fetch live weather gently in background after UI shows
        QTimer.singleShot(1500, self._fetch_weather)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(10)

        # Left half: Weather readout
        w_col = QVBoxLayout()
        w_col.setSpacing(2)

        self.lbl_city = QLabel(self._weather["city"])
        self.lbl_city.setStyleSheet("color: #7DD3FC; font-family: Consolas; font-size: 10px; font-weight: bold;")
        w_col.addWidget(self.lbl_city)

        self.lbl_temp = QLabel(f"{self._weather['temp_c']}°C")
        self.lbl_temp.setStyleSheet("color: #E0F7FF; font-family: Consolas; font-size: 26px; font-weight: 900;")
        w_col.addWidget(self.lbl_temp)

        self.lbl_desc = QLabel(self._weather["desc"])
        self.lbl_desc.setStyleSheet("color: #00F0FF; font-family: Consolas; font-size: 11px; font-weight: bold;")
        w_col.addWidget(self.lbl_desc)

        self.lbl_weather_details = QLabel(
            f"Feels Like: {self._weather['feels_like']}°C\n"
            f"Humidity: {self._weather['humidity']}%\n"
            f"Wind: {self._weather['wind_kmph']} km/h"
        )
        self.lbl_weather_details.setStyleSheet("color: #94A3B8; font-family: Consolas; font-size: 10px; line-height: 1.3;")
        w_col.addWidget(self.lbl_weather_details)
        w_col.addStretch()
        layout.addLayout(w_col, 1)

        # Right half: Digital Clock & Forecast
        c_col = QVBoxLayout()
        c_col.setSpacing(3)
        c_col.setAlignment(Qt.AlignRight | Qt.AlignTop)

        self.lbl_time = QLabel("00:00:00")
        self.lbl_time.setAlignment(Qt.AlignRight)
        self.lbl_time.setStyleSheet(
            "color: #FFFFFF; font-family: Consolas; font-size: 24px; font-weight: 900; letter-spacing: 2px;"
        )
        c_col.addWidget(self.lbl_time)

        self.lbl_ampm_date = QLabel("PM • WED, NOV 25")
        self.lbl_ampm_date.setAlignment(Qt.AlignRight)
        self.lbl_ampm_date.setStyleSheet("color: #00F0FF; font-family: Consolas; font-size: 10px; font-weight: bold;")
        c_col.addWidget(self.lbl_ampm_date)

        self.lbl_forecast = QLabel("SREE ENV MONITOR\nSENSORS: NOMINAL\nVOICE: EN / TE / HI")
        self.lbl_forecast.setAlignment(Qt.AlignRight)
        self.lbl_forecast.setStyleSheet("color: #64748B; font-family: Consolas; font-size: 9px; margin-top: 6px;")
        c_col.addWidget(self.lbl_forecast)
        c_col.addStretch()
        layout.addLayout(c_col, 1)

    def _update_clock(self):
        self.lbl_time.setText(time.strftime("%I:%M:%S"))
        self.lbl_ampm_date.setText(time.strftime("%p • %a, %b %d %Y").upper())

    def _fetch_weather(self):
        self._worker = _WeatherWorker()
        self._worker.fetched.connect(self._on_weather_ready)
        self._worker.start()

    def _on_weather_ready(self, data: dict):
        self._weather.update(data)
        self.lbl_city.setText(self._weather["city"][:28])
        self.lbl_temp.setText(f"{self._weather['temp_c']}°C")
        self.lbl_desc.setText(self._weather["desc"][:24])
        self.lbl_weather_details.setText(
            f"Feels Like: {self._weather['feels_like']}°C\n"
            f"Humidity: {self._weather['humidity']}%\n"
            f"Wind: {self._weather['wind_kmph']} km/h"
        )
        fc = self._weather.get("forecast", [])
        if fc:
            lines = [f"{d['date'][-5:]}: {d['min']}°/{d['max']}°C" for d in fc[:3]]
            self.lbl_forecast.setText("OUTLOOK\n" + "\n".join(lines))


class JarvisOsBadgeWidget(QWidget):
    """Top-center attached JARVIS OS identity & live status plate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(365, 48)
        self._provider_text = "HYBRID CORE"
        self._lang_text = "EN"
        self._user_text = platform.node() or "Boss"

    def set_status(self, provider: str, lang: str) -> None:
        self._provider_text = provider.upper()
        self._lang_text = lang.upper()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # Angled tech badge frame
        poly = QPolygonF([
            QPointF(14, 2),
            QPointF(w - 14, 2),
            QPointF(w - 2, 16),
            QPointF(w - 2, h - 4),
            QPointF(w - 14, h - 2),
            QPointF(14, h - 2),
            QPointF(2, h - 4),
            QPointF(2, 16),
        ])
        painter.setBrush(QColor(6, 22, 42, 230))
        painter.setPen(QPen(QColor(0, 240, 255, 200), 1.4))
        painter.drawPolygon(poly)

        # Left circular core emblem
        emblem_c = QPointF(28, h / 2.0)
        painter.setBrush(QColor(0, 240, 255, 50))
        painter.setPen(QPen(QColor(0, 240, 255), 1.6))
        painter.drawEllipse(emblem_c, 14, 14)
        painter.setBrush(QColor(180, 250, 255))
        painter.drawEllipse(emblem_c, 5, 5)

        # Text block
        painter.setFont(QFont("Consolas", 11, QFont.Bold))
        painter.setPen(QColor(225, 252, 255))
        painter.drawText(QRectF(52, 5, 160, 20), Qt.AlignLeft | Qt.AlignVCenter, "JARVIS OS  v2.0")

        painter.setFont(QFont("Consolas", 8))
        painter.setPen(QColor(56, 189, 248))
        painter.drawText(QRectF(52, 25, 235, 16), Qt.AlignLeft | Qt.AlignVCenter, f"User: {self._user_text[:16]} • {self._provider_text}")

        # Right status pill
        pill = QRectF(w - 68, 11, 54, 24)
        painter.setBrush(QColor(0, 120, 170, 90))
        painter.setPen(QPen(QColor(0, 240, 255, 180), 1.0))
        painter.drawRoundedRect(pill, 4, 4)
        painter.setFont(QFont("Consolas", 9, QFont.Bold))
        painter.setPen(QColor(0, 255, 180))
        painter.drawText(pill, Qt.AlignCenter, f"● {self._lang_text}")


class SreeBottomBanner(QWidget):
    """Bottom-center glowing SREE INDUSTRIES emblem matching the HUD layout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx = w / 2.0

        # Glowing side wings / circuit lines
        painter.setPen(QPen(QColor(0, 220, 255, 160), 1.6))
        painter.drawLine(QPointF(cx - 210, h - 8), QPointF(cx - 125, h - 8))
        painter.drawLine(QPointF(cx - 125, h - 8), QPointF(cx - 115, 6))
        painter.drawLine(QPointF(cx + 210, h - 8), QPointF(cx + 125, h - 8))
        painter.drawLine(QPointF(cx + 125, h - 8), QPointF(cx + 115, 6))

        # Horizontal glow bar beneath title
        painter.setPen(QPen(QColor(0, 240, 255, 220), 2.0))
        painter.drawLine(QPointF(cx - 112, h - 5), QPointF(cx + 112, h - 5))

        # Title
        font = QFont("Segoe UI", 14, QFont.Black)
        font.setItalic(True)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 3.0)
        painter.setFont(font)

        # Glow shadow pass
        painter.setPen(QColor(0, 240, 255, 90))
        painter.drawText(QRectF(cx - 160, 1, 320, h - 6), Qt.AlignCenter, "SREE INDUSTRIES")
        # Crisp foreground pass
        painter.setPen(QColor(150, 240, 255))
        painter.drawText(QRectF(cx - 160, 0, 320, h - 8), Qt.AlignCenter, "SREE INDUSTRIES")


# Backward compatibility alias
StarkBottomBanner = SreeBottomBanner
