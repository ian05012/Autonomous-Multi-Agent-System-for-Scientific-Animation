# Manim CE Best Practices — Scenes

## Core Structure
```python
from manim import *

class AnimatedScene(Scene):
    def construct(self):
        # All animation logic here
        pass
```

## Key Scene Methods
- `self.add(obj)` — add mobject instantly (no animation)
- `self.remove(obj)` — remove instantly
- `self.clear()` — remove all mobjects
- `self.play(*animations, run_time=1)` — play animations
- `self.wait(t=1)` — pause for t seconds

## Timing Rules
- Every `self.play()` must have explicit `run_time=X`.
- `self.wait(t)` counts toward total duration.
- Sum of all run_time + wait values = target_duration exactly.

## Scene Setup Pattern
```python
def construct(self):
    # Create objects
    title = Text("My Title", font_size=36).to_edge(UP)
    circle = Circle(radius=1, color=BLUE)
    
    # Animate sequentially
    self.play(Write(title), run_time=1.0)
    self.play(Create(circle), run_time=1.5)
    self.wait(0.5)
    self.play(FadeOut(title, circle), run_time=1.0)
```

## Camera
- Default scene: fixed 2D camera
- `MovingCameraScene` — for camera zoom/pan
- `ThreeDScene` — for 3D; avoid unless required (slow to render)

## Performance Rules
- Keep each scene simple: ≤ 8 mobjects.
- Avoid LaTeX/MathTex (requires LaTeX install, causes timeout).
- Use `Text()` for all text including equations.
- No loops with many iterations; no complex math in construct().
- No external files (SVG, PNG, etc.).
