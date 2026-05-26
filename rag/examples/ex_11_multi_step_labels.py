from manim import *

class MultiStepLabels(Scene):
    def construct(self):
        steps = VGroup(*[Text(f"Step {i+1}: ...", font_size=28) for i in range(3)])
        steps.arrange(DOWN, buff=0.4)
        for step in steps:
            self.play(FadeIn(step, run_time=0.6))
        self.wait(1.0)
