"""Microphone capture & Voice Activity Detection (VAD) utilities for JARVIS.

Provides:
- ``record_until_silence``: Real-time microphone listener that automatically detects
  when the user starts speaking, streams live RMS audio levels to UI visualizers,
  and automatically stops recording after *silence_duration* seconds (default 3.0s)
  once the user finishes speaking.
- ``record_to_wav``: Fixed-duration recorder preserved for compatibility.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf


DEFAULT_SAMPLE_RATE = 16000  # Optimal for Google Speech & Whisper
DEFAULT_DURATION = 10
DEFAULT_SILENCE_STOP_SECONDS = 1.5  # Reduced from 3.0s → 1.5s for faster response


def _temp_wav_path() -> Path:
    from app.config import get_settings
    settings = get_settings()
    temp_dir = settings.jarvis_data_dir / "temp_audio"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir / f"mic_{uuid.uuid4().hex}.wav"


def _compute_rms(chunk: np.ndarray) -> float:
    """Compute RMS amplitude of an int16 audio array."""
    if chunk.size == 0:
        return 0.0
    arr = chunk.astype(np.float32)
    return float(np.sqrt(np.mean(arr * arr)))


def record_until_silence(
    silence_duration: float = DEFAULT_SILENCE_STOP_SECONDS,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    wait_timeout: Optional[float] = 15.0,
    max_speech_duration: float = 45.0,
    stop_event: Optional[threading.Event] = None,
    on_speech_start: Optional[Callable[[], None]] = None,
    on_level: Optional[Callable[[float], None]] = None,
    min_threshold: float = 320.0,
) -> Optional[Path]:
    """Listen on the microphone with automatic Voice Activity Detection (VAD).

    1. Calibrates ambient noise floor for ~0.3s.
    2. Waits until speech energy exceeds the adaptive threshold (calling ``on_speech_start``).
    3. Records continuously while the user speaks, keeping a 0.5s pre-roll so the first syllable is preserved.
    4. Automatically stops ``silence_duration`` seconds (default 3.0s) after the user stops speaking.
    5. Trims excess trailing silence and saves a 16kHz mono WAV file.

    Returns:
        Path to recorded WAV file, or ``None`` if cancelled or no speech detected within ``wait_timeout``.
    """
    chunk_sec = 0.1
    chunk_samples = int(sample_rate * chunk_sec)
    pre_roll = deque(maxlen=5)  # 0.5s pre-speech context
    recorded_chunks: list[np.ndarray] = []

    speech_started = False
    speech_chunks = 0
    silence_elapsed = 0.0
    speech_elapsed = 0.0
    wait_elapsed = 0.0

    # Adaptive ambient calibration
    ambient_samples: list[float] = []
    threshold = min_threshold

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=chunk_samples,
        ) as stream:
            # Brief ambient noise sampling (3 x 100ms = 0.3s)
            for _ in range(3):
                if stop_event and stop_event.is_set():
                    return None
                data, _ = stream.read(chunk_samples)
                rms = _compute_rms(data)
                ambient_samples.append(rms)
                pre_roll.append(data.copy())

            if ambient_samples:
                noise_floor = float(np.median(ambient_samples))
                # Threshold scales gently above room noise, clamped reasonably
                threshold = max(min_threshold, min(noise_floor * 2.4 + 120.0, 2200.0))

            while True:
                if stop_event and stop_event.is_set():
                    break

                data, _ = stream.read(chunk_samples)
                rms = _compute_rms(data)

                if on_level:
                    # Normalize smoothly to [0.0, 1.0] for HUD visualizers
                    norm = min(1.0, max(0.0, (rms - threshold * 0.3) / 3500.0))
                    try:
                        on_level(norm)
                    except Exception:
                        pass

                is_voice = rms >= threshold

                if not speech_started:
                    pre_roll.append(data.copy())
                    if is_voice:
                        speech_started = True
                        speech_chunks = 1
                        silence_elapsed = 0.0
                        recorded_chunks.extend(pre_roll)
                        if on_speech_start:
                            try:
                                on_speech_start()
                            except Exception:
                                pass
                    else:
                        # Update slow ambient adaptation while idle
                        threshold = threshold * 0.97 + max(min_threshold, rms * 2.3 + 120.0) * 0.03
                        wait_elapsed += chunk_sec
                        if wait_timeout is not None and wait_elapsed >= wait_timeout:
                            return None
                else:
                    recorded_chunks.append(data.copy())
                    speech_elapsed += chunk_sec

                    if is_voice:
                        speech_chunks += 1
                        silence_elapsed = 0.0
                    else:
                        silence_elapsed += chunk_sec

                    if silence_elapsed >= silence_duration:
                        break
                    if speech_elapsed >= max_speech_duration:
                        break

    except Exception as exc:
        raise RuntimeError(f"Failed to record microphone audio: {exc}")

    # Ignore tiny accidental clicks (< 0.3s of actual voiced chunks)
    if not speech_started or speech_chunks < 2 or not recorded_chunks:
        return None

    # Trim excess trailing silence (keep ~0.4s tail out of the 3.0s silence window)
    excess_silence_chunks = max(0, int((silence_elapsed - 0.4) / chunk_sec))
    if excess_silence_chunks > 0 and len(recorded_chunks) > excess_silence_chunks + 5:
        recorded_chunks = recorded_chunks[:-excess_silence_chunks]

    audio = np.concatenate(recorded_chunks, axis=0)
    filename = _temp_wav_path()
    sf.write(str(filename), audio, samplerate=sample_rate)
    return filename


def record_to_wav(duration: int = DEFAULT_DURATION, sample_rate: int = DEFAULT_SAMPLE_RATE) -> Path:
    """Record microphone audio for *duration* seconds (fixed duration)."""
    filename = _temp_wav_path()
    try:
        audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        sf.write(str(filename), audio, samplerate=sample_rate)
    except Exception as exc:
        raise RuntimeError(f"Failed to record microphone audio: {exc}")

    return filename
