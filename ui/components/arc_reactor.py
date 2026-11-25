"""Futuristic Mark VI Triangular-Core Arc Reactor & Interactive HUD Dial for JARVIS.

Renders an animated, multi-layered holographic Iron Man JARVIS core:
- Outer interactive radial control ring with clickable HUD action segments
- Concentric rotating precision degree-tick dials & counter-rotating mechanical arcs
- 10 luminous radial thruster coil segments
- Glowing Mark VI inverted triangle core (clickable to trigger voice listening)
- Reactive colors & pulse speeds for IDLE, LISTENING, THINKING, and SPEAKING states
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QRadialGradient,
    QLinearGradient,
    QFont,
    QPainterPath,
    QPolygonF,
    QCursor,
)
from PySide6.QtWidgets import QWidget


# 12 clickable HUD segments around the perimeter ring
HUD_RING_SEGMENTS: List[Tuple[str, str]] = [
    ("LISTEN", "listen"),
    ("TEST", "test_voice"),
    ("LANG", "cycle_lang"),
    ("CHAT", "tab_chat"),
    ("APPS", "tab_apps"),
    ("FILES", "tab_files"),
    ("SYS", "tab_dashboard"),
    ("MEM", "tab_memory"),
    ("WEB", "tab_browser"),
    ("DEV", "tab_dev"),
    ("KEY", "api_key"),
    ("MUTE", "toggle_mute"),
]


class ArcReactorWidget(QWidget):
    """Futuristic glowing Mark VI triangular Arc Reactor visualizer & interactive HUD dial."""

    STATE_IDLE = "IDLE"
    STATE_LISTENING = "LISTENING"
    STATE_SPEAKING = "SPEAKING"
    STATE_THINKING = "THINKING"

    core_clicked = Signal()
    segment_clicked = Signal(str)

    def __init__(self, parent=None, size: int = 240, interactive_ring: bool = False):
        super().__init__(parent)
        self.base_size = size
        self.interactive_ring = interactive_ring
        self.setMinimumSize(size, size)
        if not interactive_ring:
            self.setMaximumSize(size + 80, size + 80)
        self.setMouseTracking(True)

        self.state = self.STATE_IDLE
        self.angle = 0.0
        self.pulse = 0.0
        self.pulse_dir = 1
        self._hovered_segment: Optional[int] = None
        self._hovered_core: bool = False
        self._audio_level: float = 0.0

        # Smooth ~30 FPS animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(33)

    def set_state(self, new_state: str):
        self.state = new_state
        self.update()

    def set_audio_level(self, level: float):
        """Optional normalized level (0.0-1.0) to modulate core glow."""
        self._audio_level = max(0.0, min(1.0, level))

    def _animate(self):
        if self.state == self.STATE_SPEAKING:
            speed = 2.2
        elif self.state == self.STATE_THINKING:
            speed = 3.8
        elif self.state == self.STATE_LISTENING:
            speed = 1.6
        else:
            speed = 0.55

        self.angle = (self.angle + speed) % 360.0

        pulse_speed = 0.065 if self.state in (self.STATE_SPEAKING, self.STATE_LISTENING, self.STATE_THINKING) else 0.02
        self.pulse += self.pulse_dir * pulse_speed
        if self.pulse >= 1.0:
            self.pulse = 1.0
            self.pulse_dir = -1
        elif self.pulse <= 0.0:
            self.pulse = 0.0
            self.pulse_dir = 1

        self.update()

    def _hit_test(self, pos: QPointF) -> Tuple[bool, Optional[int]]:
        """Return (is_core, segment_index)."""
        w, h = self.width(), self.height()
        center = QPointF(w / 2.0, h / 2.0)
        radius = min(w, h) / 2.0 - 10.0
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        dist = math.hypot(dx, dy)

        if dist <= radius * 0.44:
            return True, None

        if self.interactive_ring and (radius * 0.78 <= dist <= radius * 0.99):
            deg = (math.degrees(math.atan2(dy, dx)) + 360.0 + 90.0) % 360.0
            n = len(HUD_RING_SEGMENTS)
            seg_idx = int(deg / (360.0 / n)) % n
            return False, seg_idx

        return False, None

    def mouseMoveEvent(self, event):
        is_core, seg = self._hit_test(event.position())
        if is_core != self._hovered_core or seg != self._hovered_segment:
            self._hovered_core = is_core
            self._hovered_segment = seg
            if is_core or seg is not None:
                self.setCursor(QCursor(Qt.PointingHandCursor))
            else:
                self.setCursor(QCursor(Qt.ArrowCursor))
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_core = False
        self._hovered_segment = None
        self.setCursor(QCursor(Qt.ArrowCursor))
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            is_core, seg = self._hit_test(event.position())
            if is_core:
                self.core_clicked.emit()
            elif seg is not None:
                _, action = HUD_RING_SEGMENTS[seg]
                self.segment_clicked.emit(action)
        super().mousePressEvent(event)

    def _get_palette(self) -> Tuple[QColor, QColor, QColor]:
        """Return (primary, bright_core, aura) based on current state."""
        if self.state == self.STATE_LISTENING:
            return QColor(245, 158, 11), QColor(254, 243, 199), QColor(251, 191, 36, 140)
        if self.state == self.STATE_THINKING:
            return QColor(168, 85, 247), QColor(243, 232, 255), QColor(192, 132, 252, 150)
        if self.state == self.STATE_SPEAKING:
            return QColor(0, 240, 255), QColor(235, 252, 255), QColor(56, 189, 248, 180)
        return QColor(0, 220, 255), QColor(210, 248, 255), QColor(14, 165, 233, 120)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        center = QPointF(w / 2.0, h / 2.0)
        radius = min(w, h) / 2.0 - 10.0
        if radius <= 20:
            return

        primary, bright, aura = self._get_palette()
        intensity = 0.85 + 0.15 * self.pulse + 0.15 * self._audio_level

        # ── 1. Outer Dark HUD Backdrop & Ambient Glow ────────────────────────
        bg_grad = QRadialGradient(center, radius * 1.03)
        bg_grad.setColorAt(0.0, QColor(primary.red(), primary.green(), primary.blue(), int(55 * intensity)))
        bg_grad.setColorAt(0.55, QColor(5, 18, 36, 220))
        bg_grad.setColorAt(0.88, QColor(3, 10, 22, 240))
        bg_grad.setColorAt(1.0, QColor(2, 6, 14, 0))
        painter.setBrush(QBrush(bg_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, radius * 1.02, radius * 1.02)

        # Outermost hairline frame ring
        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 110), 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, radius * 0.99, radius * 0.99)

        # ── 2. Interactive Outer Radial HUD Button Ring ──────────────────────
        if self.interactive_ring:
            n = len(HUD_RING_SEGMENTS)
            span_deg = 360.0 / n
            r_outer = radius * 0.97
            r_inner = radius * 0.79
            r_mid = (r_outer + r_inner) / 2.0

            for i, (label, _) in enumerate(HUD_RING_SEGMENTS):
                # Start angle in Qt coordinates (0 = 3 o'clock, counter-clockwise)
                # Our hit test uses 0 = 12 o'clock clockwise -> qt_deg = 90 - cw_deg
                cw_start = i * span_deg + 1.5
                cw_end = (i + 1) * span_deg - 1.5
                qt_start = 90.0 - cw_end
                qt_span = cw_end - cw_start

                is_hovered = self._hovered_segment == i
                path = QPainterPath()
                rect_out = QRectF(center.x() - r_outer, center.y() - r_outer, r_outer * 2, r_outer * 2)
                rect_in = QRectF(center.x() - r_inner, center.y() - r_inner, r_inner * 2, r_inner * 2)

                start_rad = math.radians(qt_start)
                path.moveTo(
                    center.x() + math.cos(start_rad) * r_inner,
                    center.y() - math.sin(start_rad) * r_inner,
                )
                path.arcTo(rect_out, qt_start, qt_span)
                path.arcTo(rect_in, qt_start + qt_span, -qt_span)
                path.closeSubpath()

                if is_hovered:
                    painter.setBrush(QColor(primary.red(), primary.green(), primary.blue(), 95))
                    painter.setPen(QPen(bright, 1.5))
                else:
                    painter.setBrush(QColor(6, 22, 42, 165))
                    painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 90), 1.0))
                painter.drawPath(path)

                # Draw segment label
                cw_mid = (cw_start + cw_end) / 2.0
                mid_rad = math.radians(cw_mid - 90.0)
                tx = center.x() + math.cos(mid_rad) * r_mid
                ty = center.y() + math.sin(mid_rad) * r_mid

                font_sz = max(7, int(radius * 0.042))
                painter.setFont(QFont("Consolas", font_sz, QFont.Bold))
                painter.setPen(bright if is_hovered else QColor(180, 235, 255, 210))
                painter.drawText(QRectF(tx - 26, ty - 10, 52, 20), Qt.AlignCenter, label)

        # ── 3. Rotating Precision Ruler Tick Ring ────────────────────────────
        tick_outer = radius * (0.76 if self.interactive_ring else 0.94)
        tick_inner = radius * (0.69 if self.interactive_ring else 0.85)
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle * 0.6)

        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 150), 1.0))
        painter.drawEllipse(QPointF(0, 0), tick_outer, tick_outer)
        painter.drawEllipse(QPointF(0, 0), tick_inner, tick_inner)

        num_ticks = 96
        for i in range(num_ticks):
            rad = math.radians(i * (360.0 / num_ticks))
            is_major = (i % 8 == 0)
            is_mid = (i % 4 == 0)
            t_len = (tick_outer - tick_inner) * (0.95 if is_major else (0.65 if is_mid else 0.35))
            alpha = 230 if is_major else (160 if is_mid else 95)
            pen_w = 1.8 if is_major else 1.0
            painter.setPen(QPen(QColor(bright.red(), bright.green(), bright.blue(), alpha), pen_w))
            p1 = QPointF(math.cos(rad) * tick_outer, math.sin(rad) * tick_outer)
            p2 = QPointF(math.cos(rad) * (tick_outer - t_len), math.sin(rad) * (tick_outer - t_len))
            painter.drawLine(p1, p2)
        painter.restore()

        # ── 4. Counter-Rotating Mechanical Arcs & Gear Ring ──────────────────
        gear_r = radius * (0.65 if self.interactive_ring else 0.78)
        painter.save()
        painter.translate(center)
        painter.rotate(-self.angle * 1.15)

        gear_rect = QRectF(-gear_r, -gear_r, gear_r * 2, gear_r * 2)
        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 200), 2.5))
        for start_deg in (10, 100, 190, 280):
            painter.drawArc(gear_rect, start_deg * 16, 62 * 16)

        inner_arc_r = gear_r * 0.90
        inner_rect = QRectF(-inner_arc_r, -inner_arc_r, inner_arc_r * 2, inner_arc_r * 2)
        painter.setPen(QPen(QColor(bright.red(), bright.green(), bright.blue(), 170), 1.4, Qt.DashLine))
        painter.drawEllipse(inner_rect)
        painter.restore()

        # ── 5. 10 Luminous Radial Coil Thrusters (Mark VI style) ─────────────
        coil_outer = radius * (0.56 if self.interactive_ring else 0.67)
        coil_inner = radius * (0.43 if self.interactive_ring else 0.51)
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle * 0.25)

        num_coils = 10
        for i in range(num_coils):
            ang_c = i * (360.0 / num_coils)
            rad1 = math.radians(ang_c - 11.0)
            rad2 = math.radians(ang_c + 11.0)

            poly = QPolygonF([
                QPointF(math.cos(rad1) * coil_inner, math.sin(rad1) * coil_inner),
                QPointF(math.cos(rad1) * coil_outer, math.sin(rad1) * coil_outer),
                QPointF(math.cos(rad2) * coil_outer, math.sin(rad2) * coil_outer),
                QPointF(math.cos(rad2) * coil_inner, math.sin(rad2) * coil_inner),
            ])
            coil_alpha = int(170 + 75 * math.sin(self.pulse * math.pi + i * 0.5))
            painter.setBrush(QColor(primary.red(), primary.green(), primary.blue(), min(245, coil_alpha)))
            painter.setPen(QPen(bright, 1.0))
            painter.drawPolygon(poly)
        painter.restore()

        # ── 6. Central Neon Energy Aura ──────────────────────────────────────
        core_r = radius * (0.42 if self.interactive_ring else 0.49)
        core_glow_r = core_r * (1.08 + 0.10 * self.pulse + (0.08 if self._hovered_core else 0.0))
        core_grad = QRadialGradient(center, core_glow_r)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 240))
        core_grad.setColorAt(0.28, QColor(primary.red(), primary.green(), primary.blue(), 210))
        core_grad.setColorAt(0.68, QColor(primary.red(), primary.green(), primary.blue(), 90))
        core_grad.setColorAt(1.0, QColor(primary.red(), primary.green(), primary.blue(), 0))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, core_glow_r, core_glow_r)

        # ── 7. Inverted Glowing Mark VI Triangle Core (▽) ────────────────────
        tri_r = core_r * 0.88
        # Vertices: top-left (-150°), top-right (-30°), bottom (+90°)
        tri_pts = [
            QPointF(center.x() + math.cos(math.radians(a)) * tri_r, center.y() + math.sin(math.radians(a)) * tri_r)
            for a in (-150.0, -30.0, 90.0)
        ]
        tri_poly = QPolygonF(tri_pts)

        # Outer triangle glow stroke
        painter.setBrush(QColor(8, 28, 54, 185))
        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 120), 6.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPolygon(tri_poly)

        # Bright crisp beveled edge
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(bright, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPolygon(tri_poly)

        # Inner recessed triangle
        tri_inner_r = tri_r * 0.72
        tri_inner_pts = [
            QPointF(center.x() + math.cos(math.radians(a)) * tri_inner_r, center.y() + math.sin(math.radians(a)) * tri_inner_r)
            for a in (-150.0, -30.0, 90.0)
        ]
        painter.setBrush(QColor(primary.red(), primary.green(), primary.blue(), int(45 + 35 * self.pulse)))
        painter.setPen(QPen(QColor(primary.red(), primary.green(), primary.blue(), 200), 1.3))
        painter.drawPolygon(QPolygonF(tri_inner_pts))

        # Centroid target ring & core readout
        centroid_r = tri_r * 0.25
        painter.setPen(QPen(bright, 1.5))
        painter.setBrush(QColor(2, 12, 26, 200))
        painter.drawEllipse(center, centroid_r, centroid_r)

        painter.setFont(QFont("Consolas", max(7, int(radius * 0.048)), QFont.Bold))
        painter.setPen(bright)
        if self._hovered_core and self.state == self.STATE_IDLE:
            status_txt = "SPEAK"
        elif self.state == self.STATE_IDLE:
            status_txt = "JARVIS"
        else:
            status_txt = self.state[:6]
        painter.drawText(QRectF(center.x() - 48, center.y() - 10, 96, 20), Qt.AlignCenter, status_txt)
