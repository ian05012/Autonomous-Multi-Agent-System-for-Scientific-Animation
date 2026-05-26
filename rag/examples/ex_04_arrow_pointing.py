from manim import *

class ArrowPointing(Scene):
    def construct(self):
        arrow = Arrow(LEFT * 2, RIGHT * 2, color=YELLOW, buff=0)
        self.play(GrowArrow(arrow, run_time=1.5))
        self.wait(0.5)
