"""
tests/test_scriptwriter.py
---------------------------
Tests for the Scriptwriter Agent.

Unit tests use mocked LLM calls and run without API keys.
Integration tests (marked @pytest.mark.integration) call the real LLM API.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.scriptwriter import MAX_SCENES, MIN_SCENES, scriptwriter_node
from state import make_initial_state


# ─── Helpers ──────────────────────────────────────────────────────────────────

SAMPLE_ARTICLE = """
Quantum entanglement is one of the most fascinating phenomena in physics.
When two particles become entangled, measuring the state of one instantly
determines the state of the other, no matter the distance between them.
Einstein called this "spooky action at a distance," doubting it could be
real. Yet decades of experiments have confirmed that entanglement is genuine.
It underpins quantum computing, quantum cryptography, and quantum teleportation.
Understanding entanglement requires letting go of classical intuitions about
locality and realism. The universe, it turns out, is deeply non-local at
the quantum scale — a fact with profound implications for physics and philosophy.
"""

def _make_storyboard_json(n: int = 3) -> str:
    scenes = [
        {
            "scene_id": i + 1,
            "narration": f"This is scene {i + 1} explaining the concept clearly and in detail.",
            "visual_description": f"A diagram showing concept {i + 1} with arrows and labels.",
            "estimated_duration": 10,
        }
        for i in range(n)
    ]
    return json.dumps(scenes)


def _make_mock_llm(response_json: str) -> MagicMock:
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_json
    mock_llm.invoke.return_value = mock_response
    return mock_llm


# ─── Unit tests (mocked LLM) ──────────────────────────────────────────────────

class TestScriptwriterNode:
    @patch("agents.scriptwriter.ChatOpenAI")
    def test_returns_storyboard_list(self, mock_cls):
        mock_cls.return_value = _make_mock_llm(_make_storyboard_json(3))
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)
        assert "storyboard" in result
        assert isinstance(result["storyboard"], list)

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_storyboard_has_correct_scene_count(self, mock_cls):
        mock_cls.return_value = _make_mock_llm(_make_storyboard_json(4))
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)
        assert len(result["storyboard"]) == 4

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_each_scene_has_required_fields(self, mock_cls):
        mock_cls.return_value = _make_mock_llm(_make_storyboard_json(3))
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)
        for scene in result["storyboard"]:
            assert "scene_id" in scene
            assert "narration" in scene
            assert "visual_description" in scene
            assert "estimated_duration" in scene
            assert "status" in scene

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_scene_ids_are_sequential(self, mock_cls):
        mock_cls.return_value = _make_mock_llm(_make_storyboard_json(3))
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)
        ids = [s["scene_id"] for s in result["storyboard"]]
        assert ids == [1, 2, 3]

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_strips_markdown_code_block(self, mock_cls):
        wrapped = f"```json\n{_make_storyboard_json(3)}\n```"
        mock_cls.return_value = _make_mock_llm(wrapped)
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)
        assert len(result["storyboard"]) == 3

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_narration_padded_if_too_short(self, mock_cls):
        scenes = [
            {
                "scene_id": 1,
                "narration": "Short.",      # < 10 words
                "visual_description": "A circle appears on the screen now.",
                "estimated_duration": 10,
            }
        ] * MIN_SCENES
        mock_cls.return_value = _make_mock_llm(json.dumps(scenes))
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)
        for scene in result["storyboard"]:
            assert len(scene["narration"].split()) >= 10

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_raises_if_too_few_scenes(self, mock_cls):
        too_few = _make_storyboard_json(1)  # < MIN_SCENES
        mock_cls.return_value = _make_mock_llm(too_few)
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        with pytest.raises(RuntimeError, match="minimum"):
            scriptwriter_node(state)

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_caps_at_max_scenes(self, mock_cls):
        too_many = _make_storyboard_json(MAX_SCENES + 5)
        mock_cls.return_value = _make_mock_llm(too_many)
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)
        assert len(result["storyboard"]) <= MAX_SCENES

    @patch("agents.scriptwriter.ChatOpenAI")
    def test_raises_on_invalid_json(self, mock_cls):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "NOT VALID JSON {{{"
        mock_llm.invoke.return_value = mock_response
        mock_cls.return_value = mock_llm
        state = make_initial_state(SAMPLE_ARTICLE, "text")
        with pytest.raises(RuntimeError, match="JSON"):
            scriptwriter_node(state)


# ─── Integration test (real LLM API) ──────────────────────────────────────────

@pytest.mark.integration
class TestScriptwriterIntegration:
    def test_generates_valid_storyboard_from_article(self):
        """
        Integration: Call the real LLM API and assert a valid storyboard is returned.
        Requires OPENAI_API_KEY (or OpenRouter equivalent) to be set.
        """
        from dotenv import load_dotenv
        load_dotenv()

        state = make_initial_state(SAMPLE_ARTICLE, "text")
        result = scriptwriter_node(state)

        storyboard = result["storyboard"]
        assert isinstance(storyboard, list), "storyboard must be a list"
        assert MIN_SCENES <= len(storyboard) <= MAX_SCENES, (
            f"Expected {MIN_SCENES}–{MAX_SCENES} scenes, got {len(storyboard)}"
        )

        for scene in storyboard:
            assert len(scene["narration"].split()) >= 10, (
                f"Scene {scene['scene_id']} narration too short: {scene['narration']!r}"
            )
            assert len(scene["visual_description"].split()) >= 5, (
                f"Scene {scene['scene_id']} visual_description too short"
            )
            assert scene["estimated_duration"] >= 5.0
            assert scene["status"] in ("pending", "done", "error")
