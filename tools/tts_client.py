"""
tools/tts_client.py
--------------------
Text-to-Speech client abstraction for the Voiceover Agent.

Supports two providers (selected via TTS_PROVIDER env var):
- "openai"     → OpenAI TTS API (tts-1 model, onyx voice)
- "elevenlabs" → ElevenLabs API (voice ID from ELEVENLABS_VOICE_ID)

All providers return an AudioMeta with file_path and measured duration.
"""

from __future__ import annotations

import os
from pathlib import Path

from state import AudioMeta


# ─── Configuration ────────────────────────────────────────────────────────────

TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai").lower()
OPENAI_TTS_MODEL = "tts-1"
OPENAI_TTS_VOICE = "onyx"
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")


# ─── Duration measurement ────────────────────────────────────────────────────

def _measure_duration(file_path: str) -> float:
    """
    Measure audio file duration in seconds using librosa.
    Returns duration rounded to 1 decimal place.
    """
    import librosa
    duration = librosa.get_duration(path=file_path)
    return round(duration, 1)


# ─── Provider implementations ─────────────────────────────────────────────────

def _synthesize_openai(text: str, output_path: str) -> None:
    """Synthesize speech using OpenAI TTS API and save to output_path."""
    from openai import OpenAI

    client = OpenAI()
    response = client.audio.speech.create(
        model=OPENAI_TTS_MODEL,
        voice=OPENAI_TTS_VOICE,
        input=text,
        response_format="mp3",
    )
    response.stream_to_file(output_path)


def _synthesize_elevenlabs(text: str, output_path: str) -> None:
    """Synthesize speech using ElevenLabs API and save to output_path."""
    from elevenlabs.client import ElevenLabs

    if not ELEVENLABS_VOICE_ID:
        raise ValueError(
            "ELEVENLABS_VOICE_ID environment variable is not set. "
            "Please set it to your ElevenLabs voice ID."
        )

    client = ElevenLabs()
    audio_generator = client.text_to_speech.convert(
        voice_id=ELEVENLABS_VOICE_ID,
        text=text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )
    with open(output_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)


# ─── Public API ───────────────────────────────────────────────────────────────

def synthesize(text: str, output_path: str, scene_id: int) -> AudioMeta:
    """
    Synthesize speech for the given text and save it to output_path.

    Args:
        text: The narration text to convert to speech.
        output_path: Absolute path where the MP3 file should be saved.
        scene_id: The scene identifier (for AudioMeta).

    Returns:
        AudioMeta with file_path and duration_seconds measured from the file.

    Raises:
        ValueError: If the TTS provider is invalid or required env vars are missing.
        RuntimeError: If TTS API call fails.
    """
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    provider = TTS_PROVIDER
    if provider == "openai":
        _synthesize_openai(text, output_path)
    elif provider == "elevenlabs":
        _synthesize_elevenlabs(text, output_path)
    else:
        raise ValueError(
            f"Unknown TTS provider: '{provider}'. "
            f"Set TTS_PROVIDER to 'openai' or 'elevenlabs'."
        )

    # Measure actual duration from the generated file
    duration = _measure_duration(output_path)

    return AudioMeta(
        scene_id=scene_id,
        file_path=str(Path(output_path).resolve()),
        duration_seconds=duration,
    )
