"""Extracts facility details (type, amount, dates, tranches) from
credit agreement text blocks, typically in ARTICLE II sections."""

from __future__ import annotations

import re
from typing import Optional

from src.field_patterns import (
    AMOUNT_MULTIPLIERS,
    AMOUNT_PATTERNS,
    DATE_RE,
    EFFECTIVE_RE,
    FACILITY_TYPE_PATTERNS,
    MATURITY_RE,
    SECTION_KEYWORDS,
)
from src.models.schema import Facility, SourceRef
from src.parsing.section_detector import SectionNode, find_section_by_keyword

# ---------------------------------------------------------------------------
# Compiled patterns derived from centralized field_patterns
# ---------------------------------------------------------------------------

_FACILITY_TYPE_PATTERNS = FACILITY_TYPE_PATTERNS

_AMOUNT_RE = re.compile(AMOUNT_PATTERNS[0], re.IGNORECASE)
_MULTIPLIER = AMOUNT_MULTIPLIERS

_DATE_RE = DATE_RE
_MATURITY_RE = MATURITY_RE
_EFFECTIVE_RE = EFFECTIVE_RE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_amount(text: str) -> Optional[float]:
    """Find the first dollar amount in *text* and return it as a float."""
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    value = float(raw)
    suffix = (m.group(2) or "").lower()
    if suffix in _MULTIPLIER:
        value *= _MULTIPLIER[suffix]
    return value


def _detect_facility_type(text: str) -> str:
    """Return the first matching facility type label."""
    for ftype, pattern in _FACILITY_TYPE_PATTERNS:
        if pattern.search(text):
            return ftype
    return "unknown"


def _find_date(pattern: re.Pattern[str], text: str) -> str:
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _collect_text(blocks: list[dict], start: int, end: int) -> str:
    """Concatenate block texts within a range."""
    parts: list[str] = []
    for i in range(max(0, start), min(end + 1, len(blocks))):
        parts.append(blocks[i].get("text", ""))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_facilities(
    blocks: list[dict],
    sections: list[SectionNode],
    doc_id: str = "",
) -> list[Facility]:
    """Extract one or more :class:`Facility` objects from *blocks*.

    The function first looks in ARTICLE II sections (where facility terms
    are conventionally placed) and falls back to scanning all blocks.

    Parameters
    ----------
    blocks:
        Ordered list of text blocks.
    sections:
        Section tree returned by :func:`detect_sections`.
    doc_id:
        Document identifier for provenance.

    Returns
    -------
    list[Facility]
        One :class:`Facility` per detected tranche.
    """
    # Determine focus regions
    candidate_sections = []
    for kw in SECTION_KEYWORDS["facility"]:
        candidate_sections += find_section_by_keyword(sections, kw)

    if candidate_sections:
        focus_ranges = [
            (s.start_block_idx, s.end_block_idx) for s in candidate_sections
        ]
    else:
        # Fallback: scan everything
        focus_ranges = [(0, len(blocks) - 1)]

    # Merge text from all focus ranges
    focus_texts: list[tuple[str, int, int]] = []
    for start, end in focus_ranges:
        text = _collect_text(blocks, start, end)
        focus_texts.append((text, start, end))

    facilities: list[Facility] = []
    seen_types: set[str] = set()

    for text, start_idx, end_idx in focus_texts:
        # Split on paragraph boundaries to find per-tranche descriptions
        paragraphs = re.split(r"\n{2,}", text)
        for para in paragraphs:
            ftype = _detect_facility_type(para)
            if ftype == "unknown":
                continue
            # Avoid duplicate facility types within same scan
            amount = _parse_amount(para)
            tranche_key = (ftype, amount)
            if tranche_key in seen_types:
                continue
            seen_types.add(tranche_key)

            # Extract dates from entire focus text (dates may not be in same paragraph)
            maturity = _find_date(_MATURITY_RE, text)
            effective = _find_date(_EFFECTIVE_RE, text)

            facilities.append(
                Facility(
                    facility_type=ftype,
                    name=para.split("\n", 1)[0][:120].strip(),
                    amount=amount,
                    currency="USD",
                    effective_date=effective,
                    maturity_date=maturity,
                    source_ref=SourceRef(
                        doc_id=doc_id,
                        block=start_idx,
                        text_snippet=para[:200],
                    ),
                )
            )

    # If no structured detection succeeded, try a broad sweep
    if not facilities:
        full_text = "\n".join(b.get("text", "") for b in blocks)
        ftype = _detect_facility_type(full_text)
        amount = _parse_amount(full_text)
        if ftype != "unknown" or amount is not None:
            facilities.append(
                Facility(
                    facility_type=ftype if ftype != "unknown" else "",
                    amount=amount,
                    currency="USD",
                    effective_date=_find_date(_EFFECTIVE_RE, full_text),
                    maturity_date=_find_date(_MATURITY_RE, full_text),
                    source_ref=SourceRef(doc_id=doc_id, text_snippet=full_text[:200]),
                )
            )

    return facilities
