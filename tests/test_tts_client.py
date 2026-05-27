"""
tests/test_tts_client.py
-------------------------
Tests for the TTS client.

Unit tests mock the provider and run without API keys.
Integration tests (marked @pytest.mark.integration) make real API calls and
require either OPENAI_TTS_API_KEY (for OpenAI TTS) or ELEVENLABS_API_KEY +
ELEVENLABS_VOICE_ID (for ElevenLabs).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from state import AudioMeta


# ─── Unit tests (mocked providers) ───────────────────────────────────────────

class TestSynthesizeUnit:
    @patch("tools.tts_client._measure_duration", return_value=3.2)
    @patch("tools.tts_client._synthesize_openai")
    @patch("tools.tts_client.TTS_PROVIDER", "openai")
    def test_openai_provider_returns_audio_meta(self, mock_synth, _mock_dur):
        """With openai provider, synthesize() should return a valid AudioMeta."""
        import tools.tts_client as tts_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.mp3")
            mock_synth.side_effect = lambda text, out: Path(out).touch()
            result = tts_mod.synthesize("Hello world.", path, scene_id=1)

        assert isinstance(result, dict)
        assert result["scene_id"] == 1
        assert result["duration_seconds"] == 3.2
        assert "file_path" in result

    @patch("tools.tts_client._measure_duration", return_value=4.5)
    @patch("tools.tts_client._synthesize_elevenlabs")
    @patch("tools.tts_client.TTS_PROVIDER", "elevenlabs")
    def test_elevenlabs_provider_returns_audio_meta(self, mock_synth, _mock_dur):
        """With elevenlabs provider, synthesize() should return a valid AudioMeta."""
        import tools.tts_client as tts_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.mp3")
            mock_synth.side_effect = lambda text, out: Path(out).touch()
            result = tts_mod.synthesize("Hello world.", path, scene_id=2)

        assert result["scene_id"] == 2
        assert result["duration_seconds"] == 4.5

    @patch("tools.tts_client.TTS_PROVIDER", "invalid_provider")
    def test_invalid_provider_raises(self):
        """An unknown TTS_PROVIDER should raise ValueError."""
        import tools.tts_client as tts_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="Unknown TTS provider"):
                tts_mod.synthesize("Hello.", os.path.join(tmpdir, "x.mp3"), scene_id=1)


# ─── Integration test (real API) ─────────────────────────────────────────────

@pytest.mark.integration
class TestTTSIntegration:
    def test_openai_tts_duration_matches_librosa(self):
        """
        Integration: synthesize a short sentence with OpenAI TTS and verify
        AudioMeta.duration_seconds matches librosa.get_duration from the file.

        Requires OPENAI_TTS_API_KEY to be set.
        Skipped automatically if the key is not present.
        """
        from dotenv import load_dotenv
        load_dotenv()

        tts_key = os.getenv("OPENAI_TTS_API_KEY")
        if not tts_key:
            pytest.skip("OPENAI_TTS_API_KEY not set — skipping TTS integration test")

        import librosa
        import importlib
        import tools.tts_client as tts_mod
        importlib.reload(tts_mod)

        text = "Quantum entanglement links particles across vast distances instantly."
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "tts_test.mp3")
            audio_meta = tts_mod.synthesize(text, path, scene_id=1)

            assert os.path.exists(path), "TTS output file must exist"
            assert os.path.getsize(path) > 0, "TTS output file must not be empty"

            librosa_duration = round(librosa.get_duration(path=path), 1)
            assert audio_meta["duration_seconds"] == librosa_duration, (
                f"AudioMeta duration {audio_meta['duration_seconds']} "
                f"!= librosa duration {librosa_duration}"
            )
            assert audio_meta["duration_seconds"] > 0.5, "Duration must be > 0.5s"
