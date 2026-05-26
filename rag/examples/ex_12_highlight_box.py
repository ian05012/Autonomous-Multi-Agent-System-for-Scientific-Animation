from manim import *

class HighlightBox(Scene):
    def construct(self):
        eq = MathTex(r"F = ma", font_size=60)
        box = SurroundingRectangle(eq, color=YELLOW, buff=0.2)
        self.play(Write(eq, run_time=1.5))
        self.play(Create(box, run_time=1.0))
        self.wait(1.0)
