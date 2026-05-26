# Manim Examples Directory

This directory contains 50 curated Manim CE code examples used to ground the
Animator Agent's code generation via RAG retrieval.

## Format

Each example consists of two files:
- `<name>.py` — The Manim Python script
- `<name>.txt` — A one-line description of the visual effect it produces

## Naming Convention

Files are named `ex_<number>_<short_description>.py`, e.g.:
- `ex_01_circle_grow.py` — A circle growing from center
- `ex_02_text_write.py` — Text being written letter by letter

## Guidelines for Adding Examples

1. Each example must be self-contained (import from `manim` only)
2. The class must extend `Scene` with a `construct(self)` method
3. The `.txt` annotation must describe the visual effect in plain English
4. Examples should cover a diverse range of Manim capabilities

## Covered Categories

| Category | Examples |
|---|---|
| Basic shapes | Circles, rectangles, triangles, lines, arrows |
| Text & LaTeX | Write, FadeIn text, math equations |
| Transforms | ReplacementTransform, ApplyMatrix, morph |
| Graphs & plots | NumberPlane, axes, function plots |
| Camera | Moving camera, zooming |
| Color & style | Gradients, stroke, fill |
| Animations | Grow, Shrink, Rotate, FadeIn, FadeOut |
| Complex scenes | Multi-step explanations, highlight sequences |
| Data visualization | Bar charts, pie charts |
| Physics diagrams | Vectors, force arrows |
