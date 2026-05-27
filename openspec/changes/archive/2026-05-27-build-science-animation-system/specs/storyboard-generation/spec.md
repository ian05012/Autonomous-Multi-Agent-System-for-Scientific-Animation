## ADDED Requirements

### Requirement: Generate structured storyboard from document
The system SHALL invoke the Scriptwriter Agent to convert a `DocumentContent` object into a list of `SceneSpec` objects (storyboard JSON), with a maximum of 10 scenes per article.

#### Scenario: Successful storyboard generation
- **WHEN** Scriptwriter Agent receives a valid `DocumentContent` with at least 50 words
- **THEN** it returns a list of 3–10 `SceneSpec` objects, each with non-empty `narration`, `visual_description`, and a positive `estimated_duration` in seconds

#### Scenario: Article too complex for 10 scenes
- **WHEN** article content is long enough to warrant more than 10 scenes
- **THEN** system compresses the content to fit within 10 scenes, prioritizing key concepts identified by the LLM

### Requirement: Each scene includes narration and visual description
Every `SceneSpec` MUST contain a `narration` string (spoken text for voiceover) and a `visual_description` string (instruction for the Animator Agent describing what to animate).

#### Scenario: Scene fields are populated
- **WHEN** storyboard is generated
- **THEN** every scene in the returned list has non-empty `narration` (≥10 words) and non-empty `visual_description` (≥5 words)

### Requirement: Storyboard is serializable to JSON
The storyboard MUST be serializable to a JSON array conforming to the schema: `[{scene_id, narration, visual_description, estimated_duration}]`.

#### Scenario: Storyboard JSON export
- **WHEN** storyboard generation succeeds
- **THEN** calling `json.dumps(storyboard)` produces valid JSON with all required fields present for each scene
