"""
tests/test_state.py
-------------------
Unit tests for PipelineState serialization and helper functions.
"""

import json
import os
import tempfile

import pytest

from state import (
    AudioMeta,
    SceneSpec,
    VideoMeta,
    load_state,
    make_initial_state,
    save_state,
    state_from_dict,
    state_to_dict,
)


class TestMakeInitialState:
    def test_text_source(self):
        state = make_initial_state("Hello world " * 10, "text")
        assert state["source_type"] == "text"
        assert state["input_text"] == "Hello world " * 10
        assert state["storyboard"] == []
        assert state["audio_files"] == []
        assert state["video_clips"] == []
        assert state["error_log"] == []
        assert state["iteration"] == 0
        assert state["hitl_revision"] is None
        assert state["revision_target"] is None
        assert state["final_video_path"] is None

    def test_url_source_with_path(self):
        state = make_initial_state("", "url", input_path="https://example.com/article")
        assert state["source_type"] == "url"
        assert state["input_path"] == "https://example.com/article"


class TestStateSerialization:
    def _sample_state(self):
        state = make_initial_state("Test article content", "text")
        scene: SceneSpec = {
            "scene_id": 1,
            "narration": "This is the narration",
            "visual_description": "A circle grows from center",
            "estimated_duration": 5.0,
            "status": "done",
        }
        audio: AudioMeta = {
            "scene_id": 1,
            "file_path": "/output/audio/scene_1.mp3",
            "duration_seconds": 4.8,
        }
        video: VideoMeta = {
            "scene_id": 1,
            "file_path": "/output/video/scene_1.mp4",
            "duration_seconds": 4.8,
        }
        state["storyboard"] = [scene]
        state["audio_files"] = [audio]
        state["video_clips"] = [video]
        state["error_log"] = ["Some warning"]
        state["iteration"] = 2
        return state

    def test_round_trip(self):
        """State can be serialized to dict and back without data loss."""
        original = self._sample_state()
        serialized = state_to_dict(original)
        restored = state_from_dict(serialized)

        assert restored["storyboard"][0]["scene_id"] == 1
        assert restored["audio_files"][0]["duration_seconds"] == 4.8
        assert restored["video_clips"][0]["file_path"] == "/output/video/scene_1.mp4"
        assert restored["error_log"] == ["Some warning"]
        assert restored["iteration"] == 2

    def test_json_serializable(self):
        """state_to_dict output must be JSON-serializable."""
        state = self._sample_state()
        serialized = state_to_dict(state)
        json_str = json.dumps(serialized)
        assert json_str  # non-empty

    def test_save_and_load(self):
        """save_state / load_state round-trip via disk."""
        state = self._sample_state()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "state.json")
            save_state(state, path=path)
            assert os.path.exists(path)
            loaded = load_state(path=path)
            assert loaded is not None
            assert loaded["storyboard"][0]["narration"] == "This is the narration"

    def test_load_nonexistent_returns_none(self):
        """load_state returns None when no saved state exists."""
        result = load_state(path="/nonexistent/path/state.json")
        assert result is None

    def test_from_dict_provides_defaults(self):
        """state_from_dict fills in optional fields with defaults."""
        minimal = {"input_text": "hi", "source_type": "text"}
        state = state_from_dict(minimal)
        assert state["storyboard"] == []
        assert state["error_log"] == []
        assert state["iteration"] == 0
        assert state["final_video_path"] is None
