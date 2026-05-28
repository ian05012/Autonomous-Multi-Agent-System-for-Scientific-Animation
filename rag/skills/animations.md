# Manim CE Best Practices — Animations

## Core Rules
- Animations interpolate mobjects between states over time; play with `self.play()`.
- Use `.animate` property for chaining transforms: `self.play(obj.animate.shift(RIGHT).scale(2))`.
- Every `self.play()` MUST have an explicit `run_time=X` argument.
- Keep run_times between 0.5–2 seconds per call for natural pacing.
- Prefer `rate_func=smooth` (default) for most animations.

## Playing Multiple Animations
- Simultaneous: pass multiple animations to one `self.play()` call.
- Sequential within one call: use `Succession(anim1, anim2)`.
- `self.wait(t)` pauses; its time counts toward total duration.

## Animation Categories (Manim CE ≥ 0.18)
- **Creation**: `Create`, `Write`, `FadeIn`, `DrawBorderThenFill`, `GrowFromCenter`, `GrowArrow`
- **Removal**: `FadeOut`, `Uncreate`, `ShrinkToCenter`
- **Transform**: `Transform`, `ReplacementTransform`, `TransformFromCopy`
- **Movement**: `MoveToTarget`, `Rotate`, `Circumscribe`
- **Indication**: `Indicate`, `Flash`, `Wiggle`, `ShowCreationThenFadeOut`

## Rate Functions
- `smooth` (default) — ease in/out, best for most cases
- `linear` — constant speed, good for continuous movement
- `there_and_back` — highlights and pulses
- `rush_into` / `rush_from` — fast start or end

## Common Mistakes to Avoid
- NEVER use `ShowCreation` (removed in CE ≥ 0.18, use `Create` instead)
- NEVER use `TextMobject` or `TexMobject` (deprecated, use `Text` / `MathTex`)
- NEVER use `ApplyMethod` (deprecated, use `.animate`)
- Don't call `self.play()` with zero animations
