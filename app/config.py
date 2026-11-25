"""Configuration management for JARVIS.

Loads environment variables from .env with sensible defaults and strict validation.
Ensures sensitive tokens (like API keys) are never exposed in logs or UI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent


def _parse_authorized_folders(raw: Optional[str]) -> List[Path]:
    """Parse semicolon or comma-separated folder paths and resolve to absolute paths."""
    if not raw:
        return [BASE_DIR]
    paths: List[Path] = []
    # Split by semicolon or comma
    delim = ";" if ";" in raw else ","
    for p in raw.split(delim):
        p_clean = p.strip()
        if p_clean:
            try:
                resolved = Path(p_clean).resolve()
                paths.append(resolved)
            except Exception:
                continue
    if not paths:
        paths.append(BASE_DIR)
    return paths


class JarvisSettings(BaseModel):
    """Runtime configuration container for JARVIS."""

    # OpenAI / OpenRouter API Configuration
    openai_api_key: str = Field(default="", description="OpenAI or OpenRouter API Key")
    openai_base_url: str = Field(default="", description="API Base URL (e.g. https://openrouter.ai/api/v1)")
    openai_model: str = Field(default="gpt-4o-mini", description="Primary chat model")
    openai_transcription_model: str = Field(default="whisper-1", description="Audio STT model")
    openai_tts_model: str = Field(default="tts-1", description="Audio TTS model")
    openai_tts_voice: str = Field(default="onyx", description="TTS Voice: alloy, echo, fable, onyx, nova, shimmer")

    # Language and Voice Configuration
    jarvis_language: str = Field(default="en", description="Default language code: en, te, hi, or auto")
    jarvis_voice_speed: float = Field(default=1.0, ge=0.5, le=2.0, description="TTS playback speed")
    jarvis_wake_word_enabled: bool = Field(default=False, description="Whether wake word detector is active")
    jarvis_wake_word: str = Field(default="jarvis", description="Wake word phrase")

    # Directories
    jarvis_data_dir: Path = Field(default_factory=lambda: BASE_DIR / "data")
    jarvis_log_dir: Path = Field(default_factory=lambda: BASE_DIR / "logs")
    jarvis_log_level: str = Field(default="INFO")

    # Security & Permissions
    jarvis_authorized_folders: List[Path] = Field(default_factory=lambda: [BASE_DIR])
    jarvis_require_confirmation: bool = Field(default=True, description="Strict confirmation for CONTROL and ADVANCED actions")
    jarvis_full_pc_access: bool = Field(default=False, description="Allow full control across all PC drives, apps, settings, and automation")
    jarvis_auto_voice: bool = Field(default=True, description="Enable automatic Voice Activity Detection with 3s silence stop")

    class Config:
        arbitrary_types_allowed = True

    @property
    def is_api_key_configured(self) -> bool:
        """Return True if an OpenAI or OpenRouter API key is present and non-empty."""
        key = self.openai_api_key.strip()
        return bool(key and key != "your_openai_api_key_here")

    @property
    def is_openrouter(self) -> bool:
        """Return True if using OpenRouter."""
        return self.openai_api_key.strip().startswith("sk-or-v1-") or "openrouter.ai" in self.openai_base_url.lower()

    @property
    def effective_base_url(self) -> Optional[str]:
        """Return effective base URL based on key and explicit configuration."""
        if self.openai_base_url.strip():
            return self.openai_base_url.strip()
        if self.is_openrouter:
            return "https://openrouter.ai/api/v1"
        return None

    @property
    def effective_chat_model(self) -> str:
        """Return effective model name, prefixing provider if needed for OpenRouter."""
        model = self.openai_model.strip()
        if self.is_openrouter:
            if "/" not in model:
                return f"openai/{model}"
        return model

    def safe_dict(self) -> dict:
        """Return configuration dictionary with masked sensitive credentials."""
        d = self.model_dump()
        raw_key = self.openai_api_key.strip()
        if raw_key and raw_key != "your_openai_api_key_here":
            masked = f"{raw_key[:4]}...{raw_key[-4:]}" if len(raw_key) > 8 else "****"
            d["openai_api_key"] = masked
        else:
            d["openai_api_key"] = "(not configured)"
        # Convert paths to strings for clean logging
        d["jarvis_data_dir"] = str(self.jarvis_data_dir)
        d["jarvis_log_dir"] = str(self.jarvis_log_dir)
        d["jarvis_authorized_folders"] = [str(p) for p in self.jarvis_authorized_folders]
        return d


def load_settings() -> JarvisSettings:
    """Load settings from .env file and environment variables."""
    # Attempt to load .env file if it exists (override=True so .env stays authoritative)
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_file, override=True)
        except ImportError:
            pass

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    transcription_model = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "whisper-1").strip()
    tts_model = os.getenv("OPENAI_TTS_MODEL", "tts-1").strip()
    tts_voice = os.getenv("OPENAI_TTS_VOICE", "onyx").strip()

    lang = os.getenv("JARVIS_LANGUAGE", "en").strip().lower()
    try:
        speed = float(os.getenv("JARVIS_VOICE_SPEED", "1.0"))
    except ValueError:
        speed = 1.0

    wake_enabled = os.getenv("JARVIS_WAKE_WORD_ENABLED", "false").strip().lower() in ("true", "1", "yes")
    wake_word = os.getenv("JARVIS_WAKE_WORD", "jarvis").strip()

    data_dir_env = os.getenv("JARVIS_DATA_DIR")
    data_dir = Path(data_dir_env).resolve() if data_dir_env else (BASE_DIR / "data")

    log_dir_env = os.getenv("JARVIS_LOG_DIR")
    log_dir = Path(log_dir_env).resolve() if log_dir_env else (BASE_DIR / "logs")

    log_level = os.getenv("JARVIS_LOG_LEVEL", "INFO").strip().upper()

    auth_folders = _parse_authorized_folders(os.getenv("JARVIS_AUTHORIZED_FOLDERS"))

    req_confirm = os.getenv("JARVIS_REQUIRE_CONFIRMATION", "true").strip().lower() in ("true", "1", "yes")
    full_pc_access = os.getenv("JARVIS_FULL_PC_ACCESS", "false").strip().lower() in ("true", "1", "yes")
    auto_voice = os.getenv("JARVIS_AUTO_VOICE", "true").strip().lower() in ("true", "1", "yes")

    if full_pc_access:
        try:
            import psutil
            for part in psutil.disk_partitions(all=False):
                mp = Path(part.mountpoint).resolve()
                if mp not in auth_folders:
                    auth_folders.append(mp)
        except Exception:
            pass
        home_dir = Path.home().resolve()
        if home_dir not in auth_folders:
            auth_folders.append(home_dir)

    # Ensure data and log directories exist
    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    return JarvisSettings(
        openai_api_key=api_key,
        openai_base_url=base_url,
        openai_model=model,
        openai_transcription_model=transcription_model,
        openai_tts_model=tts_model,
        openai_tts_voice=tts_voice,
        jarvis_language=lang,
        jarvis_voice_speed=speed,
        jarvis_wake_word_enabled=wake_enabled,
        jarvis_wake_word=wake_word,
        jarvis_data_dir=data_dir,
        jarvis_log_dir=log_dir,
        jarvis_log_level=log_level,
        jarvis_authorized_folders=auth_folders,
        jarvis_require_confirmation=req_confirm,
        jarvis_full_pc_access=full_pc_access,
        jarvis_auto_voice=auto_voice,
    )


# Global singleton instance
_GLOBAL_SETTINGS: Optional[JarvisSettings] = None


def get_settings() -> JarvisSettings:
    """Retrieve the application settings singleton."""
    global _GLOBAL_SETTINGS
    if _GLOBAL_SETTINGS is None:
        _GLOBAL_SETTINGS = load_settings()
    return _GLOBAL_SETTINGS


def reload_settings() -> JarvisSettings:
    """Reload settings from disk/environment."""
    global _GLOBAL_SETTINGS
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=env_file, override=True)
        except ImportError:
            pass
    _GLOBAL_SETTINGS = load_settings()
    try:
        from ai.openai_client import reset_openai_client
        reset_openai_client()
    except Exception:
        pass
    try:
        from core.permissions import PermissionManager
        PermissionManager._instance = None
    except Exception:
        pass
    return _GLOBAL_SETTINGS
