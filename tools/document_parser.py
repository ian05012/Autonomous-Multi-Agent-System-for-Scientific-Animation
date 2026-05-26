"""
tools/document_parser.py
------------------------
Document ingestion for the Science Animation System.

Supports three input types:
- Plain text (string)
- PDF files (via pdfplumber)
- URLs (via requests + BeautifulSoup)

All parsers return a normalized DocumentContent dict consumed by the
Scriptwriter Agent.
"""

from __future__ import annotations

import re
from typing import Optional
from typing_extensions import TypedDict

import pdfplumber
import requests
from bs4 import BeautifulSoup


# ─── Output type ─────────────────────────────────────────────────────────────

class DocumentContent(TypedDict):
    """Normalized document content produced by all parser variants."""
    source_type: str        # "text" | "pdf" | "url"
    title: str              # extracted or inferred title, "Untitled" if unknown
    body: str               # full extracted text body
    word_count: int         # number of words in body


# ─── Constants ────────────────────────────────────────────────────────────────

MIN_WORD_COUNT = 50
URL_FETCH_TIMEOUT = 15  # seconds


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _count_words(text: str) -> int:
    """Count whitespace-separated words in a string."""
    return len(text.split())


def _extract_title_from_text(text: str) -> str:
    """
    Attempt to extract a title from the first non-empty line of the text.
    Falls back to "Untitled".
    """
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and len(stripped) <= 200:
            return stripped
    return "Untitled"


def _clean_body(text: str) -> str:
    """Normalize whitespace: collapse multiple blank lines into one."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ─── Public parsers ───────────────────────────────────────────────────────────

def parse_text(text: str) -> DocumentContent:
    """
    Parse a raw UTF-8 science article string.

    Args:
        text: Non-empty UTF-8 string containing the article.

    Returns:
        DocumentContent with source_type="text".

    Raises:
        ValueError: If text has fewer than MIN_WORD_COUNT words.
    """
    if not text or not text.strip():
        raise ValueError("Input text is empty.")

    word_count = _count_words(text)
    if word_count < MIN_WORD_COUNT:
        raise ValueError(
            f"Input text too short to generate a meaningful storyboard "
            f"(minimum {MIN_WORD_COUNT} words, got {word_count})."
        )

    body = _clean_body(text)
    title = _extract_title_from_text(body)

    return DocumentContent(
        source_type="text",
        title=title,
        body=body,
        word_count=word_count,
    )


def parse_pdf(file_path: str) -> DocumentContent:
    """
    Extract text from a PDF file using pdfplumber.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        DocumentContent with source_type="pdf".

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the PDF has no extractable text or is too short.
    """
    import os
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    pages_text: list[str] = []

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
    except Exception as exc:
        raise ValueError(f"Failed to open PDF: {exc}") from exc

    if not pages_text:
        raise ValueError(
            "PDF contains no extractable text. OCR is not supported in this version."
        )

    full_text = "\n\n".join(pages_text)
    body = _clean_body(full_text)
    word_count = _count_words(body)

    if word_count < MIN_WORD_COUNT:
        raise ValueError(
            f"PDF text too short to generate a meaningful storyboard "
            f"(minimum {MIN_WORD_COUNT} words, got {word_count})."
        )

    title = _extract_title_from_text(body)

    return DocumentContent(
        source_type="pdf",
        title=title,
        body=body,
        word_count=word_count,
    )


def parse_url(url: str) -> DocumentContent:
    """
    Fetch and extract the main article text from a URL.

    Uses requests + BeautifulSoup. Strips navigation, ads, scripts, and styles.

    Args:
        url: Valid HTTPS/HTTP URL pointing to an article page.

    Returns:
        DocumentContent with source_type="url".

    Raises:
        ValueError: If URL is unreachable, returns error status, times out,
                    or yields no extractable text.
    """
    try:
        response = requests.get(
            url,
            timeout=URL_FETCH_TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ScienceAnimationBot/1.0)"},
        )
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise ValueError(f"Failed to fetch URL: request timed out after {URL_FETCH_TIMEOUT}s.")
    except requests.exceptions.HTTPError as exc:
        raise ValueError(f"Failed to fetch URL: HTTP {exc.response.status_code}.")
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"Failed to fetch URL: {exc}.")

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()

    # Try common article containers first
    article_body: Optional[str] = None
    for selector in ["article", "main", '[role="main"]', ".article-body", ".post-content"]:
        element = soup.select_one(selector)
        if element:
            article_body = element.get_text(separator="\n", strip=True)
            break

    # Fall back to full body text
    if not article_body:
        article_body = soup.get_text(separator="\n", strip=True)

    body = _clean_body(article_body)

    if not body:
        raise ValueError(f"Failed to fetch URL: no extractable text content found.")

    word_count = _count_words(body)
    if word_count < MIN_WORD_COUNT:
        raise ValueError(
            f"URL content too short to generate a meaningful storyboard "
            f"(minimum {MIN_WORD_COUNT} words, got {word_count})."
        )

    # Extract title from HTML <title> or <h1>
    title_tag = soup.find("title")
    h1_tag = soup.find("h1")
    if title_tag and title_tag.get_text(strip=True):
        title = title_tag.get_text(strip=True)[:200]
    elif h1_tag and h1_tag.get_text(strip=True):
        title = h1_tag.get_text(strip=True)[:200]
    else:
        title = _extract_title_from_text(body)

    return DocumentContent(
        source_type="url",
        title=title,
        body=body,
        word_count=word_count,
    )
