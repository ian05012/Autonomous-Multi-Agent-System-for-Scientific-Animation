"""
tools/tts_client.py
--------------------
Text-to-Speech client abstraction for the Voiceover Agent.

Supports four providers (selected via TTS_PROVIDER env var):
- "openai"     → OpenAI TTS API (tts-1 model, onyx voice)
- "elevenlabs" → ElevenLabs API (voice ID from ELEVENLABS_VOICE_ID)
- "google"     → Google Cloud Text-to-Speech REST API (API key auth)
- "disabled"   → Skip TTS; generate a silent placeholder MP3

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
GOOGLE_TTS_LANGUAGE = os.getenv("GOOGLE_TTS_LANGUAGE", "en-US")
GOOGLE_TTS_VOICE = os.getenv("GOOGLE_TTS_VOICE_NAME", "en-US-Journey-D")

# TTS always uses the real OpenAI API (not proxies like OpenRouter that don't
# support audio endpoints). OPENAI_TTS_API_KEY overrides OPENAI_API_KEY for TTS.
_OPENAI_TTS_API_KEY = os.getenv("OPENAI_TTS_API_KEY") or os.getenv("OPENAI_API_KEY")
_OPENAI_TTS_BASE_URL = "https://api.openai.com/v1"


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

    client = OpenAI(api_key=_OPENAI_TTS_API_KEY, base_url=_OPENAI_TTS_BASE_URL)
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


def _synthesize_google(text: str, output_path: str) -> None:
    """Synthesize speech using Google Cloud TTS with service account credentials."""
    from google.cloud import texttospeech
    from google.oauth2 import service_account

    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if creds_path:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        client = texttospeech.TextToSpeechClient(credentials=credentials)
    else:
        # Fall back to Application Default Credentials
        client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=GOOGLE_TTS_LANGUAGE,
        name=GOOGLE_TTS_VOICE,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
    )
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )
    with open(output_path, "wb") as f:
        f.write(response.audio_content)


def _synthesize_silent(text: str, output_path: str) -> None:
    """Generate a silent MP3 whose duration approximates speaking speed (~130 wpm)."""
    import subprocess
    words = len(text.split())
    duration = max(1.0, words / 130 * 60)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-q:a", "9", "-acodec", "libmp3lame",
            output_path,
        ],
        capture_output=True,
        check=True,
    )


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
    elif provider == "google":
        _synthesize_google(text, output_path)
    elif provider == "disabled":
        _synthesize_silent(text, output_path)
    else:
        raise ValueError(
            f"Unknown TTS provider: '{provider}'. "
            f"Set TTS_PROVIDER to 'openai', 'elevenlabs', 'google', or 'disabled'."
        )

    # Measure actual duration from the generated file
    duration = _measure_duration(output_path)

    return AudioMeta(
        scene_id=scene_id,
        file_path=str(Path(output_path).resolve()),
        duration_seconds=duration,
    )
