# Credit Agreement PDF Parser — Implementation Plan

## Context

We need to build a hybrid NLP/OCR parser that ingests PDF credit agreements and outputs structured JSON with full provenance tracking. The system must handle multi-tranche deals, amendments, covenant extraction, and build per-document knowledge graphs (NetworkX v1, Neo4j-ready schema). LLM layer is scaffolded but inactive in v1. UI is a simple Streamlit app.

**Current state (as of 2026-03-16):** All 6 phases implemented and functional. 43 valid PDFs in `raw_documents/pdf/`, Python 3.13 venv active, all dependencies installed, 9/9 tests passing. Centralized pattern system (`field_patterns.py`) added post-Phase 3 to improve extraction coverage.

---

## Project Structure

```
Credit_Agreement_Parsing/
├── .env                          # LLM API keys (scaffold, empty for v1)
├── .gitignore
├── requirements.txt
├── raw_documents/                # Existing — untouched
├── scripts/                      # Existing — untouched
├── docs/
│   └── API_REFERENCE.md          # Detailed module/function documentation
├── src/
│   ├── __init__.py
│   ├── config.py                 # Paths, constants, .env loading
│   ├── field_patterns.py         # ← NEW: Centralized synonyms & regex for all extractors
│   ├── models/
│   │   ├── schema.py             # Pydantic models (JSON output contract)
│   │   └── graph_ontology.py     # NetworkX node/edge type definitions
│   ├── ingestion/
│   │   ├── pdf_extractor.py      # pdfplumber text + table extraction
│   │   ├── ocr_fallback.py       # pytesseract + pdf2image for scanned pages
│   │   └── page_segmenter.py     # Spatial layout → blocks with provenance IDs
│   ├── parsing/
│   │   ├── section_detector.py   # Regex for ARTICLE/SECTION headers
│   │   ├── party_extractor.py    # Borrower, lender, agent, guarantor
│   │   ├── facility_extractor.py # Facility type, amount, dates, currency
│   │   ├── interest_extractor.py # Rate type, benchmark, spread, floor, cap, pricing grid
│   │   ├── schedule_extractor.py # Amortization, call protection, ticking fees
│   │   ├── covenant_extractor.py # Financial, negative, affirmative covenants + thresholds
│   │   ├── amendment_extractor.py# Amendment refs, what changed
│   │   └── table_parser.py       # Pricing grids, amort schedules, covenant tables
│   ├── knowledge_graph/
│   │   ├── builder.py            # Builds per-document NetworkX DiGraph
│   │   └── queries.py            # Utility queries over the graph
│   ├── llm/
│   │   ├── interface.py          # Abstract LLMProvider class (scaffold)
│   │   └── config.py             # .env-based API key loading (scaffold)
│   └── pipeline.py               # Orchestrates: ingest → parse → graph → JSON
├── app/
│   └── streamlit_app.py          # Upload PDF, process, show preview + JSON
├── output/
│   ├── json/                     # Generated JSON per document
│   └── graphs/                   # Serialized NetworkX graphs
└── tests/
    ├── test_pdf_extractor.py
    ├── test_section_detector.py
    └── test_pipeline.py
```

---

## Dependencies (`requirements.txt`)

```
pdfplumber>=0.11.4
pdf2image>=1.17.0
pytesseract>=0.3.13
spacy>=3.8.0          # Note: 3.7.6 fails on Python 3.13; installed 3.8.11
pydantic>=2.10.5
networkx>=3.4.2
streamlit>=1.41.1
python-dotenv>=1.0.1
pytest>=8.3.4
```

> **Note:** `spacy==3.7.6` does not build on Python 3.13. The installed version is `spacy==3.8.11`.

System deps: `brew install poppler tesseract`

---

## Implementation Order (6 Phases)

### Phase 1: Foundation ✅ Complete
1. Create directory structure, venv, install deps, `.env`, `.gitignore`, `config.py`
2. **`models/schema.py`** — Pydantic models: `CreditAgreementDocument` (top-level), `SourceRef`, `Party`, `Facility`, `InterestTerms`, `PricingGridTier`, `Covenant`, `CovenantThreshold`, `StepDown`, `AmortizationSchedule`, `AmendmentInfo`. Every field carries a `source_ref` for provenance.
3. **`models/graph_ontology.py`** — Node types (Document, Party, Facility, InterestTerms, Covenant, Threshold) and edge types (HAS_PARTY, HAS_FACILITY, HAS_COVENANT, AMENDS, etc.)

### Phase 2: Ingestion ✅ Complete
4. **`ingestion/pdf_extractor.py`** — pdfplumber page-by-page text + table extraction. Flags pages with <50 chars for OCR fallback.
5. **`ingestion/page_segmenter.py`** — Splits page text into blocks/paragraphs. Assigns provenance IDs: `{doc_id}/p{page}/b{block}/l{line}`.
6. **`ingestion/ocr_fallback.py`** — pytesseract for flagged pages. Degrades gracefully without poppler/tesseract.

### Phase 3: Parsing ✅ Complete
7. **`parsing/section_detector.py`** — Regex for `ARTICLE I`, `SECTION 2.01`, `PART I`, `CLAUSE 1.1`, etc. Builds hierarchical `SectionTree` mapping sections to text blocks. Handles cross-page sections and multi-line titles.
8. **`parsing/party_extractor.py`** — spaCy NER + regex on preamble and signature pages. 5 party roles from `PARTY_ROLE_SYNONYMS`.
9. **`parsing/facility_extractor.py`** — Section-targeted: 9 facility types, amounts (`$X million`), dates, currency, multi-tranche detection. Uses `SECTION_KEYWORDS["facility"]` (10 keywords).
10. **`parsing/interest_extractor.py`** — 12 benchmarks (SOFR, Term SOFR, LIBOR, EURIBOR, SONIA, Prime, ABR, Base Rate, Fed Funds, BBSY, CDOR, TIBOR), spread, floor, cap, PIK. Uses `SECTION_KEYWORDS["interest"]` (9 keywords).
11. **`parsing/table_parser.py`** — Credit-agreement-specific table classification and cleanup.
12. **`parsing/covenant_extractor.py`** — 10 financial covenant types with ratio thresholds + step-downs, 11 negative covenant types, 12 affirmative covenant types.
13. **`parsing/amendment_extractor.py`** + **`schedule_extractor.py`** — Amendment refs (ordinals through 12th), amortization schedules, call protection (13 patterns), ticking fees (5 patterns).

### Phase 3.5: Centralized Patterns ✅ Complete (added post-Phase 3)
14. **`field_patterns.py`** — Single source of truth for all regex patterns and synonyms. All extractors refactored to import from this file. Defines 200+ patterns across 20+ field groups. Adding new synonyms requires zero extractor code changes.

### Phase 4: Integration ✅ Complete
15. **`pipeline.py`** — Wires ingest → parse → assemble `CreditAgreementDocument` → build graph. Supports `progress_callback` for UI integration (13 progress stages).
16. **`knowledge_graph/builder.py`** — Takes Pydantic model, builds NetworkX DiGraph with provenance on every node. Export to JSON/GEXF.
17. **`llm/interface.py`** + **`llm/config.py`** — Abstract `LLMProvider` + `MockLLMProvider` (no-op for v1).

### Phase 5: UI ✅ Complete
18. **`app/streamlit_app.py`** — Upload widget + "Process" button. Real-time progress bar showing extraction stage. Tabbed output: Overview, Facilities, Covenants, Amendments, Raw JSON, Knowledge Graph summary. Can also select from existing PDFs in `raw_documents/pdf/`.

### Phase 6: Validation ✅ In Progress
19. Pipeline tested on multiple PDFs. Maturity date extraction fix applied. Pattern coverage expanded via `field_patterns.py`. 9/9 unit tests passing. Full batch coverage report pending.

---

## Key Design Decisions

- **pdfplumber** over PyMuPDF: superior table extraction for pricing grids/amort schedules
- **Per-page processing**: bounded memory, provenance tracking, fault isolation
- **Regex for section detection**: credit agreement headers are formulaic; regex > ML here
- **spaCy for entity extraction**: party names, dates, amounts where NER adds value
- **Amendments as standalone docs**: tagged with `amendment_to` ref, NO auto-merging (v2 feature)
- **Multi-tranche**: `facilities` is a list; each `Facility` has its own `InterestTerms`
- **Provenance ID format**: `{doc_id}/p{page}/b{block}/l{line}` — stable, human-readable, hierarchical
- **Centralized pattern file** (`field_patterns.py`): all regex patterns and synonyms in one file. Extractors import compiled patterns — no inline regex. Expanding coverage = adding synonyms, not changing extractor logic.
- **Smart quote tolerance**: maturity/effective date patterns handle `"`, `\u201c`, `\u201d` wrapping to match SEC filing formatting quirks

---

## Test Documents (early validation)

| File | Purpose |
|------|---------|
| `011_credit_agreement.pdf` | Small, straightforward agreement |
| `022_exhibit101-revolvingcredit.pdf` | Revolving credit, SEC format |
| `029_exhibit101-firstamendmentt.pdf` | Amendment — tests amendment extractor |
| `008_BAA_Redacted_Facility_Agreement.pdf` | Large (15MB), multi-tranche UK facility |

---

## Verification

- **Phase 1**: Import Pydantic models successfully
- **Phase 2**: Extract text from 3+ PDFs, verify page counts and block IDs
- **Phase 3**: Compare extractor output against manually inspected ground truth on test docs
- **Phase 4**: Full pipeline on 5 PDFs, inspect JSON completeness and graph node/edge counts
- **Phase 5**: Streamlit: upload → preview + JSON renders correctly
- **Phase 6**: Batch all 43 PDFs, target >80% extraction for parties/facility type, >60% for covenants
