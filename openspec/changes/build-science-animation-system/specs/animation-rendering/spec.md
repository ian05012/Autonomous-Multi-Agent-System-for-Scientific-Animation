## ADDED Requirements

### Requirement: Execute Manim code in Docker sandbox
The system SHALL execute Manim Python scripts inside a Docker container using the `manimcommunity/manim:latest` image, mounting a temporary workspace directory, and collecting the rendered MP4 output.

#### Scenario: Successful render
- **WHEN** Manim code is syntactically valid and produces no runtime errors within 120 seconds
- **THEN** system copies the output MP4 to `output/video/scene_{scene_id}.mp4` and returns a `VideoMeta` object with `file_path` and `duration_seconds`

#### Scenario: Container timeout
- **WHEN** rendering exceeds 120 seconds
- **THEN** container is killed, a `TimeoutError` is recorded in `error_log`, and the self-correction loop is triggered with a prompt instructing simplification of the animation

### Requirement: Self-correction loop on rendering failure
On any rendering error, the Animator Agent SHALL send the full traceback and current code to the LLM with a correction prompt, receive revised code, and re-attempt rendering — up to a maximum of 5 attempts per scene.

#### Scenario: Error corrected within retry limit
- **WHEN** rendering fails with `AttributeError` and retry count < 5
- **THEN** the traceback is sent to the LLM, revised code is generated, and rendering is re-attempted

#### Scenario: Max retries exceeded
- **WHEN** rendering has failed 5 consecutive times for a scene
- **THEN** the scene is marked with status `"error"` in `PipelineState`, an error summary is added to `error_log`, and the pipeline proceeds to HITL interface to surface the failure to the user

### Requirement: Render output at 720p resolution by default
The Docker rendering command SHALL include `-r 1280,720` (720p) unless `RENDER_RESOLUTION=1080p` environment variable is set.

#### Scenario: Default 720p render
- **WHEN** `RENDER_RESOLUTION` is unset or set to `720p`
- **THEN** rendered MP4 has height of 720 pixels

#### Scenario: 1080p render
- **WHEN** `RENDER_RESOLUTION=1080p` is set
- **THEN** rendered MP4 has height of 1080 pixels
