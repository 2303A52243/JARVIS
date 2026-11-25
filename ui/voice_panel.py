"""Futuristic Voice Assistant HUD Panel for JARVIS.

Features:
- Animated Holographic Arc Reactor Visualizer
- Real-time Microphone recording & Whisper transcription
- Live laptop speaker speech output using Windows SAPI / OpenAI TTS
- Multi-language support: English, Telugu, and Hindi
- Voice output toggle (Mute / Unmute), Test Voice button, and API Key configuration
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QComboBox,
    QFrame,
    QTextEdit,
    QInputDialog,
    QMessageBox,
)

from ui.components.arc_reactor import ArcReactorWidget
from ui.components.api_key_dialog import show_api_key_dialog
from voice.text_to_speech import speak_text, stop_speaking, is_speaking, StreamingSpeechSession
from voice.microphone import record_until_silence, DEFAULT_SILENCE_STOP_SECONDS
from ai.jarvis_brain import process_user_query
from app.config import get_settings


class _AudioRecordWorker(QThread):
    finished = Signal(str)
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
        except Exception as e:
            self.error.emit(str(e))


class _VoiceBrainWorker(QThread):
    finished = Signal(str, str, bool, bool)
    speech_started = Signal()
    error = Signal(str)

    def __init__(self, query: str, language: str = "en", speak_enabled: bool = True):
        super().__init__()
        self.query = query
        self.language = language
        self.speak_enabled = speak_enabled

    def run(self):
        session = None
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


class _TranscribeWorker(QThread):
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
        except Exception as e:
            self.error.emit(str(e))


class VoicePanel(QWidget):
    """Voice Assistant Command Center."""

    query_ready = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_recording = False
        self.voice_enabled = True
        self.current_language = "en"
        self._record_worker = None
        self._transcribe_worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignHCenter)

        # ── Header ──────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("VOICE COMMAND & NEURAL HUD")
        title.setStyleSheet("color: #00F0FF; font-size: 20px; font-weight: 900; letter-spacing: 2px;")
        sub = QLabel("Voice Recognition (Whisper) • Speech Synthesis • Tri-lingual (EN / TE / HI)")
        sub.setStyleSheet("color: #94A3B8; font-size: 12px;")
        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box)
        header.addStretch()

        # Set API Key button
        self.btn_key = QPushButton("🔑 Set AI API Key")
        self.btn_key.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #FBBF24;
                border: 1px solid #D97706;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #D97706;
                color: #000;
            }
        """)
        self.btn_key.clicked.connect(self._open_api_key_dialog)
        header.addWidget(self.btn_key)

        # Language dropdown
        lang_lbl = QLabel("Language:")
        lang_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: bold;")
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["English (en)", "Telugu (తెలుగు)", "Hindi (हिन्दी)"])
        self.combo_lang.setStyleSheet("""
            QComboBox {
                background: #0F172A;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
        """)
        self.combo_lang.currentIndexChanged.connect(self._on_lang_changed)
        header.addWidget(lang_lbl)
        header.addWidget(self.combo_lang)

        layout.addLayout(header)

        # ── Center: Arc Reactor Visualizer ──────────────────────────────────
        reactor_container = QFrame()
        reactor_container.setStyleSheet("background: transparent;")
        r_layout = QVBoxLayout(reactor_container)
        r_layout.setAlignment(Qt.AlignCenter)

        self.reactor = ArcReactorWidget(size=220)
        r_layout.addWidget(self.reactor, alignment=Qt.AlignCenter)

        self.lbl_status = QLabel("● JARVIS CORE STANDBY")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #38BDF8; font-size: 14px; font-weight: bold; letter-spacing: 1.5px;")
        r_layout.addWidget(self.lbl_status)

        layout.addWidget(reactor_container)

        # ── Voice Controls ──────────────────────────────────────────────────
        btn_bar = QHBoxLayout()
        btn_bar.setAlignment(Qt.AlignCenter)

        self.btn_listen = QPushButton("🎙️ CLICK TO SPEAK (AUTO 1.5s STOP)")
        self.btn_listen.setMinimumWidth(290)
        self.btn_listen.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #00F0FF);
                color: #040D21;
                font-size: 14px;
                font-weight: 900;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background: #38BDF8;
            }
        """)
        self.btn_listen.clicked.connect(self._toggle_recording)
        btn_bar.addWidget(self.btn_listen)

        self.btn_test_speech = QPushButton("🔊 Test Voice")
        self.btn_test_speech.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 8px;
                padding: 12px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #0284C7;
                color: #FFFFFF;
            }
        """)
        self.btn_test_speech.clicked.connect(self._test_voice)
        btn_bar.addWidget(self.btn_test_speech)

        self.btn_mute = QPushButton("🔊 Audio: ON")
        self.btn_mute.setStyleSheet("""
            QPushButton {
                background: #064E3B;
                color: #6EE7B7;
                border: 1px solid #059669;
                border-radius: 8px;
                padding: 12px 20px;
                font-weight: bold;
            }
        """)
        self.btn_mute.clicked.connect(self._toggle_mute)
        btn_bar.addWidget(self.btn_mute)

        layout.addLayout(btn_bar)

        # ── Spoken Transcript Log ───────────────────────────────────────────
        log_box = QFrame()
        log_box.setStyleSheet("background: #0B0F19; border: 1px solid #1E293B; border-radius: 8px;")
        l_lay = QVBoxLayout(log_box)
        l_lay.setContentsMargins(12, 10, 12, 10)

        log_title = QLabel("LIVE VOICE INTERACTION LOG")
        log_title.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 800; letter-spacing: 1px;")
        l_lay.addWidget(log_title)

        self.transcript_viewer = QTextEdit()
        self.transcript_viewer.setReadOnly(True)
        self.transcript_viewer.setMaximumHeight(150)
        self.transcript_viewer.setStyleSheet("""
            QTextEdit {
                background: transparent;
                border: none;
                color: #CBD5E1;
                font-family: 'Segoe UI', Consolas;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        self.transcript_viewer.setPlainText(
            "JARVIS Voice Subsystem initialized.\n"
            "• Click '🔊 Test Voice' to hear JARVIS speak through your laptop speakers.\n"
            "• Click '🎙️ HOLD OR CLICK TO SPEAK' to record voice.\n"
            "• Click '🔑 Set OpenAI Key' to activate Whisper speech-to-text."
        )
        l_lay.addWidget(self.transcript_viewer)

        layout.addWidget(log_box, 1)

    def _open_api_key_dialog(self):
        if show_api_key_dialog(self):
            self.transcript_viewer.append("\n✅ AI API Key successfully configured! Neural engine and multilingual speech active.")
            self.lbl_status.setText("● NEURAL SPEECH & BRAIN ACTIVE")

    def _on_lang_changed(self, idx: int):
        codes = ["en", "te", "hi"]
        self.current_language = codes[idx]
        names = ["English", "Telugu", "Hindi"]
        self.transcript_viewer.append(f"ℹ️ Language set to: {names[idx]}")

    def _toggle_mute(self):
        self.voice_enabled = not self.voice_enabled
        if self.voice_enabled:
            self.btn_mute.setText("🔊 Audio: ON")
            self.btn_mute.setStyleSheet("background: #064E3B; color: #6EE7B7; border: 1px solid #059669; border-radius: 8px; padding: 12px 20px; font-weight: bold;")
        else:
            stop_speaking()
            self.btn_mute.setText("🔇 Audio: MUTED")
            self.btn_mute.setStyleSheet("background: #7F1D1D; color: #FCA5A5; border: 1px solid #DC2626; border-radius: 8px; padding: 12px 20px; font-weight: bold;")

    def _test_voice(self):
        msg = "Hello Boss. My neural voice synthesizer and laptop speaker drivers are fully operational."
        if self.current_language == "te":
            msg = "నమస్కారం బాస్! నా వాయిస్ సిస్టమ్ విజయవంతంగా పనిచేస్తుంది."
        elif self.current_language == "hi":
            msg = "नमस्ते बॉस! मेरा वॉइस सिस्टम पूरी तरह तैयार है।"

        self.transcript_viewer.append(f"\n[JARVIS]: {msg}")
        self.reactor.set_state(ArcReactorWidget.STATE_SPEAKING)
        self.lbl_status.setText("● JARVIS SPEAKING...")
        speak_text(msg, language=self.current_language, non_blocking=True)
        QTimer.singleShot(4000, lambda: self._reset_state())

    def _toggle_recording(self):
        if self.is_recording and self._record_worker and self._record_worker.isRunning():
            self._record_worker.stop()
            return

        self.is_recording = True
        self.btn_listen.setText("🔴 LISTENING (1.5s SILENCE STOP)...")
        self.btn_listen.setStyleSheet("background: #DC2626; color: white; font-size: 14px; font-weight: 900; border-radius: 8px; padding: 12px 24px;")
        self.reactor.set_state(ArcReactorWidget.STATE_LISTENING)
        self.lbl_status.setText("● LISTENING — SPEAK NOW...")

        self._record_worker = _AudioRecordWorker()
        self._record_worker.speech_started.connect(lambda: self.lbl_status.setText("● VOICE DETECTED — RECORDING..."))
        self._record_worker.level_changed.connect(self.reactor.set_audio_level)
        self._record_worker.finished.connect(self._on_recording_done)
        self._record_worker.error.connect(self._on_recording_error)
        self._record_worker.start()

    def _on_recording_done(self, wav_path: str):
        self.is_recording = False
        self.reactor.set_audio_level(0.0)
        self.btn_listen.setText("🎙️ CLICK TO SPEAK (AUTO 1.5s STOP)")
        self.btn_listen.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #00F0FF); color: #040D21; font-size: 14px; font-weight: 900; border-radius: 8px; padding: 12px 24px;")

        if not wav_path:
            self._reset_state()
            self.transcript_viewer.append("\n[Voice]: (No speech detected)")
            return

        self.reactor.set_state(ArcReactorWidget.STATE_THINKING)
        self.lbl_status.setText("● TRANSCRIBING AUDIO...")

        # Transcribe using multi-engine STT (Google Speech / Whisper)
        self._transcribe_worker = _TranscribeWorker(wav_path, language=self.current_language)
        self._transcribe_worker.finished.connect(self._on_transcribe_done)
        self._transcribe_worker.error.connect(self._on_transcribe_error)
        self._transcribe_worker.start()

    def _on_recording_error(self, err: str):
        self._reset_state()
        self.transcript_viewer.append(f"\n[Microphone Error]: {err}")

    def _on_transcribe_done(self, user_text: str):
        cleaned = user_text.strip()
        if not cleaned:
            self._reset_state()
            self.transcript_viewer.append("\n[Voice]: (No speech detected)")
            return

        self._execute_and_speak(cleaned)

    def _execute_and_speak(self, text: str):
        self.transcript_viewer.append(f"\n[Command]: {text}")
        self.reactor.set_state(ArcReactorWidget.STATE_THINKING)
        self.lbl_status.setText("● PROCESSING INSTRUCTION...")

        self._brain_worker = _VoiceBrainWorker(
            text, language=self.current_language, speak_enabled=self.voice_enabled
        )
        self._brain_worker.speech_started.connect(self._on_voice_speech_started)
        self._brain_worker.finished.connect(self._on_voice_brain_reply)
        self._brain_worker.error.connect(self._on_transcribe_error)
        self._brain_worker.start()

    def _on_voice_speech_started(self):
        self.reactor.set_state(ArcReactorWidget.STATE_SPEAKING)
        self.lbl_status.setText("● JARVIS SPEAKING...")

    def _on_voice_brain_reply(self, query: str, reply: str, should_speak: bool, already_speaking: bool):
        self.transcript_viewer.append(f"[JARVIS]: {reply}")
        if should_speak and self.voice_enabled:
            self.reactor.set_state(ArcReactorWidget.STATE_SPEAKING)
            self.lbl_status.setText("● JARVIS SPEAKING...")
            if not already_speaking:
                speak_text(reply, language=self.current_language, non_blocking=True)
            if not hasattr(self, "_voice_tts_timer"):
                self._voice_tts_timer = QTimer(self)
                self._voice_tts_timer.timeout.connect(self._check_voice_tts_done)
            self._voice_tts_timer.start(200)
        else:
            self._reset_state()
        self.query_ready.emit(query)

    def _check_voice_tts_done(self):
        if not is_speaking():
            self._voice_tts_timer.stop()
            self._reset_state()

    def _on_transcribe_error(self, err: str):
        self._reset_state()
        self.transcript_viewer.append(f"\n[Speech Recognition Note]: {err}")

    def _reset_state(self):
        self.is_recording = False
        self.reactor.set_audio_level(0.0)
        self.reactor.set_state(ArcReactorWidget.STATE_IDLE)
        self.lbl_status.setText("● JARVIS CORE STANDBY")
        self.btn_listen.setText("🎙️ CLICK TO SPEAK (AUTO 1.5s STOP)")
        self.btn_listen.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #00F0FF); color: #040D21; font-size: 14px; font-weight: 900; border-radius: 8px; padding: 12px 24px;")
