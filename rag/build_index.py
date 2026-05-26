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
    "https://docs.manim.community/en/stable/reference.html",
    "https://docs.manim.community/en/stable/reference/manim.animation.html",
    "https://docs.manim.community/en/stable/reference/manim.mobject.html",
    "https://docs.manim.community/en/stable/reference/manim.scene.html",
    "https://docs.manim.community/en/stable/reference/manim.utils.html",
    "https://docs.manim.community/en/stable/guides/index.html",
    "https://docs.manim.community/en/stable/tutorials/index.html",
    "https://docs.manim.community/en/stable/examples.html",
]

EXAMPLES_DIR = Path(__file__).parent / "examples"


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

    # 2. Index curated examples
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

    print(f"\n✓ Index built successfully with {len(all_documents)} chunks.")
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
