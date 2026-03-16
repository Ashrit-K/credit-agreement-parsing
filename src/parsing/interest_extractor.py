"""Extracts interest rate terms (benchmark, spread, floor, PIK) from
credit agreement text blocks."""

from __future__ import annotations

import re
from typing import Optional

from src.field_patterns import (
    BENCHMARK_PATTERNS,
    FLOOR_SYNONYMS,
    PIK_SYNONYMS,
    SECTION_KEYWORDS,
    SPREAD_SYNONYMS,
)
from src.models.schema import InterestTerms, SourceRef
from src.parsing.section_detector import SectionNode, find_section_by_keyword

# ---------------------------------------------------------------------------
# Compiled patterns derived from centralized field_patterns
# ---------------------------------------------------------------------------

_BENCHMARK_PATTERNS = BENCHMARK_PATTERNS

# Spread: first two synonyms are pct and bps variants
_SPREAD_PCT_RE = re.compile(SPREAD_SYNONYMS[0], re.IGNORECASE)
_SPREAD_BPS_RE = re.compile(SPREAD_SYNONYMS[1], re.IGNORECASE)

# Floor: pct (index 0), bps (index 1), zero-reference (index 3 — "benchmark floor")
_FLOOR_PCT_RE = re.compile(FLOOR_SYNONYMS[0], re.IGNORECASE)
_FLOOR_BPS_RE = re.compile(FLOOR_SYNONYMS[1], re.IGNORECASE)
_FLOOR_ZERO_RE = re.compile(FLOOR_SYNONYMS[3], re.IGNORECASE)

# PIK
_PIK_RE = re.compile(
    "|".join(f"(?:{p})" for p in PIK_SYNONYMS), re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Default rate
# ---------------------------------------------------------------------------

_DEFAULT_RATE_RE = re.compile(
    r"default\s+rate.*?(?:plus|add|\+)\s+(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_benchmarks(text: str) -> list[str]:
    """Return a list of detected benchmark names (in order of priority)."""
    found: list[str] = []
    for name, pat in _BENCHMARK_PATTERNS:
        if pat.search(text):
            found.append(name)
    return found


def _extract_spread_bps(text: str) -> Optional[float]:
    """Return spread in basis points."""
    m = _SPREAD_BPS_RE.search(text)
    if m:
        return float(m.group(1))
    m = _SPREAD_PCT_RE.search(text)
    if m:
        return float(m.group(1)) * 100
    return None


def _extract_floor_pct(text: str) -> Optional[float]:
    """Return floor as a percentage."""
    m = _FLOOR_PCT_RE.search(text)
    if m:
        return float(m.group(1))
    m = _FLOOR_BPS_RE.search(text)
    if m:
        return float(m.group(1)) / 100.0
    if _FLOOR_ZERO_RE.search(text):
        return 0.0
    return None


def _extract_default_spread_bps(text: str) -> Optional[float]:
    m = _DEFAULT_RATE_RE.search(text)
    if m:
        return float(m.group(1)) * 100
    return None


def _collect_text(blocks: list[dict], start: int, end: int) -> str:
    parts: list[str] = []
    for i in range(max(0, start), min(end + 1, len(blocks))):
        parts.append(blocks[i].get("text", ""))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_interest_terms(
    blocks: list[dict],
    sections: list[SectionNode],
    doc_id: str = "",
) -> list[InterestTerms]:
    """Extract interest rate terms from credit agreement *blocks*.

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
    list[InterestTerms]
        One per distinct benchmark detected.
    """
    # Determine focus regions (interest-related sections)
    interest_sections = []
    for kw in SECTION_KEYWORDS["interest"]:
        interest_sections += find_section_by_keyword(sections, kw)

    if interest_sections:
        text_parts: list[str] = []
        first_block: Optional[int] = None
        for sec in interest_sections:
            text_parts.append(
                _collect_text(blocks, sec.start_block_idx, sec.end_block_idx)
            )
            if first_block is None:
                first_block = sec.start_block_idx
        focus_text = "\n".join(text_parts)
    else:
        focus_text = "\n".join(b.get("text", "") for b in blocks)
        first_block = 0

    benchmarks = _detect_benchmarks(focus_text)
    if not benchmarks:
        # Return empty if no benchmark found at all
        return []

    spread_bps = _extract_spread_bps(focus_text)
    floor_pct = _extract_floor_pct(focus_text)
    is_pik = bool(_PIK_RE.search(focus_text))
    default_spread = _extract_default_spread_bps(focus_text)

    results: list[InterestTerms] = []
    for benchmark in benchmarks:
        results.append(
            InterestTerms(
                rate_type="floating",
                benchmark=benchmark,
                spread_bps=spread_bps,
                floor_pct=floor_pct,
                pik=is_pik,
                default_rate_spread_bps=default_spread,
                source_ref=SourceRef(
                    doc_id=doc_id,
                    block=first_block,
                    text_snippet=focus_text[:200],
                ),
            )
        )

    return results
