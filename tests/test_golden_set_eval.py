"""Tests for golden-set manifest loading and evaluation reporting."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models.schema import Party
from src.evaluation.golden_set_eval import (
    evaluate_manifest_entries,
    load_manifest,
)


def test_load_manifest_returns_entries(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "file_name": "a.pdf",
                        "focus": ["baseline"],
                        "expected": {"min_parties": 1, "max_parties": 5},
                    }
                ]
            }
        )
    )

    entries = load_manifest(manifest_path)

    assert len(entries) == 1
    assert entries[0].file_name == "a.pdf"
    assert entries[0].focus == ["baseline"]
    assert entries[0].expected["max_parties"] == 5


def test_evaluator_flags_manifest_threshold_and_quality_anomalies(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "file_name": "loan.pdf",
                        "focus": ["party extraction quality"],
                        "expected": {"min_parties": 2, "max_parties": 3, "min_facilities": 1},
                    }
                ]
            }
        )
    )
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    (pdf_dir / "loan.pdf").write_bytes(b"%PDF-1.4")

    class _Doc:
        parties = [
            Party(name="Borrower Corp", role="borrower"),
            Party(name="Borrower Corp", role="borrower"),
            Party(name="Lender Bank", role="lender"),
            Party(name="Mystery Entity", role=""),
        ]
        facilities = []
        covenants = [object()]
        amendments = []

    def _fake_process_document(pdf_path, save_output=False):  # noqa: ARG001
        return _Doc(), object()

    entries = load_manifest(manifest_path)
    rows = evaluate_manifest_entries(entries, pdf_dir=pdf_dir, process_fn=_fake_process_document)

    assert len(rows) == 1
    row = rows[0]
    assert row.status == "ok"
    assert row.party_count == 4
    assert row.unknown_role_count == 1
    assert row.duplicate_party_count == 1
    assert "party_count(4)>max_parties(3)" in row.anomalies
    assert "facility_count(0)<min_facilities(1)" in row.anomalies
    assert "unknown_role_parties(1)" in row.anomalies
    assert "duplicate_parties(1)" in row.anomalies


def test_evaluator_reports_processing_error(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {"file_name": "bad.pdf", "focus": ["error path"], "expected": {}},
                ]
            }
        )
    )
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir()
    (pdf_dir / "bad.pdf").write_bytes(b"%PDF-1.4")

    def _boom(pdf_path, save_output=False):  # noqa: ARG001
        raise RuntimeError("failed parse")

    entries = load_manifest(manifest_path)
    rows = evaluate_manifest_entries(entries, pdf_dir=pdf_dir, process_fn=_boom)

    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].anomalies == ["processing_error: failed parse"]
