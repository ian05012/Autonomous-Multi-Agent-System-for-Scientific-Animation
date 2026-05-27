## ADDED Requirements

### Requirement: LangGraph state machine orchestrates the full pipeline
The Supervisor Agent SHALL implement a LangGraph `StateGraph` with nodes for each agent (Scriptwriter, Voiceover, Animator, SocialMedia) and edges representing the sequential flow, conditional HITL loop, and error routing.

#### Scenario: Full pipeline execution
- **WHEN** user submits a document and triggers the pipeline
- **THEN** LangGraph executes nodes in order: document_ingestion → storyboard_generation → voiceover_synthesis → manim_code_generation → animation_rendering → video_composition → hitl_review

#### Scenario: HITL revision loop
- **WHEN** user submits a revision instruction via the HITL interface
- **THEN** LangGraph routes to the appropriate agent node, regenerates the affected scene, then proceeds to video_composition → hitl_review again

### Requirement: Pipeline state persisted after each node
After each agent node completes, the current `PipelineState` SHALL be serialized to `output/state.json` to enable recovery from failures.

#### Scenario: State persistence
- **WHEN** Scriptwriter Agent node completes
- **THEN** `output/state.json` is written with the current `PipelineState` including the populated `storyboard` field

#### Scenario: State recovery on restart
- **WHEN** `output/state.json` exists and user restarts the application
- **THEN** the Streamlit interface loads the saved state and displays the last completed stage

### Requirement: Supervisor handles agent errors gracefully
When any agent node raises an exception, the Supervisor SHALL catch it, append to `PipelineState.error_log`, and route to the HITL interface rather than crashing the pipeline.

#### Scenario: Agent error recovery
- **WHEN** any agent node raises an unhandled exception
- **THEN** the exception message is appended to `error_log`, and the graph transitions to the `hitl_review` node to surface the failure to the user
