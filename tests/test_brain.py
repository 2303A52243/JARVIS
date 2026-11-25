"""Tests for JARVIS Hybrid Brain and Natural Language responses."""

import pytest
from ai.jarvis_brain import process_user_query
from system.application_manager import launch_app, is_app_running


def test_greeting_response():
    reply, should_speak = process_user_query("hello jarvis")
    assert should_speak is True
    assert "JARVIS" in reply or "Boss" in reply


def test_system_info_query():
    reply, should_speak = process_user_query("tell me about my laptop")
    assert should_speak is True
    assert "Machine:" in reply or "Processor:" in reply or "Windows" in reply


def test_battery_query():
    reply, should_speak = process_user_query("what is my battery percentage")
    assert should_speak is True
    assert "Battery" in reply or "%" in reply


def test_telugu_query():
    reply, should_speak = process_user_query("do you know telugu")
    assert should_speak is True
    assert "తెలుగు" in reply or "Telugu" in reply


def test_hindi_query():
    reply, should_speak = process_user_query("do you know hindi")
    assert should_speak is True
    assert "हिन्दी" in reply or "हिंदी" in reply or "Hindi" in reply


def test_launch_notepad():
    res = launch_app("notepad")
    assert "Notepad" in res


def test_launch_jarvis_folder():
    res = launch_app("jarvis folder")
    assert "JARVIS" in res


def test_wake_prefix_open_folder_fast_path(tmp_path):
    """Ensure 'Jarvis open folder ...' resolves locally without needing cloud LLM."""
    from unittest.mock import patch
    from ai.jarvis_brain import _strip_wake_prefix
    import system.application_manager as am

    assert _strip_wake_prefix("Jarvis open folder agentic AI PPTs") == "open folder agentic AI PPTs"

    # Simulate an OneDrive Desktop subfolder 'agenticaippts'
    desktop_mock = tmp_path / "Desktop"
    target_dir = desktop_mock / "agenticaippts"
    target_dir.mkdir(parents=True)

    with patch.object(am, "_DESKTOP_DIR", desktop_mock), \
         patch.object(am, "_HOME", tmp_path), \
         patch("system.application_manager.subprocess.Popen") as popen_mock:
        reply, should_speak = process_user_query("Jarvis open folder agentic AI PPTs")
        assert should_speak is True
        assert "agenticaippts" in reply
        popen_mock.assert_called_once()


def test_tts_sentence_chunking():
    from voice.text_to_speech import _split_speech_chunks
    chunks = _split_speech_chunks(
        "Opening folder right away, Boss. Here are more details about your system configuration. "
        "All systems are currently operating at nominal efficiency and temperature."
    )
    assert len(chunks) >= 2
    assert chunks[0] == "Opening folder right away, Boss."
