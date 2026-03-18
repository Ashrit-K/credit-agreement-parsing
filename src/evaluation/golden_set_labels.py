"""Golden-set annotation storage and export helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.pipeline import process_document

DEFAULT_GOLDEN_SET_DIR = Path("raw_documents/golden_set")
DEFAULT_PDF_DIR = DEFAULT_GOLDEN_SET_DIR / "pdf"
DEFAULT_LABELS_DIR = DEFAULT_GOLDEN_SET_DIR / "labels"
DEFAULT_EXPECTED_OUTPUTS_PATH = DEFAULT_GOLDEN_SET_DIR / "expected_outputs.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_golden_pdfs(pdf_dir: str | Path = DEFAULT_PDF_DIR) -> list[Path]:
    """Return sorted golden-set PDF files."""
    root = Path(pdf_dir)
    return sorted(root.glob("*.pdf"))


def _provenance_dict(source_ref, fallback_doc_id: str) -> dict:
    doc_id = str(getattr(source_ref, "doc_id", "")).strip() or fallback_doc_id
    page = getattr(source_ref, "page", None)
    block = getattr(source_ref, "block", None)
    line = getattr(source_ref, "line", None)
    snippet = str(getattr(source_ref, "text_snippet", "")).strip()

    parts = [doc_id]
    if page is not None:
        parts.append(f"p{page}")
    if block is not None:
        parts.append(f"b{block}")
    if line is not None:
        parts.append(f"l{line}")

    return {
        "doc_id": doc_id,
        "page": page,
        "block": block,
        "line": line,
        "text_snippet": snippet,
        "provenance_id": "/".join(parts),
    }


def prefill_label_payload(doc) -> dict:
    """Build default annotation payload from parser output."""
    doc_id = str(getattr(doc, "doc_id", "")).strip()
    file_name = str(getattr(doc, "file_name", "")).strip()

    parties = []
    for party in getattr(doc, "parties", []):
        row = {
            "name": str(getattr(party, "name", "")),
            "role": str(getattr(party, "role", "")),
            "decision": "pending",
            "notes": "",
        }
        row.update(_provenance_dict(getattr(party, "source_ref", None), doc_id))
        parties.append(row)

    facilities = []
    for facility in getattr(doc, "facilities", []):
        row = {
            "facility_type": str(getattr(facility, "facility_type", "")),
            "name": str(getattr(facility, "name", "")),
            "amount": getattr(facility, "amount", None),
            "currency": str(getattr(facility, "currency", "")),
            "effective_date": str(getattr(facility, "effective_date", "")),
            "maturity_date": str(getattr(facility, "maturity_date", "")),
            "decision": "pending",
            "notes": "",
        }
        row.update(_provenance_dict(getattr(facility, "source_ref", None), doc_id))
        facilities.append(row)

    covenants = []
    for covenant in getattr(doc, "covenants", []):
        row = {
            "covenant_type": str(getattr(covenant, "covenant_type", "")),
            "name": str(getattr(covenant, "name", "")),
            "metric": str(getattr(covenant, "metric", "")),
            "decision": "pending",
            "notes": "",
        }
        row.update(_provenance_dict(getattr(covenant, "source_ref", None), doc_id))
        covenants.append(row)

    amendments = []
    for amendment in getattr(doc, "amendments", []):
        row = {
            "amendment_number": str(getattr(amendment, "amendment_number", "")),
            "amendment_date": str(getattr(amendment, "amendment_date", "")),
            "original_agreement_date": str(getattr(amendment, "original_agreement_date", "")),
            "decision": "pending",
            "notes": "",
        }
        row.update(_provenance_dict(getattr(amendment, "source_ref", None), doc_id))
        amendments.append(row)

    return {
        "file_name": file_name,
        "doc_id": doc_id,
        "total_pages": int(getattr(doc, "total_pages", 0) or 0),
        "status": "not_started",
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "parties": parties,
        "facilities": facilities,
        "covenants": covenants,
        "amendments": amendments,
        "expected_counts": {},
    }


def sanitize_file_stem(file_name: str) -> str:
    """Convert PDF file name to stable JSON label file stem."""
    return Path(file_name).stem + ".json"


def get_label_path(file_name: str, labels_dir: str | Path = DEFAULT_LABELS_DIR) -> Path:
    """Return label file path for a given PDF file name."""
    root = Path(labels_dir)
    return root / sanitize_file_stem(file_name)


def load_label(label_path: str | Path) -> dict:
    return json.loads(Path(label_path).read_text())


def save_label(payload: dict, label_path: str | Path) -> None:
    out = Path(label_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = _utc_now_iso()
    out.write_text(json.dumps(payload, indent=2))


def _run_process(process_fn: Callable, pdf_path: Path):
    try:
        return process_fn(pdf_path, save_output=False)
    except TypeError:
        return process_fn(pdf_path)


def load_or_create_label(
    file_name: str,
    pdf_path: str | Path,
    labels_dir: str | Path = DEFAULT_LABELS_DIR,
    process_fn: Callable = process_document,
) -> dict:
    """Load existing label payload or create one from parser prefill."""
    label_path = get_label_path(file_name, labels_dir=labels_dir)
    if label_path.exists():
        return load_label(label_path)

    doc, _ = _run_process(process_fn, Path(pdf_path))
    payload = prefill_label_payload(doc)
    save_label(payload, label_path)
    return payload


def _approved_parties(payload: dict) -> list[dict[str, str]]:
    parties = []
    for row in payload.get("parties", []):
        if str(row.get("decision", "")).lower() != "approved":
            continue
        name = str(row.get("name", "")).strip()
        role = str(row.get("role", "")).strip()
        if name and role:
            parties.append({"name": name, "role": role})
    return parties


def export_expected_outputs(
    labels_dir: str | Path = DEFAULT_LABELS_DIR,
    output_path: str | Path = DEFAULT_EXPECTED_OUTPUTS_PATH,
) -> dict:
    """Export evaluator-compatible expected outputs from approved labels."""
    root = Path(labels_dir)
    docs: list[dict] = []
    for label_file in sorted(root.glob("*.json")):
        payload = load_label(label_file)
        file_name = str(payload.get("file_name", "")).strip()
        if not file_name:
            continue

        expected_counts = payload.get("expected_counts", {})
        cleaned_counts = {}
        if isinstance(expected_counts, dict):
            for key, value in expected_counts.items():
                if isinstance(value, int):
                    cleaned_counts[str(key)] = value

        docs.append(
            {
                "file_name": file_name,
                "expected_parties": _approved_parties(payload),
                "expected_counts": cleaned_counts,
            }
        )

    result = {
        "schema_version": 1,
        "description": "Human-labeled expected outputs for golden-set regression scoring.",
        "documents": docs,
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    return result
