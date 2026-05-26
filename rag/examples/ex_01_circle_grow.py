from manim import *

class CircleGrow(Scene):
    def construct(self):
        circle = Circle(radius=0.1, color=BLUE)
        self.play(GrowFromCenter(circle, run_time=2.0))
        self.wait(0.5)
