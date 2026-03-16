# API Reference

Detailed documentation for every Python module and function in the Credit Agreement Parser.

---

## Table of Contents

- [src/config.py](#srcconfigpy)
- [src/field_patterns.py](#srcfield_patternspy)
- [src/pipeline.py](#srcpipelinepy)
- [src/models/schema.py](#srcmodelsschemapy)
- [src/models/graph_ontology.py](#srcmodelsgraph_ontologypy)
- [src/ingestion/pdf_extractor.py](#srcingestionpdf_extractorpy)
- [src/ingestion/page_segmenter.py](#srcingestionpage_segmenterpy)
- [src/ingestion/ocr_fallback.py](#srcingestionocr_fallbackpy)
- [src/parsing/section_detector.py](#srcparsingsection_detectorpy)
- [src/parsing/party_extractor.py](#srcparsingparty_extractorpy)
- [src/parsing/facility_extractor.py](#srcparsingfacility_extractorpy)
- [src/parsing/interest_extractor.py](#srcparsinginterest_extractorpy)
- [src/parsing/table_parser.py](#srcparsingtable_parserpy)
- [src/parsing/covenant_extractor.py](#srcparsingcovenant_extractorpy)
- [src/parsing/amendment_extractor.py](#srcparsingamendment_extractorpy)
- [src/parsing/schedule_extractor.py](#srcparsingschedule_extractorpy)
- [src/knowledge_graph/builder.py](#srcknowledge_graphbuilderpy)
- [src/knowledge_graph/queries.py](#srcknowledge_graphqueriespy)
- [src/llm/interface.py](#srcllminterfacepy)
- [src/llm/config.py](#srcllmconfigpy)
- [app/streamlit_app.py](#appstreamlit_apppy)

---

## `src/config.py`

Central configuration. Loads environment variables from `.env` and defines project-wide constants.

### Constants

| Name | Type | Description |
|------|------|-------------|
| `PROJECT_ROOT` | `Path` | Absolute path to the repository root (parent of `src/`). |
| `RAW_PDF_DIR` | `Path` | `raw_documents/pdf/` — location of source PDFs. |
| `OUTPUT_JSON_DIR` | `Path` | `output/json/` — where parsed JSON files are written. Created on import if missing. |
| `OUTPUT_GRAPH_DIR` | `Path` | `output/graphs/` — where graph exports are written. Created on import if missing. |
| `OCR_CHAR_THRESHOLD` | `int` | `50` — pages with fewer characters than this are flagged for OCR. |
| `LLM_API_KEY` | `str` | From `OPENAI_API_KEY` env var. Empty in v1. |
| `LLM_MODEL` | `str` | From `LLM_MODEL` env var. Defaults to `"gpt-4"`. |

---

## `src/field_patterns.py`

**Centralized synonym and regex pattern definitions for all extracted fields.** Every extractor imports its patterns from this single file. To expand coverage, add new synonyms or regex alternatives here — no extractor code changes needed.

### Helper Function

#### `compile_patterns(mapping, flags=re.IGNORECASE)`

Compile a `{label: [pattern_strings]}` dict into `[(label, compiled_regex)]` pairs. Multiple pattern strings for the same label are joined with `|` so that a single compiled regex covers all synonyms.

| Parameter | Type | Description |
|-----------|------|-------------|
| `mapping` | `dict[str, list[str]]` | Maps canonical labels to lists of regex pattern strings. |
| `flags` | `int` | Regex compile flags. Default: `re.IGNORECASE`. |

**Returns:** `list[tuple[str, re.Pattern[str]]]`

### Exported Constants

#### Section Targeting

| Name | Type | Description |
|------|------|-------------|
| `SECTION_KEYWORDS` | `dict[str, list[str]]` | 9 keyword groups (`facility`, `interest`, `covenant_financial`, `covenant_negative`, `covenant_affirmative`, `amendment`, `schedule`, `prepayment`, `fees`) mapping to section-title search terms. ~50 keywords total. |

#### Facility Types

| Name | Type | Description |
|------|------|-------------|
| `FACILITY_TYPE_SYNONYMS` | `dict[str, list[str]]` | 9 facility types: `revolving`, `term_loan_b`, `term_loan_a`, `term_loan`, `delayed_draw`, `bridge`, `letter_of_credit`, `swingline`, `incremental`. Each with 3-5 regex alternatives. |
| `FACILITY_TYPE_PATTERNS` | `list[tuple[str, Pattern]]` | Compiled from `FACILITY_TYPE_SYNONYMS` via `compile_patterns()`. |

#### Dollar Amounts

| Name | Type | Description |
|------|------|-------------|
| `AMOUNT_PATTERNS` | `list[str]` | 3 patterns: `$X million`, `X USD`, `GBP/EUR/£/€ X`. |
| `AMOUNT_MULTIPLIERS` | `dict[str, float]` | Maps `million`, `mn`, `mm`, `m`, `billion`, `bn` to numeric multipliers. |
| `CURRENCY_INDICATORS` | `dict[str, list[str]]` | 5 currencies (USD, GBP, EUR, CAD, AUD) with symbol/text patterns. |

#### Dates

| Name | Type | Description |
|------|------|-------------|
| `DATE_PATTERNS` | `list[str]` | 5 date formats: `January 1, 2024`, `Jan. 1, 2024`, `1/1/2024`, `2024-01-01`, `1 January 2024` (UK). |
| `DATE_RE` | `re.Pattern` | Combined compiled regex matching any date format. |
| `MATURITY_SYNONYMS` | `list[str]` | 7 patterns: `maturity date`, `final maturity date`, `matures on`, `terminates on`, etc. Handles smart quotes around terms. |
| `MATURITY_RE` | `re.Pattern` | Compiled: maturity-synonym followed by a date capture group. |
| `EFFECTIVE_SYNONYMS` | `list[str]` | 6 patterns: `effective date`, `closing date`, `dated as of`, `entered into`, `executed on`, etc. Handles smart quotes. |
| `EFFECTIVE_RE` | `re.Pattern` | Compiled: effective-synonym followed by a date capture group. |

#### Interest Rate Benchmarks

| Name | Type | Description |
|------|------|-------------|
| `BENCHMARK_SYNONYMS` | `dict[str, list[str]]` | 12 benchmarks: `Term SOFR`, `SOFR`, `LIBOR`, `EURIBOR`, `Prime Rate`, `ABR`, `Base Rate`, `Federal Funds Rate`, `SONIA`, `BBSY`, `CDOR`, `TIBOR`. Each with 2-5 regex alternatives. |
| `BENCHMARK_PATTERNS` | `list[tuple[str, Pattern]]` | Compiled from `BENCHMARK_SYNONYMS`. |
| `SPREAD_SYNONYMS` | `list[str]` | 5 patterns for spread extraction (%, bps, per annum). |
| `FLOOR_SYNONYMS` | `list[str]` | 7 patterns for interest rate floors. |
| `PIK_SYNONYMS` | `list[str]` | 6 patterns for payment-in-kind detection. |

#### Party Roles

| Name | Type | Description |
|------|------|-------------|
| `PARTY_ROLE_SYNONYMS` | `dict[str, list[str]]` | 5 roles: `borrower` (5 synonyms), `lender` (6), `administrative_agent` (5), `guarantor` (4), `arranger` (5). |

#### Covenants

| Name | Type | Description |
|------|------|-------------|
| `FINANCIAL_COVENANT_SYNONYMS` | `dict[str, dict]` | 10 types: leverage ratio, interest coverage, fixed charge coverage, senior leverage, debt service coverage, net worth, capex, EBITDA, liquidity, total debt. Each entry has `metric` and `patterns` keys. |
| `FINANCIAL_COVENANT_PATTERNS` | `list[tuple[str, str, Pattern]]` | Compiled: `(name, metric, regex)` tuples. |
| `NEGATIVE_COVENANT_SYNONYMS` | `dict[str, list[str]]` | 11 types: liens, indebtedness, restricted payments, dividends, asset sales, investments, mergers, affiliate transactions, restrictive agreements, sale-leaseback, line of business. |
| `NEGATIVE_COVENANT_PATTERNS` | `list[tuple[str, Pattern]]` | Compiled from `NEGATIVE_COVENANT_SYNONYMS`. |
| `AFFIRMATIVE_COVENANT_SYNONYMS` | `dict[str, list[str]]` | 12 types: financial reporting, insurance, compliance with laws, maintenance of properties, books and records, notices, use of proceeds, payment of taxes, corporate existence, inspection rights, environmental compliance, anti-corruption. |
| `AFFIRMATIVE_COVENANT_PATTERNS` | `list[tuple[str, Pattern]]` | Compiled from `AFFIRMATIVE_COVENANT_SYNONYMS`. |

#### Amendments

| Name | Type | Description |
|------|------|-------------|
| `AMENDMENT_DETECTION_SYNONYMS` | `list[str]` | 10 patterns: ordinal amendments, amended and restated, amendment number, modification agreement, waiver, consent, omnibus, restatement, supplemental. |
| `AMENDMENT_ORDINALS` | `dict[str, str]` | Maps ordinal words/abbreviations (`first`→`1`, `1st`→`1`, ... through `twelfth`→`12`). |

#### Schedules & Fees

| Name | Type | Description |
|------|------|-------------|
| `CALL_PROTECTION_SYNONYMS` | `list[str]` | 13 patterns: call protection, prepayment premium, make-whole, soft/hard/no-call, yield maintenance, repricing protection, etc. |
| `TICKING_FEE_SYNONYMS` | `list[str]` | 5 patterns: ticking fee, delayed-draw fee, undrawn fee, availability fee. |

#### Ratios & Testing

| Name | Type | Description |
|------|------|-------------|
| `RATIO_PATTERNS` | `list[str]` | 3 patterns: `X.XX to 1.00`, `X.XXx`, `X.XX:Y.YY`. |
| `TESTING_FREQUENCY_SYNONYMS` | `dict[str, list[str]]` | 4 frequencies: `quarterly`, `annual`, `monthly`, `semi-annual`. |

#### Section Headers

| Name | Type | Description |
|------|------|-------------|
| `SECTION_HEADER_PATTERNS` | `dict[str, list[str]]` | 7 header types: `article_roman`, `article_arabic`, `section_dotted`, `section_loose`, `part`, `clause`, `schedule`. Used by `section_detector.py`. |

---

## `src/pipeline.py`

Orchestrates the full extraction pipeline: ingest, parse, assemble, build graph, save output.

### `process_document(pdf_path, save_output=True, progress_callback=None)`

Runs the complete parsing pipeline on a single PDF.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `pdf_path` | `str \| Path` | required | Path to the PDF file. |
| `save_output` | `bool` | `True` | If `True`, writes JSON to `output/json/` and graph to `output/graphs/`. |
| `progress_callback` | `callable \| None` | `None` | Optional callback `(step: int, total: int, message: str)` for progress reporting. Called 13 times across the pipeline stages. |

**Returns:** `tuple[CreditAgreementDocument, nx.DiGraph]`

**Pipeline steps (13 total):**

1. Extract text and tables from PDF (pdfplumber)
2. OCR fallback on scanned pages
3. Segment pages into text blocks with provenance IDs
4. Detect ARTICLE/SECTION structure
5. Extract parties
6. Extract facility details
7. Extract interest rate terms
8. Extract covenants
9. Extract amendments and schedules
10. Extract document title and date
11. Assemble `CreditAgreementDocument` Pydantic model
12. Build NetworkX knowledge graph
13. Save JSON and graph output files

**Example:**
```python
from src.pipeline import process_document
doc, graph = process_document("raw_documents/pdf/011_credit_agreement.pdf")
print(doc.title, len(doc.facilities), graph.number_of_nodes())
```

### `process_batch(pdf_dir, limit=None)`

Processes all PDFs in a directory.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `pdf_dir` | `str \| Path` | required | Directory containing PDF files. |
| `limit` | `int \| None` | `None` | Max number of files to process. `None` means all. |

**Returns:** `list[tuple[str, bool, str]]` — list of `(filename, success, error_message)` for each file.

### Internal Functions

#### `_generate_doc_id(file_path)`

Generates a deterministic document ID from the file name: `{stem[:40]}_{md5[:8]}`.

**Parameters:** `file_path: Path`
**Returns:** `str` — e.g. `"011_credit_agreement_d3a00bb8"`

#### `_blocks_to_dicts(blocks)`

Converts `TextBlock` dataclasses to dicts with keys `text`, `block_idx`, `page`, `provenance_id` for consumption by the parsing layer.

**Parameters:** `blocks: list[TextBlock]`
**Returns:** `list[dict]`

#### `_collect_all_tables(extraction)`

Flattens all tables from all pages of an `ExtractionResult` into a single list. Normalizes `None` cells to empty strings.

**Parameters:** `extraction: ExtractionResult`
**Returns:** `list[list[list[str]]]`

#### `_extract_title(blocks)`

Scans the first 5 blocks for keywords like "CREDIT AGREEMENT", "FACILITY AGREEMENT", "LOAN AGREEMENT", "AMENDMENT". Returns the first line of the matching block (max 200 chars).

**Parameters:** `blocks: list[dict]`
**Returns:** `str`

#### `_extract_agreement_date(blocks)`

Regex search for `"dated as of {date}"` pattern in the first 10 blocks. Matches full month names (e.g. "January 1, 2024").

**Parameters:** `blocks: list[dict]`
**Returns:** `str` — the date string, or `""` if not found.

---

## `src/models/schema.py`

Pydantic models defining the JSON output contract. Every extracted field is designed to carry a `source_ref` for provenance tracking.

### `SourceRef`

Provenance pointer tracing an extracted value back to its source location.

| Field | Type | Description |
|-------|------|-------------|
| `doc_id` | `str` | Document identifier. |
| `page` | `int \| None` | 1-indexed page number. |
| `block` | `int \| None` | Block index within the page. |
| `line` | `int \| None` | Line index within the block. |
| `text_snippet` | `str` | Source text excerpt (up to ~200 chars). |

**Property:** `provenance_id` — builds `"{doc_id}/p{page}/b{block}/l{line}"` string.

### `Party`

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Party name (e.g. "JPMorgan Chase Bank, N.A."). |
| `role` | `str` | One of: `borrower`, `lender`, `administrative_agent`, `guarantor`, `arranger`, `unknown`. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `PricingGridTier`

A single row of a pricing grid table.

| Field | Type | Description |
|-------|------|-------------|
| `level_name` | `str` | Tier label (e.g. "Level I", "Tier 2"). |
| `leverage_low` | `float \| None` | Lower bound of leverage range. |
| `leverage_high` | `float \| None` | Upper bound of leverage range. |
| `spread_bps` | `float \| None` | Interest spread in basis points. |
| `commitment_fee_bps` | `float \| None` | Commitment fee in basis points. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `InterestTerms`

Interest rate structure for a facility.

| Field | Type | Description |
|-------|------|-------------|
| `rate_type` | `str` | `"fixed"` or `"floating"`. |
| `benchmark` | `str` | Reference rate: `SOFR`, `Term SOFR`, `LIBOR`, `EURIBOR`, `Prime Rate`, `ABR`, `Base Rate`. |
| `spread_bps` | `float \| None` | Spread over benchmark in basis points. |
| `floor_pct` | `float \| None` | Interest rate floor as a percentage. |
| `cap_pct` | `float \| None` | Interest rate cap as a percentage. |
| `default_rate_spread_bps` | `float \| None` | Additional spread applied during default. |
| `pik` | `bool` | `True` if interest can be paid in kind. |
| `pricing_grid` | `list[PricingGridTier]` | Tiered pricing schedule. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `AmortizationEntry`

A single row of an amortization schedule.

| Field | Type | Description |
|-------|------|-------------|
| `date` | `str` | Payment date. |
| `amount` | `float \| None` | Dollar amount. |
| `percentage` | `float \| None` | Percentage of principal. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `AmortizationSchedule`

| Field | Type | Description |
|-------|------|-------------|
| `entries` | `list[AmortizationEntry]` | Ordered schedule rows. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `Facility`

A single credit facility (tranche).

| Field | Type | Description |
|-------|------|-------------|
| `facility_type` | `str` | `revolving`, `term_loan_a`, `term_loan_b`, `delayed_draw`, `bridge`, `letter_of_credit`, or `unknown`. |
| `name` | `str` | Facility name or first line of the source paragraph. |
| `amount` | `float \| None` | Facility size in currency units (e.g. `200000000.0`). |
| `currency` | `str` | ISO currency code. Defaults to `"USD"`. |
| `effective_date` | `str` | Facility effective/closing date. |
| `maturity_date` | `str` | Facility maturity/termination date. |
| `interest_terms` | `InterestTerms \| None` | Attached by the pipeline after extraction. |
| `amortization` | `AmortizationSchedule \| None` | Attached by the pipeline from schedule extraction. |
| `commitment_fee_bps` | `float \| None` | Commitment fee in basis points. |
| `ticking_fee_bps` | `float \| None` | Ticking fee in basis points. |
| `call_protection` | `str` | Call protection description. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `CovenantThreshold`

A single threshold value for a financial covenant at a specific period.

| Field | Type | Description |
|-------|------|-------------|
| `period` | `str` | Time period (e.g. "Q1 2024", "fiscal year ending 12/31/2024"). |
| `value` | `float \| None` | Threshold ratio or amount. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `StepDown`

A covenant step-down provision.

| Field | Type | Description |
|-------|------|-------------|
| `trigger` | `str` | Condition that triggers the step-down (e.g. "leverage ratio < 3.50x"). |
| `new_value` | `str` | New covenant level after step-down (e.g. "3.50:1.00"). |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `Covenant`

| Field | Type | Description |
|-------|------|-------------|
| `covenant_type` | `str` | `"financial"`, `"negative"`, or `"affirmative"`. |
| `name` | `str` | Covenant name (e.g. "Maximum Leverage Ratio", "Limitation on Liens"). |
| `description` | `str` | Source text excerpt (up to 300 chars). |
| `metric` | `str` | Financial metric key (e.g. `leverage_ratio`, `interest_coverage_ratio`). Empty for non-financial covenants. |
| `thresholds` | `list[CovenantThreshold]` | Period-specific threshold values. Financial covenants only. |
| `step_downs` | `list[StepDown]` | Step-down provisions. |
| `testing_frequency` | `str` | `"quarterly"`, `"annual"`, or `""`. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `AmendmentInfo`

| Field | Type | Description |
|-------|------|-------------|
| `amendment_number` | `str` | Numeric or `"A&R"` for Amended and Restated. |
| `amendment_date` | `str` | Date of the amendment. |
| `original_agreement_date` | `str` | Date of the original credit agreement being amended. |
| `parties_to_amendment` | `list[str]` | Party names involved. |
| `sections_amended` | `list[str]` | List of section/article references modified (e.g. `["Section 2.01", "Article III"]`). |
| `summary_of_changes` | `str` | Description of what changed. |
| `source_ref` | `SourceRef \| None` | Provenance. |

### `CreditAgreementDocument`

Top-level output model for a fully parsed credit agreement.

| Field | Type | Description |
|-------|------|-------------|
| `doc_id` | `str` | Unique document identifier. |
| `file_name` | `str` | Source PDF file name. |
| `title` | `str` | Agreement title extracted from the first page. |
| `agreement_date` | `str` | Date the agreement was executed. |
| `effective_date` | `str` | Date the agreement becomes effective. |
| `parties` | `list[Party]` | All extracted parties. |
| `facilities` | `list[Facility]` | All extracted facilities (one per tranche). |
| `covenants` | `list[Covenant]` | All extracted covenants. |
| `amendments` | `list[AmendmentInfo]` | Amendment info (empty if not an amendment). |
| `total_pages` | `int` | Number of pages in the source PDF. |
| `extraction_metadata` | `dict` | Pipeline statistics: `file_size_bytes`, `total_blocks`, `total_tables`, `sections_detected`, `ocr_pages`. |

---

## `src/models/graph_ontology.py`

Defines the knowledge graph schema: node types, edge types, and ID generation.

### Constants

#### `NODE_TYPES`

```python
{
    "Document":      {"attrs": ["doc_id", "title", "agreement_date", "file_name"]},
    "Party":         {"attrs": ["name", "role"]},
    "Facility":      {"attrs": ["facility_type", "name", "amount", "currency", "maturity_date"]},
    "InterestTerms": {"attrs": ["rate_type", "benchmark", "spread_bps", "floor_pct"]},
    "Covenant":      {"attrs": ["covenant_type", "name", "metric", "testing_frequency"]},
    "Threshold":     {"attrs": ["period", "value"]},
    "Amendment":     {"attrs": ["amendment_number", "amendment_date", "summary_of_changes"]},
}
```

#### `EDGE_TYPES`

List of `(source_type, edge_label, target_type)` tuples:

| Source | Edge | Target |
|--------|------|--------|
| Document | `HAS_PARTY` | Party |
| Document | `HAS_FACILITY` | Facility |
| Document | `HAS_COVENANT` | Covenant |
| Document | `HAS_AMENDMENT` | Amendment |
| Facility | `HAS_INTEREST_TERMS` | InterestTerms |
| Covenant | `HAS_THRESHOLD` | Threshold |
| Amendment | `AMENDS` | Document |
| Party | `BORROWS_UNDER` | Facility |
| Party | `LENDS_UNDER` | Facility |
| Party | `AGENT_FOR` | Facility |

### `node_id(node_type, **kwargs)`

Generates a deterministic node ID by joining the type and sorted key=value pairs with `:`.

**Parameters:** `node_type: str`, `**kwargs` — key attributes
**Returns:** `str` — e.g. `"Party:name=JPMorgan:role=lender"`

---

## `src/ingestion/pdf_extractor.py`

Extracts raw text and tables from PDF files using pdfplumber.

### Dataclasses

#### `PageData`

| Field | Type | Description |
|-------|------|-------------|
| `page_num` | `int` | 1-indexed page number. |
| `text` | `str` | Extracted text from the page. |
| `tables` | `list[list[list[str \| None]]]` | Tables extracted by pdfplumber. Each table is a list of rows; each row is a list of cell values. |
| `char_count` | `int` | Length of `text`. Auto-computed in `__post_init__`. |
| `needs_ocr` | `bool` | `True` if `char_count < OCR_CHAR_THRESHOLD`. Auto-set in `__post_init__`. |

#### `PDFMetadata`

| Field | Type | Description |
|-------|------|-------------|
| `file_name` | `str` | PDF file name. |
| `file_size_bytes` | `int` | File size on disk. |
| `total_pages` | `int` | Number of pages. |

#### `ExtractionResult`

| Field | Type | Description |
|-------|------|-------------|
| `pages` | `list[PageData]` | One entry per PDF page. |
| `metadata` | `PDFMetadata` | Document-level metadata. |

### `extract_pdf(pdf_path)`

Opens a PDF with pdfplumber and extracts text and tables page by page.

**Parameters:** `pdf_path: str | Path`
**Returns:** `ExtractionResult`
**Raises:** `FileNotFoundError` if the PDF does not exist.

**Behavior:**
- Iterates `pdf.pages`, calls `page.extract_text()` and `page.extract_tables()` on each.
- Empty text defaults to `""`, empty tables to `[]`.
- `PageData.__post_init__` auto-flags pages with fewer than 50 characters for OCR.

---

## `src/ingestion/page_segmenter.py`

Splits extracted page text into paragraph-level blocks with provenance IDs.

### Dataclasses

#### `TextBlock`

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Full block text (may span multiple lines). |
| `provenance_id` | `str` | Block-level provenance: `{doc_id}/p{page}/b{block}`. |
| `page_num` | `int` | Source page number. |
| `block_num` | `int` | Block index within the page (1-indexed). |
| `lines` | `list[tuple[str, str]]` | List of `(line_text, line_provenance_id)`. Line provenance adds `/l{line}`. |
| `section_heading` | `str \| None` | Most recent ARTICLE/SECTION heading seen before this block. |

### `segment_pages(pages, doc_id)`

Segments page texts into blocks with provenance IDs.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `pages` | `list[PageData]` | Output of `extract_pdf`. |
| `doc_id` | `str` | Unique document identifier, becomes the root of all provenance IDs. |

**Returns:** `list[TextBlock]` — ordered across all pages.

**Behavior:**
- Splits each page's text on double newlines (`\n\n+`) to get paragraph blocks.
- Skips empty blocks and pages with no text.
- Tracks the most recent section heading (matching `ARTICLE|SECTION|EXHIBIT|SCHEDULE|ANNEX` patterns) and attaches it to subsequent blocks via `section_heading`.

### Internal Functions

#### `_make_provenance(doc_id, page, block, line=None)`

Builds a provenance ID string: `"{doc_id}/p{page}/b{block}"` or `"{doc_id}/p{page}/b{block}/l{line}"`.

#### `_detect_section_heading(text)`

Returns the first line of `text` if it matches an ARTICLE/SECTION/EXHIBIT/SCHEDULE/ANNEX pattern. Returns `None` otherwise.

---

## `src/ingestion/ocr_fallback.py`

OCR fallback for scanned or image-heavy PDF pages using pytesseract and pdf2image.

### `ocr_page(pdf_path, page_num, dpi=300)`

Converts a single PDF page to an image and runs OCR.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `pdf_path` | `str \| Path` | required | Path to the PDF. |
| `page_num` | `int` | required | 1-indexed page number. |
| `dpi` | `int` | `300` | Resolution for page-to-image conversion. |

**Returns:** `str` — OCR text, or `""` if dependencies are missing or OCR fails.

**Behavior:**
- Checks if `pytesseract` and `pdf2image` are importable.
- If not installed, issues a warning and returns `""`.
- Converts the single page to an image via `convert_from_path`, then runs `pytesseract.image_to_string`.
- Catches all exceptions and logs errors rather than crashing.

### `ocr_flagged_pages(pdf_path, pages, dpi=300)`

Processes only pages where `needs_ocr=True`, replacing their text with OCR output.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `pdf_path` | `str \| Path` | required | Path to the PDF. |
| `pages` | `list[PageData]` | required | Pages from `extract_pdf`. |
| `dpi` | `int` | `300` | OCR resolution. |

**Returns:** `list[PageData]` — the same list, mutated in place. Flagged pages have their `text` replaced and `needs_ocr` cleared if sufficient text is recovered.

### Internal Functions

#### `_check_dependencies()`

Returns `True` if `pytesseract` and `pdf2image` can be imported.

---

## `src/parsing/section_detector.py`

Detects ARTICLE, SECTION, PART, and CLAUSE headers in credit agreement text blocks and builds a hierarchical section tree. All header patterns imported from `SECTION_HEADER_PATTERNS` in `field_patterns.py`.

### Regex Patterns

| Pattern | Source | Matches |
|---------|--------|---------|
| `_ARTICLE_ROMAN` | `field_patterns.SECTION_HEADER_PATTERNS["article_roman"]` | `ARTICLE I`, `ARTICLE IV`, `ARTICLE XII` (case-insensitive) |
| `_ARTICLE_ARABIC` | `field_patterns.SECTION_HEADER_PATTERNS["article_arabic"]` | `ARTICLE 1`, `ARTICLE 10` |
| `_SECTION_DOTTED` | `field_patterns.SECTION_HEADER_PATTERNS["section_dotted"]` | `Section 2.01`, `SECTION 10.05` |
| `_SECTION_LOOSE` | `field_patterns.SECTION_HEADER_PATTERNS["section_loose"]` | `1.01  Definitions` (number + 2+ spaces + capitalized text) |
| `_PART` | `field_patterns.SECTION_HEADER_PATTERNS["part"]` | `PART I`, `PART 1` (UK-style agreements) |
| `_CLAUSE` | `field_patterns.SECTION_HEADER_PATTERNS["clause"]` | `Clause 1`, `CLAUSE 1.1` (UK-style agreements) |

### Dataclasses

#### `SectionNode`

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Section title text (e.g. "DEFINITIONS", "THE CREDITS"). |
| `level` | `str` | `"article"` or `"section"`. |
| `number` | `str` | The section number (e.g. `"II"`, `"2.01"`). |
| `start_block_idx` | `int` | Index of the first block belonging to this section. |
| `end_block_idx` | `int` | Index of the last block. Defaults to `-1`, set during detection. |
| `children` | `list[SectionNode]` | Child sections (sections under an article). |

**Property:** `full_heading` — `"ARTICLE II — THE CREDITS"` or `"Section 2.01 — Commitments"`.

**Method:** `walk()` — returns `self` plus all descendants in pre-order traversal.

### `detect_sections(blocks)`

Scans blocks and returns a list of top-level `SectionNode` objects with children populated.

**Parameters:** `blocks: list[dict]` — each dict must have a `"text"` key.
**Returns:** `list[SectionNode]` — top-level ARTICLE nodes, each containing child SECTION nodes.

**Behavior:**
1. Scans each block's first line against ARTICLE and SECTION regex patterns.
2. If the ARTICLE title is empty (on its own line), checks the second line of the block.
3. Assigns `end_block_idx` based on the start of the next detected section.
4. Builds hierarchy: SECTION nodes become children of the preceding ARTICLE node. Orphan sections are promoted to top-level.

### `find_section_by_keyword(sections, keyword)`

Returns every `SectionNode` (at any depth) whose title contains the keyword (case-insensitive).

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `sections` | `list[SectionNode]` | Top-level nodes from `detect_sections`. |
| `keyword` | `str` | Search term (e.g. `"INTEREST"`, `"COVENANTS"`). |

**Returns:** `list[SectionNode]`

---

## `src/parsing/party_extractor.py`

Extracts parties (borrower, lender, administrative agent, guarantor, arranger) from credit agreement text using regex + spaCy NER with **precision-first validation**. Role patterns are dynamically built from `PARTY_ROLE_SYNONYMS` in `field_patterns.py`.

### Regex Patterns

Built at import time from `field_patterns.PARTY_ROLE_SYNONYMS` (5 roles, 25 total synonyms). Matches patterns like `"Borrower", Some Corp` or `the Administrative Agent, JPMorgan Chase`. Handles smart quotes (`\u201c`, `\u201d`). Requires punctuation after role token (`","`, `":"`, or `")"`) to avoid matching narrative phrases like `"Borrower has requested..."`. Roles: `borrower` (5 synonyms), `lender` (6), `administrative_agent` (5), `guarantor` (4), `arranger` (5).

### `extract_parties(blocks, doc_id="")`

Extracts party information from credit agreement blocks.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `blocks` | `list[dict]` | required | Text blocks with `text`, `block_idx`, `page` keys. |
| `doc_id` | `str` | `""` | Document identifier for provenance. |

**Returns:** `list[Party]` — deduplicated by `(name.lower(), role)`.

**Behavior:**
1. Selects **preamble** (first 5 blocks) and **signature pages** (last 20 blocks) as focus regions.
2. Runs regex patterns for each role, capturing the entity name after the role keyword.
3. Applies precision filters to candidate names:
   - reject role-only/generic terms (`Borrower`, `Definitions`, `Effective Date`, etc.)
   - reject narrative/legal prose fragments (`has requested`, `hereby`, `pursuant`, etc.)
   - require legal-entity markers (`Bank`, `Inc.`, `LLC`, `Ltd`, `Corp`, etc.)
4. Runs spaCy NER (`en_core_web_sm`) on the same blocks, extracting `ORG` entities.
5. For NER-detected entities, infers role from surrounding context (80 chars before/after) and discards role=`unknown`.
6. Cleans names: keeps first line only, strips trailing punctuation, truncates at stop phrases like "(the", "(herein", "(collectively".

### Internal Functions

#### `_get_nlp()`

Lazy-loads and caches the spaCy `en_core_web_sm` model. Returns `spacy.language.Language`.

#### `_clean_name(raw)`

Keeps first line only, trims trailing punctuation, and truncates at common stop phrases.

#### `_is_valid_party_name(name)`

Precision gate for candidate names. Rejects role/generic tokens, prose fragments, and non-entity strings. Requires at least one legal-entity marker token.

#### `_infer_role_from_context(context)`

Guesses a party role from surrounding text by checking for keywords like "borrower", "lender", "administrative agent". Returns role string or `"unknown"`.

---

## `src/parsing/facility_extractor.py`

Extracts facility details from credit agreement text, typically from ARTICLE II sections. All patterns imported from `field_patterns.py`. Section targeting uses `SECTION_KEYWORDS["facility"]` (10 keywords).

### Regex Patterns

| Pattern | Source | Matches |
|---------|--------|---------|
| `_AMOUNT_RE` | `field_patterns.AMOUNT_PATTERNS[0]` | `$500,000,000`, `$1.5 billion`, `$250 million` |
| `_FACILITY_TYPE_PATTERNS` | `field_patterns.FACILITY_TYPE_PATTERNS` | 9 types: `revolving`, `term_loan_a`, `term_loan_b`, `term_loan`, `delayed_draw`, `bridge`, `letter_of_credit`, `swingline`, `incremental` |
| `_DATE_RE` | `field_patterns.DATE_RE` | `January 1, 2024`, `1/1/2024`, `2024-01-01`, `1 January 2024` (5 formats) |
| `_MATURITY_RE` | `field_patterns.MATURITY_RE` | `maturity date: {date}`, `"Maturity Date": {date}`, `matures on {date}`, `terminates on {date}` (7 synonym patterns, smart-quote tolerant) |
| `_EFFECTIVE_RE` | `field_patterns.EFFECTIVE_RE` | `effective date: {date}`, `closing date: {date}`, `dated as of {date}` (6 synonym patterns, smart-quote tolerant) |

### `extract_facilities(blocks, sections, doc_id="")`

Extracts one or more `Facility` objects from blocks.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `blocks` | `list[dict]` | required | Text blocks. |
| `sections` | `list[SectionNode]` | required | Section tree from `detect_sections`. |
| `doc_id` | `str` | `""` | Document identifier. |

**Returns:** `list[Facility]` — one per detected tranche.

**Behavior:**
1. Searches for sections with keywords: COMMITMENT, FACILITY, LOAN, THE CREDITS.
2. If found, restricts scanning to those sections. Otherwise, falls back to all blocks.
3. Splits focus text into paragraphs. For each paragraph, detects facility type and dollar amount.
4. Deduplicates by `(facility_type, amount)` tuple.
5. Extracts maturity and effective dates from the full focus text (dates may be in a different paragraph).
6. If no structured detection succeeds, does a broad sweep across all blocks.

### Internal Functions

#### `_parse_amount(text)`

Finds the first `$X million/billion` pattern and returns it as a `float`. Applies multipliers (`million` = 1e6, `billion` = 1e9).

#### `_detect_facility_type(text)`

Returns the first matching facility type label from `_FACILITY_TYPE_PATTERNS`, or `"unknown"`.

#### `_find_date(pattern, text)`

Runs a compiled regex against text and returns the first captured group, or `""`.

#### `_collect_text(blocks, start, end)`

Concatenates block texts within an index range.

---

## `src/parsing/interest_extractor.py`

Extracts interest rate terms from credit agreement text blocks. All patterns imported from `field_patterns.py`. Section targeting uses `SECTION_KEYWORDS["interest"]` (9 keywords).

### Regex Patterns

| Category | Source | Patterns |
|----------|--------|---------|
| **Benchmarks** (12) | `field_patterns.BENCHMARK_PATTERNS` | `Term SOFR`, `SOFR`, `LIBOR`, `EURIBOR`, `Prime Rate`, `ABR`, `Base Rate`, `Federal Funds Rate`, `SONIA`, `BBSY`, `CDOR`, `TIBOR` |
| **Spread** (5) | `field_patterns.SPREAD_SYNONYMS` | `plus 2.50%`, `+ 250 basis points`, `margin of 2.50%`, `spread equal to 250 bps`, `2.50% per annum above` |
| **Floor** (7) | `field_patterns.FLOOR_SYNONYMS` | `floor of 0.50%`, `floor of 50 basis points`, `SOFR floor`, `minimum rate of 0.50%`, `in no event shall...be less than 0.50%` |
| **PIK** (6) | `field_patterns.PIK_SYNONYMS` | `PIK`, `paid in kind`, `payment-in-kind`, `PIK toggle`, `capitalized interest` |
| **Default rate** | (inline) | `default rate...plus 2.00%` |

### `extract_interest_terms(blocks, sections, doc_id="")`

Extracts interest rate terms from credit agreement blocks.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `blocks` | `list[dict]` | required | Text blocks. |
| `sections` | `list[SectionNode]` | required | Section tree. |
| `doc_id` | `str` | `""` | Document identifier. |

**Returns:** `list[InterestTerms]` — one per distinct benchmark detected.

**Behavior:**
1. Searches for sections with keywords: INTEREST, RATE, PRICING, APPLICABLE MARGIN.
2. Scans focus text for benchmark names (in priority order: Term SOFR > SOFR > LIBOR > ...).
3. Extracts spread (in bps — percentages are converted by multiplying by 100).
4. Extracts floor (in % — basis points are divided by 100).
5. Detects PIK and default rate spread.
6. Returns one `InterestTerms` object per detected benchmark, all sharing the same spread/floor/PIK values.

### Internal Functions

#### `_detect_benchmarks(text)`

Returns a list of benchmark names found in text, ordered by detection priority.

#### `_extract_spread_bps(text)`

Returns spread in basis points. Checks bps pattern first, then percentage (converting to bps).

#### `_extract_floor_pct(text)`

Returns floor as a percentage. Checks % pattern first, then bps (converting to %), then zero-floor pattern.

#### `_extract_default_spread_bps(text)`

Extracts default rate additional spread from patterns like "default rate...plus X%".

---

## `src/parsing/table_parser.py`

Classifies and parses tables extracted by pdfplumber into structured data models.

### `classify_table(table, surrounding_text="")`

Classifies a table by examining its header row and surrounding text.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `table` | `list[list[str]]` | required | pdfplumber table (list of rows). |
| `surrounding_text` | `str` | `""` | Text near the table in the document. |

**Returns:** `str` — `"pricing_grid"`, `"amortization"`, `"covenant"`, or `"unknown"`.

**Classification keywords:**
- **pricing_grid**: pricing, spread, margin, applicable rate, commitment fee, leverage
- **amortization**: amortization, repayment, installment, principal payment, scheduled payment
- **covenant**: covenant, ratio, leverage, coverage, test, threshold, compliance

### `parse_pricing_grid(table)`

Parses a pricing grid table into `PricingGridTier` objects.

**Parameters:** `table: list[list[str]]` — must have at least 2 rows (header + data).
**Returns:** `list[PricingGridTier]`

**Behavior:**
- Heuristically locates columns by header keywords: "level"/"tier", "leverage"/"ratio", "spread"/"margin"/"rate", "commitment"/"fee".
- Parses leverage ranges (e.g. "3.00 to 4.00", ">3.50", "<2.00").
- Extracts basis point values from cells (handles `bps`, `%`, and bare numbers).

### `parse_amortization_table(table)`

Parses an amortization schedule table.

**Parameters:** `table: list[list[str]]` — must have at least 2 rows.
**Returns:** `list[AmortizationEntry]`

**Behavior:**
- Locates columns by header keywords: "date"/"period"/"payment", "amount"/"$"/"principal", "percent"/"%".
- Falls back to column 0 for dates, column 1 for amounts if headers don't match.
- Strips `$` and `,` from amount cells before parsing.

### Internal Functions

#### `_to_float(s)`

Parses a number string, stripping commas. Returns `None` on failure.

#### `_extract_bps(cell)`

Extracts a basis-point value from a table cell. Checks for `bps` suffix first, then `%` (converts to bps by multiplying by 100), then bare numbers.

---

## `src/parsing/covenant_extractor.py`

Extracts financial, negative, and affirmative covenants from credit agreement text. All patterns imported from `field_patterns.py`. Section targeting uses `SECTION_KEYWORDS["covenant_financial"]`, `["covenant_negative"]`, `["covenant_affirmative"]`. Testing frequency detection from `TESTING_FREQUENCY_SYNONYMS` (quarterly, annual, monthly, semi-annual).

### Regex Patterns

**Financial covenants** (10 types from `field_patterns.FINANCIAL_COVENANT_PATTERNS`):

| Name | Metric Key | Matches |
|------|-----------|---------|
| Maximum Leverage Ratio | `leverage_ratio` | "total leverage ratio", "net debt to EBITDA", "funded debt to EBITDA" |
| Minimum Interest Coverage Ratio | `interest_coverage_ratio` | "interest coverage ratio", "EBITDA to interest expense" |
| Minimum Fixed Charge Coverage Ratio | `fixed_charge_coverage_ratio` | "fixed charge coverage ratio", "FCCR" |
| Maximum Senior Leverage Ratio | `senior_leverage_ratio` | "senior secured leverage ratio", "first lien leverage" |
| Minimum Debt Service Coverage Ratio | `debt_service_coverage_ratio` | "debt service coverage ratio", "DSCR" |
| Minimum Net Worth | `net_worth` | "tangible net worth", "stockholders equity" |
| Maximum Capital Expenditures | `capital_expenditures` | "capital expenditures", "capex" |
| Minimum EBITDA | `minimum_ebitda` | "minimum consolidated EBITDA", "trailing twelve month EBITDA" |
| Minimum Liquidity | `liquidity` | "minimum liquidity", "unrestricted cash", "available liquidity" |
| Maximum Total Debt | `total_debt` | "maximum total indebtedness", "limitation on total debt" |

**Negative covenants** (11 types from `field_patterns.NEGATIVE_COVENANT_PATTERNS`): Liens, Indebtedness, Restricted Payments, Dividends, Asset Sales, Investments, Mergers, Transactions with Affiliates, Restrictive Agreements, Sale-Leaseback, Line of Business.

**Affirmative covenants** (12 types from `field_patterns.AFFIRMATIVE_COVENANT_PATTERNS`): Financial Reporting, Insurance, Compliance with Laws, Maintenance of Properties, Books and Records, Notices, Use of Proceeds, Payment of Taxes, Corporate Existence, Inspection Rights, Environmental Compliance, Anti-Corruption.

### `extract_covenants(blocks, sections, doc_id="")`

Extracts covenants from credit agreement blocks.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `blocks` | `list[dict]` | required | Text blocks. |
| `sections` | `list[SectionNode]` | required | Section tree. |
| `doc_id` | `str` | `""` | Document identifier. |

**Returns:** `list[Covenant]`

**Behavior:**
1. **Financial covenants**: Searches sections with keywords FINANCIAL COVENANT, FINANCIAL TEST, LEVERAGE, COVERAGE. For each matching pattern, extracts a 1700-char context window around the match. Parses ratio thresholds (e.g. "4.50 to 1.00"), step-downs, and testing frequency.
2. **Negative covenants**: Searches NEGATIVE COVENANT sections. Matches category keywords and captures 600-char context.
3. **Affirmative covenants**: Searches AFFIRMATIVE COVENANT sections. Same approach as negative.
4. Falls back to full text if no matching sections found.

### Internal Functions

#### `_extract_thresholds(text)`

Extracts ratio thresholds paired with time periods. Uses `_RATIO_RE` (e.g. "4.50 to 1.00") and `_PERIOD_RE` (e.g. "fiscal quarter ending March 31, 2024", "Q1 2024"). If ratios and periods have equal count, pairs them 1:1. Otherwise, searches for the nearest period within 150 chars before each ratio.

**Returns:** `list[CovenantThreshold]`

#### `_extract_step_downs(text)`

Finds step-down provisions matching patterns like "step-down to 3.50 to 1.00 if/when/upon {trigger}".

**Returns:** `list[StepDown]`

#### `_detect_testing_frequency(text)`

Returns `"quarterly"` if "quarter"/"quarterly" found, `"annual"` if "annual"/"annually"/"fiscal year" found, else `""`.

---

## `src/parsing/amendment_extractor.py`

Detects whether a document is an amendment and extracts amendment details. Amendment detection patterns and ordinals imported from `field_patterns.py`. Date matching uses `field_patterns.DATE_RE`.

### Regex Patterns

| Pattern | Source | Matches |
|---------|--------|---------|
| `_IS_AMENDMENT_RE` | `field_patterns.AMENDMENT_DETECTION_SYNONYMS` | 10 patterns: "First Amendment", "Amended and Restated", "Amendment No. 3", "Modification Agreement", "Waiver and Amendment", "Consent and Amendment", "Omnibus Amendment", "Restatement Agreement", "Supplemental Indenture" |
| `_AMENDMENT_NUMBER_RE` | `field_patterns.AMENDMENT_ORDINALS` | Ordinals (First through Twelfth, 1st through 12th) + "Amendment", or "Amendment No. X" |
| `_AMENDMENT_DATE_RE` | "dated as of {date}", "effective as of {date}" |
| `_ORIGINAL_DATE_RE` | "credit agreement dated {date}", "loan agreement dated {date}" |
| `_SECTION_AMENDED_RE` | "Section 2.01 is hereby amended", "Section 3.05 is deleted" |
| `_ARTICLE_AMENDED_RE` | "Article III is hereby amended" |

### `extract_amendments(blocks, sections, doc_id="")`

Detects if the document is an amendment and extracts details.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `blocks` | `list[dict]` | required | Text blocks. |
| `sections` | `list[SectionNode]` | required | Section tree. |
| `doc_id` | `str` | `""` | Document identifier. |

**Returns:** `list[AmendmentInfo]` — empty list if the document is not an amendment; list with one entry if it is.

**Behavior:**
1. Checks first 10 blocks for amendment indicators.
2. If none found, returns empty list immediately.
3. Infers amendment number from ordinals ("First" -> "1") or "Amendment No. X". "Amended and Restated" maps to `"A&R"`.
4. Extracts amendment date from "dated as of" or first date found in preamble.
5. Extracts original agreement date from "credit agreement dated {date}" across full text.
6. Lists all sections/articles being amended by scanning for "is hereby amended", "is deleted", "is replaced" patterns.

### Internal Functions

#### `_infer_amendment_number(text)`

Maps ordinals (First-Tenth, 1st-10th) to numeric strings. Returns `"A&R"` for Amended and Restated. Returns `""` if no pattern matches.

#### `_find_sections_amended(text)`

Returns a deduplicated list of `"Section X.XX"` and `"Article X"` strings that are being amended.

---

## `src/parsing/schedule_extractor.py`

Extracts amortization schedules, call protection terms, and ticking fee terms from schedule and exhibit sections. Call protection and ticking fee patterns imported from `field_patterns.py`. Section targeting uses `SECTION_KEYWORDS["schedule"]` and `SECTION_KEYWORDS["fees"]`.

### Regex Patterns

| Category | Source | Patterns |
|----------|--------|---------|
| **Call protection** (13) | `field_patterns.CALL_PROTECTION_SYNONYMS` | "call protection", "prepayment premium", "make-whole", "soft call", "hard call", "non-call", "no-call", "prepayment penalty", "redemption premium", "yield maintenance", "early repayment fee", "repricing protection", "repricing premium" |
| **Call period** | (inline) | "{N} months/years after the closing date" |
| **Call premium** | (inline) | "premium of X%" |
| **Ticking fee** (5) | `field_patterns.TICKING_FEE_SYNONYMS` | "ticking fee", "delayed-draw fee", "commitment ticking fee", "undrawn fee", "availability fee" + rate in % or bps |
| **Inline amortization** | "X% of the original principal amount", "$X million" paired with dates |

### `extract_schedules(blocks, sections, tables, doc_id="")`

Extracts schedule-related information from credit agreement blocks.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `blocks` | `list[dict]` | required | Text blocks. |
| `sections` | `list[SectionNode]` | required | Section tree. |
| `tables` | `list[list[list[str]]]` | required | All tables from pdfplumber. |
| `doc_id` | `str` | `""` | Document identifier. |

**Returns:** `dict` with keys:
- `amortization_schedules`: `list[AmortizationSchedule]` — from tables and inline text.
- `call_protection`: `dict` — keys: `has_call_protection`, `type` (make_whole/soft_call/hard_call/general), `non_call_period`, `premium_pct`, `description`. Empty dict if none found.
- `ticking_fees`: `dict` — keys: `has_ticking_fee`, `rate_bps`, `starts_after_days`, `description`. Empty dict if none found.

**Behavior:**
1. **Amortization**: Searches tables with amortization-related headers. Parses matching tables via `parse_amortization_table`. Also scans schedule/exhibit sections for inline date+amount pairs.
2. **Call protection**: Searches PREPAYMENT/CALL/REDEMPTION sections. Detects type, non-call period, premium percentage.
3. **Ticking fees**: Searches FEE/TICKING sections. Extracts rate and start delay.

### Internal Functions

#### `_extract_call_protection(text)`

Returns a dict with call protection details, or `{}` if no call protection language found.

#### `_extract_ticking_fees(text)`

Returns a dict with ticking fee details, or `{}` if no ticking fee language found.

#### `_extract_inline_amortization(text)`

Extracts amortization entries from prose by finding date + amount/percentage pairs within 200 chars of each other.

#### `_parse_amount(text)`

Finds first `$X` pattern with optional million/billion multiplier.

---

## `src/knowledge_graph/builder.py`

Builds per-document NetworkX DiGraphs from parsed `CreditAgreementDocument` models.

### `build_graph(doc)`

Builds a knowledge graph from a parsed credit agreement document.

**Parameters:** `doc: CreditAgreementDocument`
**Returns:** `nx.DiGraph`

**Graph construction:**
1. Creates a `Document` node with `doc_id`, `title`, `agreement_date`, `file_name`.
2. For each party: creates `Party` node, adds `HAS_PARTY` edge from document.
3. For each facility: creates `Facility` node, adds `HAS_FACILITY` edge from document. If the facility has `interest_terms`, creates an `InterestTerms` node with `HAS_INTEREST_TERMS` edge. Links parties to facilities based on role: `BORROWS_UNDER` (borrower), `LENDS_UNDER` (lender), `AGENT_FOR` (administrative_agent).
4. For each covenant: creates `Covenant` node, adds `HAS_COVENANT` edge. For each threshold: creates `Threshold` node with `HAS_THRESHOLD` edge.
5. For each amendment: creates `Amendment` node, adds `HAS_AMENDMENT` edge.

All nodes carry a `provenance` attribute from `source_ref.provenance_id`.

### `export_graph_json(G, output_path)`

Exports graph as node-link JSON using `nx.node_link_data`.

**Parameters:** `G: nx.DiGraph`, `output_path: Path`

### `export_graph_gexf(G, output_path)`

Exports graph as GEXF format (compatible with Gephi and Neo4j import). Converts all node attributes to strings for GEXF compatibility.

**Parameters:** `G: nx.DiGraph`, `output_path: Path`

---

## `src/knowledge_graph/queries.py`

Utility queries over credit agreement knowledge graphs.

### `get_nodes_by_type(G, node_type)`

Returns all nodes matching a given `node_type` attribute.

**Parameters:** `G: nx.DiGraph`, `node_type: str`
**Returns:** `list[tuple[str, dict]]` — list of `(node_id, attributes)`.

### `get_facilities(G)`

Returns attribute dicts for all `Facility` nodes.

**Returns:** `list[dict]`

### `get_covenants(G)`

Returns attribute dicts for all `Covenant` nodes.

**Returns:** `list[dict]`

### `get_parties_for_facility(G, facility_node_id)`

Returns all `Party` nodes connected to a facility, with their relationship type.

**Parameters:** `G: nx.DiGraph`, `facility_node_id: str`
**Returns:** `list[dict]` — each dict includes party attributes plus `"relationship"` key (e.g. `"BORROWS_UNDER"`).

### `get_thresholds_for_covenant(G, covenant_node_id)`

Returns all `Threshold` nodes connected to a covenant via `HAS_THRESHOLD` edges.

**Parameters:** `G: nx.DiGraph`, `covenant_node_id: str`
**Returns:** `list[dict]`

### `graph_summary(G)`

Returns aggregate statistics for the graph.

**Parameters:** `G: nx.DiGraph`
**Returns:** `dict` with keys:
- `total_nodes`: `int`
- `total_edges`: `int`
- `node_types`: `dict[str, int]` — count per node type
- `edge_types`: `dict[str, int]` — count per edge type

---

## `src/llm/interface.py`

Abstract LLM provider interface — scaffold for v2.

### `LLMProvider` (ABC)

Base class for LLM providers.

#### `extract_structured(text, prompt)` (abstract)

Send text + prompt to an LLM and return structured extraction.

**Parameters:** `text: str`, `prompt: str`
**Returns:** `dict`

#### `classify(text, categories)` (abstract)

Classify text into one of the given categories.

**Parameters:** `text: str`, `categories: list[str]`
**Returns:** `str`

### `MockLLMProvider`

No-op provider for v1.

- `extract_structured()` returns `{}`
- `classify()` returns `categories[0]` (or `""` if empty)

---

## `src/llm/config.py`

LLM configuration — scaffold for v2.

### Constants

#### `LLM_PROVIDERS`

```python
{
    "openai":    {"api_key_env": "OPENAI_API_KEY",    "default_model": "gpt-4"},
    "anthropic": {"api_key_env": "ANTHROPIC_API_KEY",  "default_model": "claude-sonnet-4-20250514"},
}
```

### `get_api_key(provider)`

Returns the API key for the given provider from the environment.

**Parameters:** `provider: str` — `"openai"` or `"anthropic"`
**Returns:** `str` — the key, or `""` if not set.

### `is_llm_available(provider="openai")`

Returns `True` if an API key is configured for the given provider.

---

## `app/streamlit_app.py`

Streamlit web UI for uploading and processing credit agreement PDFs.

### Page Configuration

- Title: "Credit Agreement Parser"
- Layout: wide
- Sidebar: upload widget, existing PDF dropdown, process buttons

### `display_results(doc_dict, graph_stats)`

Renders parsed results in a tabbed layout.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `doc_dict` | `dict` | JSON-serialized `CreditAgreementDocument`. |
| `graph_stats` | `dict` | Output of `graph_summary()`. |

**Tabs:**
1. **Overview** — doc ID, total pages, parties count, agreement date, facilities count, covenants count. Lists all parties with roles.
2. **Facilities** — expandable cards per facility showing type, amount, currency, dates, interest terms, pricing grid.
3. **Covenants** — expandable cards per covenant showing type, metric, description, thresholds.
4. **Amendments** — expandable cards showing amendment number, date, original date, summary, sections amended.
5. **Raw JSON** — full JSON output via `st.json()`.
6. **Knowledge Graph** — node/edge counts, node type breakdown, edge type breakdown.

### `run_pipeline(pdf_path)`

Runs the parsing pipeline with real-time progress tracking.

**Parameters:** `pdf_path: Path`

**Behavior:**
- Creates a Streamlit progress bar and status text placeholder.
- Passes an `on_progress` callback to `process_document` that updates the progress bar (0% to 100% across 13 steps) and status text (e.g. "Step 5/13: Extracting parties...").
- On success: clears progress bar, shows summary metrics, calls `display_results`.
- On error: clears progress bar, shows error message and stack trace.

### Main Flow

1. If "Process Document" clicked with an uploaded file: saves to temp file, runs pipeline.
2. If "Process Selected" clicked with a dropdown selection: runs pipeline on the selected file from `raw_documents/pdf/`.
3. Otherwise: shows info message prompting the user to upload or select a PDF.
