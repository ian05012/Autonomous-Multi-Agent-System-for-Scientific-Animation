"""
agents/social_media.py
-----------------------
Social Media Agent — LangGraph node that generates platform content
and uploads the final video to YouTube and Instagram.

Upload failures are best-effort: the pipeline does not fail if uploads fail.
"""

from __future__ import annotations

import json
import os
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from tools.llm_factory import make_llm

from state import PipelineState, save_state


def _llm_model() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o")


# ─── Content generation ───────────────────────────────────────────────────────

YOUTUBE_SYSTEM = """You are a YouTube content strategist for educational science videos.
Generate metadata optimized for educational science content.

Return JSON only:
{
  "title": "<string, ≤100 chars, engaging and descriptive>",
  "description": "<string, ≤5000 chars, includes summary, key concepts, and timestamps>",
  "tags": ["<tag1>", "<tag2>", ... at least 5 tags]
}"""

INSTAGRAM_SYSTEM = """You are an Instagram content strategist for science education accounts.
Generate an Instagram Reel caption with hashtags.

Return JSON only:
{
  "caption": "<string, ≤2200 chars total including hashtags, engaging hook + content summary + 10-30 hashtags>"
}"""


def _generate_youtube_metadata(storyboard: list, llm: ChatOpenAI) -> dict:
    """Generate YouTube title, description, and tags from storyboard."""
    storyboard_text = "\n".join(
        f"Scene {s['scene_id']}: {s['narration']}" for s in storyboard
    )
    response = llm.invoke([
        SystemMessage(content=YOUTUBE_SYSTEM),
        HumanMessage(content=f"Storyboard:\n{storyboard_text[:3000]}"),
    ])
    raw = response.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    return json.loads(raw)


def _generate_instagram_caption(storyboard: list, llm: ChatOpenAI) -> dict:
    """Generate Instagram caption with hashtags from storyboard."""
    storyboard_text = "\n".join(
        f"Scene {s['scene_id']}: {s['narration']}" for s in storyboard
    )
    response = llm.invoke([
        SystemMessage(content=INSTAGRAM_SYSTEM),
        HumanMessage(content=f"Storyboard:\n{storyboard_text[:3000]}"),
    ])
    raw = response.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    return json.loads(raw)


# ─── Agent node ───────────────────────────────────────────────────────────────

def social_media_node(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Social Media Agent.

    1. Generates YouTube and Instagram content using GPT-4o
    2. Uploads to YouTube (with retry)
    3. Uploads to Instagram (best-effort)
    4. Returns URLs in state (None if upload failed)
    """
    from tools.social_uploader import upload_to_youtube, upload_to_instagram

    storyboard = state.get("storyboard", [])
    final_video_path = state.get("final_video_path")

    if not final_video_path:
        error_msg = "SocialMedia: No final video path in state. Run composition first."
        return {"error_log": [error_msg]}

    llm = make_llm(temperature=0.5)

    # Generate content
    youtube_url = None
    instagram_url = None
    errors = []

    try:
        print("  [SocialMedia] Generating YouTube metadata...")
        yt_meta = _generate_youtube_metadata(storyboard, llm)

        print("  [SocialMedia] Uploading to YouTube...")
        youtube_url = upload_to_youtube(
            video_path=final_video_path,
            title=yt_meta.get("title", "Science Animation")[:100],
            description=yt_meta.get("description", "")[:5000],
            tags=yt_meta.get("tags", []),
        )
    except Exception as exc:
        error_msg = f"SocialMedia: YouTube upload failed — {exc}"
        errors.append(error_msg)
        print(f"  [SocialMedia] {error_msg}")

    try:
        print("  [SocialMedia] Generating Instagram caption...")
        ig_meta = _generate_instagram_caption(storyboard, llm)

        print("  [SocialMedia] Uploading to Instagram...")
        instagram_url = upload_to_instagram(
            video_path=final_video_path,
            caption=ig_meta.get("caption", "")[:2200],
        )
    except Exception as exc:
        error_msg = f"SocialMedia: Instagram upload failed — {exc}"
        errors.append(error_msg)
        print(f"  [SocialMedia] {error_msg}")

    updates: dict[str, Any] = {
        "youtube_url": youtube_url,
        "instagram_url": instagram_url,
    }
    if errors:
        updates["error_log"] = errors

    updated_state = {**state, **updates}
    save_state(updated_state)  # type: ignore[arg-type]

    return updates
