"""Language configuration and translation mapping for JARVIS.

Supports:
- English ('en')
- Telugu ('te')
- Hindi ('hi')
"""

from __future__ import annotations

from typing import Dict, Any


SUPPORTED_LANGUAGES = {
    "en": {
        "name": "English",
        "native": "English",
        "greeting": "Hello Boss. JARVIS is online and ready.",
        "voice": "Microsoft Zira Desktop - English (United States)",
        "openai_voice": "onyx",
        "edge_voice": "en-US-GuyNeural",   # fastest Edge voice (lower latency than Christopher)
        "gtts_lang": "en",
        "stt_lang": "en-IN",
    },
    "te": {
        "name": "Telugu",
        "native": "తెలుగు",
        "greeting": "నమస్కారం బాస్! నేను జార్విస్. నేను మీకు ఎలా సహాయపడగలను?",
        "voice": "Microsoft Heera",
        "openai_voice": "alloy",
        "edge_voice": "te-IN-MohanNeural",
        "gtts_lang": "te",
        "stt_lang": "te-IN",
    },
    "hi": {
        "name": "Hindi",
        "native": "हिन्दी",
        "greeting": "नमस्ते बॉस! मैं जार्विस हूँ। मैं आपकी क्या मदद कर सकता हूँ?",
        "voice": "Microsoft Heera",
        "openai_voice": "alloy",
        "edge_voice": "hi-IN-MadhurNeural",
        "gtts_lang": "hi",
        "stt_lang": "hi-IN",
    },
}


def get_language_info(code: str) -> Dict[str, Any]:
    """Get language metadata by 2-letter code."""
    return SUPPORTED_LANGUAGES.get(code.lower(), SUPPORTED_LANGUAGES["en"])


def get_supported_language_codes() -> list[str]:
    """Get list of supported language codes."""
    return list(SUPPORTED_LANGUAGES.keys())


def detect_language_from_text(text: str, default: str = "en") -> str:
    """Detect whether text is predominantly Telugu, Hindi, or English.
    
    Checks Unicode code blocks:
    - Telugu: U+0C00 - U+0C7F
    - Devanagari (Hindi): U+0900 - U+097F
    """
    if not text:
        return default

    te_count = 0
    hi_count = 0
    for ch in text:
        cp = ord(ch)
        if 0x0C00 <= cp <= 0x0C7F:
            te_count += 1
        elif 0x0900 <= cp <= 0x097F:
            hi_count += 1

    if te_count > 0 and te_count >= hi_count:
        return "te"
    if hi_count > 0 and hi_count > te_count:
        return "hi"
    return default


def get_stt_language_code(code: str) -> str:
    """Convert short language code ('te', 'hi', 'en') to BCP-47 tag for speech recognition."""
    info = get_language_info(code)
    return info.get("stt_lang", "en-IN")


def get_edge_voice_name(code: str) -> str:
    """Get recommended Edge Neural TTS voice name for the language code."""
    info = get_language_info(code)
    return info.get("edge_voice", "en-US-ChristopherNeural")
