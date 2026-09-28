"""Replaceable boundaries around parsing and model-based extraction.

Protocols keep orchestration independent from a PDF library or model vendor.
Tests can provide small in-process fakes, and future implementations can add
OCR or OpenCode-backed extraction without changing ``extract_parties``.
"""

from pathlib import Path
from typing import Any, Protocol

from .models import ExtractionResult


class PdfTextExtractor(Protocol):
    """Convert a source PDF into text suitable for party extraction."""

    def extract(self, pdf_path: Path) -> str:
        """Return document text for one validated PDF path."""
        ...


class PartyExtractor(Protocol):
    """Convert document text into validated borrower/lender information."""

    def extract(self, document_name: str, document_text: str) -> ExtractionResult:
        """Return the structured result for one document."""
        ...


class LlmClient(Protocol):
    """Provider-neutral boundary for future structured model generation."""

    def generate_structured(
        self,
        *,
        prompt: str,
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return provider output that conforms to the supplied JSON schema."""
        ...
