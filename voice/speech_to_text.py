"""Speech-to-Text (STT) engine for JARVIS.

Supports:
1. Google Speech Recognition (free, high-accuracy native support for Telugu 'te-IN', Hindi 'hi-IN', and English).
2. OpenAI Whisper API (when a valid OpenAI API key is configured).
3. Automatic fallback between engines.
"""

from __future__ import annotations

import os
from typing import Optional

from app.config import get_settings
from voice.language_manager import get_stt_language_code
from core.permissions import PermissionLevel, get_permission_manager
from security.audit_logger import get_audit_logger


def transcribe_file(audio_path: str, language: str | None = None) -> str:
    """Transcribe an audio file to text.

    Args:
        audio_path: Absolute path to WAV or MP3 file.
        language: Language code ('en', 'te', 'hi', or 'auto'). Defaults to settings.

    Returns:
        Transcribed text string.
    """
    logger = get_audit_logger()
    settings = get_settings()
    lang = (language or settings.jarvis_language or "en").lower()

    # Permission check – reading an audio file is a READ operation.
    pm = get_permission_manager()
    perm = pm.check_permission(
        action_name="transcribe_audio",
        level=PermissionLevel.READ,
        target_resource=audio_path,
        details={"language": lang},
    )
    if not perm.allowed:
        raise PermissionError(f"Permission denied for transcribe_audio: {perm.reason}")

    logger.info(f"Transcribing audio file '{audio_path}' with language '{lang}'.")

    # Strategy 1: If using standard OpenAI (not OpenRouter), try Whisper first
    if settings.is_api_key_configured and not settings.is_openrouter:
        try:
            from ai.openai_client import get_openai_client
            client = get_openai_client()
            whisper_lang = lang if lang in ("en", "te", "hi") else None
            text = client.transcribe_audio(audio_path, language=whisper_lang or "en")
            if text and text.strip():
                logger.info(f"Whisper transcription succeeded: {text[:60]}")
                return text.strip()
        except Exception as exc:
            logger.warning(f"Whisper transcription failed ({exc}); falling back to Google Speech.")

    # Strategy 2: Google Speech Recognition (free, excellent for Telugu 'te-IN' and Hindi 'hi-IN')
    bcp47_lang = get_stt_language_code(lang)
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True

        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data, language=bcp47_lang)
        if text and text.strip():
            logger.info(f"Google Speech ({bcp47_lang}) transcribed: {text.strip()}")
            return text.strip()
    except sr.UnknownValueError:
        logger.info(f"Google Speech ({bcp47_lang}) detected no intelligible words in audio.")
        return ""
    except Exception as exc:
        logger.warning(f"Google Speech transcription error ({exc}).")

    # Strategy 3: Try English fallback if non-English recognition was blank
    if bcp47_lang != "en-IN":
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="en-IN")
            if text and text.strip():
                logger.info(f"Fallback English transcription succeeded: {text.strip()}")
                return text.strip()
        except Exception:
            pass

    return ""


# Register tool for LLM usage
from core.tool_registry import register_tool

_TRANSCRIBE_SPEC = {
    "name": "transcribe_audio",
    "description": "Convert recorded speech audio to text using Google Speech / Whisper with Telugu, Hindi, and English support.",
    "parameters": {
        "type": "object",
        "properties": {
            "audio_path": {"type": "string", "description": "Absolute path to the audio file on the local filesystem."},
            "language": {"type": "string", "enum": ["en", "te", "hi", "auto"], "description": "Language code of the speech (en, te, hi)."},
        },
        "required": ["audio_path"],
    },
}

register_tool(
    name="transcribe_audio",
    func=lambda args: transcribe_file(args["audio_path"], args.get("language")),
    spec=_TRANSCRIBE_SPEC,
    level=PermissionLevel.READ,
)
