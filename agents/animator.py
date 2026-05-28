"""
agents/animator.py
-------------------
Animator Agent — LangGraph node that:
1. Generates Manim CE Python code for each scene using GPT-4o + RAG context
2. Validates the timing constraint (sum of run_times ≈ target_duration)
3. Executes the code in a Docker sandbox via manim_runner
4. Self-corrects rendering errors using a categorized LLM correction loop
   (up to MAX_RETRIES = 5 attempts per scene)
"""

from __future__ import annotations

import ast
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from state import PipelineState, SceneSpec, AudioMeta, VideoMeta, save_state
from tools.manim_runner import (
    ManimErrorType,
    ManimRenderError,
    ManimRenderTimeout,
    render_scene,
)
from rag.retriever import retrieve_manim_context, format_rag_context


# ─── Configuration ────────────────────────────────────────────────────────────

def _llm_model() -> str:
    return os.getenv("ANIMATOR_MODEL") or os.getenv("LLM_MODEL", "gpt-4o")
MAX_RETRIES = 3
PARALLEL_WORKERS = 3   # scenes rendered concurrently
TIMING_TOLERANCE = 0.5  # seconds


# ─── Code generation prompts ──────────────────────────────────────────────────

GENERATION_SYSTEM = """You are an expert Manim Community Edition (v0.18+) Python programmer.
You generate clean, executable Manim scene code for educational animations.

CRITICAL RULES:
1. Use ONLY classes and methods from the `manim` package (Manim CE ≥ 0.18).
   NEVER use manimlib or deprecated APIs.
2. The scene class MUST be named exactly: AnimatedScene
3. The class must extend Scene with a construct(self) method.
4. TIMING CONSTRAINT: The total run_time across ALL self.play() calls MUST equal
   exactly {target_duration:.1f} seconds.
   - Every self.play() call MUST include an explicit run_time=X argument.
   - The sum of all run_time values MUST equal {target_duration:.1f}.
5. Import only from manim and standard library (math, numpy, etc.).
6. PERFORMANCE — render must complete within 120 seconds:
   - Use at most 8 mobjects total. Prefer simple shapes and transforms.
   - Use ONLY Text() for all text and equations — NEVER MathTex, Tex, or LaTeX.
     (LaTeX compilation causes timeouts.)
   - Allowed mobjects: Text, Circle, Rectangle, Square, Arrow, Line, Dot, VGroup,
     NumberPlane, Axes (no plots), SurroundingRectangle, Brace.
   - NO 3D, NO particle systems, NO SVGMobject, NO ImageMobject, NO external files.
   - You may use FadeIn, FadeOut, Write, Create, Transform, ReplacementTransform,
     GrowArrow, DrawBorderThenFill, Indicate, Flash, Succession for animations.
7. NEVER use self.wait() with values > 3.
8. Add self.wait() calls as needed, but their time is INCLUDED in total duration.
9. Return ONLY the Python code. No markdown, no explanation.

MANIM BEST PRACTICES (from manim_skill):
ANIMATIONS:
- Use `.animate` for chaining transforms: `self.play(obj.animate.shift(RIGHT).scale(2), run_time=1)`
- Prefer `rate_func=smooth` (default) for natural easing.
- Play multiple animations simultaneously: `self.play(FadeIn(a), Create(b), run_time=1)`.
- NEVER use ShowCreation (use Create), TextMobject/TexMobject (use Text), ApplyMethod (use .animate).

MOBJECTS:
- Use `VGroup` to group related objects: `group = VGroup(a, b, c); group.arrange(RIGHT, buff=0.3)`.
- Method chaining: `Circle(radius=1).set_color(BLUE).shift(LEFT * 2)`.
- Use `.next_to(other, direction, buff=0.2)` for relative positioning.
- Use `.copy()` before transforming to keep the original: `self.play(TransformFromCopy(src, dst))`.

COLORS:
- Use shade variants for depth: `BLUE_B` (light), `BLUE_D` (dark).
- Gradients: `obj.set_color_by_gradient(BLUE, GREEN)`.
- Set fill and stroke separately: `obj.set_fill(YELLOW, opacity=0.5).set_stroke(WHITE, width=2)`.
- High contrast: use bright colors on the default BLACK background.

TEXT:
- `Text("label", font_size=36, color=WHITE)` — always specify font_size explicitly.
- `MarkupText('<b>bold</b> and <span fgcolor="#FF0000">red</span>')` for mixed styles.
- `label.next_to(obj, DOWN, buff=0.2)` to place labels near shapes.
- Animate with `Write(text)` for handwriting effect or `FadeIn(text, shift=UP)`.
"""

GENERATION_HUMAN = """Create a Manim animation for this scene:

VISUAL DESCRIPTION: {visual_description}

TIMING: Total animation duration MUST be exactly {target_duration:.1f} seconds.
Sum of all run_time arguments in self.play() and self.wait() calls = {target_duration:.1f}
{rag_context}

Generate the AnimatedScene class code now:"""

CORRECTION_SYSTEM = """You are an expert Manim CE debugger.
Fix the Manim Python code based on the error below.

ERROR TYPE: {error_type}
CORRECTION GUIDANCE: {correction_guidance}

RULES:
- Return ONLY the corrected Python code. No explanation, no markdown.
- Keep the class name as AnimatedScene.
- Total run_time must still equal {target_duration:.1f} seconds.
- Use only manim CE ≥ 0.18 public API.
- NEVER use MathTex, Tex, or any LaTeX — use Text() for everything.
- Use at most 5 mobjects. Simple is better.
- NEVER use ShowCreation (use Create), TextMobject (use Text), ApplyMethod (use .animate).
- Use `.animate` for transforms, `VGroup` for grouping, `next_to()` for positioning.
"""

CORRECTION_HUMAN = """ORIGINAL CODE:
{code}

ERROR TRACEBACK:
{traceback}

Fixed code:"""

ERROR_GUIDANCE = {
    ManimErrorType.HALLUCINATED_API: (
        "The code references a Manim class or method that does not exist. "
        "Use only documented Manim CE ≥ 0.18 classes. "
        "Common alternatives: Text (not TextMobject), MathTex (not TexMobject), "
        "Create (not ShowCreation), FadeIn/FadeOut, Write, GrowFromCenter, Arrow."
    ),
    ManimErrorType.SYNTAX_ERROR: (
        "Fix the Python syntax error. Check for missing colons, parentheses, "
        "incorrect indentation, or invalid Python syntax."
    ),
    ManimErrorType.TYPE_ERROR: (
        "Fix the argument type or value. Check that all method arguments match "
        "their expected types. Ensure numeric values are float/int as required."
    ),
    ManimErrorType.TIMEOUT: (
        "The animation exceeded the render time limit. You MUST radically simplify: "
        "use at most 3 mobjects total (Text + Arrow + Circle is enough). "
        "NO loops, NO complex math, NO VGroup with many children. "
        "Each self.play() should animate ONE simple object. Keep it minimal."
    ),
    ManimErrorType.UNKNOWN: (
        "Fix the error shown in the traceback. Ensure valid Manim CE ≥ 0.18 syntax."
    ),
}


# ─── Timing validation ────────────────────────────────────────────────────────

def _sum_play_runtimes(code: str) -> float:
    """
    Static analysis: sum all run_time arguments in self.play() and self.wait() calls.
    Returns the total as a float, or -1.0 if parsing fails.
    """
    total = 0.0
    # Match run_time=X patterns
    run_time_pattern = re.compile(r"run_time\s*=\s*([0-9]*\.?[0-9]+)")
    # Match self.wait(X) patterns
    wait_pattern = re.compile(r"self\.wait\s*\(\s*([0-9]*\.?[0-9]+)\s*\)")

    for match in run_time_pattern.finditer(code):
        try:
            total += float(match.group(1))
        except ValueError:
            pass

    for match in wait_pattern.finditer(code):
        try:
            total += float(match.group(1))
        except ValueError:
            pass

    return round(total, 2)


def _validate_timing(code: str, target_duration: float) -> None:
    """Warn (not raise) if total run_time deviates by more than TIMING_TOLERANCE."""
    total = _sum_play_runtimes(code)
    if total == 0.0:
        return  # Can't validate (dynamic run_time or parsing failed)
    deviation = abs(total - target_duration)
    if deviation > TIMING_TOLERANCE:
        import warnings
        warnings.warn(
            f"Timing validation: total run_time={total:.1f}s, "
            f"target={target_duration:.1f}s, deviation={deviation:.1f}s",
            RuntimeWarning,
            stacklevel=2,
        )


# ─── Code generation ──────────────────────────────────────────────────────────

def _generate_code(
    scene: SceneSpec,
    target_duration: float,
    llm: ChatOpenAI,
    extra_context: str = "",
) -> str:
    """Call GPT-4o to generate Manim code for a scene."""
    rag_chunks = retrieve_manim_context(scene["visual_description"], k=3)
    rag_context = format_rag_context(rag_chunks) if rag_chunks else ""
    if extra_context:
        rag_context += f"\n\n{extra_context}"

    system_msg = SystemMessage(
        content=GENERATION_SYSTEM.format(target_duration=target_duration)
    )
    human_msg = HumanMessage(
        content=GENERATION_HUMAN.format(
            visual_description=scene["visual_description"],
            target_duration=target_duration,
            rag_context=rag_context,
        )
    )
    response = llm.invoke([system_msg, human_msg])
    code = response.content.strip()

    # Strip markdown code blocks if present
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

    return code


def _correct_code(
    code: str,
    traceback: str,
    error_type: ManimErrorType,
    target_duration: float,
    llm: ChatOpenAI,
) -> str:
    """Call GPT-4o to correct Manim code based on a rendering error."""
    guidance = ERROR_GUIDANCE.get(error_type, ERROR_GUIDANCE[ManimErrorType.UNKNOWN])

    # For hallucinated API errors, inject fresh RAG context
    extra = ""
    if error_type == ManimErrorType.HALLUCINATED_API:
        # Extract the failing class name from traceback
        name_match = re.search(r"(AttributeError|NameError).*'([^']+)'", traceback)
        query = name_match.group(2) if name_match else "Manim animation"
        rag_chunks = retrieve_manim_context(query, k=3)
        extra = format_rag_context(rag_chunks)

    system_msg = SystemMessage(
        content=CORRECTION_SYSTEM.format(
            error_type=error_type.value,
            correction_guidance=guidance + extra,
            target_duration=target_duration,
        )
    )
    human_msg = HumanMessage(
        content=CORRECTION_HUMAN.format(code=code, traceback=traceback)
    )
    response = llm.invoke([system_msg, human_msg])
    corrected = response.content.strip()

    if corrected.startswith("```"):
        lines = corrected.split("\n")
        corrected = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])

    return corrected


# ─── Self-correction rendering loop ──────────────────────────────────────────

def _render_with_correction(
    scene: SceneSpec,
    target_duration: float,
    llm: ChatOpenAI,
) -> tuple[VideoMeta, str]:
    """
    Generate Manim code and render with up to MAX_RETRIES self-correction attempts.

    Returns:
        (VideoMeta, final_code) on success.

    Raises:
        RuntimeError: If all MAX_RETRIES attempts fail.
    """
    # Retry code generation up to 3 times on 429 rate limit
    for gen_attempt in range(3):
        try:
            code = _generate_code(scene, target_duration, llm)
            break
        except Exception as exc:
            if "429" in str(exc) and gen_attempt < 2:
                wait = 35 * (gen_attempt + 1)
                print(f"    [Animator] Rate-limited (429) on code gen, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
    _validate_timing(code, target_duration)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"    [Animator] Scene {scene['scene_id']} — render attempt {attempt}/{MAX_RETRIES}")
        try:
            video_meta = render_scene(code, scene["scene_id"])
            print(f"    [Animator] Scene {scene['scene_id']} — rendered successfully")
            return video_meta, code
        except (ManimRenderError, ManimRenderTimeout) as exc:
            last_error = exc
            print(f"    [Animator] Render error ({exc.error_type.value}): {str(exc)[:200]}")
            if attempt < MAX_RETRIES:
                print(f"    [Animator] Correcting code...")
                code = _correct_code(
                    code,
                    exc.stderr[:3000],
                    exc.error_type,
                    target_duration,
                    llm,
                )
                _validate_timing(code, target_duration)

    raise RuntimeError(
        f"Scene {scene['scene_id']} failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}"
    )


# ─── Agent node ───────────────────────────────────────────────────────────────

def animator_node(state: PipelineState) -> dict[str, Any]:
    """
    LangGraph node: Animator Agent.

    For each scene in the storyboard:
    1. Looks up the actual audio duration from audio_files
    2. Generates Manim code via GPT-4o + RAG
    3. Renders in Docker sandbox
    4. Self-corrects on errors (up to MAX_RETRIES)
    5. Marks failed scenes as "error" in the storyboard

    Returns partial state update with 'video_clips' and updated 'storyboard'.
    """
    storyboard = state.get("storyboard", [])
    audio_files = state.get("audio_files", [])

    if not storyboard:
        raise RuntimeError("Animator: No storyboard in state. Run Scriptwriter first.")
    if not audio_files:
        raise RuntimeError("Animator: No audio files in state. Run Voiceover first.")

    # Build audio duration lookup by scene_id
    audio_by_scene = {a["scene_id"]: a for a in audio_files}

    llm = ChatOpenAI(model=_llm_model(), temperature=0.2)

    # HITL partial revision support
    revision_target = state.get("revision_target")
    scenes_to_process = storyboard
    if revision_target and revision_target.get("agent") == "animator":
        target_scene_id = revision_target["scene_id"]
        scenes_to_process = [s for s in storyboard if s["scene_id"] == target_scene_id]

    video_clips: list[VideoMeta] = [
        v for v in state.get("video_clips", [])
        if not revision_target or v["scene_id"] != revision_target.get("scene_id")
    ]
    updated_storyboard = list(storyboard)
    error_messages: list[str] = []
    _lock = threading.Lock()

    from tools.progress import update as _prog
    total_scenes = len(scenes_to_process)
    completed_count = 0

    def _process_scene(scene: SceneSpec) -> tuple[int, VideoMeta | None, str | None]:
        """Process one scene; returns (scene_id, video_meta_or_None, error_or_None)."""
        scene_id = scene["scene_id"]
        audio_meta = audio_by_scene.get(scene_id)
        if audio_meta is None:
            return scene_id, None, f"Animator: No audio found for scene {scene_id}, skipping."
        target_duration = audio_meta["duration_seconds"]
        print(f"  [Animator] Processing scene {scene_id} (target: {target_duration}s)...")
        try:
            # Each thread needs its own LLM instance (not thread-safe to share)
            thread_llm = ChatOpenAI(model=_llm_model(), temperature=0.2)
            video_meta, _ = _render_with_correction(scene, target_duration, thread_llm)
            print(f"  [Animator] Scene {scene_id} — done ✓")
            return scene_id, video_meta, None
        except Exception as exc:
            err = f"Animator: Scene {scene_id} permanently failed — {exc}"
            print(f"  [Animator] ERROR: {err}")
            return scene_id, None, err

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        futures = {pool.submit(_process_scene, s): s for s in scenes_to_process}
        for future in as_completed(futures):
            scene_id, video_meta, error = future.result()
            with _lock:
                completed_count += 1
                pct = 35 + int((completed_count / total_scenes) * 50)
                _prog(pct, "Animator", f"Rendered {completed_count}/{total_scenes} scenes")
                if video_meta is not None:
                    video_clips.append(video_meta)
                    _mark_scene_done(updated_storyboard, scene_id)
                else:
                    error_messages.append(error)
                    _mark_scene_error(updated_storyboard, scene_id)
                # Save progress after every scene
                partial_updates: dict[str, Any] = {
                    "video_clips": sorted(video_clips, key=lambda v: v["scene_id"]),
                    "storyboard": updated_storyboard,
                }
                if error_messages:
                    partial_updates["error_log"] = error_messages
                save_state({**state, **partial_updates})  # type: ignore[arg-type]

    # Sort video clips by scene_id
    video_clips.sort(key=lambda v: v["scene_id"])

    updates: dict[str, Any] = {
        "video_clips": video_clips,
        "storyboard": updated_storyboard,
    }
    if error_messages:
        updates["error_log"] = error_messages

    updated_state = {**state, **updates}
    save_state(updated_state)  # type: ignore[arg-type]

    return updates


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mark_scene_done(storyboard: list[SceneSpec], scene_id: int) -> None:
    for scene in storyboard:
        if scene["scene_id"] == scene_id:
            scene["status"] = "done"
            break


def _mark_scene_error(storyboard: list[SceneSpec], scene_id: int) -> None:
    for scene in storyboard:
        if scene["scene_id"] == scene_id:
            scene["status"] = "error"
            break
