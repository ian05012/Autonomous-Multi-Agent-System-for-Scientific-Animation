## ADDED Requirements

### Requirement: Build vector index from Manim CE documentation
The system SHALL include a one-time indexing script (`rag/build_index.py`) that fetches or reads Manim CE documentation, splits it into 512-token chunks with 64-token overlap, embeds each chunk using `text-embedding-3-small`, and stores the index in a local ChromaDB collection named `"manim-docs"`.

#### Scenario: Index build succeeds
- **WHEN** `python rag/build_index.py` is run with valid `OPENAI_API_KEY`
- **THEN** ChromaDB collection `"manim-docs"` is created with ≥500 document chunks persisted to `rag/chroma_db/`

#### Scenario: Index already exists
- **WHEN** `python rag/build_index.py` is run and `rag/chroma_db/` already contains a `"manim-docs"` collection
- **THEN** script prints `"Index already exists. Use --rebuild flag to rebuild."` and exits without re-indexing

### Requirement: Retrieve top-3 relevant documentation chunks at code generation time
At Manim code generation time, the system SHALL query the ChromaDB index with the scene's `visual_description` and inject the top-3 most similar documentation chunks into the LLM prompt.

#### Scenario: RAG retrieval
- **WHEN** Animator Agent assembles the code generation prompt for a scene
- **THEN** the top-3 chunks from `"manim-docs"` most similar to `visual_description` are concatenated into a `### Manim Documentation Reference` section of the prompt

### Requirement: Include curated Manim code examples in the index
The index SHALL include 50 curated Manim code examples (stored in `rag/examples/`) annotated with the visual effect they produce, embedded alongside the documentation chunks.

#### Scenario: Example retrieval during code generation
- **WHEN** `visual_description` closely matches a known visual pattern (e.g., "draw a circle growing from center")
- **THEN** at least one of the top-3 retrieved chunks is a curated code example demonstrating that pattern
