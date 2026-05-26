"""
rag/retriever.py
----------------
LangChain + ChromaDB retriever for Manim CE documentation.

Provides retrieve_manim_context() used by the Animator Agent to inject
relevant Manim API documentation into the code generation prompt.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings


# ─── Configuration ────────────────────────────────────────────────────────────

COLLECTION_NAME = "manim-docs"
DEFAULT_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "rag/chroma_db")
EMBEDDING_MODEL = "text-embedding-3-small"


# ─── Cached vector store ──────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_vectorstore(persist_dir: str = DEFAULT_PERSIST_DIR) -> Chroma:
    """
    Load the persisted ChromaDB vector store.
    Cached so only one connection is opened per process.
    """
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    return vectorstore


# ─── Public API ───────────────────────────────────────────────────────────────

def retrieve_manim_context(
    query: str,
    k: int = 3,
    persist_dir: str = DEFAULT_PERSIST_DIR,
) -> list[str]:
    """
    Retrieve the top-k most relevant Manim documentation chunks for a query.

    Args:
        query: The search query, typically a scene's visual_description.
        k: Number of chunks to retrieve (default: 3).
        persist_dir: Path to the ChromaDB persistence directory.

    Returns:
        List of document strings (chunks) ordered by relevance.
        Returns empty list if the index is not built yet.
    """
    try:
        vectorstore = _get_vectorstore(persist_dir)
        docs = vectorstore.similarity_search(query, k=k)
        return [doc.page_content for doc in docs]
    except Exception as exc:
        # Graceful degradation: if RAG is unavailable, return empty context
        import warnings
        warnings.warn(
            f"Manim RAG retrieval failed (returning empty context): {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return []


def format_rag_context(chunks: list[str]) -> str:
    """
    Format retrieved chunks into a prompt-ready string block.

    Args:
        chunks: List of documentation chunk strings.

    Returns:
        Formatted string for injection into the Animator prompt.
    """
    if not chunks:
        return ""

    sections = []
    for i, chunk in enumerate(chunks, start=1):
        sections.append(f"### Reference {i}\n{chunk}")

    return (
        "\n\n### Manim Documentation Reference\n"
        "The following Manim CE API documentation and examples are relevant to your task:\n\n"
        + "\n\n".join(sections)
    )
