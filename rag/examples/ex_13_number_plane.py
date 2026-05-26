from manim import *

class NumberPlaneDemo(Scene):
    def construct(self):
        plane = NumberPlane()
        dot = Dot(color=RED, point=plane.c2p(2, 1))
        label = MathTex(r"(2,1)").next_to(dot, UR, buff=0.1)
        self.play(Create(plane, run_time=1.5))
        self.play(FadeIn(dot), Write(label))
        self.wait(1.0)
