"""Parses tables extracted by pdfplumber into structured data models
(pricing grids, amortization schedules, covenant tables)."""

from __future__ import annotations

import re
from typing import Optional

from src.models.schema import AmortizationEntry, PricingGridTier, SourceRef

# ---------------------------------------------------------------------------
# Table classification keywords
# ---------------------------------------------------------------------------

_PRICING_KEYWORDS = re.compile(
    r"(?:pricing|spread|margin|applicable\s+rate|commitment\s+fee|leverage)",
    re.IGNORECASE,
)
_AMORTIZATION_KEYWORDS = re.compile(
    r"(?:amortization|repayment|installment|principal\s+payment|scheduled\s+payment)",
    re.IGNORECASE,
)
_COVENANT_KEYWORDS = re.compile(
    r"(?:covenant|ratio|leverage|coverage|test|threshold|compliance)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public: classify_table
# ---------------------------------------------------------------------------

def classify_table(
    table: list[list[str]],
    surrounding_text: str = "",
) -> str:
    """Classify a pdfplumber table by examining its header row and
    the text surrounding the table.

    Parameters
    ----------
    table:
        A pdfplumber table represented as list[list[str]].
    surrounding_text:
        Text appearing near the table in the document.

    Returns
    -------
    str
        One of ``"pricing_grid"``, ``"amortization"``, ``"covenant"``,
        or ``"unknown"``.
    """
    # Build a single string from the header row + surrounding text
    header_text = " ".join(cell or "" for cell in table[0]) if table else ""
    combined = f"{header_text} {surrounding_text}"

    if _PRICING_KEYWORDS.search(combined):
        return "pricing_grid"
    if _AMORTIZATION_KEYWORDS.search(combined):
        return "amortization"
    if _COVENANT_KEYWORDS.search(combined):
        return "covenant"
    return "unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"[\d,]+(?:\.\d+)?")
_PERCENT_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*%")
_BPS_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:bps|basis\s*points)", re.IGNORECASE)
_LEVERAGE_RANGE_RE = re.compile(
    r"([<>≤≥]?\s*[\d.]+)\s*(?:to|:|-|–)\s*([<>≤≥]?\s*[\d.]+)"
)
_LEVERAGE_SINGLE_RE = re.compile(
    r"([<>≤≥])\s*([\d.]+)"
)
_DATE_LIKE_RE = re.compile(
    r"(?:\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def _to_float(s: str) -> Optional[float]:
    """Parse a number string, stripping commas."""
    s = (s or "").strip().replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _extract_bps(cell: str) -> Optional[float]:
    """Extract a basis-point value from a table cell."""
    m = _BPS_RE.search(cell)
    if m:
        return _to_float(m.group(1))
    m = _PERCENT_RE.search(cell)
    if m:
        val = _to_float(m.group(1))
        return val * 100 if val is not None else None
    # Bare number (assume bps if in pricing context)
    m = _NUMBER_RE.search(cell)
    if m:
        return _to_float(m.group(0))
    return None


# ---------------------------------------------------------------------------
# Public: parse_pricing_grid
# ---------------------------------------------------------------------------

def parse_pricing_grid(table: list[list[str]]) -> list[PricingGridTier]:
    """Parse a pricing-grid table into :class:`PricingGridTier` objects.

    Expected structure (rows after header):
        Level name | Leverage range | Spread (bps or %) | Commitment fee

    Parameters
    ----------
    table:
        list[list[str]] from pdfplumber.

    Returns
    -------
    list[PricingGridTier]
    """
    if len(table) < 2:
        return []

    header = [c.lower() if c else "" for c in table[0]]

    # Heuristically locate columns
    level_col: Optional[int] = None
    leverage_col: Optional[int] = None
    spread_col: Optional[int] = None
    fee_col: Optional[int] = None

    for i, h in enumerate(header):
        if "level" in h or "tier" in h:
            level_col = i
        elif "leverage" in h or "ratio" in h:
            leverage_col = i
        elif "spread" in h or "margin" in h or "rate" in h:
            spread_col = i
        elif "commitment" in h or "fee" in h:
            fee_col = i

    tiers: list[PricingGridTier] = []
    for row_idx, row in enumerate(table[1:], start=1):
        if not any(cell and cell.strip() for cell in row):
            continue  # skip empty rows

        level_name = row[level_col].strip() if level_col is not None and level_col < len(row) else f"Tier {row_idx}"

        leverage_low: Optional[float] = None
        leverage_high: Optional[float] = None
        if leverage_col is not None and leverage_col < len(row):
            cell = row[leverage_col] or ""
            m = _LEVERAGE_RANGE_RE.search(cell)
            if m:
                leverage_low = _to_float(re.sub(r"[<>≤≥]", "", m.group(1)))
                leverage_high = _to_float(re.sub(r"[<>≤≥]", "", m.group(2)))
            else:
                m2 = _LEVERAGE_SINGLE_RE.search(cell)
                if m2:
                    val = _to_float(m2.group(2))
                    if ">" in m2.group(1) or "≥" in m2.group(1):
                        leverage_low = val
                    else:
                        leverage_high = val

        spread_bps = _extract_bps(row[spread_col]) if spread_col is not None and spread_col < len(row) else None
        commitment_fee = _extract_bps(row[fee_col]) if fee_col is not None and fee_col < len(row) else None

        tiers.append(
            PricingGridTier(
                level_name=level_name,
                leverage_low=leverage_low,
                leverage_high=leverage_high,
                spread_bps=spread_bps,
                commitment_fee_bps=commitment_fee,
            )
        )

    return tiers


# ---------------------------------------------------------------------------
# Public: parse_amortization_table
# ---------------------------------------------------------------------------

def parse_amortization_table(table: list[list[str]]) -> list[AmortizationEntry]:
    """Parse an amortization schedule table.

    Expected structure (rows after header):
        Date | Amount or Percentage

    Parameters
    ----------
    table:
        list[list[str]] from pdfplumber.

    Returns
    -------
    list[AmortizationEntry]
    """
    if len(table) < 2:
        return []

    header = [c.lower() if c else "" for c in table[0]]

    date_col: Optional[int] = None
    amount_col: Optional[int] = None
    pct_col: Optional[int] = None

    for i, h in enumerate(header):
        if "date" in h or "period" in h or "payment" in h and date_col is None:
            date_col = i
        elif "amount" in h or "$" in h or "principal" in h:
            amount_col = i
        elif "percent" in h or "%" in h:
            pct_col = i

    # Fallback column assignment
    if date_col is None and len(header) >= 1:
        date_col = 0
    if amount_col is None and pct_col is None and len(header) >= 2:
        amount_col = 1

    entries: list[AmortizationEntry] = []
    for row in table[1:]:
        if not any(cell and cell.strip() for cell in row):
            continue

        date_str = ""
        if date_col is not None and date_col < len(row):
            date_str = (row[date_col] or "").strip()

        amount: Optional[float] = None
        if amount_col is not None and amount_col < len(row):
            raw = (row[amount_col] or "").replace("$", "").replace(",", "").strip()
            amount = _to_float(raw)

        percentage: Optional[float] = None
        if pct_col is not None and pct_col < len(row):
            m = _PERCENT_RE.search(row[pct_col] or "")
            if m:
                percentage = _to_float(m.group(1))

        entries.append(
            AmortizationEntry(
                date=date_str,
                amount=amount,
                percentage=percentage,
            )
        )

    return entries
