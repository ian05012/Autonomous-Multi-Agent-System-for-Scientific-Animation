from manim import *

class DotAlongPath(Scene):
    def construct(self):
        path = Arc(radius=2, angle=2*PI)
        dot = Dot(color=RED).move_to(path.get_start())
        self.add(path)
        self.play(MoveAlongPath(dot, path, run_time=3.0))
        self.wait(0.3)
