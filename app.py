"""
app.py
------
Streamlit HITL (Human-in-the-Loop) Review Interface for the
Science Animation System.

Features:
- Video preview of the composed draft
- Storyboard table (all scenes)
- Error banner for failed scenes
- Revision input (natural language instruction)
- Approve & Publish button

State is loaded from output/state.json and persisted after each action.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Optional

import streamlit as st

from state import load_state, save_state, PipelineState, make_initial_state


# ─── Page configuration ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="Science Animation Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

STATE_PATH = "output/state.json"


# ─── CSS ─────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 700; margin-bottom: 0.2rem; }
    .subtitle { color: #888; font-size: 1rem; margin-bottom: 2rem; }
    .scene-badge {
        display: inline-block;
        background: #1e3a5f;
        color: #7eb8f7;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-done { color: #4caf50; }
    .status-error { color: #f44336; }
    .status-pending { color: #ff9800; }
</style>
""", unsafe_allow_html=True)


# ─── Session state initialization ────────────────────────────────────────────

def _init_session() -> None:
    """Initialize Streamlit session state from disk or defaults."""
    if "pipeline_state" not in st.session_state:
        state = load_state(STATE_PATH)
        st.session_state.pipeline_state = state
    if "pipeline_running" not in st.session_state:
        st.session_state.pipeline_running = False
    if "status_message" not in st.session_state:
        st.session_state.status_message = ""


# ─── Sidebar: Input & Pipeline Control ────────────────────────────────────────

def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🎬 Science Animation Studio")
        st.markdown("---")

        st.markdown("### 📄 Input")
        source_type = st.selectbox(
            "Input type",
            ["text", "pdf", "url"],
            help="Choose how to provide your science article",
        )

        input_value = ""
        input_path = None

        if source_type == "text":
            input_value = st.text_area(
                "Paste your science article",
                height=200,
                placeholder="Paste a science article here (minimum 50 words)...",
                key="input_text",
            )
        elif source_type == "pdf":
            uploaded = st.file_uploader("Upload PDF", type=["pdf"])
            if uploaded:
                pdf_path = Path("output") / uploaded.name
                pdf_path.parent.mkdir(exist_ok=True)
                pdf_path.write_bytes(uploaded.read())
                input_value = str(pdf_path)
                input_path = str(pdf_path)
                st.success(f"Uploaded: {uploaded.name}")
        elif source_type == "url":
            input_value = st.text_input(
                "Article URL",
                placeholder="https://...",
                key="input_url",
            )
            input_path = input_value

        st.markdown("---")

        if st.button(
            "🚀 Generate Animation",
            type="primary",
            disabled=st.session_state.pipeline_running,
            use_container_width=True,
        ):
            if not input_value.strip():
                st.error("Please provide input content first.")
            else:
                _start_pipeline(input_value.strip(), source_type, input_path)

        if st.session_state.pipeline_running:
            st.info("⏳ Pipeline running...")
            st.spinner("Generating...")

        st.markdown("---")
        if st.button("🗑️ Clear & Start Over", use_container_width=True):
            if Path(STATE_PATH).exists():
                Path(STATE_PATH).unlink()
            st.session_state.pipeline_state = None
            st.session_state.status_message = ""
            st.rerun()


# ─── Pipeline runner (background thread) ──────────────────────────────────────

def _start_pipeline(
    input_value: str,
    source_type: str,
    input_path: Optional[str] = None,
) -> None:
    """Start the pipeline in a background thread."""
    initial_state = make_initial_state(input_value, source_type, input_path)  # type: ignore
    st.session_state.pipeline_state = initial_state
    st.session_state.pipeline_running = True
    st.session_state.status_message = "Pipeline starting..."

    def run():
        from agents.supervisor import run_pipeline
        try:
            final_state = run_pipeline(input_value, source_type, input_path)
            st.session_state.pipeline_state = final_state
            st.session_state.status_message = "✓ Generation complete! Review below."
        except Exception as exc:
            st.session_state.status_message = f"Pipeline error: {exc}"
        finally:
            st.session_state.pipeline_running = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    st.rerun()


def _start_revision(revision_text: str) -> None:
    """Submit a HITL revision and trigger partial regeneration."""
    state = st.session_state.pipeline_state
    if state is None:
        return

    updated_state = {**state, "hitl_revision": revision_text}
    save_state(updated_state)  # type: ignore
    st.session_state.pipeline_state = updated_state
    st.session_state.pipeline_running = True
    st.session_state.status_message = "Processing revision..."

    def run():
        from agents.supervisor import compile_pipeline
        try:
            pipeline = compile_pipeline()
            final_state = pipeline.invoke(updated_state)
            st.session_state.pipeline_state = final_state
            st.session_state.status_message = "✓ Revision applied!"
        except Exception as exc:
            st.session_state.status_message = f"Revision error: {exc}"
        finally:
            st.session_state.pipeline_running = False
            # Clear revision after processing
            if st.session_state.pipeline_state:
                st.session_state.pipeline_state = {
                    **st.session_state.pipeline_state,
                    "hitl_revision": None,
                    "revision_target": None,
                }

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    st.rerun()


def _approve_and_publish() -> None:
    """Approve the video and trigger social media publishing."""
    state = st.session_state.pipeline_state
    if state is None:
        return

    st.session_state.pipeline_running = True
    st.session_state.status_message = "Publishing to social media..."

    def run():
        from agents.social_media import social_media_node
        try:
            updates = social_media_node(state)
            st.session_state.pipeline_state = {**state, **updates}
            yt = updates.get("youtube_url")
            ig = updates.get("instagram_url")
            msg = "✓ Published! "
            if yt:
                msg += f"YouTube: {yt} "
            if ig:
                msg += f"Instagram: {ig}"
            st.session_state.status_message = msg
        except Exception as exc:
            st.session_state.status_message = f"Publish error: {exc}"
        finally:
            st.session_state.pipeline_running = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    st.rerun()


# ─── Main content area ────────────────────────────────────────────────────────

def _render_main() -> None:
    state: Optional[PipelineState] = st.session_state.pipeline_state

    st.markdown('<div class="main-title">🎬 Science Animation Studio</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">AI-powered educational video generation</div>', unsafe_allow_html=True)

    # Status message
    if st.session_state.status_message:
        if "error" in st.session_state.status_message.lower():
            st.error(st.session_state.status_message)
        elif "✓" in st.session_state.status_message:
            st.success(st.session_state.status_message)
        else:
            st.info(st.session_state.status_message)

    if state is None:
        st.markdown("### 👈 Enter your science article in the sidebar to get started")
        st.markdown("""
        **What this tool does:**
        1. 📝 Converts your science article into an educational storyboard
        2. 🎙️ Generates voiceover narration for each scene
        3. 🎨 Creates Manim animations synchronized with the audio
        4. 🎬 Composes everything into a final educational video
        5. 📱 Optionally publishes to YouTube and Instagram
        """)
        return

    # ── Error banner ──────────────────────────────────────────────────────────
    error_scenes = [s for s in state.get("storyboard", []) if s.get("status") == "error"]
    if error_scenes:
        error_ids = [str(s["scene_id"]) for s in error_scenes]
        error_log = state.get("error_log", [])
        with st.container():
            st.error(
                f"⚠️ **{len(error_scenes)} scene(s) failed to render:** Scene(s) {', '.join(error_ids)}\n\n"
                + ("\n".join(f"• {e}" for e in error_log[-3:]) if error_log else "")
                + "\n\nUse the revision input below to fix specific scenes."
            )

    # ── Tabs: Video | Storyboard | Errors ─────────────────────────────────────
    tab_video, tab_storyboard, tab_logs = st.tabs(["🎬 Video Preview", "📋 Storyboard", "📊 Logs"])

    with tab_video:
        final_video = state.get("final_video_path")
        if final_video and Path(final_video).exists():
            st.video(final_video)

            col1, col2 = st.columns(2)
            yt_url = state.get("youtube_url")
            ig_url = state.get("instagram_url")
            if yt_url:
                col1.success(f"✓ YouTube: [{yt_url}]({yt_url})")
            if ig_url:
                col2.success(f"✓ Instagram: [{ig_url}]({ig_url})")
        elif st.session_state.pipeline_running:
            st.info("⏳ Video is being generated...")
            st.progress(0.5)
        else:
            st.info("No video generated yet. Start the pipeline from the sidebar.")

    with tab_storyboard:
        storyboard = state.get("storyboard", [])
        if storyboard:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Scene": s["scene_id"],
                    "Status": s.get("status", "pending"),
                    "Narration": s["narration"][:100] + "..." if len(s["narration"]) > 100 else s["narration"],
                    "Visual": s["visual_description"][:80] + "..." if len(s["visual_description"]) > 80 else s["visual_description"],
                    "Duration (est.)": f"{s['estimated_duration']:.1f}s",
                }
                for s in storyboard
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Storyboard not yet generated.")

    with tab_logs:
        error_log = state.get("error_log", [])
        if error_log:
            for msg in error_log:
                st.code(msg, language=None)
        else:
            st.success("No errors logged.")

        # Debug info
        with st.expander("Pipeline State (debug)"):
            import json
            debug_state = {
                k: v for k, v in state.items()
                if k not in ("storyboard", "audio_files", "video_clips")
            }
            debug_state["storyboard_scenes"] = len(state.get("storyboard", []))
            debug_state["audio_files_count"] = len(state.get("audio_files", []))
            debug_state["video_clips_count"] = len(state.get("video_clips", []))
            st.json(debug_state)

    # ── HITL Controls ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ✏️ Revision Controls")

    final_video = state.get("final_video_path")
    if not final_video:
        st.info("Generate the video first before making revisions.")
        return

    col_revision, col_approve = st.columns([3, 1])

    with col_revision:
        revision_text = st.text_area(
            "Revision instruction (natural language)",
            placeholder='e.g. "Change the circle in scene 2 to red" or "Make the narration in scene 3 slower"',
            height=100,
            key="revision_input",
            disabled=st.session_state.pipeline_running,
        )
        if st.button(
            "🔄 Submit Revision",
            disabled=st.session_state.pipeline_running or not revision_text.strip(),
            use_container_width=True,
        ):
            _start_revision(revision_text.strip())

    with col_approve:
        st.markdown("#### ✅ Approve")
        st.markdown("Happy with the video?")
        if st.button(
            "🚀 Approve & Publish",
            type="primary",
            disabled=st.session_state.pipeline_running,
            use_container_width=True,
        ):
            _approve_and_publish()

    # Auto-refresh while pipeline is running
    if st.session_state.pipeline_running:
        import time
        time.sleep(3)
        st.rerun()


# ─── Entry point ─────────────────────────────────────────────────────────────

_init_session()
_render_sidebar()
_render_main()
