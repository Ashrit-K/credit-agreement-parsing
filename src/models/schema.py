"""Pydantic models defining the JSON output contract for parsed credit agreements."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    """Provenance pointer: doc_id/p{page}/b{block}/l{line}."""
    doc_id: str = ""
    page: Optional[int] = None
    block: Optional[int] = None
    line: Optional[int] = None
    text_snippet: str = ""

    @property
    def provenance_id(self) -> str:
        parts = [self.doc_id]
        if self.page is not None:
            parts.append(f"p{self.page}")
        if self.block is not None:
            parts.append(f"b{self.block}")
        if self.line is not None:
            parts.append(f"l{self.line}")
        return "/".join(parts)


class Party(BaseModel):
    name: str
    role: str = ""  # borrower, lender, administrative_agent, guarantor, etc.
    source_ref: Optional[SourceRef] = None


class PricingGridTier(BaseModel):
    level_name: str = ""       # e.g. "Level I", "Level II"
    leverage_low: Optional[float] = None
    leverage_high: Optional[float] = None
    spread_bps: Optional[float] = None  # basis points
    commitment_fee_bps: Optional[float] = None
    source_ref: Optional[SourceRef] = None


class InterestTerms(BaseModel):
    rate_type: str = ""           # fixed, floating
    benchmark: str = ""           # SOFR, LIBOR, EURIBOR, Prime, etc.
    spread_bps: Optional[float] = None
    floor_pct: Optional[float] = None
    cap_pct: Optional[float] = None
    default_rate_spread_bps: Optional[float] = None
    pik: bool = False
    pricing_grid: list[PricingGridTier] = Field(default_factory=list)
    source_ref: Optional[SourceRef] = None


class AmortizationEntry(BaseModel):
    date: str = ""
    amount: Optional[float] = None
    percentage: Optional[float] = None
    source_ref: Optional[SourceRef] = None


class AmortizationSchedule(BaseModel):
    entries: list[AmortizationEntry] = Field(default_factory=list)
    source_ref: Optional[SourceRef] = None


class Facility(BaseModel):
    facility_type: str = ""       # revolving, term_loan_a, term_loan_b, delayed_draw, bridge
    name: str = ""
    amount: Optional[float] = None
    currency: str = "USD"
    effective_date: str = ""
    maturity_date: str = ""
    interest_terms: Optional[InterestTerms] = None
    amortization: Optional[AmortizationSchedule] = None
    commitment_fee_bps: Optional[float] = None
    ticking_fee_bps: Optional[float] = None
    call_protection: str = ""
    source_ref: Optional[SourceRef] = None


class CovenantThreshold(BaseModel):
    period: str = ""              # e.g. "Q1 2024", "fiscal year ending 12/31/2024"
    value: Optional[float] = None
    source_ref: Optional[SourceRef] = None


class StepDown(BaseModel):
    trigger: str = ""             # e.g. "leverage ratio < 3.50x"
    new_value: str = ""
    source_ref: Optional[SourceRef] = None


class Covenant(BaseModel):
    covenant_type: str = ""       # financial, negative, affirmative
    name: str = ""                # e.g. "Maximum Leverage Ratio", "Minimum Interest Coverage"
    description: str = ""
    metric: str = ""              # e.g. "leverage_ratio", "interest_coverage_ratio"
    thresholds: list[CovenantThreshold] = Field(default_factory=list)
    step_downs: list[StepDown] = Field(default_factory=list)
    testing_frequency: str = ""   # quarterly, annual
    source_ref: Optional[SourceRef] = None


class AmendmentInfo(BaseModel):
    amendment_number: str = ""
    amendment_date: str = ""
    original_agreement_date: str = ""
    parties_to_amendment: list[str] = Field(default_factory=list)
    sections_amended: list[str] = Field(default_factory=list)
    summary_of_changes: str = ""
    source_ref: Optional[SourceRef] = None


class CreditAgreementDocument(BaseModel):
    """Top-level output model for a parsed credit agreement."""
    doc_id: str
    file_name: str
    title: str = ""
    agreement_date: str = ""
    effective_date: str = ""
    parties: list[Party] = Field(default_factory=list)
    facilities: list[Facility] = Field(default_factory=list)
    covenants: list[Covenant] = Field(default_factory=list)
    amendments: list[AmendmentInfo] = Field(default_factory=list)
    total_pages: int = 0
    extraction_metadata: dict = Field(default_factory=dict)
