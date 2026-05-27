## ADDED Requirements

### Requirement: Display draft video for user review
The Streamlit HITL interface SHALL display the composed draft video using `st.video`, alongside the storyboard table showing all scenes with their narration and visual descriptions.

#### Scenario: Video preview displayed
- **WHEN** pipeline composition completes and user opens the Streamlit app
- **THEN** the draft video is displayed inline with a storyboard table showing scene_id, narration, and visual_description for each scene

### Requirement: Accept natural-language revision instructions
The interface SHALL provide a text input field where users can type revision instructions in natural language (e.g., "Make the circle in scene 3 blue and slower"). Submitting the instruction triggers the partial regeneration flow.

#### Scenario: Revision submitted
- **WHEN** user types an instruction and clicks "Submit Revision"
- **THEN** `PipelineState.hitl_revision` is set to the instruction text and the revision routing flow is triggered

#### Scenario: Approval submitted
- **WHEN** user clicks "Approve & Publish"
- **THEN** pipeline proceeds to the Social Media Agent for content generation and upload

### Requirement: Show error scenes prominently
If any scene has status `"error"` in `PipelineState`, the HITL interface SHALL display a red warning banner identifying the failed scene(s) and their error summaries.

#### Scenario: Error banner displayed
- **WHEN** one or more scenes have status `"error"`
- **THEN** a red `st.error` block appears at the top of the interface listing scene IDs and truncated error messages
