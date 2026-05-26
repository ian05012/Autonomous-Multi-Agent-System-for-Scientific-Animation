from manim import *

class RotatingObject(Scene):
    def construct(self):
        triangle = Triangle(color=ORANGE)
        self.play(FadeIn(triangle))
        self.play(Rotate(triangle, angle=PI, run_time=2.0))
        self.wait(0.5)
