"""Tests for the stable Python entry point exposed to callers."""

import json
from pathlib import Path

from credit_agreement_extractor import extract_parties


def test_extract_parties_returns_json_serializable_scaffold(tmp_path: Path) -> None:
    pdf_path = tmp_path / "credit_agreement.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    result = extract_parties(pdf_path)
    round_tripped = json.loads(json.dumps(result))

    assert round_tripped == {
        "document_name": "credit_agreement.pdf",
        "status": "not_implemented",
        "borrowers": [],
        "lenders": [],
        "errors": [],
    }


def test_extract_parties_accepts_string_paths(tmp_path: Path) -> None:
    pdf_path = tmp_path / "agreement.PDF"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")

    result = extract_parties(str(pdf_path))

    assert result["document_name"] == "agreement.PDF"
