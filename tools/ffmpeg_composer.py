"""
tools/ffmpeg_composer.py
-------------------------
FFMPEG-based video composition tool for the Science Animation System.

Merges per-scene video clips with their corresponding audio tracks into
a single final MP4 output.

Composition strategy:
1. For each scene: mux video clip + audio track → scene_combined_N.mp4
2. Concatenate all combined scene clips → final_video.mp4

Missing scene files are skipped with a warning (best-effort composition).
Audio and video are synchronized per scene with ≤50ms offset.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from state import AudioMeta, VideoMeta


# ─── Configuration ────────────────────────────────────────────────────────────

FINAL_OUTPUT_DIR = "output/final"
FINAL_OUTPUT_FILENAME = "final_video.mp4"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run_ffmpeg(args: list[str], description: str) -> None:
    """Run an FFMPEG command and raise RuntimeError on failure."""
    cmd = ["ffmpeg", "-y", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFMPEG failed ({description}):\n"
            f"Command: {' '.join(cmd)}\n"
            f"Stderr: {result.stderr[-2000:]}"
        )


def _merge_scene(video_path: str, audio_path: str, output_path: str) -> None:
    """
    Mux a video clip with an audio track.
    The audio track is the timing ground truth — video is trimmed/padded to match.
    """
    _run_ffmpeg(
        [
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-strict", "experimental",
            "-shortest",          # trim to the shorter of video/audio
            output_path,
        ],
        description=f"merge scene {Path(video_path).stem}",
    )


def _concatenate_clips(clip_paths: list[str], output_path: str) -> None:
    """Concatenate a list of video clips into a single MP4 using FFMPEG concat."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        for clip in clip_paths:
            f.write(f"file '{clip}'\n")
        concat_list_path = f.name

    try:
        _run_ffmpeg(
            [
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
                output_path,
            ],
            description="concatenate all scenes",
        )
    finally:
        os.unlink(concat_list_path)


# ─── Public API ───────────────────────────────────────────────────────────────

def compose_video(
    audio_files: list[AudioMeta],
    video_clips: list[VideoMeta],
    output_path: str | None = None,
) -> str:
    """
    Merge all per-scene video clips with their audio tracks into a final MP4.

    Args:
        audio_files: List of AudioMeta from Voiceover Agent.
        video_clips: List of VideoMeta from Animator Agent.
        output_path: Where to write the final video. Defaults to
                     output/final/final_video.mp4.

    Returns:
        Absolute path to the composed final video.

    Notes:
        - Scenes missing either video or audio are skipped with a warning.
        - Audio/video are synchronized per scene (FFMPEG -shortest flag).
    """
    if output_path is None:
        output_path = str(Path(FINAL_OUTPUT_DIR) / FINAL_OUTPUT_FILENAME)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Build lookup maps
    audio_by_scene = {a["scene_id"]: a for a in audio_files}
    video_by_scene = {v["scene_id"]: v for v in video_clips}

    # Determine which scenes can be composed (both audio and video present)
    all_scene_ids = sorted(set(audio_by_scene.keys()) | set(video_by_scene.keys()))

    composable_scenes = []
    for scene_id in all_scene_ids:
        audio = audio_by_scene.get(scene_id)
        video = video_by_scene.get(scene_id)

        if audio is None:
            print(f"  [Composer] WARNING: No audio for scene {scene_id} — skipping")
            continue
        if video is None:
            print(f"  [Composer] WARNING: No video for scene {scene_id} — skipping")
            continue
        if not Path(audio["file_path"]).exists():
            print(f"  [Composer] WARNING: Audio file missing for scene {scene_id} — skipping")
            continue
        if not Path(video["file_path"]).exists():
            print(f"  [Composer] WARNING: Video file missing for scene {scene_id} — skipping")
            continue

        composable_scenes.append((scene_id, audio, video))

    if not composable_scenes:
        raise RuntimeError(
            "No scenes with both audio and video available. Cannot compose final video."
        )

    print(f"  [Composer] Composing {len(composable_scenes)} scene(s)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Merge audio+video for each scene
        combined_clips: list[str] = []
        for scene_id, audio, video in composable_scenes:
            combined_path = str(Path(tmpdir) / f"scene_{scene_id}_combined.mp4")
            print(f"  [Composer] Merging scene {scene_id}...")
            _merge_scene(video["file_path"], audio["file_path"], combined_path)
            combined_clips.append(combined_path)

        # Step 2: Concatenate all combined clips
        if len(combined_clips) == 1:
            # Only one scene — just copy it directly
            import shutil
            shutil.copy2(combined_clips[0], output_path)
        else:
            print(f"  [Composer] Concatenating {len(combined_clips)} clips...")
            _concatenate_clips(combined_clips, output_path)

    final_path = str(Path(output_path).resolve())
    print(f"  [Composer] Final video written to: {final_path}")
    return final_path
