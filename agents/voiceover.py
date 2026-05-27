"""
agents/voiceover.py
--------------------
Voiceover Agent — LangGraph node that synthesizes speech audio for each
scene's narration text using the TTS client.

Reads the storyboard from PipelineState, synthesizes one MP3 per scene,
measures actual audio duration, and populates PipelineState.audio_files.
"""

from __future__ import annotations

import os
import time
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from state import PipelineState, AudioMeta, save_state
from tools.tts_client import synthesize

# ─── Configuration ────────────────────────────────────────────────────────────

AUDIO_OUTPUT_DIR = "output/audio"
MAX_RETRIES = 3


# ─── Retry-wrapped synthesis ──────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _synthesize_with_retry(text: str, output_path: str, scene_id: int) -> AudioMeta:
    """Synthesize audio with up to MAX_RETRIES retries on failure."""
    return synthesize(text, output_path, scene_id)


# ─── Agent node ───────────────────────────────────────────────────────────────

def voiceover_node(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Voiceover Agent.

    Synthesizes speech audio for each scene in the storyboard.
    Stores audio metadata (file path + measured duration) in the pipeline state.

    Returns a partial state update with 'audio_files' populated.
    """
    storyboard = state.get("storyboard", [])
    if not storyboard:
        raise RuntimeError("Voiceover: No storyboard found in state. Run Scriptwriter first.")

    os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True)

    audio_files: list[AudioMeta] = []
    error_messages: list[str] = []

    # If this is a HITL partial revision targeting only one scene
    revision_target = state.get("revision_target")
    scenes_to_process = storyboard
    if revision_target and revision_target.get("agent") == "voiceover":
        target_scene_id = revision_target["scene_id"]
        scenes_to_process = [s for s in storyboard if s["scene_id"] == target_scene_id]
        # Keep existing audio for unchanged scenes
        audio_files = [a for a in state.get("audio_files", [])
                       if a["scene_id"] != target_scene_id]

    from tools.progress import update as _prog
    total = len(scenes_to_process)

    for i, scene in enumerate(scenes_to_process):
        scene_id = scene["scene_id"]
        narration = scene["narration"]
        output_path = os.path.join(AUDIO_OUTPUT_DIR, f"scene_{scene_id}.mp3")

        pct = 15 + int((i / total) * 20)
        _prog(pct, "Voiceover", f"Synthesizing scene {scene_id}/{total}")
        print(f"  [Voiceover] Synthesizing scene {scene_id}...")
        try:
            audio_meta = _synthesize_with_retry(narration, output_path, scene_id)
            audio_files.append(audio_meta)
            print(f"  [Voiceover] Scene {scene_id}: {audio_meta['duration_seconds']}s")
        except Exception as exc:
            error_msg = (
                f"Voiceover: Failed to synthesize scene {scene_id} "
                f"after {MAX_RETRIES} retries — {exc}"
            )
            error_messages.append(error_msg)
            print(f"  [Voiceover] ERROR: {error_msg}")

    # Sort by scene_id for consistency
    audio_files.sort(key=lambda a: a["scene_id"])

    # Persist and return
    updates: dict[str, Any] = {"audio_files": audio_files}
    if error_messages:
        updates["error_log"] = error_messages

    updated_state = {**state, **updates}
    save_state(updated_state)  # type: ignore[arg-type]

    return updates
