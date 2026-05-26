## Context

This is a greenfield project building a multi-agent AI pipeline to automate educational science animation production. No existing codebase exists. The system must orchestrate four specialized AI agents (Scriptwriter, Voiceover, Animator, Social Media) under a Supervisor Agent, render Manim animations in isolation, synchronize audio with video, and provide a human review interface before final publication.

Key constraints:
- Manim rendering is CPU/GPU intensive and can fail due to LLM code hallucination — reliability mechanisms are mandatory.
- Audio-video synchronization depends on TTS output duration, which is only known after synthesis.
- The HITL loop must allow partial regeneration (single scenes) without re-running the entire pipeline.
- All external API calls (OpenAI, ElevenLabs, YouTube, Instagram) must be abstracted behind service interfaces for swappability.

## Goals / Non-Goals

**Goals:**
- Design a LangGraph-based state machine as the central orchestrator (Supervisor Agent).
- Define a shared pipeline state schema that all agents read from and write to.
- Choose the rendering isolation strategy (Docker sandbox).
- Define the Manim self-correction loop termination policy (max retries, error categories).
- Choose the vector store for the Manim RAG knowledge base.
- Design the HITL partial regeneration routing mechanism.
- Define the FFMPEG composition pipeline.
- Choose the frontend framework for the review interface.

**Non-Goals:**
- Multi-language support (future extension).
- Real-time collaborative editing.
- Mobile application.
- GPU-accelerated rendering orchestration (out of scope for initial build).
- TikTok publishing (future extension).
- Fine-tuning any LLM model.

## Decisions

### Decision 1: LangGraph as the sole orchestration framework (not AutoGen)

**Choice**: LangGraph (explicit state machine) over AutoGen (conversational agents).

**Rationale**: The pipeline has a well-defined, deterministic sequence with conditional branching (HITL loop, error recovery, partial regeneration). LangGraph's explicit node/edge/state model maps directly to this structure and makes the flow auditable. AutoGen's conversation-driven model adds non-determinism that would complicate debugging.

**Alternatives considered**:
- AutoGen: More flexible for open-ended agent collaboration, but poorly suited to deterministic pipelines with shared structured state.
- Custom queue system (Celery): Too much boilerplate; LangGraph provides state persistence natively.

---

### Decision 2: Shared pipeline state as a typed TypedDict

**Choice**: A single `PipelineState` TypedDict passed through all LangGraph nodes.

```python
class PipelineState(TypedDict):
    input_text: str                        # raw source material
    source_type: Literal["text","pdf","url"]
    storyboard: list[SceneSpec]            # output of Scriptwriter
    audio_files: list[AudioMeta]           # output of Voiceover
    video_clips: list[VideoMeta]           # output of Animator
    final_video_path: str                  # output of FFMPEG composition
    hitl_revision: Optional[str]           # user's natural-language instruction
    revision_target: Optional[RevisionTarget]  # which scene/agent to re-run
    error_log: list[str]
    iteration: int                         # HITL loop counter
```

**Rationale**: A single shared state object prevents message-passing inconsistencies between agents. Each agent node receives the full state and returns a partial update. LangGraph merges updates using `Annotated` reducers where needed (e.g., appending errors).

---

### Decision 3: Docker sandbox for Manim rendering

**Choice**: Each Manim render job runs inside a short-lived Docker container (`manimcommunity/manim:latest`).

**Rationale**: Isolates rendering failures from the main process. Prevents malicious or broken generated code from affecting the host. Allows GPU passthrough if needed (`--gpus all`). Containers are spun up per scene and removed after completion.

**Alternatives considered**:
- Subprocess in virtualenv: Simpler but no isolation; a segfault in Manim kills the main process.
- Modal / cloud functions: Added network latency and cost; over-engineered for initial build.

**Implementation sketch**:
```python
docker run --rm -v /tmp/scenes:/workspace manimcommunity/manim:latest \
  python -m manim scene.py SceneName -o output.mp4
```

---

### Decision 4: Manim self-correction loop — max 5 retries, categorized errors

**Choice**: Up to 5 LLM-assisted correction attempts per scene. On each failure, the full traceback + current code is sent to the LLM with a targeted correction prompt. After 5 failures, the scene is flagged as `ERROR` and the pipeline surfaces it to the user via HITL.

**Error categories handled**:
1. `AttributeError` / `NameError` — hallucinated API (RAG lookup injected into correction prompt)
2. `SyntaxError` — malformed Python
3. `ValueError` / `TypeError` — wrong argument types
4. `TimeoutError` — scene took > 120s to render (code restructured to be simpler)

**Rationale**: 5 iterations covers >90% of hallucination patterns based on known Manim LLM benchmarks. Unbounded loops risk infinite cost.

---

### Decision 5: ChromaDB as the Manim RAG vector store

**Choice**: ChromaDB (local, persistent) with `text-embedding-3-small` embeddings.

**Rationale**: ChromaDB runs in-process (no separate server), persists to disk, and integrates directly with LangChain's `Chroma` retriever. The Manim documentation corpus is ~500 pages — small enough for a local store. No cloud dependency.

**Alternatives considered**:
- FAISS: No built-in persistence; manual index serialization required.
- Pinecone: Cloud-hosted, adds network dependency and cost.
- Weaviate: Heavier operational footprint.

**Index construction**: Manim CE docs (HTML → markdown chunks of 512 tokens, 64-token overlap) + 50 curated Manim code examples annotated with the visual effect they produce.

---

### Decision 6: TTS duration as animation timing ground truth

**Choice**: After Voiceover Agent synthesizes audio for a scene, the actual audio file duration (measured via `librosa.get_duration`) is passed to the Animator Agent as the `target_duration` for that scene.

**Animator prompt contract**:
> "The animation for this scene MUST have a total `run_time` of exactly `{duration:.1f}` seconds. Distribute this time across all `play()` calls. The sum of all `run_time` arguments in `self.play()` calls MUST equal `{duration:.1f}`."

**Rationale**: Generating audio first resolves the chicken-and-egg problem (animation timing depends on narration length). The LLM is given an explicit arithmetic constraint rather than an estimate.

---

### Decision 7: HITL partial regeneration routing via scene_id + agent_id

**Choice**: When the user submits a revision instruction, an LLM router classifies it into `{scene_id: int, agent: "scriptwriter"|"voiceover"|"animator"}`. The LangGraph graph routes only to that agent's node, regenerates that scene, then jumps directly to FFMPEG recomposition.

**Routing prompt**:
> "Given the user instruction: '{instruction}', and the storyboard with {N} scenes, identify: (1) the scene number (1-indexed), (2) which agent needs to act (scriptwriter, voiceover, or animator)."

**Rationale**: Full pipeline re-runs would waste rendering time. Scene-level granularity matches the storyboard data model.

---

### Decision 8: Streamlit for the HITL review interface

**Choice**: Streamlit (single-page app, `st.video`, `st.text_area`, `st.button`).

**Rationale**: Fastest to build for a research/demo system. No React/JS knowledge required. Streamlit's session state handles the HITL loop naturally. The interface only needs to show a video player, storyboard table, and a text input box.

**Alternatives considered**:
- Gradio: Slightly less control over layout; functionally equivalent.
- FastAPI + React: Much higher development overhead for no additional benefit at this stage.

---

### Decision 9: Project structure

```
science-animation-system/
├── agents/
│   ├── supervisor.py          # LangGraph graph definition
│   ├── scriptwriter.py        # Scriptwriter Agent node
│   ├── voiceover.py           # Voiceover Agent node
│   ├── animator.py            # Animator Agent node (+ correction loop)
│   └── social_media.py        # Social Media Agent node
├── tools/
│   ├── document_parser.py     # PDF / URL / text ingestion
│   ├── manim_runner.py        # Docker execution wrapper
│   ├── ffmpeg_composer.py     # FFMPEG merge utility
│   ├── tts_client.py          # OpenAI TTS / ElevenLabs abstraction
│   └── social_uploader.py     # YouTube + Instagram upload clients
├── rag/
│   ├── build_index.py         # One-time Manim docs indexer
│   └── retriever.py           # LangChain Chroma retriever wrapper
├── state.py                   # PipelineState TypedDict definition
├── app.py                     # Streamlit HITL interface entry point
├── main.py                    # CLI entry point (headless pipeline)
├── Dockerfile.manim            # Manim rendering container
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Manim code hallucination causes persistent render failures | RAG retrieval injects relevant API docs; 5-retry loop with categorized correction prompts; fallback to user via HITL |
| TTS duration instruction not followed by Animator LLM | Explicit arithmetic constraint in prompt; post-generation validation: sum all `run_time` values and warn if off by >0.5s |
| Docker startup latency adds per-scene overhead | Pre-warm container pool (1-2 idle containers); scenes render in parallel where dependencies allow |
| YouTube / Instagram API rate limits or auth expiry | Exponential backoff; OAuth2 token refresh logic; graceful degradation (save video locally if upload fails) |
| LangGraph state grows large for long articles | Cap storyboard at 10 scenes per run; store audio/video as file paths (not bytes) in state |
| Streamlit session state lost on server restart | Persist `PipelineState` to disk (JSON) after each agent completes; reload on reconnect |

## Open Questions

1. **LLM model selection per agent**: Should each agent use the same model (e.g., `gpt-4o`) or different models (e.g., cheaper model for social media copy)? → Start with `gpt-4o` uniformly; optimize later.
2. **Parallel scene rendering**: LangGraph supports parallel node execution via `Send` API. Should scenes render in parallel from the start, or sequentially first for simplicity? → Sequential first, add parallelism in optimization phase.
3. **Manim RAG index update cadence**: How often should the Manim docs index be rebuilt? → Manual rebuild on Manim CE version bumps; version-pin in `requirements.txt`.
4. **Video output resolution**: 1080p (slower) or 720p (faster for demos)? → 720p for development; 1080p flag for production runs.
