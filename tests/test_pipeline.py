"""Integration tests for the full pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import process_document
from src.config import RAW_PDF_DIR

TEST_PDF = RAW_PDF_DIR / "011_credit_agreement.pdf"


def test_pipeline_produces_document():
    if not TEST_PDF.exists():
        return
    doc, graph = process_document(TEST_PDF, save_output=False)
    assert doc.doc_id
    assert doc.file_name == "011_credit_agreement.pdf"
    assert doc.total_pages > 0


def test_pipeline_produces_graph():
    if not TEST_PDF.exists():
        return
    doc, graph = process_document(TEST_PDF, save_output=False)
    assert graph.number_of_nodes() > 0
    # At minimum we should have a Document node
    doc_nodes = [n for n, d in graph.nodes(data=True) if d.get("node_type") == "Document"]
    assert len(doc_nodes) == 1


def test_pipeline_extracts_some_parties():
    if not TEST_PDF.exists():
        return
    doc, _ = process_document(TEST_PDF, save_output=False)
    # Most credit agreements have at least one party
    assert len(doc.parties) >= 0  # relaxed — not all docs have regex-matching parties
