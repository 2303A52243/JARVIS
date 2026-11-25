"""Text-to-Speech (TTS) engine for JARVIS.

Features:
- Multi-engine architecture:
  1. Microsoft Edge Neural TTS (edge-tts): Free, human-like neural voices for Telugu, Hindi, and English.
  2. Google Translate TTS (gTTS): High-quality fallback for Telugu, Hindi, and English.
  3. OpenAI TTS: Available when an official OpenAI API key is configured.
  4. Windows SAPI: Offline fallback for English.
- Auto-detects Telugu and Hindi Unicode in text for seamless accent and voice switching.
- High-fidelity playback directly through laptop speakers using sounddevice and winsound.
"""

from __future__ import annotations

import concurrent.futures
import io
import os
import re
import socket
import tempfile
import threading
from collections import OrderedDict
from typing import List, Optional

from app.config import get_settings
from voice.language_manager import detect_language_from_text, get_edge_voice_name
from core.permissions import PermissionLevel, get_permission_manager
from security.audit_logger import get_audit_logger


_SPEECH_LOCK = threading.Lock()
_IS_SPEAKING = threading.Event()
_CURRENT_TMP_FILE: Optional[str] = None
_SPEECH_GENERATION = 0
_GEN_LOCK = threading.Lock()

# Small in-memory LRU cache so repeated short confirmations/greetings start in <1ms
_TTS_CACHE: OrderedDict[tuple, bytes] = OrderedDict()
_TTS_CACHE_MAX = 48
_TTS_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="jarvis_tts")


def is_speaking() -> bool:
    """Return True if JARVIS is currently synthesizing or playing speech audio."""
    return _IS_SPEAKING.is_set()


def _clean_text_for_speech(text: str) -> str:
    """Strip HTML, markdown formatting, emojis/bullets, and symbols that sound awkward in speech."""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)  # markdown links
    cleaned = re.sub(r"[*_`#~•⚡🔊🔇🎙️🛑✅ℹ️📁📱🖥🧠🌐👨💻]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _split_speech_chunks(text: str, first_max_chars: int = 110) -> List[str]:
    """Split text into sentence-aligned chunks so speech begins after sentence 1 finishes synthesizing."""
    cleaned = _clean_text_for_speech(text)
    if not cleaned:
        return []
    if len(cleaned) <= first_max_chars:
        return [cleaned]

    parts = [p.strip() for p in re.split(r"(?<=[.!?।])\s+|\n+", cleaned) if p.strip()]
    if len(parts) <= 1:
        return [cleaned]

    chunks: List[str] = []
    # Keep first chunk short so first audio starts quickly
    chunks.append(parts[0])
    buf = ""
    for part in parts[1:]:
        if buf and len(buf) + len(part) + 1 > 220:
            chunks.append(buf.strip())
            buf = part
        else:
            buf = f"{buf} {part}".strip() if buf else part
    if buf:
        chunks.append(buf.strip())
    return chunks


def _rate_str_from_speed(speed: Optional[float], settings) -> str:
    spd = speed if speed is not None else settings.jarvis_voice_speed
    rate_pct = int((spd - 1.0) * 100)
    return f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"


def _synthesize_edge_tts(text: str, voice_name: str, rate: str = "+0%") -> bytes:
    """Generate audio bytes using Microsoft Edge Neural TTS over IPv4 (avoids IPv6 DNS stalls)."""
    import asyncio
    import aiohttp
    import edge_tts

    async def _async_generate() -> bytes:
        # IPv4-only TCPConnector cuts Windows Edge-TTS handshake latency dramatically
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        try:
            communicator = edge_tts.Communicate(
                text,
                voice_name,
                rate=rate,
                connector=connector,
                connect_timeout=2,
                receive_timeout=3,
            )
            chunks = []
            async for chunk in communicator.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)
        finally:
            if not connector.closed:
                await connector.close()

    async def _bounded_generate() -> bytes:
        return await asyncio.wait_for(_async_generate(), timeout=2.5)

    try:
        return asyncio.run(_bounded_generate())
    except RuntimeError:
        return _TTS_POOL.submit(lambda: asyncio.run(_bounded_generate())).result()


def _synthesize_gtts(text: str, lang_code: str) -> bytes:
    """Generate audio bytes using Google Translate TTS."""
    from gtts import gTTS
    fp = io.BytesIO()
    tts = gTTS(text=text, lang=lang_code)
    tts.write_to_fp(fp)
    return fp.getvalue()


def _synthesize_offline_sapi(text: str, voice_name: Optional[str] = None) -> bytes:
    """Generate WAV bytes using Windows SAPI (English only).

    Prefers male 'David' voice to stay consistent with Edge-TTS 'GuyNeural'.
    """
    import comtypes.client
    import pythoncom

    pythoncom.CoInitialize()
    try:
        tts = comtypes.client.CreateObject("SAPI.SpVoice")

        # Try to select a consistent male voice (David) to avoid gender switching
        if voice_name is None:
            try:
                from voice.language_manager import get_language_info
                sapi_pref = get_language_info("en").get("sapi_voice", "David")
            except Exception:
                sapi_pref = "David"
            try:
                for v in tts.GetVoices():
                    desc = v.GetDescription()
                    if sapi_pref.lower() in desc.lower():
                        tts.Voice = v
                        break
            except Exception:
                pass

        fs = comtypes.client.CreateObject("SAPI.SpFileStream")
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        # 3 = SSFMCreateForWrite
        fs.Open(tmp_path, 3, False)
        tts.AudioOutputStream = fs
        tts.Speak(text, 0)
        fs.Close()

        with open(tmp_path, "rb") as fp:
            data = fp.read()
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return data
    finally:
        pythoncom.CoUninitialize()


def synthesize_speech(
    text: str,
    voice: Optional[str] = None,
    language: Optional[str] = None,
    speed: Optional[float] = None,
) -> bytes:
    """Generate spoken audio payload (MP3 or WAV bytes) for text.

    Auto-detects language if not provided. Uses LRU cache for repeated phrases.
    """
    logger = get_audit_logger()
    settings = get_settings()
    clean_text = _clean_text_for_speech(text)
    if not clean_text:
        return b""

    target_lang = language or detect_language_from_text(clean_text, default=settings.jarvis_language or "en")
    target_lang = target_lang.lower()
    rate_str = _rate_str_from_speed(speed, settings)
    edge_voice = voice or get_edge_voice_name(target_lang)

    cache_key = (clean_text, target_lang, edge_voice, rate_str)
    if len(clean_text) <= 240 and cache_key in _TTS_CACHE:
        _TTS_CACHE.move_to_end(cache_key)
        return _TTS_CACHE[cache_key]

    audio_data = b""

    # Optional instant offline SAPI mode if configured via env
    tts_mode = os.getenv("JARVIS_TTS_MODE", "neural").strip().lower()
    if tts_mode == "fast" and target_lang == "en":
        try:
            audio_data = _synthesize_offline_sapi(clean_text, voice_name=voice)
            if audio_data:
                return audio_data
        except Exception:
            pass

    # 1. Primary Engine: Microsoft Edge Neural TTS (IPv4 fast path + 2.5s cap)
    try:
        audio_data = _synthesize_edge_tts(clean_text, edge_voice, rate=rate_str)
        if audio_data:
            logger.info(f"Edge-TTS synthesis succeeded for '{target_lang}' ({edge_voice}) rate={rate_str}.")
    except Exception as exc:
        logger.warning(f"Edge-TTS failed ({exc}); falling back.")

    # 2. Secondary: Windows SAPI (male David voice — consistent with Edge GuyNeural)
    #    Preferred over gTTS for English because gTTS uses a female voice.
    if not audio_data and target_lang == "en":
        try:
            audio_data = _synthesize_offline_sapi(clean_text, voice_name=voice)
            if audio_data:
                logger.info("SAPI TTS (David male) succeeded.")
        except Exception as exc:
            logger.warning(f"SAPI TTS failed ({exc}); trying Google TTS.")

    # 3. Tertiary: Google Translate TTS (gTTS) — female voice, used for non-English or as last resort
    if not audio_data:
        try:
            gtts_code = "te" if target_lang == "te" else ("hi" if target_lang == "hi" else "en")
            audio_data = _synthesize_gtts(clean_text, gtts_code)
            if audio_data:
                logger.info(f"gTTS synthesis succeeded for '{gtts_code}'.")
        except Exception as exc:
            logger.warning(f"Google TTS failed ({exc}); checking OpenAI TTS.")

    # 4. OpenAI TTS (if configured and not OpenRouter)
    if not audio_data and settings.is_api_key_configured and not settings.is_openrouter:
        try:
            from ai.openai_client import get_openai_client
            client = get_openai_client()
            audio_data = client.generate_speech(clean_text, voice=voice)
            if audio_data:
                logger.info("OpenAI TTS succeeded.")
        except Exception as exc:
            logger.warning(f"OpenAI TTS failed ({exc}).")

    # 5. Last resort SAPI fallback for non-English (already tried for English above)
    if not audio_data and target_lang != "en":
        try:
            audio_data = _synthesize_offline_sapi(clean_text, voice_name=voice)
        except Exception as exc:
            logger.error(f"All TTS synthesis engines failed: {exc}")
            return b""

    if audio_data and len(clean_text) <= 240:
        _TTS_CACHE[cache_key] = audio_data
        while len(_TTS_CACHE) > _TTS_CACHE_MAX:
            _TTS_CACHE.popitem(last=False)

    return audio_data


def stop_speaking() -> None:
    """Immediately stop any playing or queued speech audio."""
    global _SPEECH_GENERATION
    with _GEN_LOCK:
        _SPEECH_GENERATION += 1
    _IS_SPEAKING.clear()
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass

    try:
        import winsound
        winsound.PlaySound(None, winsound.SND_PURGE)
    except Exception:
        pass


def _play_audio_payload(audio_bytes: bytes) -> None:
    """Decode and play audio bytes (MP3 or WAV) through laptop speakers."""
    global _CURRENT_TMP_FILE
    if not audio_bytes:
        return

    # Method 1: Decode in-memory with soundfile and play via sounddevice
    try:
        import soundfile as sf
        import sounddevice as sd

        data, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        sd.stop()
        sd.play(data, sample_rate)
        sd.wait()
        return
    except Exception as sd_err:
        logger = get_audit_logger()
        logger.warning(f"sounddevice playback failed ({sd_err}); falling back to winsound.")

    # Method 2: Convert to WAV file and play via winsound
    try:
        import soundfile as sf
        import winsound

        data, sample_rate = sf.read(io.BytesIO(audio_bytes))
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        sf.write(tmp_path, data, sample_rate, format="WAV")
        _CURRENT_TMP_FILE = tmp_path
        winsound.PlaySound(tmp_path, winsound.SND_FILENAME)
    except Exception as ws_err:
        logger = get_audit_logger()
        logger.error(f"winsound playback also failed: {ws_err}")
    finally:
        if _CURRENT_TMP_FILE and os.path.exists(_CURRENT_TMP_FILE):
            try:
                os.remove(_CURRENT_TMP_FILE)
            except OSError:
                pass
            _CURRENT_TMP_FILE = None


def speak_text(
    text: str,
    voice: Optional[str] = None,
    language: Optional[str] = None,
    non_blocking: bool = True,
) -> None:
    """Speak *text* through laptop speakers using pipelined sentence synthesis.

    Sentence 1 is synthesized and played immediately while subsequent sentences
    are synthesized concurrently in background threads so speech starts fast
    with zero gap between sentences.
    """
    global _SPEECH_GENERATION
    chunks = _split_speech_chunks(text)
    if not chunks:
        return

    # Stop any stale playback and claim a fresh speech generation token
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass

    with _GEN_LOCK:
        _SPEECH_GENERATION += 1
        my_gen = _SPEECH_GENERATION

    def _worker():
        _IS_SPEAKING.set()
        with _SPEECH_LOCK:
            try:
                # Start synthesizing chunk 0 immediately and prefetch remaining chunks in parallel
                futures = [
                    _TTS_POOL.submit(synthesize_speech, chunk, voice, language)
                    for chunk in chunks
                ]
                for fut in futures:
                    if my_gen != _SPEECH_GENERATION:
                        break
                    audio_bytes = fut.result()
                    if my_gen != _SPEECH_GENERATION:
                        break
                    _play_audio_payload(audio_bytes)
            except Exception as e:
                logger = get_audit_logger()
                logger.warning(f"speak_text worker failed: {e}")
            finally:
                if my_gen == _SPEECH_GENERATION:
                    _IS_SPEAKING.clear()

    if non_blocking:
        _IS_SPEAKING.set()
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
    else:
        _worker()


class StreamingSpeechSession:
    """Accepts sentences incrementally (e.g. from streaming LLM) and plays them in order."""

    def __init__(self, voice: Optional[str] = None, language: Optional[str] = None) -> None:
        global _SPEECH_GENERATION
        self.voice = voice
        self.language = language
        try:
            import sounddevice as sd
            sd.stop()
        except Exception:
            pass
        with _GEN_LOCK:
            _SPEECH_GENERATION += 1
            self.generation = _SPEECH_GENERATION
        self._queue: list[concurrent.futures.Future] = []
        self._cond = threading.Condition()
        self._closed = False
        _IS_SPEAKING.set()
        self._player_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._player_thread.start()

    def push_text(self, text: str) -> None:
        cleaned = _clean_text_for_speech(text)
        if not cleaned or self.generation != _SPEECH_GENERATION:
            return
        fut = _TTS_POOL.submit(synthesize_speech, cleaned, self.voice, self.language)
        with self._cond:
            self._queue.append(fut)
            self._cond.notify_all()

    def finish(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def _play_loop(self) -> None:
        with _SPEECH_LOCK:
            try:
                while True:
                    with self._cond:
                        while not self._queue and not self._closed and self.generation == _SPEECH_GENERATION:
                            self._cond.wait(timeout=0.2)
                        if self.generation != _SPEECH_GENERATION:
                            break
                        if not self._queue and self._closed:
                            break
                        fut = self._queue.pop(0)
                    audio_bytes = fut.result()
                    if self.generation != _SPEECH_GENERATION:
                        break
                    _play_audio_payload(audio_bytes)
            except Exception as e:
                get_audit_logger().warning(f"StreamingSpeechSession error: {e}")
            finally:
                if self.generation == _SPEECH_GENERATION:
                    _IS_SPEAKING.clear()


# Register tool for LLM usage
from core.tool_registry import register_tool

_SYNTH_SPEC = {
    "name": "synthesize_speech",
    "description": "Convert text to spoken audio supporting Telugu, Hindi, and English.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The text to be spoken."},
            "language": {"type": "string", "enum": ["en", "te", "hi", "auto"], "description": "Language code."},
            "voice": {"type": "string", "description": "Optional voice name override."},
        },
        "required": ["text"],
    },
}

register_tool(
    name="synthesize_speech",
    func=lambda args: synthesize_speech(args["text"], args.get("voice"), args.get("language")),
    spec=_SYNTH_SPEC,
    level=PermissionLevel.CONTROL,
)
