from manim import *

class NumberLineDemo(Scene):
    def construct(self):
        nl = NumberLine(x_range=[-5, 5, 1], include_numbers=True)
        dot = Dot(color=RED).move_to(nl.n2p(0))
        self.play(Create(nl, run_time=1.5))
        self.play(FadeIn(dot))
        self.play(dot.animate.move_to(nl.n2p(3)), run_time=1.5)
        self.wait(0.5)
