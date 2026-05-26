from manim import *

class LatexEquation(Scene):
    def construct(self):
        eq = MathTex(r"E = mc^2", font_size=72)
        self.play(Write(eq, run_time=2.0))
        self.wait(1.0)
