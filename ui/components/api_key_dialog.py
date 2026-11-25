"""Dialog for configuring OpenAI / OpenRouter API keys dynamically from the GUI."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from app.config import get_settings, reload_settings, BASE_DIR


class ApiKeyDialog(QDialog):
    """Futuristic modal dialog to configure OpenAI or OpenRouter API Key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure AI API Key (OpenAI / OpenRouter)")
        self.setFixedSize(540, 260)
        self.setStyleSheet("""
            QDialog {
                background-color: #070F1E;
                border: 1px solid #00F0FF;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("🔑 AI NEURAL ACCESS KEY")
        title.setStyleSheet("color: #00F0FF; font-size: 16px; font-weight: 900; letter-spacing: 1px;")
        layout.addWidget(title)

        desc = QLabel(
            "Enter your OpenAI (sk-...) or OpenRouter (sk-or-v1-...) API key:\n"
            "• 🎙️ Speech-to-Text: Native Telugu, Hindi & English recognition\n"
            "• 🔊 Neural Voice: Ultra-natural Telugu & Hindi speaking\n"
            "• 🧠 Intelligence: Deep reasoning and laptop automation"
        )
        desc.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-or-v1-... or sk-proj-...")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setStyleSheet("""
            QLineEdit {
                background: #0B1629;
                color: #00F0FF;
                border: 1px solid #1E3A8A;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                font-family: Consolas, monospace;
            }
        """)

        # Pre-fill current key if set
        settings = get_settings()
        if settings.is_api_key_configured:
            self.key_input.setText(settings.openai_api_key)

        layout.addWidget(self.key_input)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: #1E293B;
                color: #94A3B8;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save & Activate")
        btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284C7, stop:1 #00F0FF);
                color: #040D21;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: #38BDF8;
            }
        """)
        btn_save.clicked.connect(self._save_key)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _save_key(self):
        new_key = self.key_input.text().strip()
        if not new_key:
            QMessageBox.warning(self, "Empty Key", "Please enter a valid API key or cancel.")
            return

        is_openrouter = new_key.startswith("sk-or-v1-")
        base_url = "https://openrouter.ai/api/v1" if is_openrouter else ""
        model = "openai/gpt-4o-mini" if is_openrouter else "gpt-4o-mini"

        env_path = BASE_DIR / ".env"
        try:
            lines = []
            if env_path.exists():
                lines = env_path.read_text(encoding="utf-8").splitlines()

            updates = {
                "OPENAI_API_KEY": new_key,
                "OPENAI_BASE_URL": base_url,
                "OPENAI_MODEL": model,
            }

            new_lines = []
            seen = set()
            for line in lines:
                matched = False
                for k, v in updates.items():
                    if line.strip().startswith(f"{k}="):
                        new_lines.append(f"{k}={v}")
                        seen.add(k)
                        matched = True
                        break
                if not matched:
                    new_lines.append(line)

            for k, v in updates.items():
                if k not in seen:
                    new_lines.append(f"{k}={v}")

            env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            reload_settings()

            provider_name = "OpenRouter" if is_openrouter else "OpenAI"
            QMessageBox.information(
                self,
                "Key Activated",
                f"✅ {provider_name} API Key saved and activated!\n"
                f"Model: {model}\n"
                "Telugu, Hindi, and English listening and speaking are fully operational.",
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to write .env: {e}")


def show_api_key_dialog(parent=None) -> bool:
    """Convenience function to prompt for and save API key."""
    dlg = ApiKeyDialog(parent)
    return dlg.exec() == QDialog.Accepted
