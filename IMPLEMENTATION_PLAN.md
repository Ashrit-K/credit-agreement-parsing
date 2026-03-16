# Credit Agreement PDF Parser — Implementation Plan

## Context

We need to build a hybrid NLP/OCR parser that ingests PDF credit agreements and outputs structured JSON with full provenance tracking. The system must handle multi-tranche deals, amendments, covenant extraction, and build per-document knowledge graphs (NetworkX v1, Neo4j-ready schema). LLM layer is scaffolded but inactive in v1. UI is a simple Streamlit app.

**Current state:** 43 valid PDFs in `raw_documents/pdf/`, Python 3.13 available, no packages or project structure yet.

---

## Project Structure

```
Credit_Agreement_Parsing/
├── .env                          # LLM API keys (scaffold, empty for v1)
├── .gitignore
├── requirements.txt
├── raw_documents/                # Existing — untouched
├── scripts/                      # Existing — untouched
├── src/
│   ├── __init__.py
│   ├── config.py                 # Paths, constants, .env loading
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
pdfplumber==0.11.4
pdf2image==1.17.0
pytesseract==0.3.13
spacy==3.7.6
pydantic==2.10.5
networkx==3.4.2
streamlit==1.41.1
python-dotenv==1.0.1
pytest==8.3.4
```

System deps: `brew install poppler tesseract`

---

## Implementation Order (6 Phases)

### Phase 1: Foundation
1. Create directory structure, venv, install deps, `.env`, `.gitignore`, `config.py`
2. **`models/schema.py`** — Pydantic models: `CreditAgreementDocument` (top-level), `SourceRef`, `Party`, `Facility`, `InterestTerms`, `PricingGridTier`, `Covenant`, `CovenantThreshold`, `StepDown`, `AmortizationSchedule`, `AmendmentInfo`. Every field carries a `source_ref` for provenance.
3. **`models/graph_ontology.py`** — Node types (Document, Party, Facility, InterestTerms, Covenant, Threshold) and edge types (HAS_PARTY, HAS_FACILITY, HAS_COVENANT, AMENDS, etc.)

### Phase 2: Ingestion
4. **`ingestion/pdf_extractor.py`** — pdfplumber page-by-page text + table extraction. Flags pages with <50 chars for OCR fallback.
5. **`ingestion/page_segmenter.py`** — Splits page text into blocks/paragraphs. Assigns provenance IDs: `{doc_id}/p{page}/b{block}/l{line}`.
6. **`ingestion/ocr_fallback.py`** — pytesseract for flagged pages.

### Phase 3: Parsing
7. **`parsing/section_detector.py`** — Regex for `ARTICLE I`, `SECTION 2.01`, etc. Builds hierarchical `SectionTree` mapping sections to text blocks. Handles cross-page sections.
8. **`parsing/party_extractor.py`** — spaCy NER + regex on preamble and signature pages.
9. **`parsing/facility_extractor.py`** — ARTICLE II: facility type, amounts (`$X million`), dates, currency, multi-tranche detection.
10. **`parsing/interest_extractor.py`** — Benchmark (SOFR/LIBOR/EURIBOR), spread, floor, cap, PIK, pricing grid tables.
11. **`parsing/table_parser.py`** — Credit-agreement-specific table classification and cleanup.
12. **`parsing/covenant_extractor.py`** — Financial covenants (leverage ratio, coverage ratio + thresholds + step-downs), negative covenants, affirmative covenants.
13. **`parsing/amendment_extractor.py`** + **`schedule_extractor.py`** — Amendment refs, amortization schedules, call protection, ticking fees.

### Phase 4: Integration
14. **`pipeline.py`** — Wires ingest → parse → assemble `CreditAgreementDocument` → build graph.
15. **`knowledge_graph/builder.py`** — Takes Pydantic model, builds NetworkX DiGraph with provenance on every node. Export to JSON/GEXF.
16. **`llm/interface.py`** + **`llm/config.py`** — Abstract `LLMProvider` + `MockLLMProvider` (no-op for v1).

### Phase 5: UI
17. **`app/streamlit_app.py`** — Upload widget + "Process" button. Two columns: left = PDF preview (page images via pdf2image), right = tabbed JSON output (Overview, Facilities, Covenants, Schedules, Amendment, Raw JSON, Knowledge Graph viz).

### Phase 6: Validation
18. Run pipeline on all 43 PDFs. Produce coverage report per field. Tune regex patterns.

---

## Key Design Decisions

- **pdfplumber** over PyMuPDF: superior table extraction for pricing grids/amort schedules
- **Per-page processing**: bounded memory, provenance tracking, fault isolation
- **Regex for section detection**: credit agreement headers are formulaic; regex > ML here
- **spaCy for entity extraction**: party names, dates, amounts where NER adds value
- **Amendments as standalone docs**: tagged with `amendment_to` ref, NO auto-merging (v2 feature)
- **Multi-tranche**: `facilities` is a list; each `Facility` has its own `InterestTerms`
- **Provenance ID format**: `{doc_id}/p{page}/b{block}/l{line}` — stable, human-readable, hierarchical

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
