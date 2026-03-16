"""Ingestion layer: PDF extraction, page segmentation, and OCR fallback."""

from src.ingestion.pdf_extractor import ExtractionResult, PageData, PDFMetadata, extract_pdf
from src.ingestion.page_segmenter import TextBlock, segment_pages
from src.ingestion.ocr_fallback import ocr_flagged_pages, ocr_page

__all__ = [
    "ExtractionResult",
    "PDFMetadata",
    "PageData",
    "TextBlock",
    "extract_pdf",
    "ocr_flagged_pages",
    "ocr_page",
    "segment_pages",
]
