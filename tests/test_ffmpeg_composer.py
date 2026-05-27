"""
tests/test_ffmpeg_composer.py
------------------------------
Tests for FFMPEG video composition.

Unit tests use synthetic audio/video files (generated with ffmpeg).
Integration tests verify the full compose + sync pipeline.

Requires: ffmpeg installed in PATH.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from state import AudioMeta, VideoMeta
from tools.ffmpeg_composer import compose_video, verify_sync


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _make_silent_audio(path: str, duration: float) -> None:
    """Generate a silent MP3 file of given duration using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-q:a", "9",
            path,
        ],
        capture_output=True, check=True, timeout=30,
    )


def _make_black_video(path: str, duration: float, width: int = 640, height: int = 360) -> None:
    """Generate a black silent MP4 of given duration using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=black:size={width}x{height}:rate=24",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac",
            path,
        ],
        capture_output=True, check=True, timeout=60,
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not _ffmpeg_available(), reason="ffmpeg not installed")
class TestComposeVideo:
    def test_compose_two_scenes_produces_mp4(self):
        """Compose 2 minimal scene clips and verify output MP4 is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create synthetic audio + video for 2 scenes
            audio1_path = os.path.join(tmpdir, "audio_1.mp3")
            audio2_path = os.path.join(tmpdir, "audio_2.mp3")
            video1_path = os.path.join(tmpdir, "video_1.mp4")
            video2_path = os.path.join(tmpdir, "video_2.mp4")
            output_path = os.path.join(tmpdir, "final.mp4")

            _make_silent_audio(audio1_path, duration=2.0)
            _make_silent_audio(audio2_path, duration=3.0)
            _make_black_video(video1_path, duration=2.5)
            _make_black_video(video2_path, duration=3.5)

            audio_files: list[AudioMeta] = [
                {"scene_id": 1, "file_path": audio1_path, "duration_seconds": 2.0},
                {"scene_id": 2, "file_path": audio2_path, "duration_seconds": 3.0},
            ]
            video_clips: list[VideoMeta] = [
                {"scene_id": 1, "file_path": video1_path, "duration_seconds": 2.5},
                {"scene_id": 2, "file_path": video2_path, "duration_seconds": 3.5},
            ]

            result_path = compose_video(audio_files, video_clips, output_path)

            assert Path(result_path).exists(), "Output MP4 must exist"
            assert os.path.getsize(result_path) > 0, "Output MP4 must not be empty"

    def test_composed_duration_matches_sum_of_audio_durations(self):
        """
        The composed video's duration should approximately equal the sum of
        audio durations. Video clips are generated with matching durations
        to reflect the real production case where Manim timing matches TTS.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            audio1_path = os.path.join(tmpdir, "audio_1.mp3")
            audio2_path = os.path.join(tmpdir, "audio_2.mp3")
            video1_path = os.path.join(tmpdir, "video_1.mp4")
            video2_path = os.path.join(tmpdir, "video_2.mp4")
            output_path = os.path.join(tmpdir, "final.mp4")

            audio_dur1, audio_dur2 = 2.0, 3.0
            _make_silent_audio(audio1_path, duration=audio_dur1)
            _make_silent_audio(audio2_path, duration=audio_dur2)
            # Video durations match audio (realistic Manim-generated case)
            _make_black_video(video1_path, duration=audio_dur1)
            _make_black_video(video2_path, duration=audio_dur2)

            audio_files: list[AudioMeta] = [
                {"scene_id": 1, "file_path": audio1_path, "duration_seconds": audio_dur1},
                {"scene_id": 2, "file_path": audio2_path, "duration_seconds": audio_dur2},
            ]
            video_clips: list[VideoMeta] = [
                {"scene_id": 1, "file_path": video1_path, "duration_seconds": audio_dur1},
                {"scene_id": 2, "file_path": video2_path, "duration_seconds": audio_dur2},
            ]

            result_path = compose_video(audio_files, video_clips, output_path)

            # Measure output duration with ffprobe
            probe = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    result_path,
                ],
                capture_output=True, text=True, timeout=10,
            )
            actual_duration = float(probe.stdout.strip())
            expected_duration = audio_dur1 + audio_dur2  # 5.0

            assert abs(actual_duration - expected_duration) <= 0.5, (
                f"Expected ≈{expected_duration}s (sum of audio), got {actual_duration:.2f}s"
            )

    def test_verify_sync_passes_on_composed_output(self):
        """
        After composing, verify_sync() should return True — audio/video start
        times must be within 50ms of each other.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio_1.mp3")
            video_path = os.path.join(tmpdir, "video_1.mp4")
            output_path = os.path.join(tmpdir, "final.mp4")

            _make_silent_audio(audio_path, duration=3.0)
            _make_black_video(video_path, duration=3.0)

            audio_files: list[AudioMeta] = [
                {"scene_id": 1, "file_path": audio_path, "duration_seconds": 3.0},
            ]
            video_clips: list[VideoMeta] = [
                {"scene_id": 1, "file_path": video_path, "duration_seconds": 3.0},
            ]

            result_path = compose_video(audio_files, video_clips, output_path)
            assert verify_sync(result_path, tolerance_ms=50.0), (
                "Audio/video streams are not synchronized within 50ms"
            )

    def test_skips_scenes_with_missing_files(self):
        """Scenes with missing audio or video files should be skipped gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, "audio_1.mp3")
            video_path = os.path.join(tmpdir, "video_1.mp4")
            output_path = os.path.join(tmpdir, "final.mp4")

            _make_silent_audio(audio_path, duration=2.0)
            _make_black_video(video_path, duration=2.0)

            audio_files: list[AudioMeta] = [
                {"scene_id": 1, "file_path": audio_path, "duration_seconds": 2.0},
                # Scene 2 audio is missing (file doesn't exist)
                {"scene_id": 2, "file_path": "/nonexistent/audio_2.mp3", "duration_seconds": 3.0},
            ]
            video_clips: list[VideoMeta] = [
                {"scene_id": 1, "file_path": video_path, "duration_seconds": 2.0},
                {"scene_id": 2, "file_path": "/nonexistent/video_2.mp4", "duration_seconds": 3.0},
            ]

            # Should succeed with just scene 1
            result_path = compose_video(audio_files, video_clips, output_path)
            assert Path(result_path).exists()

    def test_raises_when_no_composable_scenes(self):
        """If no scenes have both audio and video, raise RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_files: list[AudioMeta] = [
                {"scene_id": 1, "file_path": "/nonexistent.mp3", "duration_seconds": 2.0},
            ]
            video_clips: list[VideoMeta] = [
                {"scene_id": 1, "file_path": "/nonexistent.mp4", "duration_seconds": 2.0},
            ]
            with pytest.raises(RuntimeError, match="No scenes"):
                compose_video(
                    audio_files, video_clips,
                    os.path.join(tmpdir, "out.mp4")
                )
