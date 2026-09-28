"""Tests for path validation and dependency-driven pipeline orchestration."""

from collections.abc import Callable
from pathlib import Path

import pytest

from credit_agreement_extractor.models import ExtractionResult, ExtractionStatus
from credit_agreement_extractor.pipeline import (
    InvalidPdfInputError,
    PartyExtractionPipeline,
)


class RecordingTextExtractor:
    """Small real fake that proves the pipeline forwards the validated path."""

    def __init__(self) -> None:
        self.received_path: Path | None = None

    def extract(self, pdf_path: Path) -> str:
        self.received_path = pdf_path
        return "extracted agreement text"


class RecordingPartyExtractor:
    """Small real fake that proves document text reaches party extraction."""

    def __init__(self) -> None:
        self.received: tuple[str, str] | None = None

    def extract(self, document_name: str, document_text: str) -> ExtractionResult:
        self.received = (document_name, document_text)
        return ExtractionResult(
            document_name=document_name,
            status=ExtractionStatus.COMPLETED,
        )


def write_minimal_pdf(path: Path) -> None:
    """Write enough bytes for an input fixture; v0.1 does not parse them."""
    path.write_bytes(b"%PDF-1.4\n%%EOF\n")


def test_pipeline_coordinates_injected_components(tmp_path: Path) -> None:
    pdf_path = tmp_path / "agreement.pdf"
    write_minimal_pdf(pdf_path)
    text_extractor = RecordingTextExtractor()
    party_extractor = RecordingPartyExtractor()
    pipeline = PartyExtractionPipeline(text_extractor, party_extractor)

    result = pipeline.run(pdf_path)

    assert result.status is ExtractionStatus.COMPLETED
    assert text_extractor.received_path == pdf_path
    assert party_extractor.received == (
        "agreement.pdf",
        "extracted agreement text",
    )


@pytest.mark.parametrize(
    ("path_factory", "message"),
    [
        (lambda root: root / "missing.pdf", "does not exist"),
        (lambda root: root, "regular file"),
    ],
)
def test_pipeline_rejects_invalid_paths(
    tmp_path: Path,
    path_factory: Callable[[Path], Path],
    message: str,
) -> None:
    pipeline = PartyExtractionPipeline(
        RecordingTextExtractor(),
        RecordingPartyExtractor(),
    )

    with pytest.raises(InvalidPdfInputError, match=message):
        pipeline.run(path_factory(tmp_path))


def test_pipeline_rejects_non_pdf_extension(tmp_path: Path) -> None:
    path = tmp_path / "agreement.txt"
    path.write_text("not a PDF")
    pipeline = PartyExtractionPipeline(
        RecordingTextExtractor(),
        RecordingPartyExtractor(),
    )

    with pytest.raises(InvalidPdfInputError, match=r"\.pdf extension"):
        pipeline.run(path)


def test_pipeline_rejects_empty_pdf(tmp_path: Path) -> None:
    path = tmp_path / "empty.PDF"
    path.touch()
    pipeline = PartyExtractionPipeline(
        RecordingTextExtractor(),
        RecordingPartyExtractor(),
    )

    with pytest.raises(InvalidPdfInputError, match="empty"):
        pipeline.run(path)
