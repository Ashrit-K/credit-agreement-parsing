"""Evaluate parser quality over curated golden-set documents."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from src.pipeline import process_document


@dataclass(slots=True)
class ManifestEntry:
    file_name: str
    focus: list[str] = field(default_factory=list)
    expected: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationRow:
    file_name: str
    status: str
    party_count: int = 0
    facility_count: int = 0
    covenant_count: int = 0
    amendment_count: int = 0
    unknown_role_count: int = 0
    duplicate_party_count: int = 0
    anomalies: list[str] = field(default_factory=list)
    focus: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, str | int]:
        return {
            "file_name": self.file_name,
            "status": self.status,
            "party_count": self.party_count,
            "facility_count": self.facility_count,
            "covenant_count": self.covenant_count,
            "amendment_count": self.amendment_count,
            "unknown_role_count": self.unknown_role_count,
            "duplicate_party_count": self.duplicate_party_count,
            "anomalies": "; ".join(self.anomalies),
            "focus": "; ".join(self.focus),
        }


_EXPECTED_FIELD_TO_METRIC = {
    "parties": "party_count",
    "facilities": "facility_count",
    "covenants": "covenant_count",
    "amendments": "amendment_count",
}


def load_manifest(manifest_path: str | Path) -> list[ManifestEntry]:
    """Load and validate manifest entries from JSON."""
    path = Path(manifest_path)
    data = json.loads(path.read_text())
    docs = data.get("documents")
    if not isinstance(docs, list):
        raise ValueError("Manifest must contain a 'documents' list.")

    entries: list[ManifestEntry] = []
    for i, doc in enumerate(docs):
        if not isinstance(doc, dict):
            raise ValueError(f"documents[{i}] must be an object.")
        file_name = str(doc.get("file_name", "")).strip()
        if not file_name:
            raise ValueError(f"documents[{i}].file_name is required.")

        raw_focus = doc.get("focus", [])
        focus = [str(item).strip() for item in raw_focus if str(item).strip()] if isinstance(raw_focus, list) else []

        raw_expected = doc.get("expected", {})
        expected: dict[str, int] = {}
        if isinstance(raw_expected, dict):
            for key, value in raw_expected.items():
                if isinstance(value, int):
                    expected[str(key)] = value

        entries.append(
            ManifestEntry(
                file_name=file_name,
                focus=focus,
                expected=expected,
            )
        )
    return entries


def _call_process(
    process_fn: Callable,
    pdf_path: Path,
):
    """Call process function while tolerating different signatures in tests."""
    try:
        return process_fn(pdf_path, save_output=False)
    except TypeError:
        return process_fn(pdf_path)


def _party_quality_counts(parties: Iterable) -> tuple[int, int]:
    """Return (unknown_role_count, duplicate_party_count)."""
    unknown_role_count = 0
    duplicate_party_count = 0
    seen: set[tuple[str, str]] = set()

    for party in parties:
        name = str(getattr(party, "name", "")).strip()
        role = str(getattr(party, "role", "")).strip()
        role_lower = role.lower()
        if not role or role_lower == "unknown":
            unknown_role_count += 1

        key = (name.lower(), role_lower)
        if key in seen:
            duplicate_party_count += 1
        else:
            seen.add(key)

    return unknown_role_count, duplicate_party_count


def _threshold_anomalies(row: EvaluationRow, expected: dict[str, int]) -> list[str]:
    anomalies: list[str] = []
    for key, threshold in expected.items():
        if key.startswith("min_"):
            field = key[len("min_"):]
            metric_name = _EXPECTED_FIELD_TO_METRIC.get(field)
            if not metric_name:
                continue
            metric_value = int(getattr(row, metric_name))
            if metric_value < threshold:
                anomalies.append(f"{metric_name}({metric_value})<{key}({threshold})")
        elif key.startswith("max_"):
            field = key[len("max_"):]
            metric_name = _EXPECTED_FIELD_TO_METRIC.get(field)
            if not metric_name:
                continue
            metric_value = int(getattr(row, metric_name))
            if metric_value > threshold:
                anomalies.append(f"{metric_name}({metric_value})>{key}({threshold})")
    return anomalies


def evaluate_manifest_entries(
    entries: list[ManifestEntry],
    pdf_dir: str | Path,
    process_fn: Callable = process_document,
) -> list[EvaluationRow]:
    """Evaluate each manifest entry by running the parser once per file."""
    pdf_root = Path(pdf_dir)
    rows: list[EvaluationRow] = []

    for entry in entries:
        pdf_path = pdf_root / entry.file_name
        if not pdf_path.exists():
            rows.append(
                EvaluationRow(
                    file_name=entry.file_name,
                    status="error",
                    anomalies=[f"missing_pdf: {pdf_path}"],
                    focus=entry.focus,
                )
            )
            continue

        try:
            doc, _ = _call_process(process_fn, pdf_path)
        except Exception as exc:  # noqa: BLE001
            rows.append(
                EvaluationRow(
                    file_name=entry.file_name,
                    status="error",
                    anomalies=[f"processing_error: {exc}"],
                    focus=entry.focus,
                )
            )
            continue

        party_count = len(getattr(doc, "parties", []))
        facility_count = len(getattr(doc, "facilities", []))
        covenant_count = len(getattr(doc, "covenants", []))
        amendment_count = len(getattr(doc, "amendments", []))
        unknown_role_count, duplicate_party_count = _party_quality_counts(getattr(doc, "parties", []))

        row = EvaluationRow(
            file_name=entry.file_name,
            status="ok",
            party_count=party_count,
            facility_count=facility_count,
            covenant_count=covenant_count,
            amendment_count=amendment_count,
            unknown_role_count=unknown_role_count,
            duplicate_party_count=duplicate_party_count,
            anomalies=[],
            focus=entry.focus,
        )

        anomalies = _threshold_anomalies(row, entry.expected)
        if unknown_role_count > 0:
            anomalies.append(f"unknown_role_parties({unknown_role_count})")
        if duplicate_party_count > 0:
            anomalies.append(f"duplicate_parties({duplicate_party_count})")
        if party_count >= 150:
            anomalies.append(f"party_count_suspiciously_high({party_count})")

        row.anomalies = anomalies
        rows.append(row)

    return rows


def evaluate_manifest(
    manifest_path: str | Path,
    pdf_dir: str | Path,
    process_fn: Callable = process_document,
) -> list[EvaluationRow]:
    """Load manifest and evaluate all entries."""
    entries = load_manifest(manifest_path)
    return evaluate_manifest_entries(entries=entries, pdf_dir=pdf_dir, process_fn=process_fn)


def format_compact_table(rows: list[EvaluationRow]) -> str:
    """Render a compact fixed-width table for terminal review."""
    headers = [
        "file",
        "status",
        "parties",
        "fac",
        "cov",
        "amd",
        "unknown",
        "dup",
        "anomalies",
    ]
    data: list[list[str]] = []
    for row in rows:
        data.append(
            [
                row.file_name,
                row.status,
                str(row.party_count),
                str(row.facility_count),
                str(row.covenant_count),
                str(row.amendment_count),
                str(row.unknown_role_count),
                str(row.duplicate_party_count),
                "; ".join(row.anomalies),
            ]
        )

    widths = [len(header) for header in headers]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def _line(parts: list[str]) -> str:
        return " | ".join(part.ljust(widths[i]) for i, part in enumerate(parts))

    top = _line(headers)
    divider = "-+-".join("-" * w for w in widths)
    lines = [top, divider]
    lines.extend(_line(row) for row in data)
    return "\n".join(lines)


def write_evaluation_csv(rows: list[EvaluationRow], output_path: str | Path) -> None:
    """Write evaluator output rows to CSV."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "file_name",
        "status",
        "party_count",
        "facility_count",
        "covenant_count",
        "amendment_count",
        "unknown_role_count",
        "duplicate_party_count",
        "anomalies",
        "focus",
    ]
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())
