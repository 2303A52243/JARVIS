"""Unit tests for Voice Activity Detection (3s silence stop) and Full PC Control tools."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

from app.config import reload_settings
from core.permissions import PermissionManager
from core.tool_registry import get_tool_registry
import system.pc_controller as pc_ctrl
from voice.microphone import record_until_silence
from voice.text_to_speech import is_speaking


class _FakeInputStream:
    """Simulated microphone stream: 0.3s ambient -> speech -> 3.2s silence."""

    def __init__(self, chunks: list[np.ndarray]):
        self._chunks = chunks
        self._idx = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def read(self, frames: int):
        if self._idx < len(self._chunks):
            c = self._chunks[self._idx]
            self._idx += 1
            return c, False
        return np.zeros((frames, 1), dtype="int16"), False


def test_vad_detects_speech_and_stops_after_3s_silence():
    sr = 16000
    chunk_len = 1600  # 100ms
    quiet = np.full((chunk_len, 1), 20, dtype="int16")
    loud = np.full((chunk_len, 1), 4000, dtype="int16")

    # 3 calibration + 2 idle + 6 speech (0.6s) + 35 silence (3.5s)
    stream_chunks = [quiet] * 5 + [loud] * 6 + [quiet] * 35
    fake_stream = _FakeInputStream(stream_chunks)

    speech_started_calls = []
    levels = []

    with patch("voice.microphone.sd.InputStream", return_value=fake_stream):
        wav_path = record_until_silence(
            silence_duration=3.0,
            sample_rate=sr,
            wait_timeout=5.0,
            on_speech_start=lambda: speech_started_calls.append(True),
            on_level=lambda lvl: levels.append(lvl),
        )

    assert wav_path is not None and wav_path.exists()
    try:
        assert len(speech_started_calls) == 1
        assert max(levels) > 0.3
        # Stopped right at 3.0s silence (30 chunks), didn't consume all 35 trailing quiet chunks
        assert fake_stream._idx <= 5 + 6 + 31
        data, read_sr = sf.read(str(wav_path))
        assert read_sr == sr
        assert len(data) > 0
    finally:
        if wav_path.exists():
            os.remove(wav_path)


def test_vad_returns_none_on_pure_silence_timeout():
    chunk_len = 1600
    quiet = np.full((chunk_len, 1), 10, dtype="int16")
    fake_stream = _FakeInputStream([quiet] * 30)

    with patch("voice.microphone.sd.InputStream", return_value=fake_stream):
        wav_path = record_until_silence(silence_duration=3.0, wait_timeout=1.0)

    assert wav_path is None


def test_tts_is_speaking_default_false():
    assert is_speaking() is False


def test_full_pc_tools_registered_and_working():
    reload_settings()
    reg = get_tool_registry()
    expected_tools = {
        "control_volume",
        "control_media",
        "control_brightness",
        "take_screenshot",
        "control_window",
        "send_keyboard_shortcut",
        "type_text",
        "mouse_control",
        "system_power_action",
        "open_url_or_search",
        "open_windows_settings",
        "clipboard_control",
        "list_running_processes",
        "run_pc_command",
        "get_system_status",
        "list_directory",
        "search_files_pc",
        "read_file_pc",
        "create_file_pc",
        "manage_file_pc",
        "web_search_live",
        "launch_app",
        "terminate_app",
        "list_installed_apps",
    }
    registered_names = {t["name"] for t in reg.list_tools()}
    assert expected_tools.issubset(registered_names)

    procs_out = pc_ctrl.list_running_processes(limit=5)
    assert "Top running processes" in procs_out

    wins_out = pc_ctrl.control_window("list_windows")
    assert isinstance(wins_out, str) and len(wins_out) > 0

    dir_out = pc_ctrl.list_directory(str(Path(__file__).resolve().parent))
    assert "test_pc_control_and_vad.py" in dir_out


def test_full_pc_access_permission_manager():
    settings = reload_settings()
    pm = PermissionManager.get_instance()
    assert settings.jarvis_full_pc_access is True
    assert pm.full_pc_access is True
    assert pm.is_path_authorized("C:\\Users")
    res = pm.check_permission("run_pc_command", level=pc_ctrl.PermissionLevel.CONTROL, target_resource="Get-Date")
    assert res.allowed is True
    assert res.requires_confirmation is False
