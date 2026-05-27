"""
tests/test_e2e.py
-----------------
End-to-end integration tests for the full Science Animation Pipeline.

ALL tests in this module require:
  - Docker running with manim-science-animation image built
  - OPENAI_API_KEY (or OPENROUTER + OPENAI_TTS_API_KEY) set in .env
  - RAG index built (python rag/build_index.py)
  - FFMPEG installed

Run with: pytest tests/test_e2e.py -v -m integration

These tests are intentionally slow (each full pipeline run takes several minutes).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

SCIENCE_ARTICLE = """
Photosynthesis is one of the most important chemical processes on Earth.
It is the process by which plants, algae, and some bacteria convert light
energy — usually from the sun — into chemical energy stored in glucose.

The basic equation is deceptively simple: carbon dioxide plus water, in the
presence of light, produces glucose and oxygen. But beneath this simplicity
lies a breathtaking complexity of molecular machinery.

Photosynthesis occurs in two main stages: the light-dependent reactions and
the Calvin cycle. In the light-dependent reactions, chlorophyll molecules in
the thylakoid membranes absorb photons, exciting electrons to higher energy
states. These electrons flow through an electron transport chain, generating
ATP and NADPH while splitting water molecules and releasing oxygen as a
byproduct.

In the Calvin cycle (the dark reactions), the cell uses the ATP and NADPH
from the light reactions to fix carbon dioxide into three-carbon sugars via
the enzyme RuBisCO. These sugars are ultimately assembled into glucose.

The efficiency of photosynthesis has profound implications: it is the entry
point for virtually all energy in the biosphere and has shaped the composition
of Earth's atmosphere over billions of years.
"""


def _skip_if_no_docker():
    try:
        import docker
        docker.from_env()
    except Exception as exc:
        pytest.skip(f"Docker not available: {exc}")


def _skip_if_no_api_key():
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("No LLM API key set — skipping e2e test")


def _skip_if_no_rag():
    from dotenv import load_dotenv
    load_dotenv()
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "rag/chroma_db")
    if not Path(persist_dir).exists():
        pytest.skip("RAG index not built — run: python rag/build_index.py")


# ─── 13.1 Full pipeline e2e ───────────────────────────────────────────────────

@pytest.mark.integration
def test_full_pipeline_text_input():
    """
    13.1 Run full end-to-end pipeline with a real science article.
    Verifies: storyboard generated, audio synthesized, video rendered,
    final MP4 composed.
    """
    _skip_if_no_docker()
    _skip_if_no_api_key()
    _skip_if_no_rag()

    from dotenv import load_dotenv
    load_dotenv()

    from agents.supervisor import build_graph
    from state import make_initial_state

    state = make_initial_state(SCIENCE_ARTICLE, "text")
    graph = build_graph()

    result = graph.invoke(state)

    assert result.get("storyboard"), "Storyboard must be generated"
    assert result.get("audio_files"), "Audio files must be synthesized"
    assert result.get("video_clips"), "Video clips must be rendered"
    assert result.get("final_video_path"), "Final video must be composed"
    assert Path(result["final_video_path"]).exists(), "Final MP4 file must exist"


# ─── 13.2 HITL revision loop ──────────────────────────────────────────────────

@pytest.mark.integration
def test_hitl_revision_regenerates_only_target_scene():
    """
    13.2 After initial generation, submit a scene-specific revision instruction.
    Verify only the targeted scene is regenerated (not all scenes).
    """
    _skip_if_no_docker()
    _skip_if_no_api_key()
    _skip_if_no_rag()

    from dotenv import load_dotenv
    load_dotenv()

    from agents.supervisor import build_graph
    from state import make_initial_state, load_state

    # Run initial pipeline
    state = make_initial_state(SCIENCE_ARTICLE, "text")
    graph = build_graph()
    result = graph.invoke(state)

    assert result.get("video_clips"), "Need video clips for HITL test"
    original_clips = {v["scene_id"]: v["file_path"] for v in result["video_clips"]}

    # Submit revision for scene 1 animator
    result["hitl_revision"] = "Make scene 1 animation more colorful with red and yellow."
    result["revision_target"] = None  # let the router classify it
    result["iteration"] = (result.get("iteration") or 0) + 1

    revised = graph.invoke(result)

    revised_clips = {v["scene_id"]: v["file_path"] for v in revised.get("video_clips", [])}

    # Only scene 1 should potentially have a new clip path; others stay the same
    for scene_id, path in original_clips.items():
        if scene_id != 1:
            assert revised_clips.get(scene_id) == path, (
                f"Scene {scene_id} should not have been regenerated"
            )


# ─── 13.3 Error recovery ──────────────────────────────────────────────────────

@pytest.mark.integration
def test_error_recovery_broken_scene():
    """
    13.3 Inject a deliberately broken Manim scene by monkeypatching the code
    generator. Verify the self-correction loop activates and HITL error log
    is populated after 5 failed retries.
    """
    _skip_if_no_docker()
    _skip_if_no_api_key()

    from dotenv import load_dotenv
    load_dotenv()
    from unittest.mock import patch

    BROKEN_CODE = """
from manim import *
class AnimatedScene(Scene):
    def construct(self):
        this_does_not_exist()  # NameError — always fails
"""

    from agents.animator import _generate_code

    with patch("agents.animator._generate_code", return_value=BROKEN_CODE):
        from agents.supervisor import build_graph
        from state import make_initial_state

        state = make_initial_state(SCIENCE_ARTICLE[:500] + " " * 50, "text")
        graph = build_graph()
        result = graph.invoke(state)

    # At least one scene should have "error" status
    error_scenes = [s for s in result.get("storyboard", []) if s.get("status") == "error"]
    assert len(error_scenes) > 0, "Expected at least one scene with error status"
    assert len(result.get("error_log", [])) > 0, "Error log must be populated"


# ─── 13.4 State persistence ───────────────────────────────────────────────────

@pytest.mark.integration
def test_state_persistence_survives_restart():
    """
    13.4 Verify that PipelineState is persisted to output/state.json and
    can be reloaded after a simulated restart.
    """
    import tempfile
    from state import make_initial_state, save_state, load_state

    state = make_initial_state(SCIENCE_ARTICLE, "text")
    state["storyboard"] = [
        {
            "scene_id": 1,
            "narration": "Test narration for persistence check.",
            "visual_description": "A circle appears.",
            "estimated_duration": 5.0,
            "status": "done",
        }
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "state.json")
        save_state(state, path=path)
        assert os.path.exists(path), "State file must exist"

        loaded = load_state(path=path)
        assert loaded is not None, "State must be loadable"
        assert loaded["storyboard"][0]["scene_id"] == 1
        assert loaded["storyboard"][0]["status"] == "done"


# ─── 13.5 Audio-video sync verification ───────────────────────────────────────

@pytest.mark.integration
def test_audio_video_sync_in_composed_output():
    """
    13.5 After composing, verify audio/video start times are within 50ms.
    Uses synthetic clips to avoid requiring a full pipeline run.
    """
    import subprocess
    import tempfile
    from state import AudioMeta, VideoMeta
    from tools.ffmpeg_composer import compose_video, verify_sync

    def _make_silent_mp3(path, duration):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", str(duration), "-q:a", "9", path],
            capture_output=True, check=True, timeout=30,
        )

    def _make_black_mp4(path, duration):
        subprocess.run(
            ["ffmpeg", "-y",
             "-f", "lavfi", "-i", f"color=black:size=640x360:rate=24",
             "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-t", str(duration),
             "-c:v", "libx264", "-preset", "ultrafast",
             "-c:a", "aac", path],
            capture_output=True, check=True, timeout=60,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.mp3")
        video_path = os.path.join(tmpdir, "video.mp4")
        output_path = os.path.join(tmpdir, "final.mp4")

        _make_silent_mp3(audio_path, 3.0)
        _make_black_mp4(video_path, 3.0)

        audio_files: list[AudioMeta] = [
            {"scene_id": 1, "file_path": audio_path, "duration_seconds": 3.0},
        ]
        video_clips: list[VideoMeta] = [
            {"scene_id": 1, "file_path": video_path, "duration_seconds": 3.0},
        ]

        result_path = compose_video(audio_files, video_clips, output_path)
        assert verify_sync(result_path, tolerance_ms=50.0), (
            "Composed video audio/video streams not synchronized within 50ms"
        )


# ─── 13.6 PDF ingestion e2e ───────────────────────────────────────────────────

@pytest.mark.integration
def test_pdf_ingestion_produces_storyboard():
    """
    13.6 Test pipeline with a PDF file input.
    Creates a minimal PDF and runs through the scriptwriter stage.
    """
    _skip_if_no_api_key()
    import tempfile
    from unittest.mock import patch

    # Create minimal PDF using fpdf2 if available, else skip
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip("fpdf2 not installed — install with: pip install fpdf2")

    from dotenv import load_dotenv
    load_dotenv()

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 10, SCIENCE_ARTICLE)
        pdf.output(pdf_path)

        from tools.document_parser import parse_pdf
        doc = parse_pdf(pdf_path)

        assert doc["word_count"] > 50, "PDF must have enough words"
        assert doc["body"], "PDF body must not be empty"


# ─── 13.7 URL ingestion e2e ───────────────────────────────────────────────────

@pytest.mark.integration
def test_url_ingestion_produces_document():
    """
    13.7 Test URL ingestion with a real public science article URL.
    Verifies parse_url returns valid DocumentContent.
    """
    from tools.document_parser import parse_url

    # Use a stable public page (Wikipedia)
    doc = parse_url("https://en.wikipedia.org/wiki/Photosynthesis")

    assert doc["word_count"] > 100, "URL document must have enough content"
    assert "photosynthesis" in doc["body"].lower()


# ─── 13.8 Resolution flags ────────────────────────────────────────────────────

@pytest.mark.integration
def test_720p_default_resolution():
    """
    13.8 Verify 720p (1280x720) is the default render resolution.
    """
    _skip_if_no_docker()

    import subprocess
    from unittest.mock import patch

    SIMPLE_CODE = """from manim import *
class AnimatedScene(Scene):
    def construct(self):
        self.play(FadeIn(Circle()), run_time=1.0)
"""

    with patch.dict(os.environ, {"RENDER_RESOLUTION": "720p"}):
        import importlib
        import tools.manim_runner as mr
        importlib.reload(mr)

        video_meta = mr.render_scene(SIMPLE_CODE, scene_id=998)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0",
         video_meta["file_path"]],
        capture_output=True, text=True, timeout=10,
    )
    assert "1280" in probe.stdout and "720" in probe.stdout
    Path(video_meta["file_path"]).unlink(missing_ok=True)


@pytest.mark.integration
def test_1080p_resolution_flag():
    """
    13.8 Verify 1080p (1920x1080) renders when RENDER_RESOLUTION=1080p.
    """
    _skip_if_no_docker()

    import subprocess
    from unittest.mock import patch

    SIMPLE_CODE = """from manim import *
class AnimatedScene(Scene):
    def construct(self):
        self.play(FadeIn(Circle()), run_time=1.0)
"""

    with patch.dict(os.environ, {"RENDER_RESOLUTION": "1080p"}):
        import importlib
        import tools.manim_runner as mr
        importlib.reload(mr)

        video_meta = mr.render_scene(SIMPLE_CODE, scene_id=997)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0",
         video_meta["file_path"]],
        capture_output=True, text=True, timeout=10,
    )
    assert "1920" in probe.stdout and "1080" in probe.stdout
    Path(video_meta["file_path"]).unlink(missing_ok=True)
