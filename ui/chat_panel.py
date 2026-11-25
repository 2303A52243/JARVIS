"""Chat interface panel for JARVIS.

Handles natural text conversations, AI reasoning, voice synthesis toggle,
quick-action prompt chips, and multi-lingual conversation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextBrowser,
    QLineEdit,
    QPushButton,
    QLabel,
    QFrame,
    QComboBox,
)


class ChatPanel(QWidget):
    """Futuristic holographic conversational interface."""

    message_submitted = Signal(str)
    voice_toggled = Signal()
    clear_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.voice_output_enabled = True
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # ── Header ──────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("AI NEURAL INTERFACE")
        title.setStyleSheet("color: #00F0FF; font-size: 18px; font-weight: 900; letter-spacing: 1.5px;")
        self.lbl_subtitle = QLabel("Sree OS • Hybrid Offline & OpenAI Engine • English / Telugu / Hindi")
        self.lbl_subtitle.setStyleSheet("color: #94A3B8; font-size: 11px;")
        title_box.addWidget(title)
        title_box.addWidget(self.lbl_subtitle)
        header.addLayout(title_box)
        header.addStretch()

        # Language selection
        self.lang_selector = QComboBox()
        self.lang_selector.addItems(["EN (English)", "TE (తెలుగు)", "HI (हिन्दी)"])
        self.lang_selector.setStyleSheet("""
            QComboBox {
                background-color: #0F172A;
                color: #38BDF8;
                border: 1px solid #0284C7;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        header.addWidget(self.lang_selector)

        # Set API Key button
        self.btn_key = QPushButton("🔑 Set AI API Key")
        self.btn_key.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #FBBF24;
                border: 1px solid #D97706;
                border-radius: 6px;
                padding: 5px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #D97706;
                color: #000;
            }
        """)
        from ui.components.api_key_dialog import show_api_key_dialog
        self.btn_key.clicked.connect(lambda: show_api_key_dialog(self))
        header.addWidget(self.btn_key)

        # Voice output toggle button
        self.btn_audio = QPushButton("🔊 Voice: ON")
        self.btn_audio.setStyleSheet("""
            QPushButton {
                background-color: #064E3B;
                color: #6EE7B7;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.btn_audio.clicked.connect(self._toggle_audio)
        header.addWidget(self.btn_audio)

        # Clear button
        self.btn_clear = QPushButton("🗑️ Clear")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #94A3B8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #F8FAFC;
            }
        """)
        self.btn_clear.clicked.connect(self._on_clear_clicked)
        header.addWidget(self.btn_clear)

        layout.addLayout(header)

        # ── Quick Action Prompt Chips ───────────────────────────────────────
        chips_layout = QHBoxLayout()
        chips = [
            ("⚡ Laptop Status", "Tell me about my laptop"),
            ("🔋 Battery", "What is my battery percentage?"),
            ("🧠 RAM Usage", "How much RAM is currently available?"),
            ("📱 Open Notepad", "Open Notepad"),
            ("📁 Find Files", "Search for files"),
            ("🌐 Search Web", "Search the web for Python tutorial"),
        ]
        for label, cmd in chips:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #0F172A;
                    color: #7DD3FC;
                    border: 1px solid #1E3A8A;
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #1E3A8A;
                    color: #FFFFFF;
                    border-color: #38BDF8;
                }
            """)
            btn.clicked.connect(lambda _, c=cmd: self._send_quick_chip(c))
            chips_layout.addWidget(btn)
        chips_layout.addStretch()
        layout.addLayout(chips_layout)

        # ── Chat Browser ────────────────────────────────────────────────────
        self.chat_browser = QTextBrowser()
        self.chat_browser.setOpenExternalLinks(True)
        self.chat_browser.setStyleSheet("""
            QTextBrowser {
                background-color: #050B14;
                border: 1px solid #0F2A4A;
                border-radius: 10px;
                padding: 16px;
                color: #E2E8F0;
                font-family: 'Segoe UI', Consolas, sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        layout.addWidget(self.chat_browser, 1)

        # ── Input Bar ───────────────────────────────────────────────────────
        input_container = QFrame()
        input_container.setStyleSheet("""
            QFrame {
                background-color: #0B132B;
                border: 1px solid #1C355E;
                border-radius: 8px;
                padding: 6px 10px;
            }
        """)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Command JARVIS (e.g. 'Tell me about my laptop', 'Open Notepad', 'Battery level')...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                color: #F8FAFC;
                font-size: 13px;
                padding: 6px;
            }
        """)
        self.input_field.returnPressed.connect(self._send_message)
        input_layout.addWidget(self.input_field, 1)

        self.btn_send = QPushButton("Send ➤")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #00F0FF);
                color: #040D21;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 900;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QPushButton:hover {
                background: #38BDF8;
            }
        """)
        self.btn_send.clicked.connect(self._send_message)
        input_layout.addWidget(self.btn_send)

        layout.addWidget(input_container)

        # Welcome message
        self.append_system_message("⚡ JARVIS Core Online. All laptop systems nominal. How may I assist you?")

    def get_selected_language_code(self) -> str:
        idx = self.lang_selector.currentIndex()
        return ["en", "te", "hi"][idx]

    def _toggle_audio(self):
        self.voice_output_enabled = not self.voice_output_enabled
        if self.voice_output_enabled:
            self.btn_audio.setText("🔊 Voice: ON")
            self.btn_audio.setStyleSheet("background-color: #064E3B; color: #6EE7B7; border: 1px solid #059669; border-radius: 6px; padding: 5px 12px; font-size: 11px; font-weight: bold;")
        else:
            from voice.text_to_speech import stop_speaking
            stop_speaking()
            self.btn_audio.setText("🔇 Voice: MUTE")
            self.btn_audio.setStyleSheet("background-color: #7F1D1D; color: #FCA5A5; border: 1px solid #DC2626; border-radius: 6px; padding: 5px 12px; font-size: 11px; font-weight: bold;")

    def _send_quick_chip(self, cmd_text: str):
        self.input_field.setText(cmd_text)
        self._send_message()

    def _send_message(self):
        text = self.input_field.text().strip()
        if text:
            self.append_user_message(text)
            self.input_field.clear()
            self.message_submitted.emit(text)

    def _on_clear_clicked(self):
        self.chat_browser.clear()
        self.append_system_message("Conversation cleared.")
        self.clear_requested.emit()

    def append_user_message(self, text: str):
        html = f"""
        <div style='margin-bottom: 14px; text-align: right;'>
            <span style='background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E3A8A, stop:1 #2563EB); color: #FFFFFF; padding: 9px 16px; border-radius: 14px 14px 3px 14px; display: inline-block; max-width: 80%; font-size: 13px; font-weight: 500;'>
                <b>You:</b> {text}
            </span>
        </div>
        """
        self.chat_browser.append(html)

    def append_assistant_message(self, text: str):
        formatted = text.replace("\n", "<br>")
        html = f"""
        <div style='margin-bottom: 14px; text-align: left;'>
            <div style='background-color: #0A1628; border-left: 3px solid #00F0FF; border: 1px solid #133256; color: #F1F5F9; padding: 12px 16px; border-radius: 4px 14px 14px 14px; display: inline-block; max-width: 88%; font-size: 13px; line-height: 1.6;'>
                <b style='color: #00F0FF; font-size: 11px; letter-spacing: 1px;'>J.A.R.V.I.S.</b><br><br>{formatted}
            </div>
        </div>
        """
        self.chat_browser.append(html)

    def append_system_message(self, text: str):
        html = f"""
        <div style='margin-bottom: 12px; text-align: center;'>
            <span style='color: #38BDF8; font-size: 11px; font-style: italic; background: rgba(14, 165, 233, 0.1); padding: 4px 12px; border-radius: 10px;'>
                {text}
            </span>
        </div>
        """
        self.chat_browser.append(html)
