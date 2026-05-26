from manim import *

class RectangleHighlight(Scene):
    def construct(self):
        rect = Rectangle(width=4, height=2, color=GREEN, fill_color=GREEN, fill_opacity=0.3)
        self.play(DrawBorderThenFill(rect, run_time=2.0))
        self.wait(0.5)
