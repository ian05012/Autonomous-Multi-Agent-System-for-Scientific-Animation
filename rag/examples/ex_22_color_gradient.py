from manim import *

class ColorGradient(Scene):
    def construct(self):
        rect = Rectangle(width=8, height=1)
        rect.set_color_by_gradient(BLUE, GREEN, YELLOW, RED)
        self.play(DrawBorderThenFill(rect, run_time=2.0))
        self.wait(0.5)
