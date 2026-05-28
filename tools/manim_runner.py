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
RENDER_TIMEOUT = 180                       # seconds
VIDEO_OUTPUT_DIR = "output/video"
RENDER_RESOLUTION = os.getenv("RENDER_RESOLUTION", "720p")

# Named Docker volume for Manim workspace — avoids Windows NTFS bind-mount permission issues.
# Set via MANIM_WORKSPACE_VOLUME env var in docker-compose. Falls back to host bind-mount.
_MANIM_WORKSPACE_VOLUME = os.getenv("MANIM_WORKSPACE_VOLUME", "")
_HOST_PROJECT_DIR = os.getenv("HOST_PROJECT_DIR", "")

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

    # Workspace directory: under named volume (Docker-managed, no Windows NTFS perms)
    # or under /app/output/manim_tmp for local runs.
    if _MANIM_WORKSPACE_VOLUME:
        # Running inside Docker — write to the named volume mount point
        workspace_dir = Path("output/manim_workspace") / f"scene_{scene_id}"
        volume_spec = {_MANIM_WORKSPACE_VOLUME: {"bind": "/workspace", "mode": "rw"}}
        scene_subdir = f"scene_{scene_id}"
        manim_script_path = f"/workspace/{scene_subdir}/scene.py"
        manim_media_dir  = f"/workspace/{scene_subdir}/media"
        working_dir      = "/workspace"
    else:
        # Local run — use tmpdir bind-mount
        workspace_dir = Path("output/manim_tmp") / f"scene_{scene_id}"
        host_path = str(workspace_dir.resolve())
        if _HOST_PROJECT_DIR and host_path.startswith("/app/"):
            host_path = os.path.join(_HOST_PROJECT_DIR, host_path[5:])
        volume_spec    = {host_path: {"bind": "/workspace", "mode": "rw"}}
        scene_subdir   = ""
        manim_script_path = "scene.py"
        manim_media_dir   = "/workspace/media"
        working_dir       = "/workspace"

    workspace_dir.mkdir(parents=True, exist_ok=True)
    # Pre-create media dir from app container so manimuser doesn't need to create it
    (workspace_dir / "media").mkdir(parents=True, exist_ok=True)
    script_target = workspace_dir / "scene.py"
    script_target.write_text(code, encoding="utf-8")

    cmd = [
        "manim",
        manim_script_path,
        class_name,
        "--media_dir", manim_media_dir,
        "--format", "mp4",
        "--quality", "l",
        "--disable_caching",
    ]

    client = _get_docker_client()
    image = _get_manim_image()
    print(f"  [Manim] volume: {volume_spec}  script: {manim_script_path}")

    try:
        container = client.containers.run(
            image=image,
            command=cmd,
            volumes=volume_spec,
            working_dir=working_dir,
            user="root",    # ensure write access to named volume dirs
            remove=False,
            detach=True,
            stdout=True,
            stderr=True,
        )
    except Exception as exc:
        raise ManimRenderError(
            f"Docker error starting container for scene {scene_id}: {exc}",
            ManimErrorType.UNKNOWN,
            str(exc),
        )

    try:
        exit_status = container.wait(timeout=RENDER_TIMEOUT)
        logs = container.logs(stdout=True, stderr=True)
        stderr_text = logs.decode("utf-8", errors="replace") if logs else ""
        exit_code = exit_status.get("StatusCode", -1)
    except Exception:
        try:
            container.kill()
        except Exception:
            pass
        raise ManimRenderTimeout()
    finally:
        try:
            container.remove(force=True)
        except Exception:
            pass

    if exit_code != 0:
        error_type = classify_error(stderr_text)
        print(f"  [Manim] render stderr:\n{stderr_text[-2000:]}")
        raise ManimRenderError(
            f"Manim render failed (scene {scene_id}): {error_type.value}",
            error_type,
            stderr_text,
        )

    mp4_files = list(workspace_dir.rglob("*.mp4"))
    if not mp4_files:
        raise ManimRenderError(
            f"Rendering succeeded but no MP4 found for scene {scene_id}",
            ManimErrorType.UNKNOWN,
            "",
        )

    shutil.copy2(str(mp4_files[0]), final_output_path)
    shutil.rmtree(workspace_dir, ignore_errors=True)

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
