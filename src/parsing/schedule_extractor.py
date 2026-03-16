"""Extracts amortization schedules, call protection terms, and ticking
fee terms from schedule/exhibit sections of credit agreements."""

from __future__ import annotations

import re
from typing import Optional

from src.field_patterns import (
    CALL_PROTECTION_SYNONYMS,
    TICKING_FEE_SYNONYMS,
    AMOUNT_PATTERNS,
    AMOUNT_MULTIPLIERS,
    DATE_RE,
    SECTION_KEYWORDS,
)
from src.models.schema import (
    AmortizationEntry,
    AmortizationSchedule,
    SourceRef,
)
from src.parsing.section_detector import SectionNode, find_section_by_keyword
from src.parsing.table_parser import parse_amortization_table

# ---------------------------------------------------------------------------
# Call protection patterns (compiled from centralized synonyms)
# ---------------------------------------------------------------------------

_CALL_PROTECTION_RE = re.compile(
    "|".join(f"(?:{p})" for p in CALL_PROTECTION_SYNONYMS),
    re.IGNORECASE,
)

_CALL_PERIOD_RE = re.compile(
    r"(\d+)\s*(?:months?|years?)\s*(?:after|from|following)\s+(?:the\s+)?(?:closing|effective)\s+date",
    re.IGNORECASE,
)

_CALL_PREMIUM_RE = re.compile(
    r"(?:premium|price)\s+(?:of|equal\s+to)\s+(\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Ticking fee patterns
# ---------------------------------------------------------------------------

_TICKING_FEE_RE = re.compile(
    "|".join(f"(?:{p})" for p in TICKING_FEE_SYNONYMS),
    re.IGNORECASE,
)

_TICKING_FEE_RATE_RE = re.compile(
    r"ticking\s+fee.*?(\d+(?:\.\d+)?)\s*(?:%|basis\s+points|bps)",
    re.IGNORECASE,
)

_TICKING_FEE_START_RE = re.compile(
    r"ticking\s+fee.*?(?:commencing|beginning|starting)\s+(\d+)\s*(?:days?|business\s+days?)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Amortization patterns (non-table)
# ---------------------------------------------------------------------------

_AMORT_INLINE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*%\s+(?:of\s+)?(?:the\s+)?(?:original|initial|aggregate)\s+"
    r"(?:principal\s+)?(?:amount|balance)",
    re.IGNORECASE,
)

_AMORT_AMOUNT_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:million|mn|billion|bn)?",
    re.IGNORECASE,
)

_DATE_RE = DATE_RE

_MULTIPLIER = AMOUNT_MULTIPLIERS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_text(blocks: list[dict], start: int, end: int) -> str:
    parts: list[str] = []
    for i in range(max(0, start), min(end + 1, len(blocks))):
        parts.append(blocks[i].get("text", ""))
    return "\n".join(parts)


def _parse_amount(text: str) -> Optional[float]:
    m = _AMORT_AMOUNT_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(",", "")
    value = float(raw)
    # Check for multiplier word after the number
    after = text[m.end(): m.end() + 20].strip().lower()
    for suffix, mult in _MULTIPLIER.items():
        if after.startswith(suffix):
            value *= mult
            break
    return value


def _extract_call_protection(text: str) -> dict:
    """Extract call protection details from text."""
    if not _CALL_PROTECTION_RE.search(text):
        return {}

    result: dict = {"has_call_protection": True}

    m = _CALL_PERIOD_RE.search(text)
    if m:
        result["non_call_period"] = f"{m.group(1)} {m.group(0).split()[-1]}"

    m = _CALL_PREMIUM_RE.search(text)
    if m:
        result["premium_pct"] = float(m.group(1))

    # Detect type
    text_lower = text.lower()
    if "make-whole" in text_lower or "make whole" in text_lower:
        result["type"] = "make_whole"
    elif "soft call" in text_lower:
        result["type"] = "soft_call"
    elif "hard call" in text_lower:
        result["type"] = "hard_call"
    else:
        result["type"] = "general"

    # Extract snippet for context
    m2 = _CALL_PROTECTION_RE.search(text)
    if m2:
        start = max(0, m2.start() - 50)
        end = min(len(text), m2.end() + 300)
        result["description"] = text[start:end].strip()

    return result


def _extract_ticking_fees(text: str) -> dict:
    """Extract ticking fee details from text."""
    if not _TICKING_FEE_RE.search(text):
        return {}

    result: dict = {"has_ticking_fee": True}

    m = _TICKING_FEE_RATE_RE.search(text)
    if m:
        raw = float(m.group(1))
        after = text[m.end() - 20: m.end()].lower()
        if "basis" in after or "bps" in after:
            result["rate_bps"] = raw
        else:
            result["rate_bps"] = raw * 100  # convert % to bps

    m = _TICKING_FEE_START_RE.search(text)
    if m:
        result["starts_after_days"] = int(m.group(1))

    m2 = _TICKING_FEE_RE.search(text)
    if m2:
        start = max(0, m2.start() - 50)
        end = min(len(text), m2.end() + 300)
        result["description"] = text[start:end].strip()

    return result


def _extract_inline_amortization(text: str) -> list[AmortizationEntry]:
    """Extract amortization entries from prose (non-table) text."""
    entries: list[AmortizationEntry] = []

    # Look for date + amount/percentage pairs
    date_matches = list(_DATE_RE.finditer(text))
    for dm in date_matches:
        # Search nearby text for amount or percentage
        nearby = text[dm.start(): min(len(text), dm.end() + 200)]

        amount = _parse_amount(nearby)
        pct_m = _AMORT_INLINE_RE.search(nearby)
        percentage = float(pct_m.group(1)) if pct_m else None

        if amount is not None or percentage is not None:
            entries.append(
                AmortizationEntry(
                    date=dm.group(0).strip(),
                    amount=amount,
                    percentage=percentage,
                )
            )

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_schedules(
    blocks: list[dict],
    sections: list[SectionNode],
    tables: list[list[list[str]]],
    doc_id: str = "",
) -> dict:
    """Extract schedule-related information from credit agreement blocks.

    Parameters
    ----------
    blocks:
        Ordered list of text blocks.
    sections:
        Section tree from :func:`detect_sections`.
    tables:
        List of tables (each a list[list[str]]) from pdfplumber.
    doc_id:
        Document identifier for provenance.

    Returns
    -------
    dict
        Keys: ``amortization_schedules``, ``call_protection``,
        ``ticking_fees``.
    """
    result: dict = {
        "amortization_schedules": [],
        "call_protection": {},
        "ticking_fees": {},
    }

    # --- Amortization schedules ---
    schedule_sections = []
    for kw in SECTION_KEYWORDS["schedule"]:
        schedule_sections += find_section_by_keyword(sections, kw)

    # From tables
    amort_tables: list[list[list[str]]] = []
    for table in tables:
        if not table:
            continue
        header_text = " ".join(cell or "" for cell in table[0]).lower()
        if any(kw in header_text for kw in ("amortization", "repayment", "installment", "payment", "date", "amount")):
            amort_tables.append(table)

    all_entries: list[AmortizationEntry] = []
    for table in amort_tables:
        all_entries.extend(parse_amortization_table(table))

    # From prose in schedule sections
    if schedule_sections:
        for sec in schedule_sections:
            sec_text = _collect_text(blocks, sec.start_block_idx, sec.end_block_idx)
            all_entries.extend(_extract_inline_amortization(sec_text))

    if all_entries:
        result["amortization_schedules"] = [
            AmortizationSchedule(
                entries=all_entries,
                source_ref=SourceRef(doc_id=doc_id, text_snippet="Amortization schedule"),
            )
        ]

    # --- Call protection ---
    full_text = "\n".join(b.get("text", "") for b in blocks)

    # Also look in specific sections
    prepay_sections = []
    for kw in SECTION_KEYWORDS["prepayment"]:
        prepay_sections += find_section_by_keyword(sections, kw)
    if prepay_sections:
        prepay_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in prepay_sections
        )
    else:
        prepay_text = full_text

    result["call_protection"] = _extract_call_protection(prepay_text)

    # --- Ticking fees ---
    fee_sections = []
    for kw in SECTION_KEYWORDS["fees"]:
        fee_sections += find_section_by_keyword(sections, kw)
    if fee_sections:
        fee_text = "\n".join(
            _collect_text(blocks, s.start_block_idx, s.end_block_idx)
            for s in fee_sections
        )
    else:
        fee_text = full_text

    result["ticking_fees"] = _extract_ticking_fees(fee_text)

    return result
