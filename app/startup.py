"""Application startup, pre-flight checks, and diagnostics for JARVIS.

Ensures that the environment, storage directories, and system interfaces
are properly configured before launching the assistant.
"""

from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any

import psutil

from app.config import get_settings
from security.audit_logger import get_audit_logger


@dataclass
class StartupDiagnostic:
    """Pre-flight system diagnostic summary."""
    os_name: str = ""
    os_version: str = ""
    python_version: str = ""
    cpu_count: int = 0
    total_ram_gb: float = 0.0
    disk_free_gb: float = 0.0
    battery_present: bool = False
    battery_percent: float = 0.0
    audio_input_available: bool = False
    audio_output_available: bool = False
    api_key_configured: bool = False
    authorized_folders: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    is_ready: bool = True


def run_startup_diagnostics() -> StartupDiagnostic:
    """Run comprehensive non-destructive checks on the host environment."""
    settings = get_settings()
    audit_logger = get_audit_logger()
    diag = StartupDiagnostic()

    # 1. Platform checks
    diag.os_name = platform.system()
    diag.os_version = f"{platform.release()} ({platform.version()})"
    diag.python_version = platform.python_version()

    if diag.os_name != "Windows":
        diag.warnings.append(f"JARVIS is optimized for Windows 10/11. Detected {diag.os_name}.")

    # 2. Hardware specs
    try:
        diag.cpu_count = psutil.cpu_count(logical=True) or 1
        ram = psutil.virtual_memory()
        diag.total_ram_gb = round(ram.total / (1024 ** 3), 2)
        disk = psutil.disk_usage(str(settings.jarvis_data_dir.anchor or "C:\\"))
        diag.disk_free_gb = round(disk.free / (1024 ** 3), 2)

        battery = psutil.sensors_battery()
        if battery is not None:
            diag.battery_present = True
            diag.battery_percent = battery.percent
    except Exception as e:
        diag.warnings.append(f"Hardware inspection warning: {e}")

    # 3. Audio hardware probe
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        output_devs = [d for d in devices if d.get("max_output_channels", 0) > 0]
        diag.audio_input_available = len(input_devs) > 0
        diag.audio_output_available = len(output_devs) > 0
        if not diag.audio_input_available:
            diag.warnings.append("No active microphone input device detected.")
        if not diag.audio_output_available:
            diag.warnings.append("No active speaker output device detected.")
    except Exception as e:
        diag.warnings.append(f"Audio device query warning: {e}")

    # 4. Storage & directories
    try:
        settings.jarvis_data_dir.mkdir(parents=True, exist_ok=True)
        settings.jarvis_log_dir.mkdir(parents=True, exist_ok=True)
        temp_audio = settings.jarvis_data_dir / "temp_audio"
        temp_audio.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        diag.is_ready = False
        diag.warnings.append(f"Storage directory initialization failed: {e}")

    # 5. API Key status
    diag.api_key_configured = settings.is_api_key_configured
    if not diag.api_key_configured:
        diag.warnings.append(
            "OpenAI API key is not yet configured. Text-only offline mode and system tools remain active. "
            "Configure OPENAI_API_KEY in .env or the Settings panel to enable AI brain & voice transcription."
        )

    diag.authorized_folders = [str(p) for p in settings.jarvis_authorized_folders]

    audit_logger.log_event(
        event_type="STARTUP_DIAGNOSTICS",
        action="run_startup_diagnostics",
        status="COMPLETED",
        details={
            "os": diag.os_name,
            "os_version": diag.os_version,
            "ram_gb": diag.total_ram_gb,
            "disk_free_gb": diag.disk_free_gb,
            "api_key_configured": diag.api_key_configured,
            "warnings_count": len(diag.warnings),
        },
    )

    return diag
