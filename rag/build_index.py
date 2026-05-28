"""
rag/build_index.py
------------------
One-time script to build the Manim CE documentation ChromaDB index.

Usage:
    python rag/build_index.py                # skip if already exists
    python rag/build_index.py --rebuild      # force rebuild
    python rag/build_index.py --validate     # validate examples first, then build

The script:
1. Downloads / reads Manim CE documentation (HTML pages) — official, trusted source
2. Splits into 512-token chunks (64-token overlap)
3. Embeds with text-embedding-3-small
4. Persists to ChromaDB at CHROMA_PERSIST_DIR

For curated examples (rag/examples/*.py):
- ONLY indexes examples that have PASSED actual Manim rendering validation.
- Run `python rag/validate_examples.py` first to validate examples.
- Unvalidated or failed examples are SKIPPED to prevent hallucination amplification.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the project root is in sys.path so `rag.*` imports resolve correctly
# regardless of whether the script is run as `python rag/build_index.py` or
# as a module `python -m rag.build_index`.
_PROJECT_ROOT = str(Path(__file__).parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

COLLECTION_NAME = "manim-docs"
PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "rag/chroma_db")
EMBEDDING_MODEL = "text-embedding-3-small"
CHUNK_SIZE = 512       # tokens (approximated as characters / 4)
CHUNK_OVERLAP = 64     # tokens overlap

# Manim CE documentation pages to index (key reference pages)
MANIM_DOC_URLS = [
    # Overview, examples, tutorials
    "https://docs.manim.community/en/stable/reference.html",
    "https://docs.manim.community/en/stable/examples.html",
    "https://docs.manim.community/en/stable/tutorials/index.html",
    "https://docs.manim.community/en/stable/tutorials/quickstart.html",
    "https://docs.manim.community/en/stable/tutorials/building_blocks.html",
    "https://docs.manim.community/en/stable/tutorials/output_and_config.html",
    "https://docs.manim.community/en/stable/guides/index.html",
    "https://docs.manim.community/en/stable/guides/using_text.html",
    "https://docs.manim.community/en/stable/guides/add_voiceovers.html",
    "https://docs.manim.community/en/stable/guides/deep_dive.html",
    # Animation reference pages
    "https://docs.manim.community/en/stable/reference/manim.animation.animation.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.creation.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.fading.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.growing.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.indication.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.movement.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.numbers.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.rotation.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.specialized.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.transform.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.transform_matching_parts.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.updater.html",
    # Geometry mobjects
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.arc.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.boolean_ops.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.line.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.polygram.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.shape_matchers.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.geometry.tips.html",
    # Graphing mobjects
    "https://docs.manim.community/en/stable/reference/manim.mobject.graphing.coordinate_systems.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.graphing.functions.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.graphing.number_line.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.graphing.probability.html",
    # Text and math
    "https://docs.manim.community/en/stable/reference/manim.mobject.text.text_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.text.tex_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.text.numbers.html",
    # Other mobjects
    "https://docs.manim.community/en/stable/reference/manim.mobject.graph.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.logo.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.matrix.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.svg.brace.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.svg.svg_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.table.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.three_d.three_dimensions.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.types.image_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.types.point_cloud_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.types.vectorized_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.value_tracker.html",
    # Scene
    "https://docs.manim.community/en/stable/reference/manim.scene.scene.html",
    "https://docs.manim.community/en/stable/reference/manim.scene.moving_camera_scene.html",
    "https://docs.manim.community/en/stable/reference/manim.scene.three_d_scene.html",
    "https://docs.manim.community/en/stable/reference/manim.scene.vector_space_scene.html",
    "https://docs.manim.community/en/stable/reference/manim.scene.zoomed_scene.html",
    # Camera
    "https://docs.manim.community/en/stable/reference/manim.camera.camera.html",
    "https://docs.manim.community/en/stable/reference/manim.camera.moving_camera.html",
    "https://docs.manim.community/en/stable/reference/manim.camera.three_d_camera.html",
    # Animation (additional)
    "https://docs.manim.community/en/stable/reference/manim.animation.composition.html",
    # Utils
    "https://docs.manim.community/en/stable/reference/manim.utils.color.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.rate_functions.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.tex.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.space_ops.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.bezier.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.paths.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.color.core.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.color.manim_colors.html",
    # Config
    "https://docs.manim.community/en/stable/reference/manim._config.html",
    # Additional mobjects
    "https://docs.manim.community/en/stable/reference/manim.mobject.frame.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.svg.svg_mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.changing.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.three_d.polyhedra.html",
    # Additional guides
    "https://docs.manim.community/en/stable/guides/configuration.html",
    "https://docs.manim.community/en/stable/faq/index.html",
    "https://docs.manim.community/en/stable/faq/general.html",
    "https://docs.manim.community/en/stable/faq/help.html",
    "https://docs.manim.community/en/stable/installation.html",
    # Changelog (rich in class/method references)
    "https://docs.manim.community/en/stable/changelog/0.18.0-changelog.html",
    "https://docs.manim.community/en/stable/changelog/0.17.0-changelog.html",
]

EXAMPLES_DIR = Path(__file__).parent / "examples"
SKILLS_DIR   = Path(__file__).parent / "skills"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fetch_url_text(url: str) -> str:
    """Fetch a URL and return its main text content."""
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "ScienceAnimationIndexer/1.0"})
        resp.raise_for_status()
    except Exception as exc:
        print(f"  [WARN] Could not fetch {url}: {exc}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _load_examples() -> list[tuple[str, dict]]:
    """
    Load ONLY validated Manim examples from rag/examples/.

    Uses validate_examples.get_valid_example_files() to filter to
    examples that have actually been rendered successfully by Manim.
    Unvalidated or failed examples are skipped to prevent RAG from
    amplifying hallucinated API usage.
    """
    docs_with_meta = []
    if not EXAMPLES_DIR.exists():
        print(f"  [WARN] Examples directory not found: {EXAMPLES_DIR}")
        return docs_with_meta

    # Import here to avoid circular dependency at module level
    from rag.validate_examples import get_valid_example_files, RESULTS_FILE

    all_py_files = sorted(EXAMPLES_DIR.glob("ex_*.py"))
    valid_files = get_valid_example_files()
    valid_names = {f.name for f in valid_files}

    skipped = [f.name for f in all_py_files if f.name not in valid_names]
    if skipped:
        print(
            f"  [WARN] Skipping {len(skipped)} unvalidated/failed examples.\n"
            f"         Run: python rag/validate_examples.py  to validate them.\n"
            f"         Skipped: {', '.join(skipped[:5])}"
            + (f" ... and {len(skipped)-5} more" if len(skipped) > 5 else "")
        )

    if not valid_files:
        print(
            "  [WARN] No validated examples found — skipping examples entirely.\n"
            "         Official Manim docs will still be indexed.\n"
            "         To validate examples: python rag/validate_examples.py"
        )
        return docs_with_meta

    print(f"  Loading {len(valid_files)}/{len(all_py_files)} validated examples...")

    for py_file in sorted(valid_files, key=lambda f: f.name):
        content = py_file.read_text(encoding="utf-8")
        annotation_file = py_file.with_suffix(".txt")
        annotation = ""
        if annotation_file.exists():
            annotation = annotation_file.read_text(encoding="utf-8").strip()

        text = f"# Manim Example (VALIDATED): {py_file.stem}\n"
        if annotation:
            text += f"# Visual Effect: {annotation}\n"
        text += content

        docs_with_meta.append(
            (text, {"source": str(py_file), "type": "example", "validated": True})
        )

    return docs_with_meta


def _load_skills() -> list[tuple[str, dict]]:
    """Load Manim best-practice skill files from rag/skills/*.md."""
    docs = []
    if not SKILLS_DIR.exists():
        return docs
    for md_file in sorted(SKILLS_DIR.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        text = f"# Manim Skill: {md_file.stem}\n{content}"
        docs.append((text, {"source": str(md_file), "type": "skill"}))
    print(f"  Loaded {len(docs)} skill files from {SKILLS_DIR}")
    return docs


# ─── Main ─────────────────────────────────────────────────────────────────────

def build_index(rebuild: bool = False, validate_first: bool = False) -> None:
    """
    Build or rebuild the Manim documentation ChromaDB index.

    Args:
        rebuild:        If True, delete and rebuild the existing index.
        validate_first: If True, run example validation before indexing.
    """
    if validate_first:
        print("Running example validation before indexing...")
        from rag.validate_examples import run_validation
        run_validation(revalidate=False)
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    from langchain_core.documents import Document
    from langchain_openai import OpenAIEmbeddings

    persist_dir = PERSIST_DIR
    collection_exists = os.path.exists(persist_dir) and any(
        Path(persist_dir).iterdir()
    ) if os.path.exists(persist_dir) else False

    if collection_exists and not rebuild:
        print("Index already exists. Use --rebuild flag to rebuild.")
        return

    if rebuild and collection_exists:
        import shutil
        print(f"Rebuilding index — removing {persist_dir}...")
        shutil.rmtree(persist_dir)

    print("Building Manim documentation index...")
    print(f"  Persist directory: {persist_dir}")

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE * 4,       # ~512 tokens (4 chars/token approx)
        chunk_overlap=CHUNK_OVERLAP * 4,
        length_function=len,
    )

    all_documents: list[Document] = []

    # 1. Index Manim documentation pages
    print(f"\nFetching {len(MANIM_DOC_URLS)} documentation pages...")
    for url in MANIM_DOC_URLS:
        print(f"  Fetching: {url}")
        text = _fetch_url_text(url)
        if not text:
            continue
        chunks = splitter.split_text(text)
        for chunk in chunks:
            all_documents.append(
                Document(page_content=chunk, metadata={"source": url, "type": "docs"})
            )
    print(f"  → {len(all_documents)} chunks from documentation pages")

    # 2. Index skill best-practice files (always included, no validation needed)
    print(f"\nLoading Manim skill files from {SKILLS_DIR}...")
    skill_docs = _load_skills()
    for text, meta in skill_docs:
        chunks = splitter.split_text(text)
        for chunk in chunks:
            all_documents.append(Document(page_content=chunk, metadata=meta))
    print(f"  → {len(skill_docs)} skill files indexed")

    # 3. Index curated examples
    print(f"\nLoading curated examples from {EXAMPLES_DIR}...")
    example_docs = _load_examples()
    for text, meta in example_docs:
        chunks = splitter.split_text(text)
        for chunk in chunks:
            all_documents.append(Document(page_content=chunk, metadata=meta))
    print(f"  → {len(example_docs)} example files indexed")

    print(f"\nTotal chunks to embed: {len(all_documents)}")
    print("Embedding and persisting to ChromaDB (this may take a few minutes)...")

    # Batch in groups of 100 to avoid rate limits
    batch_size = 100
    vectorstore = None
    for i in range(0, len(all_documents), batch_size):
        batch = all_documents[i : i + batch_size]
        if vectorstore is None:
            vectorstore = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                collection_name=COLLECTION_NAME,
                persist_directory=persist_dir,
            )
        else:
            vectorstore.add_documents(batch)
        print(f"  Embedded {min(i + batch_size, len(all_documents))}/{len(all_documents)} chunks...")

    print(f"\nOK Index built successfully with {len(all_documents)} chunks.")
    print(f"  Persisted to: {persist_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Manim CE documentation RAG index.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild even if index already exists.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run example validation before building the index.",
    )
    args = parser.parse_args()
    build_index(rebuild=args.rebuild, validate_first=args.validate)
