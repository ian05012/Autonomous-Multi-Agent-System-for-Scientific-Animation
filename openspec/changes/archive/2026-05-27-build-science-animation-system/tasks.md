## 1. Project Foundation & Environment Setup

- [x] 1.1 Initialize Python project structure: create all directories (`agents/`, `tools/`, `rag/`, `output/audio/`, `output/video/`, `output/final/`)
- [x] 1.2 Create `requirements.txt` with all dependencies (langchain, langgraph, manim, chromadb, openai, elevenlabs, pdfplumber, beautifulsoup4, requests, librosa, streamlit, docker, ffmpeg-python, python-dotenv)
- [x] 1.3 Create `.env.example` with all required environment variable keys (OPENAI_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID, TTS_PROVIDER, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, INSTAGRAM_ACCESS_TOKEN, RENDER_RESOLUTION)
- [x] 1.4 Create `Dockerfile.manim` extending `manimcommunity/manim:latest` with any additional dependencies
- [x] 1.5 Create `docker-compose.yml` for local development (Streamlit app + optional services)
- [x] 1.6 Verify Docker daemon is accessible from Python via `docker` SDK (`docker.from_env()` succeeds)

## 2. Shared State Definition

- [x] 2.1 Create `state.py` with `SceneSpec`, `AudioMeta`, `VideoMeta`, `RevisionTarget`, and `PipelineState` TypedDicts as defined in `design.md`
- [x] 2.2 Add `PipelineState` JSON serialization/deserialization helpers (`to_json()`, `from_json()`) that handle file-path-only storage for audio/video metadata
- [x] 2.3 Write unit tests for state serialization round-trip

## 3. Document Ingestion

- [x] 3.1 Create `tools/document_parser.py` with `parse_text(text: str) -> DocumentContent` function
- [x] 3.2 Implement `parse_pdf(file_path: str) -> DocumentContent` using `pdfplumber`; handle encrypted/scanned PDF error cases per spec
- [x] 3.3 Implement `parse_url(url: str) -> DocumentContent` using `requests` + `BeautifulSoup`; handle timeout, 4xx/5xx, and empty-content cases per spec
- [x] 3.4 Add input validation: raise descriptive errors for text < 50 words, unreadable PDFs, unreachable URLs
- [x] 3.5 Write unit tests for all three ingestion paths (valid + error cases)

## 4. Manim RAG Knowledge Base

- [x] 4.1 Create `rag/build_index.py` script that loads Manim CE HTML docs, splits into 512-token chunks (64-token overlap), embeds with `text-embedding-3-small`, and persists to ChromaDB collection `"manim-docs"`
- [x] 4.2 Add `--rebuild` flag to `build_index.py` that clears and rebuilds the index; skip if already exists without flag (per spec)
- [x] 4.3 Curate and create 25 annotated Manim code examples in `rag/examples/` (LLM-generated; remaining 25 to be added)
- [x] 4.4 Modify `build_index.py` to only index validated examples via `rag/validate_examples.py` (Plan C: validation before indexing)
- [x] 4.5 Create `rag/retriever.py` with `retrieve_manim_context(query: str, k: int = 3) -> list[str]` function that queries ChromaDB and returns top-k chunks
- [x] 4.6 Run `build_index.py` to build the initial index and verify ≥500 chunks indexed

## 5. Scriptwriter Agent

- [x] 5.1 Create `agents/scriptwriter.py` with the Scriptwriter Agent LangGraph node function
- [x] 5.2 Write the system prompt for storyboard generation (educational storytelling, scene segmentation, 3–10 scenes, JSON output format)
- [x] 5.3 Implement LLM call using `gpt-4o` to generate storyboard JSON from `DocumentContent`
- [x] 5.4 Add output validation: verify 3–10 scenes, each with non-empty `narration` (≥10 words) and `visual_description` (≥5 words), valid JSON (per spec)
- [x] 5.5 Handle articles that would produce >10 scenes by adding a compression instruction to the prompt
- [x] 5.6 Write integration test: provide a sample science article and assert valid storyboard JSON is returned

## 6. Voiceover Agent

- [x] 6.1 Create `tools/tts_client.py` with `synthesize(text: str, output_path: str) -> AudioMeta` abstracting OpenAI TTS and ElevenLabs behind a common interface
- [x] 6.2 Implement OpenAI TTS path (`tts-1` model, `onyx` voice) in `tts_client.py`
- [x] 6.3 Implement ElevenLabs TTS path in `tts_client.py` using `ELEVENLABS_VOICE_ID` env var
- [x] 6.4 Add provider selection logic based on `TTS_PROVIDER` environment variable (per spec)
- [x] 6.5 Implement audio duration measurement using `librosa.get_duration` (measured from file, not API response, per spec)
- [x] 6.6 Create `agents/voiceover.py` with the Voiceover Agent node that calls `tts_client.synthesize` for each scene and populates `PipelineState.audio_files`
- [x] 6.7 Add retry logic: retry TTS API call up to 3 times on failure before surfacing error (per spec)
- [x] 6.8 Write integration test with OpenAI TTS: synthesize a short sentence and assert `AudioMeta.duration_seconds` matches `librosa.get_duration`

## 7. Animator Agent — Code Generation

- [x] 7.1 Create `agents/animator.py` with the Animator Agent node skeleton
- [x] 7.2 Write the Manim code generation system prompt: include `visual_description`, `target_duration`, timing constraint arithmetic instruction, and RAG context placeholder
- [x] 7.3 Implement `generate_manim_code(scene: SceneSpec, target_duration: float) -> str` that calls `retrieve_manim_context` and assembles the full prompt, then calls `gpt-4o`
- [x] 7.4 Implement static timing validation: parse generated code, sum all `run_time` values in `self.play()` calls, warn if deviation > 0.5s from `target_duration`
- [x] 7.5 Write unit test: given a mock scene and duration, assert generated code contains a Manim `Scene` subclass with a `construct()` method

## 8. Animator Agent — Docker Rendering & Self-Correction

- [x] 8.1 Create `tools/manim_runner.py` with `render_scene(code: str, scene_id: int) -> VideoMeta` that writes code to a temp file, runs Docker container, and collects MP4 output
- [x] 8.2 Implement Docker execution: mount temp workspace, set 120s timeout, capture stdout/stderr (per spec)
- [x] 8.3 Implement error classification in `manim_runner.py`: detect `AttributeError`, `NameError`, `SyntaxError`, `TypeError`/`ValueError`, `TimeoutError` from stderr
- [x] 8.4 Implement self-correction loop in `animator.py`: on render failure, send traceback + code to LLM with correction prompt, receive revised code, retry; max 5 attempts (per spec)
- [x] 8.5 Write correction prompt for each error category (hallucinated API → inject RAG docs; syntax error → fix syntax; timeout → simplify animation)
- [x] 8.6 Implement max-retries-exceeded handling: set scene status to `"error"`, append to `error_log`, continue pipeline (per spec)
- [x] 8.7 Implement resolution control: pass `-r 1280,720` or `-r 1920,1080` based on `RENDER_RESOLUTION` env var (per spec)
- [x] 8.8 Write integration test: render a simple known-good Manim scene and assert MP4 file is produced with correct resolution

## 9. Video Composition

- [x] 9.1 Create `tools/ffmpeg_composer.py` with `compose_video(audio_files: list[AudioMeta], video_files: list[VideoMeta], output_path: str) -> str` function
- [x] 9.2 Implement FFMPEG command to merge each scene's video clip with its audio track (per-scene audio+video merge, then concatenation)
- [x] 9.3 Handle missing scene files gracefully: skip missing scenes, log warning, compose remaining scenes (per spec)
- [x] 9.4 Verify synchronization: the composed video's scene N audio track starts within 50ms of scene N video clip (per spec)
- [x] 9.5 Write integration test: compose 2 minimal scene clips and assert output MP4 duration equals sum of audio durations

## 10. Pipeline Orchestration (Supervisor Agent)

- [x] 10.1 Create `agents/supervisor.py` defining the LangGraph `StateGraph` with nodes for all agents and FFMPEG composition
- [x] 10.2 Define graph edges: `document_ingestion → storyboard_generation → voiceover_synthesis → animation_rendering → video_composition → hitl_review`
- [x] 10.3 Implement conditional edge from `hitl_review`: "revision submitted" → `revision_router` → appropriate agent node → `video_composition`; "approved" → `social_media`
- [x] 10.4 Implement `revision_router` node: LLM-based routing that classifies revision instruction to `{scene_id, agent}` (per spec)
- [x] 10.5 Implement state persistence: serialize `PipelineState` to `output/state.json` after each node completes (per spec)
- [x] 10.6 Implement state recovery: on Streamlit startup, load `output/state.json` if it exists (per spec)
- [x] 10.7 Implement global error handling in Supervisor: catch exceptions from any agent node, append to `error_log`, route to `hitl_review` (per spec)
- [x] 10.8 Create `main.py` as CLI entry point to run the full pipeline headlessly (no Streamlit)

## 11. HITL Review Interface

- [x] 11.1 Create `app.py` as the Streamlit application entry point; load `PipelineState` from `output/state.json` on startup
- [x] 11.2 Implement video display section: `st.video` for `final_video_path`, fallback message if video not yet generated
- [x] 11.3 Implement storyboard table: `st.dataframe` showing scene_id, narration (truncated), visual_description (truncated) for all scenes
- [x] 11.4 Implement error banner: display `st.error` block if any scene has status `"error"`, listing scene IDs and error summaries (per spec)
- [x] 11.5 Implement revision input: `st.text_area` for natural-language revision instruction + "Submit Revision" button that sets `hitl_revision` and triggers the pipeline HITL loop
- [x] 11.6 Implement approve button: "Approve & Publish" button that triggers the Social Media Agent node
- [x] 11.7 Implement interface refresh: after partial regeneration completes, reload the Streamlit page to display the updated video

## 12. Social Media Agent

- [x] 12.1 Create `tools/social_uploader.py` with YouTube upload function using YouTube Data API v3 and OAuth2 credentials
- [x] 12.2 Implement YouTube OAuth2 flow: read credentials from `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET`, handle token refresh
- [x] 12.3 Implement YouTube metadata generation: LLM prompt to generate title (≤100 chars), description (≤5000 chars), and ≥5 tags from storyboard (per spec)
- [x] 12.4 Implement YouTube upload with retry (up to 3 times, exponential backoff); log failure and surface local path if all retries fail (per spec)
- [x] 12.5 Implement Instagram caption generation: LLM prompt to generate caption (≤2200 chars with 10–30 hashtags) from storyboard (per spec)
- [x] 12.6 Implement Instagram Reel upload via Graph API using `INSTAGRAM_ACCESS_TOKEN` env var
- [x] 12.7 Create `agents/social_media.py` with the Social Media Agent LangGraph node that calls all generation and upload functions
- [x] 12.8 Make social media upload best-effort: pipeline does not fail if uploads fail (per spec)

## 13. End-to-End Integration & Testing

- [x] 13.1 Run full end-to-end pipeline with a real 500-word science article: verify storyboard generated, audio synthesized, video rendered, final MP4 composed
- [x] 13.2 Test HITL revision loop: submit a revision instruction after initial generation, verify only the targeted scene is regenerated and final video is recomposed
- [x] 13.3 Test error recovery: inject a deliberately broken Manim scene, verify self-correction loop activates, verify HITL error banner is shown after 5 failed retries
- [x] 13.4 Test state persistence: kill the pipeline mid-run, restart, verify Streamlit loads the saved state correctly
- [x] 13.5 Verify audio-video synchronization in composed output: check that scene audio starts within 50ms of corresponding video clip
- [x] 13.6 Test PDF ingestion: run pipeline with a PDF file input end-to-end
- [x] 13.7 Test URL ingestion: run pipeline with a science article URL end-to-end
- [x] 13.8 Verify 720p default render resolution and 1080p flag behavior

## 14. Documentation & Cleanup

- [x] 14.1 Update `README.md` with setup instructions (environment variables, Docker setup, RAG index build, running Streamlit app)
- [x] 14.2 Add inline docstrings to all public functions in `agents/` and `tools/`
- [x] 14.3 Add `rag/examples/README.md` documenting the format of curated Manim examples
- [x] 14.4 Create a sample `.env` file with placeholder values for all required keys
- [x] 14.5 Add `Makefile` or `run.sh` script with common commands: `make setup`, `make build-rag`, `make run`, `make test`
