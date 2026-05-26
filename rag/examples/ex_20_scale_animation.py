from manim import *

class ScaleAnimation(Scene):
    def construct(self):
        text = Text("BIG IDEA", font_size=36, color=WHITE)
        self.play(FadeIn(text))
        self.play(text.animate.scale(2).set_color(YELLOW), run_time=1.5)
        self.wait(0.5)
