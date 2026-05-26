from manim import *

class ForceDiagram(Scene):
    def construct(self):
        box = Square(side_length=1, color=GRAY, fill_color=GRAY, fill_opacity=0.5)
        gravity = Arrow(box.get_bottom(), box.get_bottom() + DOWN*1.5, color=RED, buff=0)
        label = Text("mg", font_size=24, color=RED).next_to(gravity, RIGHT)
        self.play(FadeIn(box, run_time=0.5))
        self.play(GrowArrow(gravity, run_time=1.0), Write(label, run_time=1.0))
        self.wait(1.0)
