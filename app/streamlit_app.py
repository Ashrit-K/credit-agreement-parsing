"""Streamlit UI for Credit Agreement PDF Parser."""

import json
import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import process_document
from src.knowledge_graph.queries import graph_summary


st.set_page_config(page_title="Credit Agreement Parser", layout="wide")
st.title("Credit Agreement PDF Parser")

# Sidebar
st.sidebar.header("Upload & Process")
uploaded_file = st.sidebar.file_uploader("Upload a PDF", type=["pdf"])
process_btn = st.sidebar.button("Process Document", type="primary", disabled=not uploaded_file)

# Also allow selecting from existing PDFs
raw_pdf_dir = Path(__file__).resolve().parent.parent / "raw_documents" / "pdf"
existing_pdfs = sorted(raw_pdf_dir.glob("*.pdf")) if raw_pdf_dir.exists() else []
if existing_pdfs:
    st.sidebar.markdown("---")
    st.sidebar.header("Or Select Existing PDF")
    selected_existing = st.sidebar.selectbox(
        "Choose from raw_documents/pdf/",
        options=[""] + [p.name for p in existing_pdfs],
    )
    process_existing_btn = st.sidebar.button("Process Selected", disabled=not selected_existing)
else:
    selected_existing = ""
    process_existing_btn = False


def display_results(doc_dict: dict, graph_stats: dict) -> None:
    """Display parsed results in tabbed layout."""
    tab_overview, tab_facilities, tab_covenants, tab_amendments, tab_raw, tab_graph = st.tabs(
        ["Overview", "Facilities", "Covenants", "Amendments", "Raw JSON", "Knowledge Graph"]
    )

    with tab_overview:
        st.subheader("Document Overview")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Document ID", doc_dict.get("doc_id", ""))
            st.metric("Total Pages", doc_dict.get("total_pages", 0))
            st.metric("Parties Found", len(doc_dict.get("parties", [])))
        with col2:
            st.metric("Agreement Date", doc_dict.get("agreement_date", "N/A"))
            st.metric("Facilities", len(doc_dict.get("facilities", [])))
            st.metric("Covenants", len(doc_dict.get("covenants", [])))

        if doc_dict.get("title"):
            st.write(f"**Title:** {doc_dict['title']}")

        if doc_dict.get("parties"):
            st.subheader("Parties")
            for p in doc_dict["parties"]:
                st.write(f"- **{p.get('role', 'unknown').title()}**: {p.get('name', '')}")

    with tab_facilities:
        st.subheader("Facilities")
        if not doc_dict.get("facilities"):
            st.info("No facilities extracted.")
        for i, f in enumerate(doc_dict.get("facilities", [])):
            with st.expander(f"Facility {i+1}: {f.get('name') or f.get('facility_type', 'Unknown')}", expanded=True):
                col1, col2, col3 = st.columns(3)
                col1.write(f"**Type:** {f.get('facility_type', '')}")
                col2.write(f"**Amount:** {f.get('amount', 'N/A')}")
                col3.write(f"**Currency:** {f.get('currency', 'USD')}")

                col1, col2 = st.columns(2)
                col1.write(f"**Effective Date:** {f.get('effective_date', 'N/A')}")
                col2.write(f"**Maturity Date:** {f.get('maturity_date', 'N/A')}")

                if f.get("interest_terms"):
                    it = f["interest_terms"]
                    st.write("**Interest Terms:**")
                    st.write(f"  Benchmark: {it.get('benchmark', 'N/A')}, "
                             f"Spread: {it.get('spread_bps', 'N/A')} bps, "
                             f"Floor: {it.get('floor_pct', 'N/A')}%")
                    if it.get("pricing_grid"):
                        st.write("**Pricing Grid:**")
                        st.json(it["pricing_grid"])

    with tab_covenants:
        st.subheader("Covenants")
        if not doc_dict.get("covenants"):
            st.info("No covenants extracted.")
        for cov in doc_dict.get("covenants", []):
            with st.expander(f"{cov.get('covenant_type', '').title()}: {cov.get('name', '')}"):
                st.write(f"**Type:** {cov.get('covenant_type', '')}")
                st.write(f"**Metric:** {cov.get('metric', 'N/A')}")
                if cov.get("description"):
                    st.write(f"**Description:** {cov['description']}")
                if cov.get("thresholds"):
                    st.write("**Thresholds:**")
                    for t in cov["thresholds"]:
                        st.write(f"  - {t.get('period', '')}: {t.get('value', '')}")

    with tab_amendments:
        st.subheader("Amendments")
        if not doc_dict.get("amendments"):
            st.info("No amendment information extracted.")
        for amend in doc_dict.get("amendments", []):
            with st.expander(f"Amendment {amend.get('amendment_number', 'N/A')}"):
                st.write(f"**Date:** {amend.get('amendment_date', 'N/A')}")
                st.write(f"**Original Agreement Date:** {amend.get('original_agreement_date', 'N/A')}")
                if amend.get("summary_of_changes"):
                    st.write(f"**Summary:** {amend['summary_of_changes']}")
                if amend.get("sections_amended"):
                    st.write(f"**Sections Amended:** {', '.join(amend['sections_amended'])}")

    with tab_raw:
        st.subheader("Raw JSON Output")
        st.json(doc_dict)

    with tab_graph:
        st.subheader("Knowledge Graph Summary")
        if graph_stats:
            col1, col2 = st.columns(2)
            col1.metric("Total Nodes", graph_stats.get("total_nodes", 0))
            col2.metric("Total Edges", graph_stats.get("total_edges", 0))

            if graph_stats.get("node_types"):
                st.write("**Node Types:**")
                for ntype, count in graph_stats["node_types"].items():
                    st.write(f"  - {ntype}: {count}")

            if graph_stats.get("edge_types"):
                st.write("**Edge Types:**")
                for etype, count in graph_stats["edge_types"].items():
                    st.write(f"  - {etype}: {count}")


def run_pipeline(pdf_path: Path) -> None:
    """Run the parsing pipeline and display results with progress tracking."""
    progress_bar = st.progress(0)
    status_text = st.empty()

    def on_progress(step: int, total: int, message: str) -> None:
        progress_bar.progress(step / total)
        status_text.markdown(f"**Step {step}/{total}:** {message}")

    try:
        doc, graph = process_document(pdf_path, progress_callback=on_progress)
        progress_bar.progress(1.0)
        status_text.empty()
        doc_dict = json.loads(doc.model_dump_json())
        stats = graph_summary(graph)

        meta = doc_dict.get("extraction_metadata", {})
        st.success(
            f"Done — {doc.total_pages} pages, "
            f"{meta.get('total_blocks', 0)} blocks, "
            f"{len(doc.parties)} parties, "
            f"{len(doc.facilities)} facilities, "
            f"{len(doc.covenants)} covenants, "
            f"{stats.get('total_nodes', 0)} graph nodes"
        )
        display_results(doc_dict, stats)
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Error processing {pdf_path.name}: {e}")
        st.exception(e)


# Main area
if process_btn and uploaded_file:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = Path(tmp.name)
    run_pipeline(tmp_path)

elif process_existing_btn and selected_existing:
    pdf_path = raw_pdf_dir / selected_existing
    run_pipeline(pdf_path)

else:
    st.info("Upload a PDF or select an existing one from the sidebar, then click Process.")
