from manim import *
import numpy as np

class WaveFunction(Scene):
    def construct(self):
        axes = Axes(x_range=[0, 4*PI, PI], y_range=[-1.5, 1.5])
        wave = axes.plot(lambda x: np.sin(x), color=BLUE)
        self.play(Create(axes, run_time=1.0))
        self.play(Create(wave, run_time=2.0))
        self.wait(0.5)
