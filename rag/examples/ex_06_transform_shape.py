from manim import *

class TransformShape(Scene):
    def construct(self):
        circle = Circle(color=RED)
        square = Square(color=BLUE)
        self.play(FadeIn(circle, run_time=0.5))
        self.play(ReplacementTransform(circle, square, run_time=2.0))
        self.wait(0.5)
