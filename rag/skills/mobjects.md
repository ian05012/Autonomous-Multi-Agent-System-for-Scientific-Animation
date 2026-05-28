# Manim CE Best Practices — Mobjects

## Hierarchy
- `Mobject` → base class
- `VMobject` → vector shapes (Circle, Square, Arrow, Line, Text, MathTex, Axes)
- `VGroup` → container for multiple VMobjects (prefer over plain `Group`)
- `ImageMobject` — avoid in sandboxed rendering (no external files)

## Positioning Methods
- `obj.move_to(point)` — absolute position
- `obj.shift(direction * amount)` — relative move
- `obj.next_to(other, direction, buff=0.2)` — place relative to another object
- `obj.to_edge(edge)` — align to screen edge
- `obj.to_corner(corner)` — align to screen corner
- Edge constants: `UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR`

## Sizing
- `obj.scale(factor)` — scale uniformly
- `obj.set_width(w)` / `obj.set_height(h)` — set absolute size

## VGroup Patterns
```python
group = VGroup(obj1, obj2, obj3)
group.arrange(RIGHT, buff=0.3)   # lay out in a row
group.arrange(DOWN, buff=0.2)    # lay out in a column
group.move_to(ORIGIN)
```

## Method Chaining
Most methods return `self`, so chain them:
```python
Circle(radius=1).set_color(BLUE).shift(LEFT * 2).scale(1.5)
```

## Copying
- Use `.copy()` to duplicate without affecting the original.
- `TransformFromCopy(src, dst)` animates a copy transforming into destination.

## Submobjects
- Iterate over `obj.submobjects` for batch operations.
- Access by index: `vgroup[0]`, `vgroup[1:]`

## Best Practices
- Prefer `VGroup` over `Group` for vector objects.
- Use `SurroundingRectangle(obj)` to highlight.
- Use `Brace(obj, direction)` for labeling dimensions.
- Keep total mobject count ≤ 8 for fast rendering.
