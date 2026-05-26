"""
state.py
--------
Shared pipeline state definitions for the Science Animation System.
All LangGraph agent nodes read from and write to PipelineState.
"""

from __future__ import annotations

import json
import os
from typing import Annotated, Literal, Optional

from typing_extensions import TypedDict


# ─── Sub-types ────────────────────────────────────────────────────────────────

class SceneSpec(TypedDict):
    """A single storyboard scene produced by the Scriptwriter Agent."""
    scene_id: int               # 1-indexed
    narration: str              # spoken text for voiceover
    visual_description: str     # animation instruction for Animator Agent
    estimated_duration: float   # estimated seconds (overridden by actual audio)
    status: str                 # "pending" | "done" | "error"


class AudioMeta(TypedDict):
    """Metadata for a synthesized audio file produced by the Voiceover Agent."""
    scene_id: int
    file_path: str              # absolute path to MP3 file
    duration_seconds: float     # measured from actual file via librosa


class VideoMeta(TypedDict):
    """Metadata for a rendered video clip produced by the Animator Agent."""
    scene_id: int
    file_path: str              # absolute path to MP4 file
    duration_seconds: float     # measured from rendered clip


class RevisionTarget(TypedDict):
    """Routing decision from the HITL revision router."""
    scene_id: int               # 1-indexed scene to regenerate
    agent: Literal["scriptwriter", "voiceover", "animator"]
    confidence: Literal["high", "low"]


# ─── Reducer helpers ──────────────────────────────────────────────────────────

def _append_errors(existing: list[str], update: list[str]) -> list[str]:
    """LangGraph reducer: append new errors to existing error log."""
    return existing + update


# ─── Main Pipeline State ──────────────────────────────────────────────────────

class PipelineState(TypedDict):
    """
    Central state object passed through all LangGraph nodes.
    Each agent node receives the full state and returns a partial update.
    """
    # Input
    input_text: str                                # raw source material
    source_type: Literal["text", "pdf", "url"]    # how input was provided
    input_path: Optional[str]                      # file path or URL if applicable

    # Agent outputs (populated sequentially)
    storyboard: list[SceneSpec]                    # Scriptwriter output
    audio_files: list[AudioMeta]                   # Voiceover output
    video_clips: list[VideoMeta]                   # Animator output
    final_video_path: Optional[str]                # FFMPEG composition output

    # HITL fields
    hitl_revision: Optional[str]                   # user's natural-language instruction
    revision_target: Optional[RevisionTarget]      # which scene/agent to re-run
    iteration: int                                 # HITL loop counter (starts at 0)

    # Error tracking (uses append reducer)
    error_log: Annotated[list[str], _append_errors]

    # Social media outputs
    youtube_url: Optional[str]
    instagram_url: Optional[str]


# ─── Serialization helpers ────────────────────────────────────────────────────

def state_to_dict(state: PipelineState) -> dict:
    """Convert PipelineState to a plain dict for JSON serialization."""
    return dict(state)


def state_from_dict(data: dict) -> PipelineState:
    """Reconstruct a PipelineState from a plain dict loaded from JSON."""
    # Provide defaults for optional fields
    data.setdefault("storyboard", [])
    data.setdefault("audio_files", [])
    data.setdefault("video_clips", [])
    data.setdefault("final_video_path", None)
    data.setdefault("hitl_revision", None)
    data.setdefault("revision_target", None)
    data.setdefault("iteration", 0)
    data.setdefault("error_log", [])
    data.setdefault("youtube_url", None)
    data.setdefault("instagram_url", None)
    data.setdefault("input_path", None)
    return data  # type: ignore[return-value]


def save_state(state: PipelineState, path: str = "output/state.json") -> None:
    """Persist PipelineState to disk after each agent node completes."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state_to_dict(state), f, indent=2, ensure_ascii=False)


def load_state(path: str = "output/state.json") -> Optional[PipelineState]:
    """
    Load PipelineState from disk if it exists.
    Returns None if no saved state is found.
    """
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return state_from_dict(data)


def make_initial_state(
    input_text: str,
    source_type: Literal["text", "pdf", "url"],
    input_path: Optional[str] = None,
) -> PipelineState:
    """Create a fresh PipelineState for a new pipeline run."""
    return {
        "input_text": input_text,
        "source_type": source_type,
        "input_path": input_path,
        "storyboard": [],
        "audio_files": [],
        "video_clips": [],
        "final_video_path": None,
        "hitl_revision": None,
        "revision_target": None,
        "iteration": 0,
        "error_log": [],
        "youtube_url": None,
        "instagram_url": None,
    }
