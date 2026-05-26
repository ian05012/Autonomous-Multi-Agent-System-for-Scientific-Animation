from manim import *

class TextWrite(Scene):
    def construct(self):
        text = Text("Hello, Science!", font_size=48)
        self.play(Write(text, run_time=2.0))
        self.wait(1.0)
