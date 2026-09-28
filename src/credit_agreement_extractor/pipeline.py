"""Path validation and orchestration for the party-extraction pipeline."""

from pathlib import Path

from .models import ExtractionResult, ExtractionStatus
from .protocols import PartyExtractor, PdfTextExtractor


class InvalidPdfInputError(ValueError):
    """Raised when the public input cannot safely represent a source PDF."""


def _validated_pdf_path(pdf_path: str | Path) -> Path:
    """Normalize and validate input without modifying the source document."""
    path = Path(pdf_path).expanduser()
    if not path.exists():
        raise InvalidPdfInputError(f"PDF path does not exist: {path}")
    if not path.is_file():
        raise InvalidPdfInputError(f"PDF path is not a regular file: {path}")
    if path.suffix.lower() != ".pdf":
        raise InvalidPdfInputError(f"PDF path must use a .pdf extension: {path}")
    if path.stat().st_size == 0:
        raise InvalidPdfInputError(f"PDF file is empty: {path}")
    return path


class ScaffoldPdfTextExtractor:
    """Non-fabricating boundary used before a PDF parser is selected.

    Returning an empty string is intentional: the following party extractor is
    also a scaffold and returns an explicit status instead of pretending that
    document content has been parsed.
    """

    def extract(self, pdf_path: Path) -> str:
        """Acknowledge the validated path without reading or transforming it."""
        return ""


class ScaffoldPartyExtractor:
    """Return a transparent scaffold result with no invented legal entities."""

    def extract(self, document_name: str, document_text: str) -> ExtractionResult:
        """Return the stable JSON shape while substantive extraction is absent."""
        return ExtractionResult(
            document_name=document_name,
            status=ExtractionStatus.NOT_IMPLEMENTED,
        )


class PartyExtractionPipeline:
    """Coordinate independently replaceable PDF and party extraction stages."""

    def __init__(
        self,
        text_extractor: PdfTextExtractor,
        party_extractor: PartyExtractor,
    ) -> None:
        self._text_extractor = text_extractor
        self._party_extractor = party_extractor

    def run(self, pdf_path: str | Path) -> ExtractionResult:
        """Validate one source path and return a validated extraction result."""
        path = _validated_pdf_path(pdf_path)
        document_text = self._text_extractor.extract(path)
        return self._party_extractor.extract(path.name, document_text)
