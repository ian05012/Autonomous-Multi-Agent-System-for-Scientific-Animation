## ADDED Requirements

### Requirement: Generate Manim CE Python code for each scene
The Animator Agent SHALL generate a valid Manim CE Python script for each scene, using the scene's `visual_description` and `target_duration` (from audio) as inputs, augmented by RAG-retrieved Manim documentation snippets.

#### Scenario: Successful code generation
- **WHEN** Animator Agent receives a `SceneSpec` with `visual_description` and `target_duration`
- **THEN** it returns a Python string containing a Manim `Scene` subclass whose `construct()` method produces the described animation

#### Scenario: RAG context injected into prompt
- **WHEN** code generation prompt is assembled
- **THEN** the top-3 relevant Manim documentation chunks (by cosine similarity to `visual_description`) are included in the prompt context

### Requirement: Generated code enforces timing constraint
The generated Manim code MUST distribute animation run time such that the sum of all `run_time` arguments in `self.play()` calls equals `target_duration` ± 0.5 seconds.

#### Scenario: Timing constraint validation
- **WHEN** Manim code is generated
- **THEN** a static analysis step sums all `run_time` values in `self.play()` calls and warns if the total deviates by more than 0.5 seconds from `target_duration`

### Requirement: Animation uses only Manim CE public API
Generated code SHALL only use classes and methods from the `manim` package (Manim Community Edition ≥ 0.18). References to `manimlib` or deprecated APIs SHALL be caught and corrected.

#### Scenario: Hallucinated API detection
- **WHEN** generated code references a non-existent Manim class or method
- **THEN** the rendering step captures the `AttributeError` or `NameError` and triggers the self-correction loop
