"""Full-Screen Sree Industries / JARVIS OS Holographic HUD Home Panel.

Combines:
- Authentic 3-column Iron Man JARVIS OS layout:
  * Left HUD: Audio Spectrum Matrix, CPU Telemetry, RAM Usage, Storage Ring, Network Up/Down
  * Centerpiece: JARVIS OS Identity Badge, Interactive Mark VI Triangular Arc Reactor, Inline Neural Command & Transcript, SREE INDUSTRIES footer
  * Right HUD: System/IP/Battery/Uptime, Digital Clock & Weather, Per-Core Load Spectrum, Quick App & Module Dock
- Full Multilingual Voice (English, Telugu, Hindi) + OpenRouter/OpenAI Brain integration
- Non-blocking background QThread workers so HUD animations stay smooth at 30 FPS
"""

from __future__ import annotations

import math
import os
import platform
import random
import socket
import threading
import time
from typing import List, Optional

import psutil
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QSizePolicy,
)

from app.config import get_settings
from ai.jarvis_brain import process_user_query
from system.application_manager import launch_app
from voice.microphone import record_until_silence, DEFAULT_SILENCE_STOP_SECONDS
from voice.text_to_speech import speak_text, stop_speaking, is_speaking, StreamingSpeechSession
from ui.components.arc_reactor import ArcReactorWidget
from ui.components.api_key_dialog import show_api_key_dialog
from ui.components.hud_widgets import (
    HudFrame,
    WaveformGraphWidget,
    CircularDriveGauge,
    DigitalClockWeatherWidget,
    JarvisOsBadgeWidget,
    SreeBottomBanner,
    StarkBottomBanner,
)


class _HudRecordWorker(QThread):
    finished = Signal(str)  # empty string if no speech detected
    speech_started = Signal()
    level_changed = Signal(float)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            path = record_until_silence(
                silence_duration=DEFAULT_SILENCE_STOP_SECONDS,
                wait_timeout=12.0,
                stop_event=self._stop_event,
                on_speech_start=lambda: self.speech_started.emit(),
                on_level=lambda lvl: self.level_changed.emit(lvl),
            )
            self.finished.emit(str(path) if path else "")
        except Exception as exc:
            self.error.emit(str(exc))


class _AutoVadMonitorWorker(QThread):
    """Continuous hands-free Voice Activity Detection monitor (stops after 1.5s silence)."""

    audio_captured = Signal(str)
    speech_started = Signal()
    level_changed = Signal(float)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self._stop_event = threading.Event()
        self._cycle_abort = threading.Event()
        self._paused = False

    def set_paused(self, paused: bool):
        self._paused = paused
        if paused:
            self._cycle_abort.set()
        else:
            self._cycle_abort.clear()

    def stop(self):
        self._stop_event.set()
        self._cycle_abort.set()

    def run(self):
        was_speaking_tts = False
        while not self._stop_event.is_set():
            if self._paused or is_speaking():
                if is_speaking():
                    was_speaking_tts = True
                self.level_changed.emit(0.0)
                time.sleep(0.12)
                continue

            if was_speaking_tts:
                # Echo tail cooldown after JARVIS finishes speaking
                was_speaking_tts = False
                time.sleep(0.25)
                continue

            self._cycle_abort.clear()
            try:
                path = record_until_silence(
                    silence_duration=DEFAULT_SILENCE_STOP_SECONDS,
                    wait_timeout=1.2,
                    stop_event=self._cycle_abort,
                    on_speech_start=lambda: self.speech_started.emit(),
                    on_level=lambda lvl: self.level_changed.emit(lvl),
                )
                if path and not self._stop_event.is_set() and not self._paused:
                    self._paused = True
                    self.audio_captured.emit(str(path))
            except Exception as exc:
                self.error.emit(str(exc))
                time.sleep(1.0)


class _HudTranscribeWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, audio_path: str, language: str = "en"):
        super().__init__()
        self.audio_path = audio_path
        self.language = language

    def run(self):
        try:
            from voice.speech_to_text import transcribe_file
            text = transcribe_file(self.audio_path, language=self.language)
            self.finished.emit(text)
        except Exception as exc:
            self.error.emit(str(exc))


class _HudBrainWorker(QThread):
    finished = Signal(str, str, bool, bool)
    speech_started = Signal()
    error = Signal(str)

    def __init__(self, query: str, language: str = "en", speak_enabled: bool = True):
        super().__init__()
        self.query = query
        self.language = language
        self.speak_enabled = speak_enabled

    def run(self):
        session: Optional[StreamingSpeechSession] = None
        started = False

        def _on_sentence(chunk: str):
            nonlocal session, started
            if not self.speak_enabled:
                return
            if session is None:
                session = StreamingSpeechSession(language=self.language)
                started = True
                self.speech_started.emit()
            session.push_text(chunk)

        try:
            reply, should_speak = process_user_query(
                self.query,
                language=self.language,
                on_sentence=_on_sentence if self.speak_enabled else None,
            )
            if session is not None:
                session.finish()
            self.finished.emit(self.query, reply, should_speak, started)
        except Exception as exc:
            if session is not None:
                session.finish()
            self.error.emit(str(exc))


class JarvisHudHomePanel(QWidget):
    """Main Sree Industries Holographic Command Center."""

    navigate_requested = Signal(str)
    interaction_logged = Signal(str, str)  # user_text, jarvis_reply
    language_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_language = get_settings().jarvis_language
        if self.current_language not in ("en", "te", "hi"):
            self.current_language = "en"

        self.is_recording = False
        self.voice_enabled = True
        self.auto_voice_enabled = getattr(get_settings(), "jarvis_auto_voice", True)
        self._live_mic_level = 0.0
        self._last_net_io = psutil.net_io_counters()
        self._last_net_ts = time.time()
        self._eq_phase = 0.0
        self._local_ip = self._detect_local_ip()

        self._record_worker: Optional[_HudRecordWorker] = None
        self._auto_worker: Optional[_AutoVadMonitorWorker] = None
        self._transcribe_worker: Optional[_HudTranscribeWorker] = None
        self._brain_worker: Optional[_HudBrainWorker] = None

        self._init_ui()
        self._sync_badge_status()

        # Telemetry refresh timer (every 1.0s)
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(self._update_telemetry)
        self._telemetry_timer.start(1000)

        # Equalizer animation timer (every 80ms)
        self._eq_timer = QTimer(self)
        self._eq_timer.timeout.connect(self._animate_equalizer)
        self._eq_timer.start(80)

        # Poll TTS playback finish cleanly instead of fixed timer cutoffs
        self._tts_watch_timer = QTimer(self)
        self._tts_watch_timer.timeout.connect(self._check_tts_done)

        QTimer.singleShot(250, self._update_telemetry)
        QTimer.singleShot(1400, self._maybe_start_auto_voice)

    @staticmethod
    def _detect_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return "127.0.0.1"

    def _hud_btn_style(self, highlight: bool = False) -> str:
        if highlight:
            return """
                QPushButton {
                    background: rgba(0, 180, 230, 65);
                    color: #E0F7FF;
                    border: 1px solid #00F0FF;
                    border-radius: 3px;
                    padding: 5px 8px;
                    font-family: Consolas;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #00F0FF;
                    color: #020814;
                }
            """
        return """
            QPushButton {
                background: rgba(6, 26, 50, 190);
                color: #7DD3FC;
                border: 1px solid #0C4A6E;
                border-radius: 3px;
                padding: 5px 8px;
                font-family: Consolas;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(2, 132, 199, 130);
                color: #FFFFFF;
                border-color: #00F0FF;
            }
        """

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(12)

        # ════════════════════════════════════════════════════════════════════
        # LEFT COLUMN: AUDIO / CPU / RAM / STORAGE / NETWORK
        # ════════════════════════════════════════════════════════════════════
        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        # L1: Audio & Voice Matrix
        self.frame_audio = HudFrame("AUDIO MATRIX", "16KHZ // MONO")
        self.eq_graph = WaveformGraphWidget(mode="bars", max_points=26, min_height=46)
        self.frame_audio.inner_layout.addWidget(self.eq_graph)

        audio_btns = QHBoxLayout()
        audio_btns.setSpacing(4)
        self.btn_hud_listen = QPushButton("🎙️ SPEAK")
        self.btn_hud_listen.setStyleSheet(self._hud_btn_style(highlight=True))
        self.btn_hud_listen.clicked.connect(self.start_listening)

        self.btn_auto_voice = QPushButton("AUTO: ON" if self.auto_voice_enabled else "AUTO: OFF")
        self.btn_auto_voice.setStyleSheet(self._hud_btn_style(highlight=self.auto_voice_enabled))
        self.btn_auto_voice.clicked.connect(self.toggle_auto_voice)

        self.btn_hud_test = QPushButton("🔊 TEST")
        self.btn_hud_test.setStyleSheet(self._hud_btn_style())
        self.btn_hud_test.clicked.connect(self.test_voice)

        self.btn_hud_mute = QPushButton("🔊 ON")
        self.btn_hud_mute.setStyleSheet(self._hud_btn_style())
        self.btn_hud_mute.clicked.connect(self.toggle_mute)

        audio_btns.addWidget(self.btn_hud_listen, 2)
        audio_btns.addWidget(self.btn_auto_voice, 2)
        audio_btns.addWidget(self.btn_hud_test, 1)
        audio_btns.addWidget(self.btn_hud_mute, 1)
        self.frame_audio.inner_layout.addLayout(audio_btns)
        left_col.addWidget(self.frame_audio)

        # L2: CPU Telemetry
        self.frame_cpu = HudFrame("CPU TELEMETRY", "0.0%")
        self.cpu_graph = WaveformGraphWidget(mode="area", max_points=45, min_height=54)
        self.frame_cpu.inner_layout.addWidget(self.cpu_graph)
        self.lbl_cpu_meta = QLabel("CORES: -- • FREQ: -- MHz • PIDS: --")
        self.lbl_cpu_meta.setStyleSheet("color: #7DD3FC; font-family: Consolas; font-size: 9px;")
        self.frame_cpu.inner_layout.addWidget(self.lbl_cpu_meta)
        left_col.addWidget(self.frame_cpu)

        # L3: RAM Memory
        self.frame_ram = HudFrame("RAM MEMORY", "0.0%")
        self.ram_graph = WaveformGraphWidget(
            mode="area",
            max_points=45,
            primary_color=QColor(56, 189, 248),
            min_height=52,
        )
        self.frame_ram.inner_layout.addWidget(self.ram_graph)
        self.lbl_ram_meta = QLabel("USED: -- GB / TOTAL: -- GB")
        self.lbl_ram_meta.setStyleSheet("color: #7DD3FC; font-family: Consolas; font-size: 9px;")
        self.frame_ram.inner_layout.addWidget(self.lbl_ram_meta)
        left_col.addWidget(self.frame_ram)

        # L4: Storage Matrix
        self.frame_disk = HudFrame("STORAGE DRIVES", "ONLINE")
        self.drive_gauge = CircularDriveGauge("C:\\")
        self.frame_disk.inner_layout.addWidget(self.drive_gauge)
        left_col.addWidget(self.frame_disk)

        # L5: Network Traffic Up/Down
        self.frame_net = HudFrame("NETWORK TRAFFIC UP/DOWN", "0 KB/s")
        self.net_graph = WaveformGraphWidget(
            mode="dual",
            max_points=45,
            primary_color=QColor(0, 240, 255),
            secondary_color=QColor(245, 158, 11),
            min_height=54,
        )
        self.frame_net.inner_layout.addWidget(self.net_graph)
        self.lbl_net_meta = QLabel("DOWN: 0.0 KB/s • UP: 0.0 KB/s")
        self.lbl_net_meta.setStyleSheet("color: #7DD3FC; font-family: Consolas; font-size: 9px;")
        self.frame_net.inner_layout.addWidget(self.lbl_net_meta)
        left_col.addWidget(self.frame_net)

        root.addLayout(left_col, 27)

        # ════════════════════════════════════════════════════════════════════
        # CENTER COLUMN: BADGE + MARK VI ARC REACTOR + CONSOLE + SREE LOGO
        # ════════════════════════════════════════════════════════════════════
        center_col = QVBoxLayout()
        center_col.setSpacing(4)
        center_col.setAlignment(Qt.AlignHCenter)

        # Top Identity Badge
        self.badge = JarvisOsBadgeWidget()
        center_col.addWidget(self.badge, 0, Qt.AlignHCenter)

        # Giant Interactive Mark VI Arc Reactor
        self.reactor = ArcReactorWidget(size=350, interactive_ring=True)
        self.reactor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.reactor.core_clicked.connect(self.start_listening)
        self.reactor.segment_clicked.connect(self._on_ring_segment)
        center_col.addWidget(self.reactor, 5)

        # Live Status Pill
        self.lbl_core_status = QLabel("● CORE ONLINE — CLICK TRIANGLE TO SPEAK")
        self.lbl_core_status.setAlignment(Qt.AlignCenter)
        self.lbl_core_status.setStyleSheet(
            "color: #00F0FF; font-family: Consolas; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        )
        center_col.addWidget(self.lbl_core_status)

        # Compact Holographic Transcript & Command Input
        self.frame_console = HudFrame("NEURAL COMMAND CONSOLE", "EN / TE / HI")
        self.frame_console.setMaximumHeight(168)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setStyleSheet("""
            QTextEdit {
                background: rgba(2, 8, 18, 200);
                border: 1px solid #0C4A6E;
                color: #E2E8F0;
                font-family: 'Segoe UI', Consolas;
                font-size: 11px;
                padding: 4px 6px;
            }
        """)
        self.transcript.setPlainText(
            "J.A.R.V.I.S. HUD Initialized • Click center triangle to speak or type below."
        )
        self.frame_console.inner_layout.addWidget(self.transcript, 1)

        cmd_row = QHBoxLayout()
        cmd_row.setSpacing(6)
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Command JARVIS in English, Telugu (తెలుగు), or Hindi (हिन्दी)...")
        self.cmd_input.setStyleSheet("""
            QLineEdit {
                background: rgba(4, 18, 36, 220);
                border: 1px solid #0284C7;
                color: #F0F9FF;
                font-family: 'Segoe UI', Consolas;
                font-size: 11px;
                padding: 5px 8px;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border-color: #00F0FF;
            }
        """)
        self.cmd_input.returnPressed.connect(self._on_inline_submit)

        self.btn_cmd_send = QPushButton("EXEC ➤")
        self.btn_cmd_send.setStyleSheet(self._hud_btn_style(highlight=True))
        self.btn_cmd_send.clicked.connect(self._on_inline_submit)

        cmd_row.addWidget(self.cmd_input, 1)
        cmd_row.addWidget(self.btn_cmd_send)
        self.frame_console.inner_layout.addLayout(cmd_row)

        center_col.addWidget(self.frame_console, 2)

        # Sree Industries Footer
        self.sree_banner = SreeBottomBanner()
        self.stark_banner = self.sree_banner
        center_col.addWidget(self.sree_banner)

        root.addLayout(center_col, 46)

        # ════════════════════════════════════════════════════════════════════
        # RIGHT COLUMN: LINK/SYSTEM + CLOCK/WEATHER + CORES + QUICK LAUNCH
        # ════════════════════════════════════════════════════════════════════
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        # R1: System Link & Controls
        self.frame_sys = HudFrame("SYSTEM CORE & LINK", self._local_ip)
        self.lbl_sys_info = QLabel("OS: Windows\nUPTIME: --\nBATTERY: --")
        self.lbl_sys_info.setStyleSheet("color: #BAE6FD; font-family: Consolas; font-size: 10px; line-height: 1.35;")
        self.frame_sys.inner_layout.addWidget(self.lbl_sys_info)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["EN (English)", "TE (తెలుగు)", "HI (हिन्दी)"])
        idx_map = {"en": 0, "te": 1, "hi": 2}
        self.combo_lang.setCurrentIndex(idx_map.get(self.current_language, 0))
        self.combo_lang.setStyleSheet("""
            QComboBox {
                background: #061A32;
                color: #00F0FF;
                border: 1px solid #0284C7;
                border-radius: 3px;
                padding: 4px 8px;
                font-family: Consolas;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        self.combo_lang.currentIndexChanged.connect(self._on_lang_index_changed)

        self.btn_api_key = QPushButton("🔑 API KEY")
        self.btn_api_key.setStyleSheet(self._hud_btn_style())
        self.btn_api_key.clicked.connect(self.open_api_key_dialog)

        ctrl_row.addWidget(self.combo_lang, 1)
        ctrl_row.addWidget(self.btn_api_key)
        self.frame_sys.inner_layout.addLayout(ctrl_row)
        right_col.addWidget(self.frame_sys)

        # R2: Digital Clock & Atmospheric Weather
        self.frame_chrono = HudFrame("CHRONO & ATMOSPHERIC", "LOCAL")
        self.clock_weather = DigitalClockWeatherWidget()
        self.frame_chrono.inner_layout.addWidget(self.clock_weather)
        right_col.addWidget(self.frame_chrono, 0)

        # R3: CPU Core Spectrum & Neural Subsystems
        self.frame_cores = HudFrame("LOGICAL CORE LOAD", "MULTICORE")
        self.cores_graph = WaveformGraphWidget(mode="bars", max_points=16, min_height=76)
        self.frame_cores.inner_layout.addWidget(self.cores_graph, 1)
        self.lbl_ai_status = QLabel("STT: GOOGLE/WHISPER • TTS: NEURAL EDGE")
        self.lbl_ai_status.setStyleSheet("color: #38BDF8; font-family: Consolas; font-size: 9px;")
        self.frame_cores.inner_layout.addWidget(self.lbl_ai_status)
        right_col.addWidget(self.frame_cores, 1)

        # R4: System Telemetry & Security Feed
        settings = get_settings()
        pc_mode = "FULL CONTROL (ALL DRIVES)" if settings.jarvis_full_pc_access else "SANDBOXED"
        self.frame_audit = HudFrame("SECURITY & SYSTEM FEED", "FULL ACCESS" if settings.jarvis_full_pc_access else "PROTECTED")
        self.lbl_sec_feed = QLabel(
            f"• PC ACCESS        : {pc_mode}\n"
            f"• AUTO VOICE VAD   : {'ON (3.0s SILENCE)' if self.auto_voice_enabled else 'MANUAL'}\n"
            "• VOICE LANGUAGES  : EN / TE / HI"
        )
        self.lbl_sec_feed.setStyleSheet("color: #6EE7B7; font-family: Consolas; font-size: 9px; line-height: 1.4;")
        self.frame_audit.inner_layout.addWidget(self.lbl_sec_feed)
        right_col.addWidget(self.frame_audit, 0)

        # R5: Quick Launch & Subsystems Dock
        self.frame_dock = HudFrame("TACTICAL QUICK LAUNCH", "MODULES")
        dock_grid = QGridLayout()
        dock_grid.setSpacing(5)

        quick_items = [
            ("🌐 CHROME", lambda: self._quick_launch_app("chrome")),
            ("💻 VS CODE", lambda: self._quick_launch_app("vscode")),
            ("📝 NOTEPAD", lambda: self._quick_launch_app("notepad")),
            ("📂 EXPLORER", lambda: self._quick_launch_app("explorer")),
            ("💬 CHAT TAB", lambda: self.navigate_requested.emit("chat")),
            ("📱 APPS TAB", lambda: self.navigate_requested.emit("apps")),
            ("📁 FILES TAB", lambda: self.navigate_requested.emit("files")),
            ("🧠 MEMORY", lambda: self.navigate_requested.emit("memory")),
        ]
        for idx, (lbl, handler) in enumerate(quick_items):
            btn = QPushButton(lbl)
            btn.setStyleSheet(self._hud_btn_style())
            btn.clicked.connect(handler)
            dock_grid.addWidget(btn, idx // 2, idx % 2)

        self.frame_dock.inner_layout.addLayout(dock_grid)
        right_col.addWidget(self.frame_dock)

        root.addLayout(right_col, 27)

    def _sync_badge_status(self):
        settings = get_settings()
        if settings.is_api_key_configured:
            provider = "OPENROUTER" if settings.is_openrouter else "OPENAI"
        else:
            provider = "OFFLINE"
        self.badge.set_status(provider, self.current_language)

    def _animate_equalizer(self):
        self._eq_phase += 0.35
        bars = []
        state = self.reactor.state
        live = self._live_mic_level
        for i in range(26):
            if state == ArcReactorWidget.STATE_SPEAKING:
                val = 30.0 + 65.0 * abs(math.sin(self._eq_phase * 1.4 + i * 0.45)) * random.uniform(0.6, 1.0)
            elif state == ArcReactorWidget.STATE_LISTENING or live > 0.04:
                base = max(14.0, live * 92.0)
                val = base * (0.45 + 0.55 * abs(math.cos(self._eq_phase * 1.2 + i * 0.4)))
            elif state == ArcReactorWidget.STATE_THINKING:
                val = 20.0 + 40.0 * abs(math.sin(self._eq_phase * 2.0 + i * 0.25))
            else:
                val = 6.0 + 12.0 * abs(math.sin(self._eq_phase * 0.35 + i * 0.3))
            bars.append(val)
        self.eq_graph.set_bars(bars, max_scale=100.0)
        if state in (ArcReactorWidget.STATE_SPEAKING, ArcReactorWidget.STATE_LISTENING):
            self.reactor.set_audio_level(max(live, sum(bars) / (len(bars) * 100.0)))
        else:
            self.reactor.set_audio_level(0.0)

    def _update_telemetry(self):
        try:
            # CPU
            cpu_pct = psutil.cpu_percent(interval=None)
            per_cpu = psutil.cpu_percent(interval=None, percpu=True)
            freq = psutil.cpu_freq()
            freq_mhz = int(freq.current) if freq else 0
            pids = len(psutil.pids())

            self.frame_cpu.set_tag(f"{cpu_pct:.1f}%")
            self.cpu_graph.push_value(cpu_pct, max_scale=100.0, overlay=f"{cpu_pct:.1f}%")
            self.lbl_cpu_meta.setText(f"CORES: {len(per_cpu)} • FREQ: {freq_mhz} MHz • PIDS: {pids}")
            self.cores_graph.set_bars(per_cpu or [cpu_pct], max_scale=100.0)

            # RAM
            vm = psutil.virtual_memory()
            used_gb = vm.used / (1024 ** 3)
            total_gb = vm.total / (1024 ** 3)
            self.frame_ram.set_tag(f"{vm.percent:.1f}%")
            self.ram_graph.push_value(vm.percent, max_scale=100.0, overlay=f"{vm.percent:.1f}%")
            self.lbl_ram_meta.setText(f"USED: {used_gb:.1f} GB / TOTAL: {total_gb:.1f} GB")

            # Disk
            settings = get_settings()
            anchor = str(settings.jarvis_data_dir.anchor or "C:\\")
            disk = psutil.disk_usage(anchor)
            free_gb = disk.free / (1024 ** 3)
            total_disk_gb = disk.total / (1024 ** 3)
            self.drive_gauge.set_usage(anchor, disk.percent, free_gb, total_disk_gb)

            # Network delta
            now = time.time()
            net = psutil.net_io_counters()
            dt = max(0.1, now - self._last_net_ts)
            down_kbps = ((net.bytes_recv - self._last_net_io.bytes_recv) / 1024.0) / dt
            up_kbps = ((net.bytes_sent - self._last_net_io.bytes_sent) / 1024.0) / dt
            self._last_net_io = net
            self._last_net_ts = now

            net_scale = max(50.0, down_kbps * 1.2, up_kbps * 1.2)
            self.frame_net.set_tag(f"{down_kbps + up_kbps:.1f} KB/s")
            self.net_graph.push_value(down_kbps, up_kbps, max_scale=net_scale, overlay=f"↓{down_kbps:.0f} ↑{up_kbps:.0f}")
            self.lbl_net_meta.setText(
                f"DOWN: {down_kbps:.1f} KB/s • UP: {up_kbps:.1f} KB/s • TOT: {(net.bytes_recv + net.bytes_sent) / (1024**2):.0f} MB"
            )

            # System Uptime & Battery
            uptime_sec = int(time.time() - psutil.boot_time())
            hrs, rem = divmod(uptime_sec, 3600)
            mins, secs = divmod(rem, 60)
            bat = psutil.sensors_battery()
            bat_str = f"{bat.percent:.0f}% ({'AC' if bat.power_plugged else 'BAT'})" if bat else "AC POWER"
            self.lbl_sys_info.setText(
                f"NODE   : {platform.node()} (Win {platform.release()})\n"
                f"UPTIME : {hrs:02d}h {mins:02d}m {secs:02d}s\n"
                f"BATTERY: {bat_str}"
            )
        except Exception:
            pass

    def _on_ring_segment(self, action: str):
        mapping = {
            "listen": self.start_listening,
            "test_voice": self.test_voice,
            "cycle_lang": self.cycle_language,
            "toggle_mute": self.toggle_mute,
            "api_key": self.open_api_key_dialog,
            "tab_chat": lambda: self.navigate_requested.emit("chat"),
            "tab_apps": lambda: self.navigate_requested.emit("apps"),
            "tab_files": lambda: self.navigate_requested.emit("files"),
            "tab_dashboard": lambda: self.navigate_requested.emit("dashboard"),
            "tab_memory": lambda: self.navigate_requested.emit("memory"),
            "tab_browser": lambda: self.navigate_requested.emit("browser"),
            "tab_dev": lambda: self.navigate_requested.emit("dev"),
        }
        fn = mapping.get(action)
        if fn:
            fn()

    def set_language(self, lang_code: str):
        idx_map = {"en": 0, "te": 1, "hi": 2}
        if lang_code in idx_map:
            self.combo_lang.blockSignals(True)
            self.combo_lang.setCurrentIndex(idx_map[lang_code])
            self.combo_lang.blockSignals(False)
            self.current_language = lang_code
            self._sync_badge_status()

    def _on_lang_index_changed(self, idx: int):
        codes = ["en", "te", "hi"]
        names = ["English", "Telugu (తెలుగు)", "Hindi (हिन्दी)"]
        self.current_language = codes[idx]
        self._sync_badge_status()
        self.transcript.append(f"ℹ️ Language switched to: {names[idx]}")
        self.language_changed.emit(self.current_language)

    def cycle_language(self):
        next_idx = (self.combo_lang.currentIndex() + 1) % 3
        self.combo_lang.setCurrentIndex(next_idx)

    def open_api_key_dialog(self):
        if show_api_key_dialog(self):
            self._sync_badge_status()
            self.transcript.append("✅ AI API Key saved and activated.")

    def toggle_mute(self):
        self.voice_enabled = not self.voice_enabled
        if self.voice_enabled:
            self.btn_hud_mute.setText("🔊 ON")
            self.transcript.append("🔊 Voice output enabled.")
        else:
            stop_speaking()
            self.btn_hud_mute.setText("🔇 MUTE")
            self.transcript.append("🔇 Voice output muted.")

    def _maybe_start_auto_voice(self):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        if self.auto_voice_enabled:
            self._start_auto_monitor()
            self._reset_reactor()

    def _start_auto_monitor(self):
        if self._auto_worker and self._auto_worker.isRunning():
            self._auto_worker.set_paused(False)
            return
        self._auto_worker = _AutoVadMonitorWorker()
        self._auto_worker.speech_started.connect(self._on_auto_speech_started)
        self._auto_worker.level_changed.connect(self._on_mic_level)
        self._auto_worker.audio_captured.connect(self._on_record_done)
        self._auto_worker.error.connect(self._on_record_error)
        self._auto_worker.start()

    def _stop_auto_monitor(self):
        if self._auto_worker and self._auto_worker.isRunning():
            self._auto_worker.stop()
            self._auto_worker.wait(2000)

    def shutdown(self):
        """Cleanly halt background VAD & timers on window close."""
        self._stop_auto_monitor()
        if self._record_worker and self._record_worker.isRunning():
            self._record_worker.stop()
            self._record_worker.wait(1500)

    def _refresh_security_feed(self):
        settings = get_settings()
        pc_mode = "FULL CONTROL (ALL DRIVES)" if settings.jarvis_full_pc_access else "SANDBOXED"
        self.lbl_sec_feed.setText(
            f"• PC ACCESS        : {pc_mode}\n"
            f"• AUTO VOICE VAD   : {'ON (1.5s SILENCE)' if self.auto_voice_enabled else 'MANUAL'}\n"
            "• VOICE LANGUAGES  : EN / TE / HI"
        )

    def toggle_auto_voice(self):
        self.auto_voice_enabled = not self.auto_voice_enabled
        self.btn_auto_voice.setText("AUTO: ON" if self.auto_voice_enabled else "AUTO: OFF")
        self.btn_auto_voice.setStyleSheet(self._hud_btn_style(highlight=self.auto_voice_enabled))
        self._refresh_security_feed()
        if self.auto_voice_enabled:
            self._start_auto_monitor()
            self.transcript.append("🎙️ Auto-Voice Detection ON (auto-stops 1.5s after silence).")
        else:
            self._stop_auto_monitor()
            self.transcript.append("🎙️ Auto-Voice Detection OFF (manual trigger mode).")
        self._reset_reactor()

    def _on_auto_speech_started(self):
        self.is_recording = True
        self.btn_hud_listen.setText("🔴 SPEAKING...")
        self.reactor.set_state(ArcReactorWidget.STATE_LISTENING)
        self.lbl_core_status.setText("● VOICE DETECTED — LISTENING (1.5s SILENCE STOP)")

    def _on_mic_level(self, level: float):
        self._live_mic_level = level

    def test_voice(self):
        msg = "Hello Boss. Sree Industries JARVIS interface and neural voice drivers are online."
        if self.current_language == "te":
            msg = "నమస్కారం బాస్! నా వాయిస్ సిస్టమ్ విజయవంతంగా పనిచేస్తుంది."
        elif self.current_language == "hi":
            msg = "नमस्ते बॉस! मेरा वॉइस सिस्टम पूरी तरह तैयार है।"

        self.transcript.append(f"[JARVIS]: {msg}")
        self.reactor.set_state(ArcReactorWidget.STATE_SPEAKING)
        self.lbl_core_status.setText("● JARVIS SPEAKING...")
        if self.voice_enabled:
            speak_text(msg, language=self.current_language, non_blocking=True)
            self._tts_watch_timer.start(250)
        else:
            QTimer.singleShot(2000, self._reset_reactor)

    def start_listening(self):
        if self.is_recording and self._record_worker and self._record_worker.isRunning():
            self._record_worker.stop()
            return
        if self._auto_worker and self._auto_worker.isRunning():
            self._auto_worker.set_paused(True)
            self._auto_worker.stop()
            self._auto_worker.wait(1500)

        self.is_recording = True
        self.btn_hud_listen.setText("🔴 LISTENING...")
        self.reactor.set_state(ArcReactorWidget.STATE_LISTENING)
        self.lbl_core_status.setText("● LISTENING — SPEAK NOW (1.5s SILENCE STOP)")

        self._record_worker = _HudRecordWorker()
        self._record_worker.speech_started.connect(self._on_auto_speech_started)
        self._record_worker.level_changed.connect(self._on_mic_level)
        self._record_worker.finished.connect(self._on_record_done)
        self._record_worker.error.connect(self._on_record_error)
        self._record_worker.start()

    def _on_record_done(self, wav_path: str):
        self.is_recording = False
        self._live_mic_level = 0.0
        self.btn_hud_listen.setText("🎙️ SPEAK")

        if not wav_path:
            self._reset_reactor()
            self.transcript.append("[Voice]: (No speech detected)")
            return

        self.reactor.set_state(ArcReactorWidget.STATE_THINKING)
        self.lbl_core_status.setText("● TRANSCRIBING AUDIO...")

        self._transcribe_worker = _HudTranscribeWorker(wav_path, language=self.current_language)
        self._transcribe_worker.finished.connect(self._on_transcribe_done)
        self._transcribe_worker.error.connect(self._on_transcribe_error)
        self._transcribe_worker.start()

    def _on_record_error(self, err: str):
        self._reset_reactor()
        self.transcript.append(f"[Mic Error]: {err}")

    def _on_transcribe_done(self, text: str):
        cleaned = text.strip()
        if not cleaned:
            self._reset_reactor()
            self.transcript.append("[Voice]: (No clear speech detected)")
            return
        self.submit_command(cleaned)

    def _on_transcribe_error(self, err: str):
        self._reset_reactor()
        self.transcript.append(f"[Speech Error]: {err}")

    def _on_inline_submit(self):
        text = self.cmd_input.text().strip()
        if text:
            self.cmd_input.clear()
            self.submit_command(text)

    def submit_command(self, text: str):
        if self._auto_worker and self._auto_worker.isRunning():
            self._auto_worker.set_paused(True)
        self.transcript.append(f"\n[You]: {text}")
        self.reactor.set_state(ArcReactorWidget.STATE_THINKING)
        self.lbl_core_status.setText("● EXECUTING & THINKING...")

        self._brain_worker = _HudBrainWorker(
            text, language=self.current_language, speak_enabled=self.voice_enabled
        )
        self._brain_worker.speech_started.connect(self._on_brain_speech_started)
        self._brain_worker.finished.connect(self._on_brain_reply)
        self._brain_worker.error.connect(self._on_brain_error)
        self._brain_worker.start()

    def _on_brain_speech_started(self):
        self.reactor.set_state(ArcReactorWidget.STATE_SPEAKING)
        self.lbl_core_status.setText("● JARVIS SPEAKING...")

    def _on_brain_reply(self, query: str, reply: str, should_speak: bool, already_speaking: bool = False):
        self.transcript.append(f"[JARVIS]: {reply}")
        self.interaction_logged.emit(query, reply)

        if should_speak and self.voice_enabled:
            self.reactor.set_state(ArcReactorWidget.STATE_SPEAKING)
            self.lbl_core_status.setText("● JARVIS SPEAKING...")
            if not already_speaking:
                speak_text(reply, language=self.current_language, non_blocking=True)
            self._tts_watch_timer.start(200)
        else:
            self._reset_reactor()

    def _check_tts_done(self):
        if not is_speaking():
            self._tts_watch_timer.stop()
            self._reset_reactor()

    def _on_brain_error(self, err: str):
        self._reset_reactor()
        self.transcript.append(f"[Brain Error]: {err}")

    def _quick_launch_app(self, app_name: str):
        try:
            res = launch_app(app_name)
            self.transcript.append(f"[Action]: {res}")
        except Exception as exc:
            self.transcript.append(f"[Launch Error]: {exc}")

    def _reset_reactor(self):
        self.is_recording = False
        self._live_mic_level = 0.0
        self.btn_hud_listen.setText("🎙️ SPEAK")
        self.reactor.set_state(ArcReactorWidget.STATE_IDLE)
        if self.auto_voice_enabled:
            self.lbl_core_status.setText("● AUTO-VOICE ARMED — SPEAK ANYTIME (1.5s SILENCE STOP)")
            if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                if self._auto_worker and self._auto_worker.isRunning():
                    self._auto_worker.set_paused(False)
                else:
                    self._start_auto_monitor()
        else:
            self.lbl_core_status.setText("● CORE ONLINE — CLICK TRIANGLE TO SPEAK")
