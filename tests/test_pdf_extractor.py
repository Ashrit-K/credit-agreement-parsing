"""Tests for PDF extraction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingestion.pdf_extractor import extract_pdf
from src.config import RAW_PDF_DIR

# Use a small, known PDF for testing
TEST_PDF = RAW_PDF_DIR / "011_credit_agreement.pdf"


def test_extract_pdf_returns_pages():
    if not TEST_PDF.exists():
        return  # skip if test file not available
    result = extract_pdf(TEST_PDF)
    assert len(result.pages) > 0
    assert result.metadata.total_pages > 0
    assert result.metadata.file_name == "011_credit_agreement.pdf"


def test_extract_pdf_page_has_text():
    if not TEST_PDF.exists():
        return
    result = extract_pdf(TEST_PDF)
    # At least the first page should have text
    assert result.pages[0].char_count > 0
    assert len(result.pages[0].text) > 0


def test_extract_pdf_metadata():
    if not TEST_PDF.exists():
        return
    result = extract_pdf(TEST_PDF)
    assert result.metadata.file_size_bytes > 0
