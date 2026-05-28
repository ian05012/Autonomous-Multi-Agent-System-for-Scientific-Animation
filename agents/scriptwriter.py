"""
agents/scriptwriter.py
-----------------------
Scriptwriter Agent — LangGraph node that converts DocumentContent into
a structured storyboard JSON.

The agent uses GPT-4o to extract key educational concepts from the input
document and structure them as a sequence of SceneSpecs, each containing
narration text and a visual animation description.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from tools.llm_factory import make_llm

from state import PipelineState, SceneSpec, save_state


# ─── Configuration ────────────────────────────────────────────────────────────

def _llm_model() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o")
MAX_SCENES = 10
MIN_SCENES = 3


# ─── Prompts ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a world-class educational science communicator specializing in 
creating animated video scripts in the style of 3Blue1Brown.

Your task is to convert a science article into a structured storyboard for an animated 
educational video. You must identify the key concepts, structure them as a compelling 
narrative, and describe both what should be SAID (narration) and what should be SHOWN 
(animation) for each scene.

RULES:
1. Generate between {min_scenes} and {max_scenes} scenes total.
2. Each scene must have:
   - narration: The exact spoken text (at least 10 words). Natural, conversational, educational.
   - visual_description: A clear, specific description of what to animate (at least 5 words).
     Focus on concrete visual elements: shapes, colors, movements, equations, diagrams.
   - estimated_duration: Estimated seconds for the narration (typically 8-15 seconds per scene).
3. The scenes must tell a coherent educational story with a clear arc:
   - Opening: Hook the viewer with the core question or phenomenon
   - Middle: Build understanding step by step
   - Closing: Synthesize insights and leave the viewer with a lasting takeaway
4. Keep narration concise and precise. Avoid filler words.
5. Visual descriptions should reference specific Manim-compatible elements:
   shapes (Circle, Square, Arrow), text (Text, MathTex), graphs (Axes, NumberLine),
   transforms (Transform, FadeIn, FadeOut), etc.
6. If the article is too complex for {max_scenes} scenes, prioritize the most 
   important educational insights.

Return ONLY a valid JSON array. No markdown, no explanation. Format:
[
  {{
    "scene_id": 1,
    "narration": "...",
    "visual_description": "...",
    "estimated_duration": 12
  }},
  ...
]"""

HUMAN_PROMPT = """Convert the following science article into an educational animation storyboard:

TITLE: {title}

ARTICLE:
{body}"""


# ─── Agent node ───────────────────────────────────────────────────────────────

def scriptwriter_node(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Scriptwriter Agent.

    Reads the ingested document text from PipelineState and generates
    a storyboard as a list of SceneSpecs.

    Returns a partial state update with 'storyboard' populated.
    """
    from tools.document_parser import parse_text, parse_pdf, parse_url, DocumentContent

    # 1. Parse the document based on source type
    source_type = state["source_type"]
    try:
        if source_type == "text":
            doc = parse_text(state["input_text"])
        elif source_type == "pdf":
            doc = parse_pdf(state.get("input_path") or state["input_text"])
        elif source_type == "url":
            doc = parse_url(state.get("input_path") or state["input_text"])
        else:
            raise ValueError(f"Unknown source_type: {source_type}")
    except Exception as exc:
        error_msg = f"Scriptwriter: Document ingestion failed — {exc}"
        save_state({**state, "error_log": state.get("error_log", []) + [error_msg]})
        raise RuntimeError(error_msg) from exc

    # 2. Call LLM to generate storyboard
    from tools.progress import update as _prog
    _prog(5, "Scriptwriter", "Generating storyboard from article...")
    llm = make_llm(temperature=0.3)

    system_msg = SystemMessage(
        content=SYSTEM_PROMPT.format(min_scenes=MIN_SCENES, max_scenes=MAX_SCENES)
    )
    human_msg = HumanMessage(
        content=HUMAN_PROMPT.format(title=doc["title"], body=doc["body"][:8000])
    )

    # Retry up to 3 times on 429 rate-limit errors
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            response = llm.invoke([system_msg, human_msg])
            raw_json = response.content.strip()

            # Strip markdown code blocks if present
            if raw_json.startswith("```"):
                lines = raw_json.split("\n")
                raw_json = "\n".join(lines[1:-1]) if lines[-1] == "```" else "\n".join(lines[1:])

            scenes_data: list[dict] = json.loads(raw_json)
            break  # success
        except json.JSONDecodeError as exc:
            error_msg = f"Scriptwriter: Failed to parse LLM JSON output — {exc}"
            raise RuntimeError(error_msg) from exc
        except Exception as exc:
            last_exc = exc
            # Retry on rate-limit (429)
            if "429" in str(exc) and attempt < 2:
                wait = 35 * (attempt + 1)
                print(f"  [Scriptwriter] Rate-limited (429), retrying in {wait}s...")
                time.sleep(wait)
                continue
            error_msg = f"Scriptwriter: LLM call failed — {exc}"
            raise RuntimeError(error_msg) from exc
    else:
        raise RuntimeError(f"Scriptwriter: LLM call failed after retries — {last_exc}")

    # 3. Validate and normalize scenes
    storyboard: list[SceneSpec] = []
    for i, scene_data in enumerate(scenes_data[:MAX_SCENES]):
        narration = scene_data.get("narration", "").strip()
        visual_desc = scene_data.get("visual_description", "").strip()
        estimated_duration = float(scene_data.get("estimated_duration", 10.0))

        # Validate per spec
        narration_words = len(narration.split())
        visual_words = len(visual_desc.split())

        if narration_words < 10:
            padding = "This scene visually explores the concept through animated elements step by step."
            narration = narration + " " + padding
        if visual_words < 5:
            visual_desc = visual_desc + " Show the key concept with animated elements."

        scene: SceneSpec = {
            "scene_id": i + 1,
            "narration": narration,
            "visual_description": visual_desc,
            "estimated_duration": max(5.0, estimated_duration),
            "status": "pending",
        }
        storyboard.append(scene)

    if len(storyboard) < MIN_SCENES:
        raise RuntimeError(
            f"Scriptwriter: Generated only {len(storyboard)} scenes "
            f"(minimum {MIN_SCENES} required)."
        )

    _prog(15, "Scriptwriter", f"Storyboard ready — {len(storyboard)} scenes")

    # 4. Persist state and return update
    updated_state = {**state, "storyboard": storyboard}
    save_state(updated_state)  # type: ignore[arg-type]

    return {"storyboard": storyboard}
