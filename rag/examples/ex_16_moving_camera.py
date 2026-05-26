from manim import *

class MovingCameraDemo(MovingCameraScene):
    def construct(self):
        circle = Circle(radius=0.5, color=BLUE)
        self.add(circle)
        self.play(self.camera.frame.animate.scale(0.5).move_to(circle), run_time=2.0)
        self.wait(0.5)
