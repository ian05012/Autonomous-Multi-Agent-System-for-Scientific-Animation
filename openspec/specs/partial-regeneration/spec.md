## ADDED Requirements

### Requirement: Route revision instruction to correct agent and scene
The system SHALL use an LLM router to parse the user's natural-language revision instruction and identify: (1) the target `scene_id` (1-indexed integer), and (2) the target `agent` (`"scriptwriter"`, `"voiceover"`, or `"animator"`).

#### Scenario: Successful routing
- **WHEN** user submits instruction "Change the circle in scene 2 to red"
- **THEN** router returns `{scene_id: 2, agent: "animator"}`

#### Scenario: Ambiguous instruction
- **WHEN** instruction does not clearly reference a scene number
- **THEN** router infers the most relevant scene based on content similarity and returns its best guess with `confidence: "low"` flagged in the state

### Requirement: Regenerate only the targeted scene
The system SHALL regenerate only the scene identified by the router, re-run only the targeted agent for that scene, and recompose the final video using the new output alongside unchanged scene files.

#### Scenario: Partial regeneration
- **WHEN** routing identifies scene_id=3 and agent="animator"
- **THEN** only `output/video/scene_3.mp4` is regenerated; all other scene files remain unchanged; FFMPEG recomposes the final video

### Requirement: Updated final video displayed after regeneration
After partial regeneration and FFMPEG recomposition, the HITL interface SHALL refresh to display the updated draft video.

#### Scenario: Interface refreshes
- **WHEN** partial regeneration and recomposition complete
- **THEN** `st.video` displays the newly composed video and the previous draft is overwritten
