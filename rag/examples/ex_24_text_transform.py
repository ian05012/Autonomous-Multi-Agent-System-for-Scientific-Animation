from manim import *

class TextTransform(Scene):
    def construct(self):
        t1 = Text("Before", font_size=48)
        t2 = Text("After", font_size=48, color=GREEN)
        self.play(Write(t1, run_time=1.0))
        self.play(TransformMatchingShapes(t1, t2, run_time=1.5))
        self.wait(0.5)
