# Manim CE Best Practices — Colors

## Built-in Color Constants
Primary: `RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, PINK, WHITE, BLACK, GRAY`
Shades (A=lightest, E=darkest): `RED_A, RED_B, RED_C, RED_D, RED_E`
Special: `TEAL, GOLD, MAROON, DARK_BLUE, DARK_BROWN, LIGHT_GRAY, LIGHT_PINK`

## Applying Colors
```python
Circle(color=RED)                   # set on creation
obj.set_color(BLUE)                 # change after creation
obj.set_fill(YELLOW, opacity=0.5)   # fill color + opacity
obj.set_stroke(WHITE, width=2)      # stroke color + width
```

## Gradients
```python
obj.set_color_by_gradient(BLUE, GREEN)         # two-color gradient
obj.set_color_by_gradient(RED, YELLOW, GREEN)  # multi-color
```

## Custom Colors
```python
my_color = ManimColor("#FF6B6B")   # hex string
my_color = ManimColor.from_rgb((0.5, 0.8, 1.0))
```

## Color Manipulation
```python
color.lighter()   # brighter variant
color.darker()    # darker variant
color.invert()    # complementary color
interpolate_color(RED, BLUE, 0.5)  # midpoint between two colors
```

## Opacity
- Range: 0.0 (transparent) to 1.0 (fully opaque)
- `obj.set_opacity(0.7)`
- `FadeIn(obj)` animates from 0 to 1

## Design Best Practices
- Use shade variants (RED_B, BLUE_D) for depth and hierarchy.
- High contrast between background (usually BLACK) and foreground objects.
- Use consistent color coding: e.g., one color per concept throughout a scene.
- Gradients work best on large filled shapes.
- Consider colorblind accessibility: avoid red+green combinations alone.
