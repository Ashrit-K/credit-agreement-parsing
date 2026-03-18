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
    load_expected_labels,
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


def test_load_expected_labels_returns_lookup(tmp_path):
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "file_name": "loan.pdf",
                        "expected_parties": [
                            {"name": "Borrower Corp", "role": "borrower"},
                            {"name": "Lender Bank", "role": "lender"},
                        ],
                        "expected_counts": {"facilities": 1},
                    }
                ]
            }
        )
    )

    labels = load_expected_labels(expected_path)

    assert "loan.pdf" in labels
    assert labels["loan.pdf"]["expected_counts"]["facilities"] == 1
    assert len(labels["loan.pdf"]["expected_parties"]) == 2


def test_evaluator_flags_missing_and_unexpected_expected_parties(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "file_name": "loan.pdf",
                        "focus": ["label comparison"],
                        "expected": {},
                    }
                ]
            }
        )
    )
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "file_name": "loan.pdf",
                        "expected_parties": [
                            {"name": "Borrower Corp", "role": "borrower"},
                            {"name": "Lender Bank", "role": "lender"},
                        ],
                        "expected_counts": {"facilities": 1, "amendments": 0},
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
            Party(name="Unexpected Agent LLC", role="administrative_agent"),
        ]
        facilities = [object(), object()]
        covenants = []
        amendments = [object()]

    def _fake_process_document(pdf_path, save_output=False):  # noqa: ARG001
        return _Doc(), object()

    labels = load_expected_labels(expected_path)
    entries = load_manifest(manifest_path)
    rows = evaluate_manifest_entries(
        entries=entries,
        pdf_dir=pdf_dir,
        process_fn=_fake_process_document,
        expected_labels=labels,
    )

    assert len(rows) == 1
    anomalies = rows[0].anomalies
    assert "missing_expected_parties(1)" in anomalies
    assert "unexpected_parties(1)" in anomalies
    assert "facility_count(2)!=expected_facilities(1)" in anomalies
    assert "amendment_count(1)!=expected_amendments(0)" in anomalies


def test_expected_party_matching_ignores_minor_punctuation(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "file_name": "loan.pdf",
                        "focus": ["normalization"],
                        "expected": {},
                    }
                ]
            }
        )
    )
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "file_name": "loan.pdf",
                        "expected_parties": [
                            {"name": "Borrower Corp, Inc.", "role": "Borrower"},
                            {"name": "Lender Bank, N.A.", "role": "Lender"},
                        ],
                        "expected_counts": {},
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
            Party(name="BORROWER CORP INC", role="borrower"),
            Party(name="Lender Bank NA", role="lender"),
        ]
        facilities = []
        covenants = []
        amendments = []

    def _fake_process_document(pdf_path, save_output=False):  # noqa: ARG001
        return _Doc(), object()

    labels = load_expected_labels(expected_path)
    entries = load_manifest(manifest_path)
    rows = evaluate_manifest_entries(
        entries=entries,
        pdf_dir=pdf_dir,
        process_fn=_fake_process_document,
        expected_labels=labels,
    )

    assert len(rows) == 1
    assert not any(a.startswith("missing_expected_parties(") for a in rows[0].anomalies)
    assert not any(a.startswith("unexpected_parties(") for a in rows[0].anomalies)
