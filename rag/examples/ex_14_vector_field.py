from manim import *
import numpy as np

class VectorFieldDemo(Scene):
    def construct(self):
        def field_func(pos):
            x, y, _ = pos
            return np.array([-y, x, 0]) * 0.3
        vf = ArrowVectorField(field_func)
        self.play(Create(vf, run_time=2.0))
        self.wait(1.0)
