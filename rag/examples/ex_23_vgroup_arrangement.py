from manim import *

class VGroupArrangement(Scene):
    def construct(self):
        circles = VGroup(*[Circle(radius=0.4, color=c) for c in [RED, GREEN, BLUE, YELLOW]])
        circles.arrange(RIGHT, buff=0.3)
        self.play(FadeIn(circles, shift=UP, run_time=1.5))
        self.wait(0.5)
