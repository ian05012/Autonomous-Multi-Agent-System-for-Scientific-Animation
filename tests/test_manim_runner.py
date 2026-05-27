"""
tests/test_manim_runner.py
---------------------------
Tests for the Manim Docker rendering sandbox.

Unit tests mock Docker and run without Docker.
Integration tests (marked @pytest.mark.integration) require Docker +
the manim-science-animation image to be built.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.manim_runner import ManimErrorType, classify_error


# ─── classify_error tests ─────────────────────────────────────────────────────

class TestClassifyError:
    def test_attribute_error_classified_as_hallucinated_api(self):
        stderr = "AttributeError: type object 'ShowCreation' has no attribute 'create'"
        assert classify_error(stderr) == ManimErrorType.HALLUCINATED_API

    def test_name_error_classified_as_hallucinated_api(self):
        stderr = "NameError: name 'TextMobject' is not defined"
        assert classify_error(stderr) == ManimErrorType.HALLUCINATED_API

    def test_syntax_error_classified_correctly(self):
        stderr = "SyntaxError: invalid syntax at line 10"
        assert classify_error(stderr) == ManimErrorType.SYNTAX_ERROR

    def test_type_error_classified_correctly(self):
        stderr = "TypeError: expected float, got str"
        assert classify_error(stderr) == ManimErrorType.TYPE_ERROR

    def test_value_error_classified_correctly(self):
        stderr = "ValueError: invalid literal for int() with base 10"
        assert classify_error(stderr) == ManimErrorType.TYPE_ERROR

    def test_empty_stderr_returns_unknown(self):
        assert classify_error("") == ManimErrorType.UNKNOWN

    def test_unrecognized_error_returns_unknown(self):
        assert classify_error("ImportError: cannot import module") == ManimErrorType.UNKNOWN


# ─── Integration test: real Docker render ─────────────────────────────────────

SIMPLE_MANIM_SCENE = """from manim import *

class AnimatedScene(Scene):
    def construct(self):
        circle = Circle(color=BLUE)
        self.play(GrowFromCenter(circle), run_time=2.0)
        self.play(FadeOut(circle), run_time=1.0)
"""


@pytest.mark.integration
class TestManimRunnerIntegration:
    def test_renders_simple_scene_and_produces_mp4(self):
        """
        Integration: render a known-good Manim scene and assert:
        - MP4 file is produced
        - Duration is > 0
        - Default resolution is 720p (1280x720)
        Requires Docker and the manim-science-animation image.
        """
        import docker as docker_sdk

        try:
            docker_sdk.from_env()
        except Exception:
            pytest.skip("Docker daemon not accessible — skipping Manim integration test")

        from tools.manim_runner import render_scene

        video_meta = render_scene(SIMPLE_MANIM_SCENE, scene_id=999)

        assert video_meta is not None
        assert Path(video_meta["file_path"]).exists(), "MP4 file must exist"
        assert video_meta["duration_seconds"] > 0, "Video duration must be > 0"
        assert video_meta["scene_id"] == 999

        # Verify resolution using ffprobe
        import subprocess
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0",
                video_meta["file_path"],
            ],
            capture_output=True, text=True, timeout=10,
        )
        dimensions = result.stdout.strip()
        assert "1280" in dimensions and "720" in dimensions, (
            f"Expected 720p (1280x720) by default, got: {dimensions}"
        )

        # Cleanup
        Path(video_meta["file_path"]).unlink(missing_ok=True)
