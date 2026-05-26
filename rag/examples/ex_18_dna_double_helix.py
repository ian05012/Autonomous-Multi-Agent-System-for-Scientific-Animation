from manim import *
import numpy as np

class DNADoubleHelix(Scene):
    def construct(self):
        strand1 = ParametricFunction(
            lambda t: np.array([np.cos(t), t/3 - 2, 0]),
            t_range=[0, 4*PI], color=BLUE
        )
        strand2 = ParametricFunction(
            lambda t: np.array([np.cos(t + PI), t/3 - 2, 0]),
            t_range=[0, 4*PI], color=RED
        )
        self.play(Create(strand1, run_time=2.0), Create(strand2, run_time=2.0))
        self.wait(0.5)
