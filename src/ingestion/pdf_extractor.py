"""PDF text and table extraction using pdfplumber."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from src.config import OCR_CHAR_THRESHOLD


@dataclass
class PageData:
    """Extracted content for a single PDF page."""

    page_num: int
    text: str
    tables: list[list[list[str | None]]] = field(default_factory=list)
    char_count: int = 0
    needs_ocr: bool = False

    def __post_init__(self) -> None:
        self.char_count = len(self.text)
        if self.char_count < OCR_CHAR_THRESHOLD:
            self.needs_ocr = True


@dataclass
class PDFMetadata:
    """High-level metadata about the ingested PDF."""

    file_name: str
    file_size_bytes: int
    total_pages: int


@dataclass
class ExtractionResult:
    """Bundle returned by extract_pdf: page data plus document metadata."""

    pages: list[PageData]
    metadata: PDFMetadata


def extract_pdf(pdf_path: str | Path) -> ExtractionResult:
    """Open a PDF and extract text + tables page by page.

    Parameters
    ----------
    pdf_path:
        Filesystem path to the PDF file.

    Returns
    -------
    ExtractionResult
        Contains a list of ``PageData`` (one per page) and ``PDFMetadata``.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    file_size_bytes = os.path.getsize(pdf_path)
    pages: list[PageData] = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

        for page in pdf.pages:
            page_num = page.page_number  # 1-indexed

            raw_text = page.extract_text() or ""
            raw_tables = page.extract_tables() or []

            page_data = PageData(
                page_num=page_num,
                text=raw_text,
                tables=raw_tables,
            )
            pages.append(page_data)

    metadata = PDFMetadata(
        file_name=pdf_path.name,
        file_size_bytes=file_size_bytes,
        total_pages=total_pages,
    )

    return ExtractionResult(pages=pages, metadata=metadata)
