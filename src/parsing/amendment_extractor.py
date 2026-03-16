"""Detects whether a document is an amendment and extracts amendment
details (number, date, original agreement date, sections amended)."""

from __future__ import annotations

import re
from typing import Optional

from src.field_patterns import (
    AMENDMENT_DETECTION_SYNONYMS,
    AMENDMENT_ORDINALS,
    DATE_RE,
    SECTION_KEYWORDS,
)
from src.models.schema import AmendmentInfo, SourceRef
from src.parsing.section_detector import SectionNode

# ---------------------------------------------------------------------------
# Amendment detection patterns (compiled from centralized synonyms)
# ---------------------------------------------------------------------------

_IS_AMENDMENT_RE = re.compile(
    "|".join(f"(?:{p})" for p in AMENDMENT_DETECTION_SYNONYMS),
    re.IGNORECASE,
)

_AMENDMENT_NUMBER_RE = re.compile(
    "|".join(f"(?:{p})" for p in AMENDMENT_DETECTION_SYNONYMS),
    re.IGNORECASE,
)

_ORDINAL_MAP = AMENDMENT_ORDINALS

_DATE_RE = DATE_RE

_AMENDMENT_DATE_RE = re.compile(
    r"(?:dated\s+(?:as\s+of\s+)?|effective\s+(?:as\s+of\s+)?)"
    r"(" + _DATE_RE.pattern + r")",
    re.IGNORECASE,
)

_ORIGINAL_DATE_RE = re.compile(
    r"(?:(?:credit|loan)\s+agreement\s+dated\s+(?:as\s+of\s+)?)"
    r"(" + _DATE_RE.pattern + r")",
    re.IGNORECASE,
)

_SECTION_AMENDED_RE = re.compile(
    r"(?:Section|SECTION)\s+(\d+\.\d+)\s+.*?(?:is\s+hereby\s+amended|"
    r"is\s+amended|shall\s+be\s+amended|is\s+deleted|is\s+replaced)",
    re.IGNORECASE,
)

_ARTICLE_AMENDED_RE = re.compile(
    r"(?:ARTICLE|Article)\s+([IVXLCDM]+|\d+)\s+.*?(?:is\s+hereby\s+amended|"
    r"is\s+amended|shall\s+be\s+amended)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_amendment_number(text: str) -> str:
    """Try to extract a numeric amendment number from the title/preamble."""
    text_lower = text.lower()
    for ordinal, num in _ORDINAL_MAP.items():
        pattern = re.compile(
            rf"\b{re.escape(ordinal)}\b\s+amendment", re.IGNORECASE
        )
        if pattern.search(text):
            return num

    m = re.search(r"Amendment\s+(?:No\.|Number)\s*(\d+)", text, re.IGNORECASE)
    if m:
        return m.group(1)

    if re.search(r"\bAmended\s+and\s+Restated\b", text, re.IGNORECASE):
        return "A&R"

    return ""


def _find_sections_amended(text: str) -> list[str]:
    """Return a list of section/article numbers being amended."""
    amended: list[str] = []
    for m in _SECTION_AMENDED_RE.finditer(text):
        section_num = m.group(1)
        if section_num not in amended:
            amended.append(f"Section {section_num}")
    for m in _ARTICLE_AMENDED_RE.finditer(text):
        article_num = m.group(1)
        label = f"Article {article_num}"
        if label not in amended:
            amended.append(label)
    return amended


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_amendments(
    blocks: list[dict],
    sections: list[SectionNode],
    doc_id: str = "",
) -> list[AmendmentInfo]:
    """Detect if the document is an amendment and extract details.

    Parameters
    ----------
    blocks:
        Ordered list of text blocks.
    sections:
        Section tree from :func:`detect_sections`.
    doc_id:
        Document identifier for provenance.

    Returns
    -------
    list[AmendmentInfo]
        Empty list if the document is not an amendment.
    """
    if not blocks:
        return []

    # Check title / first few blocks for amendment indicators
    preamble_text = "\n".join(
        b.get("text", "") for b in blocks[: min(10, len(blocks))]
    )

    if not _IS_AMENDMENT_RE.search(preamble_text):
        return []

    full_text = "\n".join(b.get("text", "") for b in blocks)

    amendment_number = _infer_amendment_number(preamble_text)

    # Amendment date (from preamble)
    amendment_date = ""
    m = _AMENDMENT_DATE_RE.search(preamble_text)
    if m:
        amendment_date = m.group(1).strip()
    elif dates := list(_DATE_RE.finditer(preamble_text)):
        amendment_date = dates[0].group(0).strip()

    # Original agreement date
    original_date = ""
    m = _ORIGINAL_DATE_RE.search(full_text)
    if m:
        original_date = m.group(1).strip()

    # Sections being amended
    sections_amended = _find_sections_amended(full_text)

    return [
        AmendmentInfo(
            amendment_number=amendment_number,
            amendment_date=amendment_date,
            original_agreement_date=original_date,
            sections_amended=sections_amended,
            source_ref=SourceRef(
                doc_id=doc_id,
                block=0,
                text_snippet=preamble_text[:200],
            ),
        )
    ]
