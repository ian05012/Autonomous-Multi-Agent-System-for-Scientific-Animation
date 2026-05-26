from manim import *

class FadeInOut(Scene):
    def construct(self):
        text = Text("Quantum Mechanics", font_size=40)
        self.play(FadeIn(text, run_time=1.0))
        self.wait(1.5)
        self.play(FadeOut(text, run_time=1.0))
        self.wait(0.3)
