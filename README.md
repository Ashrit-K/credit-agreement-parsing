# Credit Agreement Parser

A Python pipeline for converting public credit agreements into structured,
evidence-backed JSON. The target output covers parties, interest terms,
maturity and extension provisions, covenants, repayment terms, call protection,
and other material agreement terms.

The project is under active development. Document conversion is operational;
topic mapping and substantive LLM extraction are still planned. The current
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
| Versioned hierarchy sidecar | Pending (`A10`) |
| Page-first chunks and topic map | Planned (`Stage B`) |
| Shared OpenCode LLM interface | Planned (`Stage C`) |
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

To prepare for future live LLM calls, copy the environment template and add
credentials only to the local `.env` file:

```bash
cp .env.example .env
```

```dotenv
OPENCODE_API_KEY=your-key-here
OPENCODE_MODEL=your-model-id
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_API_STYLE=responses
```

The `.env` file is ignored by Git. Never commit API keys or other credentials.
The OpenCode transport layer is not wired into the extraction pipeline yet, so
these settings are currently reserved for that planned stage.

## Convert a document

`convert_document()` accepts a PDF, HTML, or HTM path without changing the
source file:

```python
from credit_agreement_extractor import convert_document

artifact = convert_document("raw_documents/pdf/example.pdf")

print(artifact.docling_json_path)
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
├── document.md            # readable development and review copy
└── manifest.json          # source identity and conversion configuration
```

The SHA-256 value is a fingerprint calculated from the source bytes. Repeating
a conversion can reuse a complete cache entry only when both the source
fingerprint and conversion profile match. The planned `A10` increment will add
`document.hierarchy.json` to this artifact set.

## Party-extraction scaffold

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
