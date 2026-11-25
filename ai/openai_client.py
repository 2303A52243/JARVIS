"""OpenAI / OpenRouter client wrapper for JARVIS.

Uses the official OpenAI Python SDK (v1.0.0+).
Supports both standard OpenAI and OpenRouter endpoints.
Handles chat completion, Whisper speech-to-text transcription, and OpenAI TTS.
All model identifiers and base URLs are configurable via environment variables.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
from openai import OpenAI
from app.config import get_settings
from security.audit_logger import get_audit_logger


_OPENROUTER_FALLBACK_MODELS = [
    "openai/gpt-4.1-nano",
    "google/gemini-2.5-flash",
    "anthropic/claude-haiku-4.5",
]


class OpenAIClient:
    """Encapsulates OpenAI / OpenRouter API interactions using the modern SDK."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = get_audit_logger()
        self.chat_model = self.settings.effective_chat_model
        self.transcription_model = self.settings.openai_transcription_model
        self.tts_model = self.settings.openai_tts_model
        self.tts_voice = getattr(self.settings, "openai_tts_voice", "onyx")
        self._sdk_client: Optional[OpenAI] = None
        self._sdk_key: str = ""
        self._sdk_base_url: Optional[str] = None

    def _get_api_client(self) -> OpenAI:
        settings = get_settings()
        self.settings = settings
        if not settings.is_api_key_configured:
            raise RuntimeError("API key is missing or not configured.")

        base_url = settings.effective_base_url
        if (
            self._sdk_client is not None
            and self._sdk_key == settings.openai_api_key
            and self._sdk_base_url == base_url
        ):
            return self._sdk_client

        headers: Dict[str, str] = {}
        if settings.is_openrouter:
            headers["HTTP-Referer"] = "https://jarvis.local"
            headers["X-Title"] = "JARVIS Assistant"

        http_client = httpx.Client(
            timeout=httpx.Timeout(10.0, connect=4.0),
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
        )
        self._sdk_client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=base_url,
            default_headers=headers if headers else None,
            timeout=10.0,
            max_retries=0,
            http_client=http_client,
        )
        self._sdk_key = settings.openai_api_key
        self._sdk_base_url = base_url
        return self._sdk_client

    def chat_complete(
        self,
        messages: List[Dict[str, Any]],
        *,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> Any:
        """Perform a chat completion request (supports OpenAI/OpenRouter tool calling & fast fallback)."""
        client = self._get_api_client()
        primary_model = self.settings.effective_chat_model

        models_to_try = [primary_model]
        if self.settings.is_openrouter:
            for fb in _OPENROUTER_FALLBACK_MODELS:
                if fb not in models_to_try:
                    models_to_try.append(fb)

        last_exc: Optional[Exception] = None
        for idx, model_name in enumerate(models_to_try):
            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "stream": stream,
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = tool_choice or "auto"

            self.logger.info(
                f"Calling chat API – model={model_name}, stream={stream}, tools={len(tools) if tools else 0}"
            )
            try:
                response = client.chat.completions.create(**payload)
                return response
            except Exception as exc:
                last_exc = exc
                self.logger.warning(f"Chat request failed on '{model_name}': {exc}")
                # Only fall back across models on transient rate-limit / unavailability / timeout
                msg_lower = str(exc).lower()
                retryable = any(code in msg_lower for code in ("429", "404", "502", "503", "504", "timeout", "timed out", "rate"))
                if not retryable or idx == len(models_to_try) - 1:
                    self.logger.error(f"Chat request failed: {exc}")
                    raise
        if last_exc:
            raise last_exc

    def transcribe_audio(self, audio_path: str, language: str = "en") -> str:
        """Transcribe an audio file using Whisper (OpenAI only)."""
        settings = get_settings()
        if settings.is_openrouter:
            raise NotImplementedError("OpenRouter does not support Whisper transcription. Use Google Speech STT instead.")

        client = self._get_api_client()
        try:
            with open(audio_path, "rb") as fp:
                response = client.audio.transcriptions.create(
                    model=self.transcription_model,
                    file=fp,
                    language=language if language != "auto" else None,
                )
            return response.text
        except Exception as exc:
            self.logger.error(f"OpenAI transcription failed: {exc}")
            raise

    def generate_speech(self, text: str, voice: Optional[str] = None) -> bytes:
        """Generate spoken audio (MP3) for *text* (OpenAI only)."""
        settings = get_settings()
        if settings.is_openrouter:
            raise NotImplementedError("OpenRouter does not support TTS. Use Edge-TTS or Google TTS instead.")

        client = self._get_api_client()
        voice_name = voice or self.tts_voice
        try:
            response = client.audio.speech.create(
                model=self.tts_model,
                voice=voice_name,
                input=text,
            )
            return response.content
        except Exception as exc:
            self.logger.error(f"OpenAI TTS failed: {exc}")
            raise


_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    """Singleton accessor – creates a client on first use."""
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client


def reset_openai_client() -> None:
    """Reset the singleton instance (e.g. after reloading settings)."""
    global _client
    _client = None


def warm_up_openai_client() -> None:
    """Pre-warm DNS & TLS keep-alive pool so first chat turn has zero handshake stall.

    Sends a lightweight GET /models request (1-token overhead) to establish the
    TCP+TLS connection into the keep-alive pool before the user submits a query.
    All exceptions are silently swallowed — this is best-effort only.
    """
    try:
        c = get_openai_client()
        if not c.settings.is_api_key_configured:
            return
        sdk = c._get_api_client()
        # Use a real lightweight API call to establish TLS connection.
        # /models is cheap (no generation), just warms up the socket pool.
        sdk.models.list()
    except Exception:
        pass
