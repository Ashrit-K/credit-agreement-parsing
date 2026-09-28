"""Validated domain models for party extraction.

These models define the first reviewable JSON contract. They deliberately keep
unknown ownership as ``None`` and use empty collections only for facts that have
not been extracted. Later pipeline stages can add evidence without changing the
public function's basic return shape.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class ExtractionStatus(StrEnum):
    """Lifecycle states exposed in the JSON result."""

    NOT_IMPLEMENTED = "not_implemented"
    COMPLETED = "completed"
    FAILED = "failed"


class Evidence(BaseModel):
    """A concise source location supporting a future extracted fact."""

    page: int | None = None
    section: str | None = None
    excerpt: str


class ParentCompany(BaseModel):
    """A parent entity and the evidenced relationship to the named party."""

    name: str
    relationship: str


class Party(BaseModel):
    """A borrower, lender, agent, arranger, or related contractual party."""

    name: str
    role: str
    is_primary: bool = False
    parent: ParentCompany | None = None
    evidence: list[Evidence] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Complete JSON boundary returned for one source PDF."""

    document_name: str
    status: ExtractionStatus
    borrowers: list[Party] = Field(default_factory=list)
    lenders: list[Party] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
