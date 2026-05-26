from manim import *

class AxesAndPlot(Scene):
    def construct(self):
        axes = Axes(x_range=[-3, 3], y_range=[-2, 2], axis_config={"color": WHITE})
        curve = axes.plot(lambda x: x**2 - 1, color=YELLOW)
        self.play(Create(axes, run_time=1.5))
        self.play(Create(curve, run_time=1.5))
        self.wait(0.5)
