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

from langchain_core.messages import SystemMessage, HumanMessage
from tools.llm_factory import make_animator_llm

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

GENERATION_SYSTEM = """You are a world-class science animation director using Manim Community Edition (v0.18+).
Your animations are used in educational videos inspired by 3Blue1Brown: visually stunning, conceptually clear,
and narratively driven. Every scene must feel purposeful — shapes, colors, and motion all serve the idea.

═══════════════════════════════════════════════════════════
REFERENCE EXAMPLE — study this carefully before generating
═══════════════════════════════════════════════════════════
from manim import *

class AnimatedScene(Scene):
    def construct(self):
        # ── ACT 1: introduce ──────────────────────────────
        title = Text("Photosynthesis", font_size=44, color=TEAL)
        title.to_edge(UP, buff=0.4)
        self.play(FadeIn(title, shift=UP * 0.3), run_time=0.8)

        # ── ACT 2: build visual narrative ─────────────────
        sun   = Circle(radius=0.6).set_fill(YELLOW, opacity=0.8).set_stroke(ORANGE, width=2)
        plant = Rectangle(width=0.9, height=1.6, color=GREEN_D).set_fill(GREEN_D, opacity=0.7)
        arrow = Arrow(LEFT, RIGHT, color=YELLOW_B, buff=0)

        scene_group = VGroup(sun, arrow, plant).arrange(RIGHT, buff=0.6).move_to(ORIGIN)
        self.play(GrowFromCenter(sun), run_time=0.7)
        self.play(GrowArrow(arrow), Create(plant), run_time=1.0)

        label = Text("Light  →  Energy", font_size=28, color=WHITE)
        label.next_to(scene_group, DOWN, buff=0.4)
        self.play(Write(label), run_time=0.8)

        # ValueTracker example — animating a changing quantity
        energy = ValueTracker(0)
        counter = always_redraw(
            lambda: Text(f"Energy: {energy.get_value():.0f}%", font_size=24, color=YELLOW)
                    .next_to(plant, RIGHT, buff=0.4)
        )
        self.add(counter)
        self.play(energy.animate.set_value(100), run_time=1.5)

        # ── ACT 3: emphasise key insight ──────────────────
        self.play(Indicate(plant, color=GREEN_A, scale_factor=1.15), run_time=0.6)
        self.wait(0.3)
        self.play(FadeOut(VGroup(title, scene_group, label, counter)), run_time=0.5)
# Total: 0.8+0.7+1.0+0.8+1.5+0.6+0.3+0.5 = 6.2s  ← adjust run_times to match your target
══════════════ end of reference example ══════════════

═══════════════════════════════════════════════════════════
PART 1 — HARD TECHNICAL CONSTRAINTS (violation = render failure)
═══════════════════════════════════════════════════════════

API & CLASS:
- Use ONLY `manim` package (CE ≥ 0.18). NEVER manimlib or deprecated APIs.
- Class name MUST be exactly: AnimatedScene(Scene)
- Import only from manim and Python stdlib (math, numpy).

TIMING (mandatory):
- Total of ALL self.play() run_time values + ALL self.wait() values = exactly {target_duration:.1f}s.
- EVERY self.play() call must have an explicit run_time=X.

PERFORMANCE (render must finish in < 120s):
- Max 8 mobjects on screen at any time. Remove old objects before adding new ones.
- NEVER use MathTex, Tex, or LaTeX — use Text() or MarkupText() only.
- Allowed mobjects: Text, MarkupText, Circle, Ellipse, Rectangle, Square, Triangle,
  RoundedRectangle, Arrow, Line, DashedLine, Dot, Polygon, VGroup,
  SurroundingRectangle, Underline, Brace, NumberLine, Axes, Arc, ArcBetweenPoints.
- ValueTracker + always_redraw() — USE THIS to animate changing numbers/percentages:
    v = ValueTracker(0)
    label = always_redraw(lambda: Text(f"{v.get_value():.0f}", font_size=32).move_to(ORIGIN))
    self.add(label)
    self.play(v.animate.set_value(100), run_time=2)
- NO 3D scenes, NO SVGMobject, NO ImageMobject, NO external files.
- self.wait() values must be ≤ 2.0 each.

OUTPUT: Return ONLY raw Python code. No markdown fences, no comments, no explanation.

═══════════════════════════════════════════════════════════
PART 2 — LAYOUT & POSITIONING (violation = overlapping / clipped elements)
═══════════════════════════════════════════════════════════

CANVAS: 16:9 frame. Safe zone: X ∈ [-6.5, 6.5], Y ∈ [-3.5, 3.5]. Keep ≥ 0.4 margin from edges.
ORIGIN (0,0) = screen center. UP/DOWN/LEFT/RIGHT = unit vectors.

POSITIONING RULES:
✓ Use .next_to(ref, DIRECTION, buff=0.3) — always preferred over manual coordinates.
✓ Use .to_edge(UP/DOWN/LEFT/RIGHT, buff=0.4) to anchor to screen edge.
✓ Use .move_to(ORIGIN) to center objects.
✓ Use VGroup(...).arrange(RIGHT, buff=0.5) for row layouts — guarantees no overlap.
✓ Use VGroup(...).arrange(DOWN, buff=0.4) for column layouts.
✓ Always call .arrange() BEFORE .move_to() or .shift().
✓ Title placement: title.to_edge(UP, buff=0.4) — always safe.
✓ Label placement: label.next_to(shape, DOWN, buff=0.25)

ANTI-OVERLAP (mandatory):
✗ NEVER place two objects at the same position.
✗ NEVER use raw coordinates like move_to(UP * 2.5) when .next_to() achieves the same result.
✗ For title + body: title at top edge, body at center or slightly below center.
✗ For side-by-side: left at LEFT*3, right at RIGHT*3 — or use VGroup.arrange(RIGHT).

SCALING:
- Long text: font_size ≤ 28. If group too wide: group.scale_to_fit_width(11).
- Title: font_size 40–48. Body: font_size 28–36. Labels: font_size 22–28.
- After scaling, re-check position with .to_edge() or .move_to().

═══════════════════════════════════════════════════════════
PART 3 — VISUAL QUALITY & STORYTELLING (this is what separates good from great)
═══════════════════════════════════════════════════════════

SCENE STRUCTURE — every scene should have 3 acts:
  ACT 1 (20% of time): Introduce the main visual element with a compelling entry animation.
  ACT 2 (60% of time): Develop the concept — show change, relationship, or process through motion.
  ACT 3 (20% of time): Emphasize the key insight with Indicate/Flash/color change, then exit cleanly.

ANIMATION VARIETY — use at least 3 different animation types per scene:
  ENTRY:   Write(text), Create(shape), GrowFromCenter(obj), FadeIn(obj, shift=UP)
  MOTION:  obj.animate.shift(), obj.animate.scale(), obj.animate.set_color(), Transform(a, b)
  EMPHASIS: Indicate(obj, color=YELLOW, scale_factor=1.3), Flash(obj, color=YELLOW),
            Circumscribe(obj, color=YELLOW), obj.animate.set_color(YELLOW)
  EXIT:    FadeOut(obj), ShrinkToCenter(obj), obj.animate.shift(DOWN*3)

COLOR STRATEGY — use intentional color coding:
  Background: BLACK (default)
  Primary concept: BLUE or TEAL (cool = stable, foundational)
  Secondary/contrast: YELLOW or ORANGE (warm = dynamic, changing)
  Accent/emphasis: RED_B or PINK (alert, important)
  Labels/text: WHITE (always readable)
  Use .set_color_by_gradient(BLUE, GREEN) for continuous quantities.
  WRONG: all objects WHITE. RIGHT: meaningful color per role.

MOTION PRINCIPLES:
- Nothing should appear/disappear without purpose. Every transition tells a story.
- Use simultaneous animations: self.play(Create(a), FadeIn(b, shift=LEFT), run_time=1.2)
- For processes: use sequential Succession or chained .animate calls.
- Scale up (scale_factor=1.2) to draw attention, scale down to de-emphasize.
- Arrow/Line growth: GrowArrow(arrow) or Create(line) with rate_func=linear for processes.

VISUAL METAPHORS — match visual to concept:
  Relationship/connection → Arrow between objects
  Containment/set → outer Rectangle/Circle containing inner elements
  Process/flow → sequence of arrows, objects moving along a path
  Growth/increase → GrowFromCenter, then scale up
  Comparison → side-by-side objects with labels
  Emphasis/discovery → Indicate + Flash + color change

CLEANING UP:
- When introducing a new concept, FadeOut the old group first.
- self.play(FadeOut(old_group), run_time=0.4) then build new elements.
- Never let old irrelevant objects linger while new content appears.

═══════════════════════════════════════════════════════════
PART 4 — FORBIDDEN PATTERNS (never do these)
═══════════════════════════════════════════════════════════
✗ ShowCreation → use Create
✗ TextMobject / TexMobject → use Text
✗ ApplyMethod → use .animate
✗ All objects in WHITE with no color differentiation
✗ Static scene: every object just FadeIn then FadeOut with nothing happening
✗ Text wall: displaying a long paragraph as a single Text object
✗ Placing objects without checking for overlap
✗ Using font_size > 60 for any text
✗ self.wait(t) where t > 2
"""

DESIGN_SYSTEM = """You are a Manim scene director. Given a visual description and duration,
produce a precise scene design document. This document will be handed directly to a code
generator — it must be unambiguous and executable.

OUTPUT FORMAT (use exactly these section headers):

OBJECTS:
List every visual element. Format: `- <id>: <ManimClass> | <key params> | color=<COLOR>`
Example:
- title: Text | "Newton's Laws" | color=TEAL, font_size=44
- circle: Circle | radius=1.0 | color=BLUE, fill=BLUE opacity=0.7
- arrow: Arrow | color=YELLOW
- label: Text | "Force = ma" | color=WHITE, font_size=30

LAYOUT:
One line per object. Use ONLY these positioning methods:
- <id>: to_edge(UP/DOWN/LEFT/RIGHT, buff=0.4)
- <id>: move_to(ORIGIN) / move_to(LEFT*X) / move_to(RIGHT*X) / move_to(UP*Y)
- <id>: next_to(<ref_id>, UP/DOWN/LEFT/RIGHT, buff=0.3)
- <id>: VGroup(<id1>,<id2>,...).arrange(RIGHT/DOWN, buff=0.4).move_to(ORIGIN)
All objects MUST stay within X∈[-6.5,6.5], Y∈[-3.5,3.5].

SHOT PLAN:
Number each shot. Format: `Shot N (Xs–Ys): <actions>`
Actions use: enter <id>[<AnimClass>], keep <id>, exit <id>[FadeOut], transform <id>[<anim>], emphasise <id>[Indicate/Flash]
The sum of all shot durations MUST equal {target_duration:.1f}s exactly.

RULES:
- Max 6 objects total on screen at any time.
- Every object must have an explicit enter and exit.
- No two objects may occupy the same screen region.
- Titles always at top edge. Labels always next_to their parent object.
- Prefer VGroup.arrange() over manual coordinates for 2+ sibling objects.
- Use intentional color coding: primary concept=BLUE/TEAL, dynamic change=YELLOW/ORANGE, emphasis=RED_B.
"""

DESIGN_HUMAN = """Design a Manim scene for:

VISUAL DESCRIPTION: {visual_description}
NARRATION HINT: {narration}
DURATION: {target_duration:.1f} seconds

Produce the OBJECTS, LAYOUT, and SHOT PLAN now:"""

GENERATION_HUMAN = """Implement this Manim scene exactly as designed. The design is your hard spec — follow it faithfully.

━━━ SCENE DESIGN ━━━
{scene_design}

━━━ CODE REQUIREMENTS ━━━
- Class name: AnimatedScene(Scene)
- Total duration: exactly {target_duration:.1f}s (all run_time + wait values must sum to this)
- Follow the shot plan order and timings precisely
- Follow the layout spec — use the exact positioning methods listed
- Use only Manim CE ≥ 0.18 API. Never MathTex/Tex. Text() for all text.
{rag_context}
Generate ONLY the Python code, no explanation:"""

CORRECTION_SYSTEM = """You are an expert Manim CE debugger. Fix the code so it renders successfully.

ERROR TYPE: {error_type}
CORRECTION GUIDANCE: {correction_guidance}

STRICT RULES:
- Return ONLY corrected Python code. No markdown, no explanation.
- Class name must stay: AnimatedScene
- Total duration must stay: {target_duration:.1f}s
- Use manim CE ≥ 0.18 API only. Never MathTex/Tex/LaTeX — use Text().
- NEVER ShowCreation (→ Create), TextMobject (→ Text), ApplyMethod (→ .animate).

LAYOUT FIXES (most common cause of failures):
- Safe area: X ∈ [-6.5, 6.5], Y ∈ [-3.5, 3.5]. Move out-of-bounds objects inside.
- Replace raw coordinates with: .to_edge(UP, buff=0.4) or .next_to(ref, DOWN, buff=0.3).
- Replace overlapping positions with: VGroup(...).arrange(RIGHT/DOWN, buff=0.5).
- Long text overflowing: reduce font_size to 24 or use scale_to_fit_width(11).
- If too many objects: merge into VGroup or remove less important ones.
- Title always: title.to_edge(UP, buff=0.4). Body always: body.move_to(ORIGIN) or below center.
- Use `.next_to(other, direction, buff=0.3)` instead of raw coordinate shifts.
- Use `.to_edge(UP, buff=0.5)` for titles, `.to_edge(DOWN, buff=0.5)` for captions.
- Scale down large objects: `obj.scale_to_fit_width(12)` or `.scale_to_fit_height(6)`.
- Font sizes: body ≤ 36, titles ≤ 52. Reduce font_size for long strings.
- FadeOut old objects before showing new ones in the same area.
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
        "Fix the error shown in the traceback. Ensure valid Manim CE ≥ 0.18 syntax. "
        "Also check for layout issues: objects outside safe area (X:[-6.5,6.5], Y:[-3.5,3.5]), "
        "overlapping elements, or text that is too large for the screen."
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


# ─── Stage 1: Scene Design ────────────────────────────────────────────────────

def _design_scene(scene: SceneSpec, target_duration: float, llm: ChatOpenAI) -> str:
    """Stage 1: generate a structured design document (objects, layout, shot plan)."""
    from tools.progress import log as _log
    system_msg = SystemMessage(
        content=DESIGN_SYSTEM.format(target_duration=target_duration)
    )
    human_msg = HumanMessage(
        content=DESIGN_HUMAN.format(
            visual_description=scene["visual_description"],
            narration=scene.get("narration", "")[:200],
            target_duration=target_duration,
        )
    )
    response = llm.invoke([system_msg, human_msg])
    design = response.content.strip()
    _log(f"Scene {scene['scene_id']} design ready", stage="Animator", kind="design")
    # Log the design doc (truncated) so it shows in the frontend
    for line in design.split("\n")[:20]:
        if line.strip():
            _log(f"  {line}", stage="Animator", kind="design")
    print(f"    [Animator] Scene {scene['scene_id']} design:\n{design[:300]}...")
    return design


# ─── Stage 2: Code generation ─────────────────────────────────────────────────

def _generate_code(
    scene: SceneSpec,
    target_duration: float,
    llm: ChatOpenAI,
    scene_design: str = "",
    extra_context: str = "",
) -> str:
    """Stage 2: generate Manim code from the scene design document."""
    rag_chunks = retrieve_manim_context(scene["visual_description"], k=3)
    rag_context = format_rag_context(rag_chunks) if rag_chunks else ""
    if extra_context:
        rag_context += f"\n\n{extra_context}"

    system_msg = SystemMessage(
        content=GENERATION_SYSTEM.format(target_duration=target_duration)
    )
    human_msg = HumanMessage(
        content=GENERATION_HUMAN.format(
            scene_design=scene_design or f"VISUAL: {scene['visual_description']}",
            target_duration=target_duration,
            rag_context=rag_context,
        )
    )
    response = llm.invoke([system_msg, human_msg])
    code = response.content.strip()

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
    from tools.progress import log as _log
    sid = scene["scene_id"]

    # ── Stage 1: Scene Design ──────────────────────────────────────────────────
    _log(f"Scene {sid}: designing layout & shot plan...", stage="Animator")
    scene_design = ""
    for attempt in range(3):
        try:
            scene_design = _design_scene(scene, target_duration, llm)
            break
        except Exception as exc:
            if "429" in str(exc) and attempt < 2:
                time.sleep(30 * (attempt + 1))
            else:
                _log(f"Scene {sid}: design stage failed, generating without spec", stage="Animator", kind="warn")
                break

    # ── Stage 2: Code Generation ───────────────────────────────────────────────
    _log(f"Scene {sid}: generating Manim code...", stage="Animator")
    for gen_attempt in range(3):
        try:
            code = _generate_code(scene, target_duration, llm, scene_design=scene_design)
            break
        except Exception as exc:
            if "429" in str(exc) and gen_attempt < 2:
                wait = 35 * (gen_attempt + 1)
                _log(f"Scene {sid}: rate limited, retrying in {wait}s...", stage="Animator", kind="warn")
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

    llm = make_animator_llm(temperature=0.2)

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

    from tools.progress import update as _prog, log as _log
    total_scenes = len(scenes_to_process)
    completed_count = 0
    _log(f"Rendering {total_scenes} scenes ({PARALLEL_WORKERS} parallel workers)...", stage="Animator")

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
            thread_llm = make_animator_llm(temperature=0.2)
            video_meta, _ = _render_with_correction(scene, target_duration, thread_llm)
            _log(f"Scene {scene_id} rendered ✓  ({video_meta['duration_seconds']:.1f}s)", stage="Animator", kind="success")
            print(f"  [Animator] Scene {scene_id} — done ✓")
            return scene_id, video_meta, None
        except Exception as exc:
            err = f"Animator: Scene {scene_id} permanently failed — {exc}"
            _log(f"Scene {scene_id} failed: {str(exc)[:120]}", stage="Animator", kind="error")
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
