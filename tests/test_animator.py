"""
tests/test_animator.py
-----------------------
Unit tests for the Animator Agent code generation and static analysis.

Tests do NOT require API keys or Docker — all LLM calls are mocked.
Integration tests (marked with @pytest.mark.integration) require Docker.
"""

from __future__ import annotations

import re
import warnings
from unittest.mock import MagicMock, patch

import pytest

from agents.animator import (
    MAX_RETRIES,
    TIMING_TOLERANCE,
    _generate_code,
    _sum_play_runtimes,
    _validate_timing,
)
from state import SceneSpec


# ─── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_SCENE: SceneSpec = {
    "scene_id": 1,
    "narration": "A circle appears on screen and grows from the center.",
    "visual_description": "A blue circle grows from the center of the screen.",
    "estimated_duration": 5.0,
    "status": "pending",
}

VALID_MANIM_CODE = """from manim import *

class AnimatedScene(Scene):
    def construct(self):
        circle = Circle(color=BLUE)
        self.play(GrowFromCenter(circle), run_time=3.0)
        self.play(FadeOut(circle), run_time=2.0)
"""

MANIM_CODE_WRONG_TIMING = """from manim import *

class AnimatedScene(Scene):
    def construct(self):
        circle = Circle(color=BLUE)
        self.play(GrowFromCenter(circle), run_time=1.0)
        self.wait(0.5)
"""


# ─── _sum_play_runtimes tests ──────────────────────────────────────────────────

class TestSumPlayRuntimes:
    def test_sums_run_time_kwargs(self):
        code = "self.play(FadeIn(x), run_time=2.0)\nself.play(FadeOut(x), run_time=3.0)"
        assert _sum_play_runtimes(code) == 5.0

    def test_sums_self_wait(self):
        code = "self.wait(1.5)\nself.wait(2.5)"
        assert _sum_play_runtimes(code) == 4.0

    def test_sums_mixed(self):
        code = "self.play(Create(x), run_time=3.0)\nself.wait(2.0)"
        assert _sum_play_runtimes(code) == 5.0

    def test_returns_zero_for_no_runtimes(self):
        code = "self.play(FadeIn(x))"
        assert _sum_play_runtimes(code) == 0.0

    def test_handles_integer_runtimes(self):
        code = "self.play(Write(t), run_time=3)\nself.play(FadeOut(t), run_time=2)"
        assert _sum_play_runtimes(code) == 5.0

    def test_handles_valid_manim_code(self):
        total = _sum_play_runtimes(VALID_MANIM_CODE)
        assert total == 5.0


# ─── _validate_timing tests ───────────────────────────────────────────────────

class TestValidateTiming:
    def test_no_warning_when_within_tolerance(self):
        code = "self.play(FadeIn(x), run_time=5.0)"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _validate_timing(code, target_duration=5.0)
        assert len(w) == 0

    def test_warning_when_beyond_tolerance(self):
        code = "self.play(FadeIn(x), run_time=1.5)"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _validate_timing(code, target_duration=5.0)
        assert len(w) == 1
        assert "deviation" in str(w[0].message).lower()

    def test_no_warning_when_no_runtimes_found(self):
        code = "self.play(FadeIn(x))"
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _validate_timing(code, target_duration=5.0)
        assert len(w) == 0


# ─── _generate_code tests (mocked LLM) ────────────────────────────────────────

class TestGenerateCode:
    def _make_mock_llm(self, response_content: str) -> MagicMock:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = response_content
        mock_llm.invoke.return_value = mock_response
        return mock_llm

    @patch("agents.animator.retrieve_manim_context", return_value=[])
    def test_generated_code_contains_animated_scene_class(self, _mock_rag):
        mock_llm = self._make_mock_llm(VALID_MANIM_CODE)
        code = _generate_code(SAMPLE_SCENE, target_duration=5.0, llm=mock_llm)

        assert "class AnimatedScene" in code
        assert "Scene" in code

    @patch("agents.animator.retrieve_manim_context", return_value=[])
    def test_generated_code_contains_construct_method(self, _mock_rag):
        mock_llm = self._make_mock_llm(VALID_MANIM_CODE)
        code = _generate_code(SAMPLE_SCENE, target_duration=5.0, llm=mock_llm)

        assert "def construct(self)" in code

    @patch("agents.animator.retrieve_manim_context", return_value=[])
    def test_strips_markdown_code_blocks(self, _mock_rag):
        wrapped = f"```python\n{VALID_MANIM_CODE}\n```"
        mock_llm = self._make_mock_llm(wrapped)
        code = _generate_code(SAMPLE_SCENE, target_duration=5.0, llm=mock_llm)

        assert not code.startswith("```")
        assert "class AnimatedScene" in code

    @patch("agents.animator.retrieve_manim_context", return_value=[])
    def test_target_duration_passed_to_prompt(self, _mock_rag):
        mock_llm = self._make_mock_llm(VALID_MANIM_CODE)
        _generate_code(SAMPLE_SCENE, target_duration=7.5, llm=mock_llm)

        call_args = mock_llm.invoke.call_args
        messages = call_args[0][0]
        system_content = messages[0].content
        assert "7.5" in system_content

    @patch("agents.animator.retrieve_manim_context", return_value=["RAG chunk 1"])
    @patch("agents.animator.format_rag_context", return_value="RAG CONTEXT")
    def test_rag_context_included_when_available(self, _mock_fmt, _mock_rag):
        mock_llm = self._make_mock_llm(VALID_MANIM_CODE)
        _generate_code(SAMPLE_SCENE, target_duration=5.0, llm=mock_llm)

        call_args = mock_llm.invoke.call_args
        messages = call_args[0][0]
        human_content = messages[1].content
        assert "RAG CONTEXT" in human_content
