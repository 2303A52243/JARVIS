"""Unit tests for JARVIS configuration management."""

import os
from pathlib import Path
from app.config import JarvisSettings, load_settings, _parse_authorized_folders, BASE_DIR


def test_default_settings():
    settings = load_settings()
    assert settings.openai_model  # model is configured (non-empty)
    assert settings.jarvis_language in ("en", "te", "hi", "auto")
    assert settings.jarvis_voice_speed >= 0.5
    assert not settings.jarvis_wake_word_enabled
    assert settings.jarvis_data_dir.exists()
    assert settings.jarvis_log_dir.exists()


def test_safe_dict_redaction():
    settings = JarvisSettings(
        openai_api_key="sk-proj-1234567890abcdef1234567890abcdef",
        openai_model="gpt-4o",
    )
    safe = settings.safe_dict()
    assert "1234567890abcdef" not in safe["openai_api_key"]
    assert "..." in safe["openai_api_key"]
    assert safe["openai_model"] == "gpt-4o"


def test_authorized_folder_parsing():
    raw = f"{str(BASE_DIR)};C:\\Windows\\Temp"
    folders = _parse_authorized_folders(raw)
    assert len(folders) >= 1
    assert BASE_DIR in folders
