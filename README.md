# Credit Agreement PDF Parser

A hybrid NLP/OCR parser that ingests PDF credit agreements and outputs structured JSON with full provenance tracking and per-document knowledge graphs.

## What It Does

The parser takes any credit agreement PDF — revolving credit facilities, term loans, amendments, multi-tranche deals — and extracts structured data across six dimensions:

1. **Parties** — Borrower, lender, administrative agent, guarantor, arranger
2. **Facilities** — Type (revolving, term loan A/B, bridge, delayed draw), amount, currency, dates
3. **Interest Terms** — Benchmark rate (12 benchmarks: SOFR, Term SOFR, LIBOR, EURIBOR, SONIA, Prime, ABR, Base Rate, Fed Funds, BBSY, CDOR, TIBOR), spread, floor, cap, PIK, pricing grids
4. **Covenants** — Financial (leverage ratio, coverage ratios + thresholds + step-downs), negative (liens, indebtedness, restricted payments), affirmative (reporting, insurance)
5. **Amendments** — Amendment number, date, original agreement reference, sections amended
6. **Schedules** — Amortization schedules, call protection, ticking fees

Every extracted field carries a **provenance reference** (`doc_id/p{page}/b{block}/l{line}`) tracing it back to the source text.

## Architecture

```
PDF ──► Ingestion ──► Parsing ──► Assembly ──► Knowledge Graph
         │              │            │              │
     pdfplumber     regex+NER    Pydantic       NetworkX
     OCR fallback   spaCy        validation     DiGraph
     segmentation   tables
                       │
                  field_patterns.py
                  (centralized synonyms & regex)
```

### Centralized Pattern System (`src/field_patterns.py`)

All extractors import their regex patterns and synonyms from a single file. To expand coverage for any field, add new synonyms or regex alternatives in `field_patterns.py` — no extractor code changes needed. Currently defines **200+ regex patterns** across 20+ field groups including facility types (9), benchmarks (12), financial covenants (10), negative covenants (11), affirmative covenants (12), party roles (5), and date/amount/ratio patterns.

### Ingestion Layer (`src/ingestion/`)

| Module | What it does |
|--------|-------------|
| `pdf_extractor.py` | pdfplumber page-by-page text + table extraction. Flags pages with <50 chars for OCR. |
| `ocr_fallback.py` | pytesseract + pdf2image for scanned/image-heavy pages. Degrades gracefully if poppler/tesseract not installed. |
| `page_segmenter.py` | Splits page text into paragraph-level blocks. Assigns hierarchical provenance IDs. |

### Parsing Layer (`src/parsing/`)

| Module | Data source | What it extracts |
|--------|-------------|-----------------|
| `section_detector.py` | Text blocks | ARTICLE/SECTION/PART/CLAUSE headers → hierarchical section tree |
| `party_extractor.py` | Text blocks (preamble + signature pages) | Party names and roles via regex + spaCy, with precision filters to suppress narrative false positives |
| `facility_extractor.py` | Text blocks (ARTICLE II sections) | Facility type (9 types), dollar amounts, effective/maturity dates, multi-tranche |
| `interest_extractor.py` | Text blocks | Benchmark rate (12 benchmarks), spread (bps/%), floor, cap, PIK flag, default rate |
| `table_parser.py` | pdfplumber tables | Classifies tables (pricing grid, amortization, covenant) and parses into structured models |
| `covenant_extractor.py` | Text blocks | Financial covenants (10 types) with ratio thresholds, negative covenants (11 types), affirmative covenants (12 types) |
| `amendment_extractor.py` | Text blocks | Amendment detection, number, date, sections amended |
| `schedule_extractor.py` | Tables + text blocks | Amortization entries, call protection terms, ticking fees |

### Data Models (`src/models/`)

| Module | Contents |
|--------|---------|
| `schema.py` | 12 Pydantic models defining the JSON output contract: `CreditAgreementDocument`, `Party`, `Facility`, `InterestTerms`, `PricingGridTier`, `Covenant`, `CovenantThreshold`, `StepDown`, `AmortizationSchedule`, `AmortizationEntry`, `AmendmentInfo`, `SourceRef` |
| `graph_ontology.py` | 7 node types (`Document`, `Party`, `Facility`, `InterestTerms`, `Covenant`, `Threshold`, `Amendment`) and 10 edge types (`HAS_PARTY`, `HAS_FACILITY`, `BORROWS_UNDER`, etc.) |

### Knowledge Graph (`src/knowledge_graph/`)

| Module | What it does |
|--------|-------------|
| `builder.py` | Builds a NetworkX DiGraph from the parsed Pydantic model. Provenance on every node. Exports to JSON and GEXF (Neo4j-ready). |
| `queries.py` | Utility queries: get facilities, covenants, parties-for-facility, thresholds-for-covenant, graph summary statistics. |

### Pipeline (`src/pipeline.py`)

Orchestrates the full flow:

1. **Extract** — PDF text + tables via pdfplumber
2. **OCR** — Fallback for scanned pages
3. **Segment** — Split into provenance-tagged blocks
4. **Detect sections** — Build section tree
5. **Extract entities** — Parties, facilities, interest terms, covenants, amendments, schedules
6. **Assemble** — Populate `CreditAgreementDocument` Pydantic model
7. **Build graph** — Create NetworkX DiGraph
8. **Save** — Write JSON + graph to `output/`

Supports a `progress_callback` parameter for UI integration.

### LLM Scaffold (`src/llm/`)

Abstract `LLMProvider` interface with a `MockLLMProvider` (no-op) for v1. Ready for v2 integration with OpenAI/Anthropic APIs.

### Streamlit UI (`app/streamlit_app.py`)

- Upload a PDF or select from existing files in `raw_documents/pdf/`
- Real-time progress bar showing extraction stage
- Tabbed output: Overview, Facilities, Covenants, Amendments, Raw JSON, Knowledge Graph summary

## Setup

### Prerequisites

- Python 3.11+
- (Optional) `brew install poppler tesseract` for OCR support on scanned PDFs

### Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pdfplumber | 0.11.x | PDF text + table extraction |
| pdf2image | 1.17.x | PDF page → image conversion (OCR) |
| pytesseract | 0.3.x | OCR engine wrapper |
| spacy | 3.x | NER for party extraction |
| pydantic | 2.x | Data validation and JSON schema |
| networkx | 3.x | Knowledge graph construction |
| streamlit | 1.x | Web UI |
| python-dotenv | 1.x | Environment variable loading |
| pytest | 8.x | Testing |

## Usage

### Streamlit UI

```bash
source venv/bin/activate
streamlit run app/streamlit_app.py
# Opens at http://localhost:8501
```

### Python API — Single Document

```python
from src.pipeline import process_document

doc, graph = process_document("raw_documents/pdf/011_credit_agreement.pdf")

# Structured output
print(doc.title)
print(doc.facilities[0].facility_type, doc.facilities[0].amount)
for cov in doc.covenants:
    print(f"  [{cov.covenant_type}] {cov.name}")

# Knowledge graph
print(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
```

### Python API — Batch Processing

```python
from src.pipeline import process_batch

results = process_batch("raw_documents/pdf/", limit=10)
for filename, success, error in results:
    status = "OK" if success else f"FAIL: {error}"
    print(f"  {filename}: {status}")
```

### JSON Output

Processed documents are saved to `output/json/` as structured JSON:

```json
{
  "doc_id": "011_credit_agreement_d3a00bb8",
  "file_name": "011_credit_agreement.pdf",
  "title": "STANDBY LINE OF CREDIT AGREEMENT",
  "agreement_date": "",
  "parties": [
    {"name": "Example Corp", "role": "borrower", "source_ref": {"doc_id": "...", "page": 1}}
  ],
  "facilities": [
    {"facility_type": "revolving", "amount": 200000000.0, "currency": "USD"}
  ],
  "covenants": [
    {"covenant_type": "negative", "name": "Limitation on Liens"}
  ]
}
```

### Graph Output

Knowledge graphs are saved to `output/graphs/` as JSON (node-link format) and can be exported to GEXF for Neo4j/Gephi import.

## Testing

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

Tests cover:
- `test_pdf_extractor.py` — PDF extraction returns pages, text, metadata
- `test_section_detector.py` — ARTICLE/SECTION detection and keyword search
- `test_pipeline.py` — End-to-end pipeline produces valid document and graph
- `test_convert_htm_to_pdf.py` — HTML normalization and overflow-fix CSS injection
- `test_party_extractor.py` — party false-positive regression controls
- `test_golden_set_eval.py` — manifest-driven golden-set evaluation and anomaly flags

### Golden Set Regression Review

Run the parser across curated regression docs and flag suspicious outputs:

```bash
venv/bin/python scripts/evaluate_golden_set.py --fail-on-anomaly
```

Outputs:
- terminal table with per-document counts and anomaly tags
- CSV report at `output/golden_set/golden_set_eval.csv`
- thresholds and review focus loaded from `raw_documents/golden_set/golden_set_manifest.json`

## Project Structure

```
Credit_Agreement_Parsing/
├── app/
│   └── streamlit_app.py          # Web UI
├── docs/
│   └── API_REFERENCE.md          # Detailed module/function documentation
├── src/
│   ├── config.py                 # Paths, constants, .env loading
│   ├── field_patterns.py         # Centralized synonyms & regex for all extractors
│   ├── pipeline.py               # Orchestration: ingest → parse → graph → JSON
│   ├── models/
│   │   ├── schema.py             # Pydantic output models
│   │   └── graph_ontology.py     # Node/edge type definitions
│   ├── ingestion/
│   │   ├── pdf_extractor.py      # pdfplumber extraction
│   │   ├── ocr_fallback.py       # pytesseract OCR
│   │   └── page_segmenter.py     # Block segmentation + provenance
│   ├── parsing/
│   │   ├── section_detector.py   # ARTICLE/SECTION headers
│   │   ├── party_extractor.py    # Borrower, lender, agent, guarantor
│   │   ├── facility_extractor.py # Facility type, amount, dates
│   │   ├── interest_extractor.py # Rate, benchmark, spread, floor
│   │   ├── table_parser.py       # Pricing grids, amort tables
│   │   ├── covenant_extractor.py # Financial, negative, affirmative
│   │   ├── amendment_extractor.py# Amendment refs and changes
│   │   └── schedule_extractor.py # Amortization, call protection, fees
│   ├── knowledge_graph/
│   │   ├── builder.py            # NetworkX DiGraph construction
│   │   └── queries.py            # Graph query utilities
│   └── llm/
│       ├── interface.py          # Abstract LLMProvider (v2 scaffold)
│       └── config.py             # API key loading (v2 scaffold)
├── output/
│   ├── json/                     # Generated JSON per document
│   └── graphs/                   # Serialized knowledge graphs
├── raw_documents/
│   ├── pdf/                      # 45 source PDFs
│   └── htm/                      # 34 HTM source files
├── tests/
│   ├── test_pdf_extractor.py
│   ├── test_section_detector.py
│   ├── test_pipeline.py
│   ├── test_convert_htm_to_pdf.py
│   └── test_party_extractor.py
├── scripts/                      # Download and conversion utilities
├── requirements.txt
└── .env                          # API keys (scaffold, not committed)
```

## How Extraction Works

### Text-Based Extraction (primary)

Most extractors operate on **text blocks** — paragraph-level chunks split from pdfplumber output. They use:

- **Centralized regex patterns** (`src/field_patterns.py`) — all 200+ patterns defined in one file covering dollar amounts (`$X million`), dates (5 formats), ratios (`3.50 to 1.00`), section headers (`ARTICLE`, `SECTION`, `PART`, `CLAUSE`), facility types (9 types), benchmarks (12 types), covenants (33 types), party roles (5 roles)
- **spaCy NER** (`en_core_web_sm`) for organization entity recognition in party extraction
- **Section-aware scanning** — extractors target specific ARTICLE/SECTION ranges using `SECTION_KEYWORDS` (9 keyword groups, ~50 keywords total) from `field_patterns.py`

### Table-Based Extraction (secondary)

The table parser classifies pdfplumber-extracted tables by type:

- **Pricing grids** — leverage tiers mapped to spread/commitment fee basis points
- **Amortization tables** — date/amount/percentage schedules
- **Covenant tables** — period/threshold matrices

The schedule extractor bridges both sources, trying table parsing first and falling back to inline text patterns.

### Provenance Tracking

Every extracted value carries a `SourceRef` with:
- `doc_id` — unique document identifier
- `page` — 1-indexed page number
- `block` — paragraph block index within the page
- `line` — line number within the block (optional)
- `text_snippet` — source text excerpt

This enables traceability from any JSON field back to the exact location in the source PDF.

## Known Limitations (v1)

- **Party extraction** now prioritizes precision over recall. Generic/legal prose false positives are filtered aggressively, so some edge-case aliases may be omitted.
- **Section detection** requires conventional ARTICLE/SECTION formatting. Agreements with non-standard headings may have weaker extraction.
- **Interest terms** in tables only (without surrounding prose) may be missed by the text-block-based extractor.
- **OCR** requires poppler and tesseract installed. Without them, scanned pages are skipped gracefully.
- **No cross-document linking** — amendments are tagged but not merged with the original agreement.
- **LLM layer** is scaffolded but inactive.

## v2 Roadmap

- LLM-assisted extraction for ambiguous clauses and non-standard formatting
- Cross-document amendment merging
- Neo4j graph database integration
- Improved table → extractor wiring (pricing grid data feeding into InterestTerms)
- Ground-truth validation suite with manually annotated documents
- Batch processing dashboard with coverage metrics
