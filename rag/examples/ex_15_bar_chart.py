from manim import *

class BarChartDemo(Scene):
    def construct(self):
        chart = BarChart(
            values=[3, 6, 2, 8, 4],
            bar_names=["A", "B", "C", "D", "E"],
            y_range=[0, 10, 2],
            bar_colors=[BLUE, GREEN, RED, YELLOW, ORANGE],
        )
        self.play(Create(chart, run_time=2.0))
        self.wait(1.0)
