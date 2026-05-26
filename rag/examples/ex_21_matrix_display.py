from manim import *

class MatrixDisplay(Scene):
    def construct(self):
        mat = Matrix([[1, 2], [3, 4]], v_buff=1.2, h_buff=1.5)
        self.play(Write(mat, run_time=2.0))
        self.wait(1.0)
