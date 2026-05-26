"""
tools/manim_runner.py
----------------------
Docker-based Manim rendering sandbox for the Animator Agent.

Each scene is rendered inside a short-lived Docker container using the
manimcommunity/manim image. The container mounts a temporary workspace,
runs the Manim script, and returns the output MP4.

Error categories detected from stderr:
- AttributeError / NameError  → hallucinated Manim API
- SyntaxError                 → malformed Python
- TypeError / ValueError      → wrong argument types
- TimeoutError                → render exceeded 120 seconds
"""

from __future__ import annotations

import os
import shutil
import tempfile
from enum import Enum
from pathlib import Path

import docker
from docker.errors import ContainerError, ImageNotFound

from state import VideoMeta


# ─── Configuration ────────────────────────────────────────────────────────────

MANIM_IMAGE = "manim-science-animation"   # local tag built from Dockerfile.manim
MANIM_IMAGE_FALLBACK = "manimcommunity/manim:latest"
RENDER_TIMEOUT = 120                       # seconds
VIDEO_OUTPUT_DIR = "output/video"
RENDER_RESOLUTION = os.getenv("RENDER_RESOLUTION", "720p")

RESOLUTION_FLAGS = {
    "720p":  ["-r", "1280,720"],
    "1080p": ["-r", "1920,1080"],
}


# ─── Error classification ─────────────────────────────────────────────────────

class ManimErrorType(str, Enum):
    HALLUCINATED_API = "hallucinated_api"    # AttributeError / NameError
    SYNTAX_ERROR = "syntax_error"            # SyntaxError
    TYPE_ERROR = "type_error"                # TypeError / ValueError
    TIMEOUT = "timeout"                      # render timeout
    UNKNOWN = "unknown"                      # other


def classify_error(stderr: str) -> ManimErrorType:
    """Classify a Manim render error from its stderr traceback."""
    if not stderr:
        return ManimErrorType.UNKNOWN
    if "AttributeError" in stderr or "NameError" in stderr:
        return ManimErrorType.HALLUCINATED_API
    if "SyntaxError" in stderr:
        return ManimErrorType.SYNTAX_ERROR
    if "TypeError" in stderr or "ValueError" in stderr:
        return ManimErrorType.TYPE_ERROR
    return ManimErrorType.UNKNOWN


class ManimRenderError(Exception):
    """Raised when Manim rendering fails."""
    def __init__(self, message: str, error_type: ManimErrorType, stderr: str):
        super().__init__(message)
        self.error_type = error_type
        self.stderr = stderr


class ManimRenderTimeout(ManimRenderError):
    """Raised when Manim rendering exceeds the timeout."""
    def __init__(self, stderr: str = ""):
        super().__init__(
            f"Manim render exceeded {RENDER_TIMEOUT}s timeout",
            ManimErrorType.TIMEOUT,
            stderr,
        )


# ─── Docker rendering ─────────────────────────────────────────────────────────

def _get_docker_client() -> docker.DockerClient:
    """Get a Docker client connected to the local daemon."""
    try:
        return docker.from_env()
    except Exception as exc:
        raise RuntimeError(
            f"Cannot connect to Docker daemon: {exc}\n"
            "Ensure Docker is running and accessible."
        ) from exc


def _get_manim_image() -> str:
    """Return the Manim Docker image name to use."""
    client = _get_docker_client()
    try:
        client.images.get(MANIM_IMAGE)
        return MANIM_IMAGE
    except ImageNotFound:
        return MANIM_IMAGE_FALLBACK


def render_scene(code: str, scene_id: int, class_name: str = "AnimatedScene") -> VideoMeta:
    """
    Render a Manim scene inside a Docker container.

    Args:
        code:       Python Manim script content.
        scene_id:   Scene identifier (used for output filename).
        class_name: The Manim Scene subclass name in the script.

    Returns:
        VideoMeta with file_path and duration_seconds.

    Raises:
        ManimRenderError: If rendering fails (with error type and traceback).
        ManimRenderTimeout: If rendering exceeds RENDER_TIMEOUT seconds.
    """
    os.makedirs(VIDEO_OUTPUT_DIR, exist_ok=True)
    resolution_flags = RESOLUTION_FLAGS.get(RENDER_RESOLUTION, RESOLUTION_FLAGS["720p"])
    output_filename = f"scene_{scene_id}.mp4"
    final_output_path = str(Path(VIDEO_OUTPUT_DIR) / output_filename)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write Manim script to workspace
        script_path = Path(tmpdir) / "scene.py"
        script_path.write_text(code, encoding="utf-8")

        # Build Docker command
        cmd = [
            "manim",
            "scene.py",
            class_name,
            "--media_dir", "/workspace/media",
            "--format", "mp4",
            *resolution_flags,
        ]

        client = _get_docker_client()
        image = _get_manim_image()

        try:
            container = client.containers.run(
                image=image,
                command=cmd,
                volumes={tmpdir: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                remove=True,
                detach=False,
                stdout=True,
                stderr=True,
                timeout=RENDER_TIMEOUT,
            )
            logs = container if isinstance(container, bytes) else b""

        except docker.errors.ContainerError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
            error_type = classify_error(stderr)
            raise ManimRenderError(
                f"Manim render failed (scene {scene_id}): {error_type.value}",
                error_type,
                stderr,
            )
        except Exception as exc:
            if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                raise ManimRenderTimeout()
            raise ManimRenderError(
                f"Docker error for scene {scene_id}: {exc}",
                ManimErrorType.UNKNOWN,
                str(exc),
            )

        # Find the rendered MP4 in workspace
        mp4_files = list(Path(tmpdir).rglob("*.mp4"))
        if not mp4_files:
            raise ManimRenderError(
                f"Rendering succeeded but no MP4 found for scene {scene_id}",
                ManimErrorType.UNKNOWN,
                "",
            )

        # Copy to output directory
        shutil.copy2(str(mp4_files[0]), final_output_path)

    # Measure actual video duration
    duration = _measure_video_duration(final_output_path)

    return VideoMeta(
        scene_id=scene_id,
        file_path=str(Path(final_output_path).resolve()),
        duration_seconds=duration,
    )


def _measure_video_duration(file_path: str) -> float:
    """Measure the duration of an MP4 file in seconds using ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        return round(float(result.stdout.strip()), 1)
    except Exception:
        return 0.0
