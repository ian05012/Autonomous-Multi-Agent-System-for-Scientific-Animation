"""
agents/supervisor.py
---------------------
Supervisor Agent — the LangGraph StateGraph that orchestrates the full
Science Animation pipeline.

Graph flow:
  document_ingestion
       ↓
  storyboard_generation  (Scriptwriter Agent)
       ↓
  voiceover_synthesis    (Voiceover Agent)
       ↓
  animation_rendering    (Animator Agent)
       ↓
  video_composition      (FFMPEG)
       ↓
  hitl_review            ← waits for human input
       ↓
  [revision submitted] → revision_router → [targeted agent] → video_composition
  [approved]           → social_media

All agent errors are caught, appended to error_log, and routed to hitl_review.
State is persisted to disk after each node completes.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from tools.llm_factory import make_llm

from state import (
    PipelineState,
    RevisionTarget,
    load_state,
    save_state,
    make_initial_state,
)
from agents.scriptwriter import scriptwriter_node
from agents.voiceover import voiceover_node
from agents.animator import animator_node
from agents.social_media import social_media_node
from tools.ffmpeg_composer import compose_video


# ─── Configuration ────────────────────────────────────────────────────────────

def _llm_model() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o")


# ─── Node wrappers with error handling ────────────────────────────────────────

def _safe_node(node_fn, node_name: str):
    """Wrap a node function with global error handling."""
    def wrapped(state: PipelineState) -> dict[str, Any]:
        try:
            return node_fn(state)
        except Exception as exc:
            error_msg = f"{node_name}: Unhandled error — {exc}"
            print(f"  [Supervisor] ERROR in {node_name}: {exc}")
            return {"error_log": [error_msg]}
    return wrapped


# ─── FFMPEG composition node ──────────────────────────────────────────────────

def composition_node(state: PipelineState) -> dict[str, Any]:
    """LangGraph node: FFMPEG video composition with optional subtitles."""
    import os as _os
    from tools.subtitle_generator import generate_srt, SUBTITLE_ENABLED
    from tools.progress import update as _prog

    try:
        _prog(87, "Composer", "Preparing subtitles...")
        subtitle_path = None
        if SUBTITLE_ENABLED and state.get("storyboard") and state.get("audio_files"):
            srt_path = "output/subtitles.srt"
            try:
                subtitle_path = generate_srt(
                    storyboard=state["storyboard"],
                    audio_files=state["audio_files"],
                    output_path=srt_path,
                )
            except Exception as exc:
                print(f"  [Subtitles] WARNING: Subtitle generation failed ({exc}), skipping.")

        _prog(93, "Composer", "Composing final video...")
        final_path = compose_video(
            audio_files=state.get("audio_files", []),
            video_clips=state.get("video_clips", []),
            subtitle_path=subtitle_path,
        )
        from tools.progress import finish as _finish
        _finish("Video ready!")
        updated = {**state, "final_video_path": final_path}
        save_state(updated)  # type: ignore[arg-type]
        return {"final_video_path": final_path}
    except Exception as exc:
        error_msg = f"Composition: {exc}"
        return {"error_log": [error_msg]}


# ─── HITL review node ─────────────────────────────────────────────────────────

def hitl_review_node(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Human-in-the-Loop review gate.

    In the LangGraph graph, this node simply persists state and signals
    that the pipeline is paused waiting for user input. The Streamlit
    interface reads the saved state and presents the review UI.

    The graph's conditional edge determines whether to continue to
    social_media (approved) or loop back through revision_router.
    """
    updated_state = {**state, "iteration": state.get("iteration", 0) + 1}
    save_state(updated_state)  # type: ignore[arg-type]
    print(f"  [Supervisor] Reached HITL review (iteration {updated_state['iteration']})")
    return {"iteration": updated_state["iteration"]}


# ─── Revision router node ─────────────────────────────────────────────────────

REVISION_ROUTER_SYSTEM = """You are a pipeline router. Given a user's revision instruction 
and a storyboard, identify which scene and which agent needs to act.

Return JSON only, no explanation:
{
  "scene_id": <integer, 1-indexed>,
  "agent": "<scriptwriter|voiceover|animator>",
  "confidence": "<high|low>"
}

Rules:
- scriptwriter: changes to the narration text or story content
- voiceover: changes to the voice speed, tone, or re-reading of narration  
- animator: changes to the visual animation (colors, shapes, speed, effects)
- If scene is ambiguous, pick the most likely one and set confidence=low
"""


def revision_router_node(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Route HITL revision instruction to the correct agent and scene.

    Uses GPT-4o to classify the user's natural-language instruction into
    {scene_id, agent, confidence}.
    """
    import json
    revision = state.get("hitl_revision", "")
    storyboard = state.get("storyboard", [])

    if not revision:
        return {"revision_target": None}

    storyboard_summary = "\n".join(
        f"Scene {s['scene_id']}: {s['narration'][:80]}... | Visual: {s['visual_description'][:60]}..."
        for s in storyboard
    )

    llm = make_llm(temperature=0)
    response = llm.invoke([
        SystemMessage(content=REVISION_ROUTER_SYSTEM),
        HumanMessage(
            content=f"User instruction: {revision}\n\nStoryboard:\n{storyboard_summary}"
        ),
    ])

    try:
        raw = response.content.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])
        routing = json.loads(raw)
        target = RevisionTarget(
            scene_id=int(routing["scene_id"]),
            agent=routing["agent"],
            confidence=routing.get("confidence", "high"),
        )
        print(f"  [Router] Routing revision to: scene {target['scene_id']}, agent={target['agent']}")
    except Exception as exc:
        # Default to animator on scene 1 if routing fails
        target = RevisionTarget(scene_id=1, agent="animator", confidence="low")
        print(f"  [Router] Routing failed ({exc}), defaulting to scene 1 animator")

    return {"revision_target": target}


# ─── Social media node ────────────────────────────────────────────────────────
# (delegates to agents/social_media.py)


# ─── Conditional edges ────────────────────────────────────────────────────────

def route_after_hitl(state: PipelineState) -> Literal["revision_router", "social_media", "end"]:
    """
    Conditional edge from hitl_review.
    - If hitl_revision is set → revision_router
    - If no revision and no error → social_media
    - Otherwise → end
    """
    if state.get("hitl_revision"):
        return "revision_router"
    if state.get("final_video_path"):
        return "social_media"
    return "end"


def route_after_revision(
    state: PipelineState,
) -> Literal["scriptwriter_node", "voiceover_node", "animator_node"]:
    """Route to the correct agent after revision routing."""
    target = state.get("revision_target")
    if target is None:
        return "animator_node"  # fallback
    agent = target.get("agent", "animator")
    if agent == "scriptwriter":
        return "scriptwriter_node"
    elif agent == "voiceover":
        return "voiceover_node"
    else:
        return "animator_node"


# ─── Graph construction ───────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct the LangGraph StateGraph for the full pipeline.

    Node sequence:
        scriptwriter_node → voiceover_node → animator_node
        → composition_node → hitl_review_node
        → [revision_router → targeted agent → composition_node]
        → social_media_node → END
    """
    graph = StateGraph(PipelineState)

    # Add all nodes
    graph.add_node("scriptwriter_node", _safe_node(scriptwriter_node, "Scriptwriter"))
    graph.add_node("voiceover_node", _safe_node(voiceover_node, "Voiceover"))
    graph.add_node("animator_node", _safe_node(animator_node, "Animator"))
    graph.add_node("composition_node", _safe_node(composition_node, "Composition"))
    graph.add_node("hitl_review_node", hitl_review_node)
    graph.add_node("revision_router", _safe_node(revision_router_node, "RevisionRouter"))
    graph.add_node("social_media_node", _safe_node(social_media_node, "SocialMedia"))

    # Main pipeline edges
    graph.set_entry_point("scriptwriter_node")
    graph.add_edge("scriptwriter_node", "voiceover_node")
    graph.add_edge("voiceover_node", "animator_node")
    graph.add_edge("animator_node", "composition_node")
    graph.add_edge("composition_node", "hitl_review_node")

    # HITL conditional routing
    graph.add_conditional_edges(
        "hitl_review_node",
        route_after_hitl,
        {
            "revision_router": "revision_router",
            "social_media": "social_media_node",
            "end": END,
        },
    )

    # Revision routing to specific agent
    graph.add_conditional_edges(
        "revision_router",
        route_after_revision,
        {
            "scriptwriter_node": "scriptwriter_node",
            "voiceover_node": "voiceover_node",
            "animator_node": "animator_node",
        },
    )

    # After partial revision → recompose → HITL again
    # (scriptwriter/voiceover also loop through animator for dependent updates)
    graph.add_edge("social_media_node", END)

    return graph


def compile_pipeline():
    """Compile and return the runnable LangGraph pipeline."""
    graph = build_graph()
    return graph.compile()


# ─── Entry point ─────────────────────────────────────────────────────────────

def run_pipeline(
    input_text: str,
    source_type: str = "text",
    input_path: str | None = None,
) -> PipelineState:
    """
    Run the full pipeline from document input to HITL review.

    Args:
        input_text:  Raw text (for source_type="text") or file path/URL.
        source_type: "text" | "pdf" | "url"
        input_path:  File path (pdf) or URL (url). Overrides input_text for routing.

    Returns:
        Final PipelineState after the graph completes.
    """
    from state import make_initial_state
    from tools.progress import reset as _reset, update as _prog

    _reset()
    _prog(2, "Starting", "Initialising pipeline...")

    initial_state = make_initial_state(input_text, source_type, input_path)  # type: ignore[arg-type]
    pipeline = compile_pipeline()

    print("\n[Supervisor] Starting pipeline...")
    final_state = pipeline.invoke(initial_state)
    print("[Supervisor] Pipeline complete.")

    return final_state
