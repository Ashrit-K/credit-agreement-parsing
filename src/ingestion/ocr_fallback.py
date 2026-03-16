"""OCR fallback for scanned / image-heavy PDF pages using pytesseract + pdf2image."""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

from src.ingestion.pdf_extractor import PageData

logger = logging.getLogger(__name__)


def _check_dependencies() -> bool:
    """Return True if pytesseract and pdf2image are importable and functional."""
    try:
        import pytesseract  # noqa: F401
        from pdf2image import convert_from_path  # noqa: F401

        return True
    except ImportError:
        return False


def ocr_page(pdf_path: str | Path, page_num: int, dpi: int = 300) -> str:
    """Convert a single PDF page to an image and OCR it.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    page_num:
        1-indexed page number to OCR.
    dpi:
        Resolution for the page-to-image conversion.

    Returns
    -------
    str
        Extracted text, or an empty string if dependencies are missing or
        OCR fails.
    """
    if not _check_dependencies():
        warnings.warn(
            "pytesseract or pdf2image (poppler) not installed. "
            "OCR fallback is unavailable — returning empty string.",
            stacklevel=2,
        )
        return ""

    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(
            str(pdf_path),
            first_page=page_num,
            last_page=page_num,
            dpi=dpi,
        )
        if not images:
            logger.warning("pdf2image returned no images for page %d", page_num)
            return ""

        text: str = pytesseract.image_to_string(images[0])
        return text.strip()

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "OCR failed for page %d of %s: %s", page_num, pdf_path, exc
        )
        return ""


def ocr_flagged_pages(
    pdf_path: str | Path,
    pages: list[PageData],
    dpi: int = 300,
) -> list[PageData]:
    """Run OCR on every page flagged with ``needs_ocr=True``.

    Pages that do *not* need OCR are returned unchanged. For flagged pages
    the text is replaced with the OCR output and ``needs_ocr`` is reset to
    False. If OCR still yields insufficient text the flag stays True so
    downstream code can handle it.

    Parameters
    ----------
    pdf_path:
        Path to the source PDF.
    pages:
        List of ``PageData`` objects (typically from ``extract_pdf``).
    dpi:
        Resolution passed to ``ocr_page``.

    Returns
    -------
    list[PageData]
        The same list with OCR text patched in where applicable.
    """
    if not _check_dependencies():
        warnings.warn(
            "pytesseract or pdf2image (poppler) not installed. "
            "Skipping OCR for all flagged pages.",
            stacklevel=2,
        )
        return pages

    from src.config import OCR_CHAR_THRESHOLD

    flagged_count = sum(1 for p in pages if p.needs_ocr)
    if flagged_count == 0:
        return pages

    logger.info(
        "Running OCR on %d flagged page(s) in %s", flagged_count, pdf_path
    )

    for page_data in pages:
        if not page_data.needs_ocr:
            continue

        ocr_text = ocr_page(pdf_path, page_data.page_num, dpi=dpi)

        if ocr_text:
            page_data.text = ocr_text
            page_data.char_count = len(ocr_text)
            # Only clear the flag if we got meaningful text
            if page_data.char_count >= OCR_CHAR_THRESHOLD:
                page_data.needs_ocr = False

    return pages
