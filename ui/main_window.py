"""Main application window for JARVIS.

Sree Industries Holographic Cyber-Interface (JARVIS OS v2.0).
Opens directly into the 3-column Iron Man HUD Command Center, with seamless
access to Voice Studio, Neural Chat, System Dashboard, Apps, Files, Memory,
Browser, and Developer panels.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, QPointF, QThread, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QStatusBar,
    QPushButton,
    QLabel,
)

from ui.hud_home_panel import JarvisHudHomePanel
from ui.voice_panel import VoicePanel
from ui.chat_panel import ChatPanel
from ui.dashboard import DashboardPanel
from ai.jarvis_brain import process_user_query
from voice.text_to_speech import speak_text, stop_speaking, is_speaking, StreamingSpeechSession


class _ChatBrainWorker(QThread):
    finished = Signal(str, bool, bool)
    speech_started = Signal()
    error = Signal(str)

    def __init__(self, query: str, language: str = "en", speak_enabled: bool = True):
        super().__init__()
        self.query = query
        self.language = language
        self.speak_enabled = speak_enabled

    def run(self):
        session: StreamingSpeechSession | None = None
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
            self.finished.emit(reply, should_speak, started)
        except Exception as exc:
            if session is not None:
                session.finish()
            self.error.emit(str(exc))


class _CyberGridBackground(QWidget):
    """Dark Sree Industries cybernetic grid & ambient central radial glow."""

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()

        # Deep space-navy backdrop
        painter.fillRect(0, 0, w, h, QColor(2, 7, 16))

        # Subtle cyan ambient center glow behind Arc Reactor
        glow = QRadialGradient(QPointF(w / 2.0, h * 0.48), min(w, h) * 0.55)
        glow.setColorAt(0.0, QColor(0, 140, 210, 38))
        glow.setColorAt(0.6, QColor(4, 30, 62, 18))
        glow.setColorAt(1.0, QColor(2, 7, 16, 0))
        painter.fillRect(0, 0, w, h, glow)

        # Subtle HUD gridlines
        painter.setPen(QPen(QColor(0, 160, 220, 16), 1.0))
        step = 36
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)


class MainWindow(QMainWindow):
    """Futuristic Sree Industries Desktop Interface for JARVIS."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S. OS v2.0 – Sree Industries Neural HUD")
        self.resize(1460, 880)
        self._tab_map: dict[str, QWidget] = {}
        self._init_ui()
        self._connect_signals()
        # Delay load auxiliary modules so window appears instantly
        QTimer.singleShot(800, self._load_extra_tabs)
        QTimer.singleShot(300, self._warm_up_background)

    def _warm_up_background(self):
        import threading
        from ai.openai_client import warm_up_openai_client
        threading.Thread(target=warm_up_openai_client, daemon=True).start()

    def _init_ui(self):
        central = _CyberGridBackground()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Sree Industries Cyberpunk Tab Bar ──────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setMovable(False)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border-top: 1px solid #00F0FF;
                background: transparent;
            }
            QTabBar::tab {
                background: #041020;
                color: #7DD3FC;
                padding: 8px 16px;
                border: 1px solid #0C3658;
                border-bottom: none;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                font-family: Consolas, 'Segoe UI';
                font-weight: bold;
                font-size: 11px;
                letter-spacing: 0.8px;
                min-width: 78px;
                margin-right: 2px;
            }
            QTabBar::tab:hover {
                background: #092542;
                color: #00F0FF;
                border-color: #0284C7;
            }
            QTabBar::tab:selected {
                background: #061A33;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-bottom: 2px solid #020710;
            }
        """)

        # Tab 0: Full Iron Man JARVIS OS HUD (Primary Interface)
        self.hud_home = JarvisHudHomePanel()
        self.tabs.addTab(self.hud_home, "⚡ JARVIS HUD")
        self._tab_map["hud"] = self.hud_home

        # Tab 1: Voice Assistant Studio
        self.voice_panel = VoicePanel()
        self.tabs.addTab(self.voice_panel, "🎙️ Voice Studio")
        self._tab_map["voice"] = self.voice_panel

        # Tab 2: AI Neural Chat
        self.chat = ChatPanel()
        self.tabs.addTab(self.chat, "💬 Neural Chat")
        self._tab_map["chat"] = self.chat

        # Tab 3: System Dashboard
        self.dashboard = DashboardPanel()
        self.tabs.addTab(self.dashboard, "🖥️ Dashboard")
        self._tab_map["dashboard"] = self.dashboard

        # Placeholders for remaining modules (loaded after window shows)
        self._apps_placeholder = QLabel("  Loading Applications panel…")
        self._files_placeholder = QLabel("  Loading Files panel…")
        self.tabs.addTab(self._apps_placeholder, "📱 Apps")
        self.tabs.addTab(self._files_placeholder, "📁 Files")

        layout.addWidget(self.tabs)

        # ── Status Bar ──────────────────────────────────────────────────────
        self.status = QStatusBar()
        self.status.setStyleSheet(
            "background: #030A16; color: #38BDF8; font-family: Consolas; font-size: 11px; padding: 3px 8px; border-top: 1px solid #0C3658;"
        )
        self.setStatusBar(self.status)

        # Emergency Stop Button
        self._stop_btn = QPushButton("🛑 EMERGENCY STOP")
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background: #7F1D1D;
                color: #FCA5A5;
                border: 1px solid #DC2626;
                padding: 3px 12px;
                border-radius: 4px;
                font-family: Consolas;
                font-weight: 900;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #991B1B;
                color: #FFFFFF;
            }
        """)
        self._stop_btn.clicked.connect(self._emergency_stop)
        self.status.addPermanentWidget(self._stop_btn)
        self.status.showMessage("⚡ J.A.R.V.I.S. OS v2.0 Online • Sree Industries Holographic HUD Active")

    def _load_extra_tabs(self):
        """Asynchronously load extra panels once UI is visible."""
        try:
            from ui.system_panel import SystemPanel
            self.system_panel = SystemPanel()
            idx = self.tabs.indexOf(self._apps_placeholder)
            self.tabs.removeTab(idx)
            self.tabs.insertTab(idx, self.system_panel, "📱 Apps")
            self._tab_map["apps"] = self.system_panel
        except Exception as e:
            self.status.showMessage(f"Apps panel error: {e}")

        try:
            from ui.file_manager import FileManagerPanel
            self.file_manager = FileManagerPanel()
            idx = self.tabs.indexOf(self._files_placeholder)
            self.tabs.removeTab(idx)
            self.tabs.insertTab(idx, self.file_manager, "📁 Files")
            self._tab_map["files"] = self.file_manager
        except Exception as e:
            self.status.showMessage(f"Files panel error: {e}")

        try:
            from ui.memory_panel import MemoryPanel
            self.memory_panel = MemoryPanel()
            self.tabs.addTab(self.memory_panel, "🧠 Memory")
            self._tab_map["memory"] = self.memory_panel
        except Exception as e:
            self.status.showMessage(f"Memory panel error: {e}")

        try:
            from ui.browser_panel import BrowserPanel
            self.browser_panel = BrowserPanel()
            self.tabs.addTab(self.browser_panel, "🌐 Browser")
            self._tab_map["browser"] = self.browser_panel
        except Exception as e:
            self.status.showMessage(f"Browser panel error: {e}")

        try:
            from ui.developer_panel import DeveloperPanel
            self.developer_panel = DeveloperPanel()
            self.tabs.addTab(self.developer_panel, "👨‍💻 Dev")
            self._tab_map["dev"] = self.developer_panel
        except Exception as e:
            self.status.showMessage(f"Dev panel error: {e}")

        self.status.showMessage("⚡ J.A.R.V.I.S. OS Ready • Multilingual Neural Voice (EN / TE / HI) Active")

    def _connect_signals(self):
        self.chat.message_submitted.connect(self.handle_user_message)
        self.voice_panel.query_ready.connect(self.handle_voice_query)
        self.hud_home.navigate_requested.connect(self.navigate_to_module)
        self.hud_home.interaction_logged.connect(self._sync_hud_to_chat)
        self.hud_home.language_changed.connect(self._sync_language)

    def navigate_to_module(self, module_key: str):
        widget = self._tab_map.get(module_key)
        if widget is not None:
            self.tabs.setCurrentWidget(widget)

    def _sync_hud_to_chat(self, user_text: str, jarvis_reply: str):
        self.chat.append_user_message(f"⚡ [HUD]: {user_text}")
        self.chat.append_assistant_message(jarvis_reply)

    def _sync_language(self, lang_code: str):
        idx_map = {"en": 0, "te": 1, "hi": 2}
        if lang_code in idx_map:
            self.chat.lang_selector.setCurrentIndex(idx_map[lang_code])
            self.voice_panel.combo_lang.setCurrentIndex(idx_map[lang_code])

    def handle_user_message(self, text: str):
        """Handle chat messages asynchronously with early sentence TTS output."""
        lang = self.chat.get_selected_language_code()
        speak_enabled = self.chat.voice_output_enabled
        self.status.showMessage("⚡ J.A.R.V.I.S. is thinking...")

        self._chat_worker = _ChatBrainWorker(text, language=lang, speak_enabled=speak_enabled)
        self._chat_worker.speech_started.connect(
            lambda: self.status.showMessage("🔊 J.A.R.V.I.S. is speaking...")
        )
        self._chat_worker.finished.connect(
            lambda reply, should_speak, already_speaking: self._on_chat_reply(
                reply, should_speak, already_speaking, lang, speak_enabled
            )
        )
        self._chat_worker.error.connect(
            lambda err: self.status.showMessage(f"Error: {err}")
        )
        self._chat_worker.start()

    def _on_chat_reply(self, reply: str, should_speak: bool, already_speaking: bool, lang: str, speak_enabled: bool):
        self.chat.append_assistant_message(reply)
        if speak_enabled and should_speak:
            self.status.showMessage("🔊 J.A.R.V.I.S. is speaking...")
            if not already_speaking:
                speak_text(reply, language=lang, non_blocking=True)
            if not hasattr(self, "_chat_tts_timer"):
                self._chat_tts_timer = QTimer(self)
                self._chat_tts_timer.timeout.connect(self._check_chat_tts_done)
            self._chat_tts_timer.start(200)
        else:
            self.status.showMessage("⚡ J.A.R.V.I.S. Online • Standing by")

    def _check_chat_tts_done(self):
        if not is_speaking():
            self._chat_tts_timer.stop()
            self.status.showMessage("⚡ J.A.R.V.I.S. Online • Standing by")

    def handle_voice_query(self, text: str):
        """Sync voice query to chat tab."""
        self.chat.append_user_message(f"🎙️ [Voice]: {text}")

    def _emergency_stop(self):
        stop_speaking()
        self.hud_home.shutdown()
        from core.permissions import get_permission_manager
        pm = get_permission_manager()
        if hasattr(pm, "trigger_emergency_stop"):
            pm.trigger_emergency_stop()
        self.status.showMessage("🛑 EMERGENCY STOP TRIGGERED – ALL ACTIONS AND AUDIO HALTED")
        self.chat.append_system_message("🛑 Emergency stop activated. All ongoing actions and voice playback halted.")
        self.hud_home.transcript.append("🛑 Emergency stop activated. All ongoing actions and audio halted.")

    def closeEvent(self, event):
        self.hud_home.shutdown()
        stop_speaking()
        super().closeEvent(event)

    def register_permission_handler(self, handler):
        from core.permissions import get_permission_manager
        get_permission_manager().set_confirmation_handler(handler)
