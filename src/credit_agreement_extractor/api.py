"""Stable Python entry point for credit-agreement party extraction."""

from pathlib import Path
from typing import Any
from .tracing import traced

from .pipeline import (
    PartyExtractionPipeline,
    ScaffoldPartyExtractor,
    ScaffoldPdfTextExtractor,
)


@traced('party_scaffold')
def extract_parties(pdf_path: str | Path, *, debug: bool = False,
                    run_id: str | None = None, trace_root: str | Path = 'tmp/runs') -> dict[str, Any]:
    """Return validated, JSON-serializable party data for one PDF.

    The default stages are intentionally non-substantive in v0.1. They establish
    the public contract and return ``not_implemented`` without guessing facts.
    """
    pipeline = PartyExtractionPipeline(
        text_extractor=ScaffoldPdfTextExtractor(),
        party_extractor=ScaffoldPartyExtractor(),
    )
    result = pipeline.run(pdf_path)
    return result.model_dump(mode="json")
