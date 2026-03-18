"""Streamlit app for golden-set annotation with parser-prefilled provenance."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation.golden_set_labels import (
    DEFAULT_EXPECTED_OUTPUTS_PATH,
    DEFAULT_LABELS_DIR,
    DEFAULT_PDF_DIR,
    export_expected_outputs,
    get_label_path,
    list_golden_pdfs,
    load_label,
    load_or_create_label,
    save_label,
)

DECISIONS = ["pending", "approved", "rejected"]


def _render_pdf(pdf_path: Path, page: int) -> None:
    data = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
    html = (
        f'<embed src="data:application/pdf;base64,{data}#page={page}" '
        'type="application/pdf" width="100%" height="980"/>'
    )
    st.components.v1.html(html, height=1000, scrolling=True)


def _queue_rows(pdf_paths: list[Path], labels_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for pdf_path in pdf_paths:
        label_path = get_label_path(pdf_path.name, labels_dir=labels_dir)
        status = "not_started"
        reviewed = 0
        approved = 0
        if label_path.exists():
            payload = load_label(label_path)
            status = str(payload.get("status", "in_review"))
            all_rows = (
                payload.get("parties", [])
                + payload.get("facilities", [])
                + payload.get("covenants", [])
                + payload.get("amendments", [])
            )
            reviewed = sum(1 for row in all_rows if row.get("decision") in {"approved", "rejected"})
            approved = sum(1 for row in all_rows if row.get("decision") == "approved")

        rows.append(
            {
                "file_name": pdf_path.name,
                "status": status,
                "reviewed_rows": reviewed,
                "approved_rows": approved,
            }
        )
    return rows


def _format_doc_label(row: dict) -> str:
    return f"{row['file_name']}  [{row['status']}]  reviewed={row['reviewed_rows']} approved={row['approved_rows']}"


def _as_records(df: pd.DataFrame, cols: Iterable[str]) -> list[dict]:
    selected_cols = list(cols)
    out = []
    for record in df.to_dict(orient="records"):
        out.append({k: record.get(k) for k in selected_cols})
    return out


def _column_config():
    return {
        "decision": st.column_config.SelectboxColumn("decision", options=DECISIONS),
        "notes": st.column_config.TextColumn("notes", width="large"),
        "text_snippet": st.column_config.TextColumn("text_snippet", width="large"),
    }


def _records_for_editor(payload: dict, key: str, columns: list[str]) -> pd.DataFrame:
    rows = payload.get(key, [])
    if rows:
        return pd.DataFrame(rows)
    return pd.DataFrame(columns=columns)


def _expected_count_default(payload: dict, key: str, fallback: int) -> int:
    value = payload.get("expected_counts", {}).get(key)
    return int(value) if isinstance(value, int) else fallback


def _approved_count(rows: list[dict]) -> int:
    return sum(1 for row in rows if str(row.get("decision", "")).lower() == "approved")


def main() -> None:
    st.set_page_config(page_title="Golden Set Labeler", layout="wide")
    st.title("Golden Set Labeler (Phase 1)")
    st.caption("Review parser-prefilled outputs, keep provenance, approve/edit/reject rows, and export expected outputs.")

    labels_dir = DEFAULT_LABELS_DIR
    labels_dir.mkdir(parents=True, exist_ok=True)

    pdf_paths = list_golden_pdfs(DEFAULT_PDF_DIR)
    if not pdf_paths:
        st.error(f"No PDFs found in {DEFAULT_PDF_DIR}")
        return

    queue = _queue_rows(pdf_paths, labels_dir)
    queue_map = {row["file_name"]: row for row in queue}

    st.sidebar.header("Queue")
    selected_name = st.sidebar.selectbox(
        "Document",
        options=[row["file_name"] for row in queue],
        format_func=lambda name: _format_doc_label(queue_map[name]),
    )
    selected_pdf = DEFAULT_PDF_DIR / selected_name

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Labels dir: `{labels_dir}`")
    st.sidebar.caption(f"Expected outputs: `{DEFAULT_EXPECTED_OUTPUTS_PATH}`")

    label_path = get_label_path(selected_name, labels_dir=labels_dir)
    payload = load_or_create_label(
        file_name=selected_name,
        pdf_path=selected_pdf,
        labels_dir=labels_dir,
    )

    status_value = st.sidebar.selectbox(
        "Document status",
        options=["not_started", "in_review", "approved"],
        index=["not_started", "in_review", "approved"].index(payload.get("status", "in_review")),
    )

    page_max = max(1, int(payload.get("total_pages", 1) or 1))
    page_num = st.sidebar.number_input("PDF page", min_value=1, max_value=page_max, value=1, step=1)

    left, right = st.columns([1.4, 1.0], gap="medium")
    with left:
        st.subheader(selected_name)
        _render_pdf(selected_pdf, page=int(page_num))

    with right:
        st.subheader("Expected Outputs")
        st.write(f"**doc_id:** `{payload.get('doc_id', '')}`")
        st.write(f"**label file:** `{label_path}`")

        party_cols = [
            "name",
            "role",
            "decision",
            "notes",
            "doc_id",
            "page",
            "block",
            "line",
            "provenance_id",
            "text_snippet",
        ]
        facility_cols = [
            "facility_type",
            "name",
            "amount",
            "currency",
            "effective_date",
            "maturity_date",
            "decision",
            "notes",
            "doc_id",
            "page",
            "block",
            "line",
            "provenance_id",
            "text_snippet",
        ]
        covenant_cols = [
            "covenant_type",
            "name",
            "metric",
            "decision",
            "notes",
            "doc_id",
            "page",
            "block",
            "line",
            "provenance_id",
            "text_snippet",
        ]
        amendment_cols = [
            "amendment_number",
            "amendment_date",
            "original_agreement_date",
            "decision",
            "notes",
            "doc_id",
            "page",
            "block",
            "line",
            "provenance_id",
            "text_snippet",
        ]

        tab_parties, tab_facilities, tab_covenants, tab_amendments, tab_counts = st.tabs(
            ["Parties", "Facilities", "Covenants", "Amendments", "Counts"]
        )

        with tab_parties:
            parties_df = st.data_editor(
                _records_for_editor(payload, "parties", party_cols),
                num_rows="dynamic",
                column_config=_column_config(),
                key=f"parties_{selected_name}",
                use_container_width=True,
            )

        with tab_facilities:
            facilities_df = st.data_editor(
                _records_for_editor(payload, "facilities", facility_cols),
                num_rows="dynamic",
                column_config=_column_config(),
                key=f"facilities_{selected_name}",
                use_container_width=True,
            )

        with tab_covenants:
            covenants_df = st.data_editor(
                _records_for_editor(payload, "covenants", covenant_cols),
                num_rows="dynamic",
                column_config=_column_config(),
                key=f"covenants_{selected_name}",
                use_container_width=True,
            )

        with tab_amendments:
            amendments_df = st.data_editor(
                _records_for_editor(payload, "amendments", amendment_cols),
                num_rows="dynamic",
                column_config=_column_config(),
                key=f"amendments_{selected_name}",
                use_container_width=True,
            )

        with tab_counts:
            st.caption("Override expected counts if needed. Defaults can come from approved rows.")
            expected_parties = st.number_input(
                "Expected parties",
                min_value=0,
                value=_expected_count_default(payload, "parties", _approved_count(payload.get("parties", []))),
                step=1,
                key=f"count_parties_{selected_name}",
            )
            expected_facilities = st.number_input(
                "Expected facilities",
                min_value=0,
                value=_expected_count_default(payload, "facilities", _approved_count(payload.get("facilities", []))),
                step=1,
                key=f"count_facilities_{selected_name}",
            )
            expected_covenants = st.number_input(
                "Expected covenants",
                min_value=0,
                value=_expected_count_default(payload, "covenants", _approved_count(payload.get("covenants", []))),
                step=1,
                key=f"count_covenants_{selected_name}",
            )
            expected_amendments = st.number_input(
                "Expected amendments",
                min_value=0,
                value=_expected_count_default(payload, "amendments", _approved_count(payload.get("amendments", []))),
                step=1,
                key=f"count_amendments_{selected_name}",
            )

        updated_payload = {
            **payload,
            "status": status_value,
            "parties": _as_records(parties_df, party_cols),
            "facilities": _as_records(facilities_df, facility_cols),
            "covenants": _as_records(covenants_df, covenant_cols),
            "amendments": _as_records(amendments_df, amendment_cols),
            "expected_counts": {
                "parties": int(expected_parties),
                "facilities": int(expected_facilities),
                "covenants": int(expected_covenants),
                "amendments": int(expected_amendments),
            },
        }

        col_save, col_export = st.columns(2)
        with col_save:
            if st.button("Save Label", type="primary", use_container_width=True):
                save_label(updated_payload, label_path)
                st.success(f"Saved label file: {label_path}")
        with col_export:
            if st.button("Export expected_outputs.json", use_container_width=True):
                save_label(updated_payload, label_path)
                exported = export_expected_outputs(labels_dir=labels_dir, output_path=DEFAULT_EXPECTED_OUTPUTS_PATH)
                st.success(
                    f"Exported {len(exported.get('documents', []))} documents to {DEFAULT_EXPECTED_OUTPUTS_PATH}"
                )

        with st.expander("Raw label JSON", expanded=False):
            st.code(json.dumps(updated_payload, indent=2), language="json")


if __name__ == "__main__":
    main()
