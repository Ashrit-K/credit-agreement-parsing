# Golden-Set Labeler Rationale

## Why We Built This App

Manual QA for extraction quality was too slow and error-prone:
- reviewers had to open PDFs separately and compare parser output by hand
- provenance (where a label came from) was not consistently captured
- expected outputs were hard to maintain as the parser changed

The Streamlit Golden-Set Labeler was built to make review efficient and auditable.

## Problem Statement

We needed a workflow where a reviewer can:
- inspect a source PDF and expected output side-by-side
- approve/edit/reject parser-prefilled candidates instead of typing everything from scratch
- keep data lineage with each labeled row
- export evaluator-ready expected outputs for automated regression checks

## Design Decisions (Phase 1)

1. Review-first workflow
- parser pre-fills parties/facilities/covenants/amendments
- reviewer mostly confirms and edits, rather than creating labels from zero

2. Provenance-first records
- each row includes `doc_id`, `page`, `block`, `line`, `provenance_id`, and `text_snippet`
- provenance is editable so human corrections are captured

3. File-based, version-controlled storage
- one label JSON per document in `raw_documents/golden_set/labels/`
- deterministic export to `raw_documents/golden_set/expected_outputs.json`

4. Keep implementation lightweight
- Streamlit app for rapid iteration and team adoption
- no custom PDF-selection frontend in Phase 1

## Expected Outcomes

- faster labeling throughput (approve/edit/reject)
- traceable expected outputs with lineage
- easier regression evaluation as parser rules evolve
- lower onboarding effort for new reviewers

## Scope Boundary

Phase 1 does not include coordinate-level text selection from the PDF viewer.
That can be added in a later phase via a custom PDF.js component when needed.
