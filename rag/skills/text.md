# Manim CE Best Practices — Text

## When to Use Each Class
- `Text(str)` — regular text, labels, titles; uses Pango/Cairo (no LaTeX needed)
- `MarkupText(str)` — mixed styling within one text object using HTML-like tags
- `MathTex(str)` — LaTeX math; AVOID in sandboxed rendering (requires LaTeX install)
- `Paragraph(str)` — multi-line text with alignment control

## Text Basics
```python
label = Text("Hello World", font_size=36, color=WHITE)
label.to_edge(UP)
label.move_to(ORIGIN)
```

## Common Parameters
- `font_size` — default 48; use 24–48 for most labels
- `color` — any Manim color constant or hex
- `font` — system font name: "Arial", "Courier New", "Times New Roman"
- `weight` — `NORMAL` or `BOLD`
- `slant` — `NORMAL`, `ITALIC`, or `OBLIQUE`
- `line_spacing` — multiplier for multi-line text

## MarkupText (mixed styles)
```python
t = MarkupText('<b>Bold</b> and <i>italic</i> and <span fgcolor="#FF0000">red</span>')
```

## Character Indexing
```python
text = Text("HELLO")
text[0]      # first character 'H'
text[1:3]    # characters 'EL'
self.play(text[0].animate.set_color(RED))
```

## Multi-line
```python
para = Paragraph("Line one", "Line two", "Line three", alignment="center")
```

## Positioning with Other Objects
```python
label = Text("Label", font_size=24)
label.next_to(circle, DOWN, buff=0.2)
label.to_edge(UP, buff=0.3)
```

## Animations with Text
```python
self.play(Write(text), run_time=1.5)           # handwriting effect
self.play(FadeIn(text, shift=UP), run_time=1)  # fade in with movement
self.play(FadeOut(text), run_time=0.5)
self.play(Transform(old_text, new_text), run_time=1)
```

## Critical Rule
NEVER use `MathTex`, `Tex`, or any LaTeX in this project — LaTeX compilation
requires a full TeX installation and will timeout in Docker.
Use `Text()` for everything including mathematical notation written as plain text.
