"""Tests for golden-set label storage and expected-output export."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.schema import AmendmentInfo, Covenant, Facility, Party, SourceRef
from src.evaluation.golden_set_labels import (
    export_expected_outputs,
    get_label_path,
    load_or_create_label,
    prefill_label_payload,
)


def test_prefill_label_payload_populates_provenance_fields():
    doc = SimpleNamespace(
        doc_id="doc-123",
        file_name="sample.pdf",
        parties=[
            Party(
                name="Borrower Corp",
                role="borrower",
                source_ref=SourceRef(
                    doc_id="doc-123",
                    page=3,
                    block=5,
                    line=2,
                    text_snippet="Borrower Corp (the \"Borrower\")",
                ),
            )
        ],
        facilities=[
            Facility(
                facility_type="revolving",
                name="Revolving Credit Facility",
                amount=1000000.0,
                currency="USD",
                source_ref=SourceRef(doc_id="doc-123", page=7, block=2, line=1, text_snippet="Revolving facility"),
            )
        ],
        covenants=[
            Covenant(
                covenant_type="negative",
                name="Limitation on Liens",
                metric="liens",
                source_ref=SourceRef(doc_id="doc-123", page=11, block=1, line=3, text_snippet="No liens"),
            )
        ],
        amendments=[
            AmendmentInfo(
                amendment_number="1",
                amendment_date="January 1, 2025",
                source_ref=SourceRef(doc_id="doc-123", page=14, block=4, line=2, text_snippet="First amendment"),
            )
        ],
    )

    payload = prefill_label_payload(doc)

    assert payload["file_name"] == "sample.pdf"
    assert payload["doc_id"] == "doc-123"
    assert payload["parties"][0]["page"] == 3
    assert payload["parties"][0]["block"] == 5
    assert payload["parties"][0]["line"] == 2
    assert payload["parties"][0]["provenance_id"] == "doc-123/p3/b5/l2"
    assert payload["parties"][0]["decision"] == "pending"
    assert payload["facilities"][0]["facility_type"] == "revolving"
    assert payload["covenants"][0]["name"] == "Limitation on Liens"
    assert payload["amendments"][0]["amendment_number"] == "1"


def test_load_or_create_label_creates_file_with_prefill(tmp_path):
    labels_dir = tmp_path / "labels"
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    doc = SimpleNamespace(
        doc_id="doc-456",
        file_name="sample.pdf",
        parties=[Party(name="Lender Bank", role="lender", source_ref=SourceRef(doc_id="doc-456", page=2, block=1, line=1))],
        facilities=[],
        covenants=[],
        amendments=[],
    )

    def _fake_process_document(path, save_output=False):  # noqa: ARG001
        return doc, object()

    payload = load_or_create_label(
        file_name="sample.pdf",
        pdf_path=pdf_path,
        labels_dir=labels_dir,
        process_fn=_fake_process_document,
    )
    label_path = get_label_path("sample.pdf", labels_dir=labels_dir)

    assert label_path.exists()
    assert payload["doc_id"] == "doc-456"
    assert payload["parties"][0]["name"] == "Lender Bank"


def test_export_expected_outputs_uses_only_approved_rows(tmp_path):
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()
    output_path = tmp_path / "expected_outputs.json"

    label_path = labels_dir / "sample.json"
    label_path.write_text(
        json.dumps(
            {
                "file_name": "sample.pdf",
                "doc_id": "doc-789",
                "expected_counts": {"facilities": 2, "amendments": 1},
                "parties": [
                    {"name": "Borrower Corp", "role": "borrower", "decision": "approved"},
                    {"name": "Noise Party", "role": "lender", "decision": "rejected"},
                ],
            }
        )
    )

    exported = export_expected_outputs(labels_dir=labels_dir, output_path=output_path)

    assert output_path.exists()
    assert exported["documents"][0]["file_name"] == "sample.pdf"
    assert exported["documents"][0]["expected_parties"] == [
        {"name": "Borrower Corp", "role": "borrower"}
    ]
    assert exported["documents"][0]["expected_counts"] == {"facilities": 2, "amendments": 1}
