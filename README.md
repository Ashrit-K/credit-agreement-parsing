# Credit Agreement Parser

A Python pipeline for converting public credit agreements into structured,
evidence-backed JSON. The target output covers parties, interest terms,
maturity and extension provisions, covenants, repayment terms, call protection,
and other material agreement terms.

The project is under active development. Document conversion and page-first
evidence chunking, LLM topic classification, and topic mapping are operational;
substantive legal-term extraction is still planned. The current
`extract_parties()` function intentionally returns `not_implemented` rather
than inventing borrower or lender data.

## Current status

| Area | Status |
| --- | --- |
| PDF, HTML, and HTM intake | Implemented and tested |
| Local PDF OCR with English RapidOCR | Implemented and tested |
| Gzip-wrapped SEC HTML handling | Implemented and tested |
| Canonical Docling JSON, readable Markdown, and manifest | Implemented and tested |
| Docling PDF heading-hierarchy inference | Implemented and tested |
| Hierarchy sidecar transformation | Implemented and tested (`A10`) |
| Sidecar persistence and final Stage A artifact | Implemented and tested (`A11`) |
| Page-first provenance-preserving chunks | Implemented and tested (`B1`) |
| Heuristic topic guesses and cited rule matches | Implemented and tested (`B2`) |
| LLM topic reflection and provenance-preserving topic map | Implemented and tested (`B3`, `B4`) |
| Evidence retrieval and bundle assembly | Planned (`B5`, `B6`) |
| Shared OpenCode LLM interface | Implemented and tested (`Stage C`; Responses live, Chat fake-HTTP tested) |
| Local telemetry and opt-in detailed debug capture | Implemented; Phoenix deferred |
| Sleeve-based legal-term extraction | Planned (`Stage D`) |

The authoritative numbered architecture, Mermaid diagram, and implementation
status live in [`docs/conversion_pipeline.md`](docs/conversion_pipeline.md).
Agreed but unfinished work is tracked in
[`docs/build_backlog.md`](docs/build_backlog.md).

## Requirements

- Python 3.11
- [uv](https://docs.astral.sh/uv/) for dependency and environment management

Docling, RapidOCR, and the current conversion pipeline run locally. An API key
is not required for document conversion or the test suite.

## Setup

Clone the repository and install the locked dependencies:

```bash
git clone https://github.com/Ashrit-K/credit-agreement-parsing.git
cd credit-agreement-parsing
uv sync --python 3.11
```

To enable B3 live LLM calls, copy the environment template and add
credentials only to the local `.env` file:

```bash
cp .env.example .env
```

```dotenv
OPENCODE_API_KEY=your-key-here
OPENCODE_MODEL=gpt-5.6-luna
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_API_STYLE=responses
```

The `.env` file is ignored by Git. Never commit API keys or other credentials.
The shared OpenCode client is wired into B3. B3 defaults to Luna/high; the
general client defaults to medium reasoning. Model/API-style/reasoning overrides
are available per call. The legal extraction sleeves are not yet implemented.

## Convert a document

`convert_document()` accepts a PDF, HTML, or HTM path without changing the
source file:

```python
from credit_agreement_extractor import convert_document

artifact = convert_document("raw_documents/pdf/example.pdf")

print(artifact.docling_json_path)
print(artifact.hierarchy_json_path)
print(artifact.markdown_path)
print(artifact.manifest_path)
```

Run the example through the managed environment:

```bash
uv run python your_script.py
```

By default, conversion artifacts are stored under a content-addressed folder:

```text
tmp/converted/<source-sha256>/
├── document.docling.json  # canonical downstream source
├── document.hierarchy.json # generic hierarchy keyed by canonical item IDs
├── document.md            # readable development and review copy
└── manifest.json          # source identity and conversion configuration
```

The SHA-256 value is a fingerprint calculated from the source bytes. Repeating
a conversion can reuse a complete cache entry only when both the source
fingerprint and conversion profile match. Cache validation also requires a
schema-version-1 hierarchy sidecar carrying the same source fingerprint. A10
builds that deterministic sidecar from canonical Docling JSON, and A11 writes
the manifest last before returning the completed Stage A artifact.

## Build page-first chunks

`build_chunks()` consumes a completed Stage A artifact and writes a separate,
schema-versioned Stage B artifact:

```python
from credit_agreement_extractor import build_chunks, convert_document

conversion = convert_document("raw_documents/pdf/example.pdf")
chunks = build_chunks(conversion)

print(chunks.chunks_json_path)
print(chunks.cached)
```

The default output is:

```text
tmp/stage_b/<source-sha256>/document.chunks.json
```

PDF content is page-first. Large pages split only between canonical Docling
items, while tables and explicit Docling lists remain atomic. HTML without page
provenance uses deterministic reading-order chunks targeting 12,000 characters
and prefers heading boundaries. Chunks do not overlap, invent pages, or replace
source wording with summaries. Every item retains its canonical ID so full
bounding-box and character-span provenance can be resolved from Stage A.

The persisted artifact also serves as a development cache. It is reused only
when the source, schema, chunking profile, canonical JSON hash, and hierarchy
sidecar hash all match.

## Propose topics for chunks

B2 is available through `classify_chunks(chunks)`, which writes
`document.topic-signals.json` alongside `document.chunks.json`. Its eight-topic
vocabulary and PIK/call-protection subtopics live in `topic_taxonomy.py`.
Every match produces a provisional label and cited rule evidence, without
strength or confidence scores. B3's LLM reflection refines them.

## Classify topics and build the map

```python
from credit_agreement_extractor import (
    convert_document, build_chunks, classify_chunks, reflect_topics,
    build_topic_map, summarize_run,
)

# Share one identifier across APIs so all stages are inspectable as one run.
options = {"debug": True, "run_id": "agreement-review-001"}
conversion = convert_document("raw_documents/pdf/example.pdf", **options)
chunks = build_chunks(conversion, **options)
guesses = classify_chunks(chunks, **options)
labels = reflect_topics(chunks, guesses, **options)  # Paid OpenCode calls.
topic_map = build_topic_map(chunks, labels, **options)  # No LLM call.
print(topic_map.topic_map_json_path)
print(summarize_run(options["run_id"]))
```

B3 produces one validated final topic list per chunk, with supporting Docling
item IDs. It reviews all chunks in batches of up to five and 24,000 evidence
characters; oversized atomic chunks stay intact. B4 builds an index from each
approved topic to classified chunks and their cited source items. Neither step
creates summaries, invents categories, or implements field extraction.

Matching validated B3 batch checkpoints resume without repeating paid calls.
Input/settings/prompt or shared topic-definition changes invalidate reuse;
`force=True` bypasses it. B3 uses `b3-reflection-v2` with explicit topic meanings
and boundaries maintained in `topic_taxonomy.py`; B2 phrase rules are unchanged.
The current snapshot has 156 passing tests. Existing saved-run HTML reflects
the original v1 model calls, not a v2 rerun or measured accuracy improvement.
`reflect_topics(..., model="gpt-5.6-luna", reasoning_effort="low")` overrides
defaults for experiments. Unknown model IDs require an explicit supported
`api_style`; unexpected returned-model substitutions fail rather than hiding them.

Artifacts beside B1 are `document.topic-classifications.json` and
`document.topic-map.json`. Source corpus files remain untouched.

### Local traces and debug mode

All public pipeline/file APIs accept `debug`, `run_id`, and `trace_root`.
Basic stage events and individual LLM attempts are always saved under
`tmp/runs/<run-id>/events.jsonl`. Debug mode additionally saves intermediate
artifact contents, prompts, responses and validation diagnostics under `debug/`.
Run IDs, nested span IDs, batch IDs and source fingerprints link those records.
Keys and authorization headers are excluded; hidden model reasoning is not saved.

`summarize_run()` groups requests/retries, failures, known token usage, latency
and known/unknown costs by model, stage and document. Luna estimates use a dated
OpenCode rate snapshot; unknown models or unsupported pricing tiers stay unknown.
Supply a `pricing` mapping to `OpenCodeClient` for custom dated rates, or `{}` to
disable estimates. Estimated costs are not provider bills, and retries count.
Phoenix is deferred: there is no observability server to start.

The live acceptance check used a tiny synthetic excerpt, not a corpus accuracy
evaluation. Responses/Luna/high returned the requested model and reasoning;
Chat Completions has fake-HTTP coverage but no live open-model trial yet.
Unmatched chunks remain included. Classification accuracy awaits reviewed
ground truth; the current corpus checks verify coverage and provenance.

```python
from credit_agreement_extractor import classify_chunks

topics = classify_chunks(chunks)
print(topics.topic_signals_json_path)
```

## Party-extraction scaffold API

The package also exposes the intended high-level API shape:

```python
from credit_agreement_extractor import extract_parties

result = extract_parties("raw_documents/pdf/example.pdf")
print(result)
```

This validates the PDF path and returns JSON-serializable data, but it does not
yet parse or infer legal parties. Its current `not_implemented` status is a
deliberate safeguard against fabricated results.

## Evidence and extraction design

The planned pipeline keeps extraction results traceable to the source:

1. Stage A converts the document while retaining canonical Docling item IDs,
   reading order, and page provenance.
2. Stage B builds page-first chunks and a topic map that points back to the
   original items instead of replacing them with summaries.
3. Stage C provides shared model routing and API adapters for each LLM step.
4. Stage D runs only the requested extraction sleeves, validates their schemas
   and citations independently, and merges the validated results.

Values must distinguish missing, uncertain, and not-applicable information.
Models may cite canonical item IDs, but application code resolves those IDs to
verified page and source evidence.

## Review a saved pipeline run

The read-only HTML reviewer joins logged artifacts to original source text,
pages, heading context and tables. Its stage selector exposes Stage A's four
conversion artifacts, B1 chunks, B2 guesses/rule matches, B3 final labels/model
attempts, B4 topic-map memberships, and Stage C transport snapshots. Pending
retrieval/extraction stages show no fabricated outputs. Click a citation to
focus its source passage; review unclassified chunks for possible omissions.

```bash
uv run --no-sync python -m credit_agreement_extractor.review \
  eval-011-20261001-01 tmp/runs/eval-011-20261001-01/review.html
```

Open the exported HTML in a browser. It is self-contained, uses only that run's
saved debug outputs, and makes no LLM calls. Export again to refresh newer logs.
Source text is the converter's wording, not a new transcription of the PDF;
Stage A substeps were not separately traced in this run. No live job-launch UI
or reviewer-label persistence is included. Runs need `debug=True` to capture
the content needed for inspection.

## Run the tests

```bash
uv run --frozen pytest -q
```

## Repository layout

```text
src/credit_agreement_extractor/  # Python package
tests/                           # unit and regression tests
docs/                            # architecture, plans, and corpus audits
raw_documents/pdf/               # immutable source PDFs
raw_documents/htm/               # immutable source HTML/HTM files
tmp/converted/                    # ignored generated conversion artifacts
tmp/stage_b/                      # ignored B1–B4 artifacts and B3 checkpoints
tmp/runs/                         # ignored local telemetry and debug snapshots
```

Files under `raw_documents/` are the preserved public source corpus. Do not
rename, overwrite, delete, or silently transform them. Generated artifacts and
extraction results belong outside that directory.

## Development conventions

- Use `uv` and the project virtual environment for all Python work.
- Keep conversion, legal-term extraction, LLM reasoning, validation, and
  evidence capture independently testable.
- Update the pipeline diagram and build backlog together when a tracked
  component starts or finishes.
- Do not mark a diagram component implemented until its acceptance checks pass.
- Preserve uncertainty and source wording instead of guessing legal facts.

See [`AGENTS.md`](AGENTS.md) for the complete project instructions.
