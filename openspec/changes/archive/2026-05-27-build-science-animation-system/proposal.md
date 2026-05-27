## Why

Producing high-quality educational science animations (like those by 3Blue1Brown) traditionally demands professional scripting, Manim programming, voiceover production, and video editing — skills most educators lack and processes that take days. This project builds a fully automated, multi-agent AI pipeline that transforms a science article or PDF into a finished, narrated educational video with human review built in, collapsing production time from days to minutes.

## What Changes

- **New system from scratch**: No existing codebase — this is a greenfield build.
- Introduce a **Supervisor Agent** (LangGraph state machine) to orchestrate the full pipeline.
- Introduce a **Scriptwriter Agent** that parses science articles/PDFs/URLs and generates structured storyboard JSON.
- Introduce a **Voiceover Agent** that converts narration text to speech (OpenAI TTS / ElevenLabs) and returns precise audio duration metadata.
- Introduce an **Animator Agent** that generates Manim Python code, executes it inside a Docker sandbox, and self-corrects rendering errors via an LLM feedback loop.
- Introduce a **Social Media Agent** that generates platform-specific descriptions, titles, and hashtags, then uploads to YouTube and Instagram.
- Introduce a **HITL Review Interface** (Streamlit) for users to preview the draft video and submit natural-language revision instructions.
- Introduce a **RAG knowledge base** of Manim CE documentation to reduce code hallucination in the Animator Agent.
- Add an **FFMPEG composition step** to merge per-scene video clips and audio into a final MP4.

## Capabilities

### New Capabilities

- `document-ingestion`: Parse and extract key educational content from science articles (plain text), PDFs, and URLs into a normalized internal format consumed by downstream agents.
- `storyboard-generation`: Convert ingested document content into a structured storyboard JSON (scene_id, narration, visual_description, estimated_duration) using an LLM Scriptwriter Agent.
- `voiceover-synthesis`: Generate speech audio for each scene's narration text via TTS APIs (OpenAI TTS / ElevenLabs), returning audio files and precise duration metadata for animation timing.
- `manim-code-generation`: Produce executable Manim CE Python code for each storyboard scene, guided by visual_description and audio duration, using a RAG-augmented LLM prompt.
- `animation-rendering`: Execute generated Manim code inside an isolated Docker sandbox, capture errors, and run a self-correcting LLM loop to fix and re-render until success or max retries.
- `video-composition`: Merge all per-scene rendered video clips with their corresponding audio tracks using FFMPEG into a single cohesive MP4 output.
- `hitl-review`: Provide a Streamlit web interface for users to watch the draft video, inspect the storyboard, and submit natural-language revision instructions targeting specific scenes or agents.
- `partial-regeneration`: Route HITL revision instructions to the appropriate agent (Scriptwriter, Voiceover, or Animator), regenerate only the affected scenes, and recompose the final video.
- `social-media-publishing`: Generate platform-tailored titles, descriptions, and hashtags for the finished video, then upload automatically to YouTube (Data API v3) and Instagram (Graph API).
- `pipeline-orchestration`: Coordinate all agents via a LangGraph state machine (Supervisor Agent), managing shared state, task sequencing, error recovery, and retry logic across the full pipeline.
- `manim-rag-knowledge-base`: Build and serve a vector-store retrieval index over Manim CE documentation and curated examples to ground Manim code generation and reduce hallucination.

### Modified Capabilities

_(None — this is a new project with no existing specs.)_

## Impact

- **New dependencies**: Python 3.11+, LangChain, LangGraph, Manim CE, FFMPEG, Docker, OpenAI API, ElevenLabs API, YouTube Data API v3, Instagram Graph API, a vector store (e.g., ChromaDB or FAISS), Streamlit.
- **Infrastructure**: Requires a machine with Docker daemon and sufficient GPU/CPU for Manim rendering; FFMPEG must be installed in the rendering container.
- **API keys / secrets**: OpenAI, ElevenLabs, YouTube OAuth2, Instagram OAuth2 — managed via `.env` / secrets manager.
- **No breaking changes** to external systems (greenfield).
