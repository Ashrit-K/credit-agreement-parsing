"""B2 rules classify evidence provisionally and preserve citation identity."""
import copy
import json

import pytest

from credit_agreement_extractor.topic_signals import (
    InvalidTopicInputError, classify_chunk_document, classify_chunks,
)
from credit_agreement_extractor.chunking import ChunkArtifact


def document(text, *, heading=None):
    item = {"item_id": "#/texts/0", "text": text, "original_text": text,
            "heading_path": [] if heading is None else [
                {"item_id": "#/texts/1", "text": heading, "depth": 1}]}
    items = [item]
    if heading:
        items.insert(0, {"item_id": "#/texts/1", "text": heading,
                         "original_text": heading, "heading_path": []})
    ids = [i["item_id"] for i in items]
    return {"schema_version": 1, "status": "completed", "source_sha256": "a" * 64,
            "source_reading_order": ids,
            "chunks": [{"chunk_id": "chunk-000001", "item_ids": ids,
                        "items": items, "content": text}]}


@pytest.mark.parametrize("text,topic", [
    ("THE BORROWERS and the lender", "parties_and_roles"),
    ("Borrowing Base", "facility_and_commitment_terms"),
    ("Applicable Margin and ticking fee", "interest_and_fees"),
    ("Scheduled Maturity Date", "maturity_termination_extension"),
    ("Mandatory Prepayment", "repayment_and_prepayment"),
    ("Financial Covenants", "covenants"),
    ("Guarantee and Indemnity", "guarantees_and_security"),
    ("Events of Default", "default_and_remedies"),
])
def test_specific_vocabulary_proposes_topic(text, topic):
    assert topic in classify_chunk_document(document(text))["classifications"][0]["proposed_topics"]


def test_broad_word_proposes_initial_guess_without_strength():
    row = classify_chunk_document(document("The Borrower shall deliver a notice."))["classifications"][0]
    assert row["proposed_topics"] == ["parties_and_roles"]
    assert all("strength" not in s and "confidence" not in s for s in row["signals"])


@pytest.mark.parametrize("text,child,parent", [
    ("PIK Election", "interest_and_fees.pik_toggle", "interest_and_fees"),
    ("Make-whole premium", "repayment_and_prepayment.call_protection", "repayment_and_prepayment"),
])
def test_subtopic_proposes_parent(text, child, parent):
    assert {child, parent} <= set(classify_chunk_document(document(text))["classifications"][0]["proposed_topics"])


def test_contextual_payment_timing():
    assert "interest_and_fees" in classify_chunk_document(document("Interest payable quarterly in arrears"))["classifications"][0]["proposed_topics"]
    assert classify_chunk_document(document("Quarterly financial reporting"))["classifications"][0]["proposed_topics"] == []


def test_inherited_heading_produces_cited_context():
    row = classify_chunk_document(document("3.50 percent", heading="Interest"))["classifications"][0]
    assert "interest_and_fees" in row["proposed_topics"]
    assert any(s["source_kind"] == "heading" and "#/texts/1" in s["item_ids"] for s in row["signals"])


def test_deterministic_and_no_mutation():
    source = document("HIBOR pricing ratchet Actual/360")
    before = copy.deepcopy(source)
    assert classify_chunk_document(source) == classify_chunk_document(source)
    assert source == before


def test_preserves_unmatched_chunks():
    row = classify_chunk_document(document("Unrelated prose"))["classifications"][0]
    assert row["chunk_id"] == "chunk-000001"
    assert row["proposed_topics"] == []


def test_rejects_duplicate_chunk_ids():
    source = document("Interest")
    source["chunks"].append(copy.deepcopy(source["chunks"][0]))
    with pytest.raises(InvalidTopicInputError):
        classify_chunk_document(source)


def test_file_wrapper_preserves_input(tmp_path):
    directory = tmp_path / ("a" * 64)
    directory.mkdir()
    path = directory / "document.chunks.json"
    path.write_text(json.dumps(document("SOFR")))
    original = path.read_bytes()
    artifact = ChunkArtifact("a" * 64, directory, path, 1, "page-first-v1-chars-12000", False)
    output = classify_chunks(artifact)
    assert output.topic_signals_json_path.is_file()
    assert path.read_bytes() == original
    assert json.loads(output.topic_signals_json_path.read_text())["inputs"]["chunks_json_sha256"]


@pytest.mark.parametrize("rate", ["HIBOR", "AUD LIBOR", "STIBOR", "CORRA", "CDOR", "€STR", "TONAR", "BBSW"])
def test_benchmark_aliases_are_topic_signals(rate):
    row = classify_chunk_document(document(rate))["classifications"][0]
    assert "interest_and_fees" in row["proposed_topics"]


def test_wildcard_stops_at_paragraph_boundary():
    row = classify_chunk_document(document("Unrelated material\nSenior secured loan"))["classifications"][0]
    signals = [s for s in row["signals"] if s["rule_id"].endswith(".wildcard")]
    assert signals
    assert all("\n" not in s["matched_text"] for s in signals)
    assert any(s["matched_text"] == "Senior secured loan" for s in signals)


def test_table_rendering_uses_chunk_evidence_without_fabricated_cell_citation():
    source = document("")
    item = source["chunks"][0]["items"][0]
    item.update(item_id="#/tables/0", item_type="table", text=None, original_text=None)
    source["chunks"][0].update(item_ids=["#/tables/0"], content="Pricing grid\tLeverage ratio\tMargin")
    source["source_reading_order"] = ["#/tables/0"]
    row = classify_chunk_document(source)["classifications"][0]
    assert {"interest_and_fees", "covenants"} <= set(row["proposed_topics"])
    assert all(s["item_ids"] == ["#/tables/0"] and s["source_kind"] == "chunk_content" for s in row["signals"])


def test_phrase_boundary_does_not_match_lender_inside_other_word():
    assert classify_chunk_document(document("blender"))["classifications"][0]["proposed_topics"] == []


def test_hyphen_spelling_variants():
    labels = classify_chunk_document(document("payment–in–kind"))["classifications"][0]["proposed_topics"]
    assert "interest_and_fees.pik_toggle" in labels
