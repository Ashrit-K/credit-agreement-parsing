"""Extracts financial, negative, and affirmative covenants from
credit agreement text blocks."""

from __future__ import annotations

import re
from typing import Optional

from src.field_patterns import (
    FINANCIAL_COVENANT_PATTERNS,
    NEGATIVE_COVENANT_PATTERNS,
    AFFIRMATIVE_COVENANT_PATTERNS,
    RATIO_PATTERNS,
    TESTING_FREQUENCY_SYNONYMS,
    SECTION_KEYWORDS,
)
from src.models.schema import Covenant, CovenantThreshold, SourceRef, StepDown
from src.parsing.section_detector import SectionNode, find_section_by_keyword

# ---------------------------------------------------------------------------
# Ratio pattern (compiled from centralized RATIO_PATTERNS)
# ---------------------------------------------------------------------------

_RATIO_RE = re.compile(RATIO_PATTERNS[0], re.IGNORECASE)

# ---------------------------------------------------------------------------
# Step-down / step-up pattern
# ---------------------------------------------------------------------------

_STEP_DOWN_RE = re.compile(
    r"(?:step[\s-]*down|reduced?\s+to|decreases?\s+to)\s*[:\s]*"
    r"(\d+\.\d+)\s*(?:to|:)\s*1\.0?0?\s*"
    r"(?:(?:if|when|upon)\s+(.+?)(?:\.|;|$))?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Testing frequency (compiled from centralized TESTING_FREQUENCY_SYNONYMS)
# ---------------------------------------------------------------------------

_TESTING_FREQUENCY_RES: dict[str, re.Pattern[str]] = {}
for _freq_label, _freq_patterns in TESTING_FREQUENCY_SYNONYMS.items():
    _combined = "|".join(f"(?:{p})" for p in _freq_patterns)
    _TESTING_FREQUENCY_RES[_freq_label] = re.compile(_combined, re.IGNORECASE)

# ---------------------------------------------------------------------------
# Period pattern (for thresholds)
# ---------------------------------------------------------------------------

_PERIOD_RE = re.compile(
    r"(?:fiscal\s+(?:quarter|year)\s+ending\s+[\w/,\s]+?\d{4}|"
    r"Q[1-4]\s+\d{4}|"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_text(blocks: list[dict], start: int, end: int) -> str:
    parts: list[str] = []
    for i in range(max(0, start), min(end + 1, len(blocks))):
        parts.append(blocks[i].get("text", ""))
    return "\n".join(parts)


def _extract_thresholds(text: str) -> list[CovenantThreshold]:
    """Extract ratio thresholds paired with time periods."""
    thresholds: list[CovenantThreshold] = []
    ratios = list(_RATIO_RE.finditer(text))
    periods = list(_PERIOD_RE.finditer(text))

    if ratios and periods and len(ratios) == len(periods):
        for r, p in zip(ratios, periods):
            thresholds.append(
                CovenantThreshold(
                    period=p.group(0).strip(),
                    value=float(r.group(1)),
                )
            )
    elif ratios:
        for r in ratios:
            # Find nearest period text before this ratio
            nearby = text[max(0, r.start() - 150): r.start()]
            pm = _PERIOD_RE.search(nearby)
            thresholds.append(
                CovenantThreshold(
                    period=pm.group(0).strip() if pm else "",
                    value=float(r.group(1)),
                )
            )

    return thresholds


def _extract_step_downs(text: str) -> list[StepDown]:
    """Extract step-down provisions."""
    step_downs: list[StepDown] = []
    for m in _STEP_DOWN_RE.finditer(text):
        new_ratio = m.group(1)
        trigger = (m.group(2) or "").strip()
        step_downs.append(
            StepDown(
                trigger=trigger if trigger else "unspecified",
                new_value=f"{new_ratio}:1.00",
            )
        )
    return step_downs


def _detect_testing_frequency(text: str) -> str:
    for freq_label, freq_re in _TESTING_FREQUENCY_RES.items():
        if freq_re.search(text):
            return freq_label
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_covenants(
    blocks: list[dict],
    sections: list[SectionNode],
    doc_id: str = "",
) -> list[Covenant]:
    """Extract covenants from credit agreement *blocks*.

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
    list[Covenant]
    """
    covenants: list[Covenant] = []

    # ---- Financial covenants ----
    fin_sections = []
    for kw in SECTION_KEYWORDS["covenant_financial"]:
        fin_sections += find_section_by_keyword(sections, kw)
    if fin_sections:
        fin_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in fin_sections
        )
    else:
        fin_text = "\n".join(b.get("text", "") for b in blocks)

    for cov_name, metric, pattern in FINANCIAL_COVENANT_PATTERNS:
        if pattern.search(fin_text):
            # Extract the paragraph around the match for threshold analysis
            m = pattern.search(fin_text)
            if m is None:
                continue
            context_start = max(0, m.start() - 200)
            context_end = min(len(fin_text), m.end() + 1500)
            context = fin_text[context_start:context_end]

            thresholds = _extract_thresholds(context)
            step_downs = _extract_step_downs(context)
            freq = _detect_testing_frequency(context)

            covenants.append(
                Covenant(
                    covenant_type="financial",
                    name=cov_name,
                    description=context[:300].strip(),
                    metric=metric,
                    thresholds=thresholds,
                    step_downs=step_downs,
                    testing_frequency=freq,
                    source_ref=SourceRef(
                        doc_id=doc_id,
                        block=fin_sections[0].start_block_idx if fin_sections else None,
                        text_snippet=context[:200],
                    ),
                )
            )

    # ---- Negative covenants ----
    neg_sections = []
    for kw in SECTION_KEYWORDS["covenant_negative"]:
        neg_sections += find_section_by_keyword(sections, kw)
    if neg_sections:
        neg_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in neg_sections
        )
    else:
        neg_text = fin_text  # fallback to full text

    for cov_name, pattern in NEGATIVE_COVENANT_PATTERNS:
        if pattern.search(neg_text):
            m = pattern.search(neg_text)
            if m is None:
                continue
            context_start = max(0, m.start() - 100)
            context_end = min(len(neg_text), m.end() + 500)
            context = neg_text[context_start:context_end]

            covenants.append(
                Covenant(
                    covenant_type="negative",
                    name=cov_name,
                    description=context[:300].strip(),
                    source_ref=SourceRef(
                        doc_id=doc_id,
                        text_snippet=context[:200],
                    ),
                )
            )

    # ---- Affirmative covenants ----
    aff_sections = []
    for kw in SECTION_KEYWORDS["covenant_affirmative"]:
        aff_sections += find_section_by_keyword(sections, kw)
    if aff_sections:
        aff_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in aff_sections
        )
    else:
        aff_text = fin_text

    for cov_name, pattern in AFFIRMATIVE_COVENANT_PATTERNS:
        if pattern.search(aff_text):
            m = pattern.search(aff_text)
            if m is None:
                continue
            context_start = max(0, m.start() - 100)
            context_end = min(len(aff_text), m.end() + 500)
            context = aff_text[context_start:context_end]

            covenants.append(
                Covenant(
                    covenant_type="affirmative",
                    name=cov_name,
                    description=context[:300].strip(),
                    source_ref=SourceRef(
                        doc_id=doc_id,
                        text_snippet=context[:200],
                    ),
                )
            )

    return covenants
