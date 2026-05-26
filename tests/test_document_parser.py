"""
tests/test_document_parser.py
------------------------------
Unit tests for document_parser: text, PDF, and URL ingestion paths.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from tools.document_parser import (
    MIN_WORD_COUNT,
    DocumentContent,
    parse_pdf,
    parse_text,
    parse_url,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_ARTICLE = (
    "The Quantum Nature of Light and Its Implications for Modern Physics. "
    "Light has fascinated scientists for centuries, from Newton's corpuscular theory "
    "to Maxwell's electromagnetic wave equations. The photoelectric effect, explained "
    "by Einstein in 1905, demonstrated that light behaves as discrete packets of energy "
    "called photons. This wave-particle duality is at the heart of quantum mechanics. "
    "Modern experiments such as the double-slit experiment continue to reveal the "
    "mysterious nature of light and matter at the quantum scale. "
    * 3  # repeat to exceed 50-word minimum easily
)


# ─── parse_text ───────────────────────────────────────────────────────────────

class TestParseText:
    def test_valid_article(self):
        result = parse_text(SAMPLE_ARTICLE)
        assert result["source_type"] == "text"
        assert result["title"] != ""
        assert len(result["body"]) > 0
        assert result["word_count"] >= MIN_WORD_COUNT

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_text("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_text("   \n\n  ")

    def test_too_short_raises(self):
        short_text = "This is too short."
        with pytest.raises(ValueError, match="minimum"):
            parse_text(short_text)

    def test_word_count_accurate(self):
        text = " ".join(["word"] * 100)
        result = parse_text(text)
        assert result["word_count"] == 100

    def test_untitled_fallback(self):
        # Text with no clear short first line
        long_first_line = "x" * 300 + "\n" + "actual content " * 20
        result = parse_text(long_first_line)
        # Should not crash; title is either extracted or "Untitled"
        assert isinstance(result["title"], str)


# ─── parse_pdf ────────────────────────────────────────────────────────────────

class TestParsePdf:
    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_pdf("/nonexistent/path/file.pdf")

    def test_scanned_pdf_raises(self):
        """PDF with no extractable text should raise ValueError."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            # Write a minimal valid-but-empty-text PDF
            f.write(b"%PDF-1.4\n%%EOF")
            tmp_path = f.name
        try:
            with patch("pdfplumber.open") as mock_open:
                mock_pdf = MagicMock()
                mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
                mock_pdf.__exit__ = MagicMock(return_value=False)
                mock_pdf.pages = [MagicMock(extract_text=MagicMock(return_value=None))]
                mock_open.return_value = mock_pdf
                with pytest.raises(ValueError, match="no extractable text"):
                    parse_pdf(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_valid_pdf_extraction(self):
        """Mock a PDF with text and assert DocumentContent is returned."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            with patch("pdfplumber.open") as mock_open:
                mock_pdf = MagicMock()
                mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
                mock_pdf.__exit__ = MagicMock(return_value=False)
                page = MagicMock()
                page.extract_text = MagicMock(return_value=SAMPLE_ARTICLE)
                mock_pdf.pages = [page]
                mock_open.return_value = mock_pdf
                result = parse_pdf(tmp_path)
                assert result["source_type"] == "pdf"
                assert result["word_count"] >= MIN_WORD_COUNT
        finally:
            os.unlink(tmp_path)


# ─── parse_url ────────────────────────────────────────────────────────────────

class TestParseUrl:
    def _mock_response(self, html: str, status_code: int = 200):
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.status_code = status_code
        mock_resp.raise_for_status = MagicMock()
        if status_code >= 400:
            import requests
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=mock_resp
            )
        return mock_resp

    def test_valid_url(self):
        html = f"""
        <html><head><title>Quantum Physics</title></head>
        <body><article>{SAMPLE_ARTICLE}</article></body></html>
        """
        with patch("requests.get", return_value=self._mock_response(html)):
            result = parse_url("https://example.com/article")
        assert result["source_type"] == "url"
        assert result["title"] == "Quantum Physics"
        assert result["word_count"] >= MIN_WORD_COUNT

    def test_404_raises(self):
        import requests as req
        with patch("requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            http_error = req.exceptions.HTTPError(response=mock_resp)
            mock_resp.raise_for_status.side_effect = http_error
            mock_get.return_value = mock_resp
            mock_get.side_effect = None
            with pytest.raises(ValueError, match="HTTP"):
                with patch("requests.get", side_effect=http_error):
                    parse_url("https://example.com/notfound")

    def test_timeout_raises(self):
        import requests as req
        with patch("requests.get", side_effect=req.exceptions.Timeout):
            with pytest.raises(ValueError, match="timed out"):
                parse_url("https://example.com/slow")

    def test_empty_content_raises(self):
        html = "<html><body></body></html>"
        with patch("requests.get", return_value=self._mock_response(html)):
            with pytest.raises(ValueError):
                parse_url("https://example.com/empty")
