"""Extracts financial, negative, and affirmative covenants from
credit agreement text blocks."""

from __future__ import annotations

import re
from typing import Optional

from src.models.schema import Covenant, CovenantThreshold, SourceRef, StepDown
from src.parsing.section_detector import SectionNode, find_section_by_keyword

# ---------------------------------------------------------------------------
# Ratio pattern (e.g. "4.50 to 1.00", "3.50:1.0")
# ---------------------------------------------------------------------------

_RATIO_RE = re.compile(r"(\d+\.\d+)\s*(?:to|:)\s*1\.0?0?")

# ---------------------------------------------------------------------------
# Financial covenant names and metrics
# ---------------------------------------------------------------------------

_FINANCIAL_COVENANT_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "Maximum Leverage Ratio",
        "leverage_ratio",
        re.compile(
            r"(?:maximum\s+)?(?:total\s+)?leverage\s+ratio|"
            r"(?:total\s+)?(?:net\s+)?debt\s+to\s+(?:ebitda|earnings)",
            re.IGNORECASE,
        ),
    ),
    (
        "Minimum Interest Coverage Ratio",
        "interest_coverage_ratio",
        re.compile(
            r"(?:minimum\s+)?interest\s+coverage\s+ratio",
            re.IGNORECASE,
        ),
    ),
    (
        "Minimum Fixed Charge Coverage Ratio",
        "fixed_charge_coverage_ratio",
        re.compile(
            r"(?:minimum\s+)?fixed\s+charge\s+coverage\s+ratio",
            re.IGNORECASE,
        ),
    ),
    (
        "Maximum Senior Leverage Ratio",
        "senior_leverage_ratio",
        re.compile(
            r"(?:maximum\s+)?senior\s+(?:secured\s+)?leverage\s+ratio",
            re.IGNORECASE,
        ),
    ),
    (
        "Minimum Debt Service Coverage Ratio",
        "debt_service_coverage_ratio",
        re.compile(
            r"(?:minimum\s+)?debt\s+service\s+coverage\s+ratio",
            re.IGNORECASE,
        ),
    ),
    (
        "Minimum Net Worth",
        "net_worth",
        re.compile(
            r"(?:minimum\s+)?(?:tangible\s+)?net\s+worth",
            re.IGNORECASE,
        ),
    ),
    (
        "Maximum Capital Expenditures",
        "capital_expenditures",
        re.compile(
            r"(?:maximum\s+)?capital\s+expenditures?|capex",
            re.IGNORECASE,
        ),
    ),
]

# ---------------------------------------------------------------------------
# Negative covenant categories
# ---------------------------------------------------------------------------

_NEGATIVE_COVENANT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Limitation on Liens", re.compile(r"\bliens?\b", re.IGNORECASE)),
    ("Limitation on Indebtedness", re.compile(r"\bindebtedness\b", re.IGNORECASE)),
    ("Restricted Payments", re.compile(r"\brestricted\s+payments?\b", re.IGNORECASE)),
    ("Limitation on Dividends", re.compile(r"\bdividends?\b", re.IGNORECASE)),
    ("Limitation on Asset Sales", re.compile(r"\basset\s+sales?\b|\bdispositions?\b", re.IGNORECASE)),
    ("Limitation on Investments", re.compile(r"\binvestments?\b", re.IGNORECASE)),
    ("Limitation on Mergers", re.compile(r"\bmergers?\b|\bconsolid", re.IGNORECASE)),
    ("Limitation on Transactions with Affiliates", re.compile(r"\baffiliate\s+transactions?\b|\btransactions?\s+with\s+affiliates?\b", re.IGNORECASE)),
    ("Limitation on Restrictive Agreements", re.compile(r"\brestrictive\s+agreements?\b", re.IGNORECASE)),
]

# ---------------------------------------------------------------------------
# Affirmative covenant categories
# ---------------------------------------------------------------------------

_AFFIRMATIVE_COVENANT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Financial Reporting", re.compile(r"\bfinancial\s+(?:statements?|reports?|reporting)\b", re.IGNORECASE)),
    ("Insurance", re.compile(r"\binsurance\b", re.IGNORECASE)),
    ("Compliance with Laws", re.compile(r"\bcompliance\s+with\s+laws?\b", re.IGNORECASE)),
    ("Maintenance of Properties", re.compile(r"\bmaintenance\s+of\s+propert", re.IGNORECASE)),
    ("Books and Records", re.compile(r"\bbooks\s+and\s+records?\b", re.IGNORECASE)),
    ("Notices", re.compile(r"\bnotices?\b", re.IGNORECASE)),
    ("Use of Proceeds", re.compile(r"\buse\s+of\s+proceeds?\b", re.IGNORECASE)),
]

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
# Testing frequency
# ---------------------------------------------------------------------------

_QUARTERLY_RE = re.compile(r"\bquarter(?:ly)?\b", re.IGNORECASE)
_ANNUAL_RE = re.compile(r"\bannual(?:ly)?\b|\bfiscal\s+year\b", re.IGNORECASE)

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
    if _QUARTERLY_RE.search(text):
        return "quarterly"
    if _ANNUAL_RE.search(text):
        return "annual"
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
    fin_sections = (
        find_section_by_keyword(sections, "FINANCIAL COVENANT")
        + find_section_by_keyword(sections, "FINANCIAL TEST")
        + find_section_by_keyword(sections, "LEVERAGE")
        + find_section_by_keyword(sections, "COVERAGE")
    )
    if fin_sections:
        fin_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in fin_sections
        )
    else:
        fin_text = "\n".join(b.get("text", "") for b in blocks)

    for cov_name, metric, pattern in _FINANCIAL_COVENANT_PATTERNS:
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
    neg_sections = find_section_by_keyword(sections, "NEGATIVE COVENANT")
    if neg_sections:
        neg_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in neg_sections
        )
    else:
        neg_text = fin_text  # fallback to full text

    for cov_name, pattern in _NEGATIVE_COVENANT_PATTERNS:
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
    aff_sections = find_section_by_keyword(sections, "AFFIRMATIVE COVENANT")
    if aff_sections:
        aff_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in aff_sections
        )
    else:
        aff_text = fin_text

    for cov_name, pattern in _AFFIRMATIVE_COVENANT_PATTERNS:
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
