# Docling Conversion Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a Python function that converts a local PDF, HTML, or HTM credit agreement into durable Docling JSON, derived Markdown, and a conversion manifest without modifying the source corpus.

**Architecture:** `convert_document()` validates and fingerprints a source file, normalizes gzip-wrapped HTML into a temporary workspace, and delegates parsing to a replaceable converter adapter. Docling JSON is the canonical intermediate; Markdown is a human- and LLM-friendly derivative. Artifacts are cached in a SHA-256-addressed directory, while the existing party-extraction scaffold remains unchanged until a later increment explicitly connects conversion to LLM extraction.

**Tech Stack:** Python 3.11, uv, Docling 2 with RapidOCR, Pydantic 2, pytest

## Global Constraints

- Use Python 3.11 and the existing `.venv`, `.python-version`, `pyproject.toml`, and `uv.lock`.
- Use `uv` for dependency changes and all Python/test execution.
- Run Docling and OCR locally; do not call a paid conversion or OCR API.
- Configure OCR for English because the current corpus scope is English-only.
- Treat `raw_documents/pdf/` and `raw_documents/htm/` as immutable.
- Write generated artifacts only beneath the caller-supplied output root, defaulting to `tmp/converted/`.
- Use the full source SHA-256 as the cache directory name and never require callers to provide it.
- Store Docling JSON as the canonical conversion result and Markdown as a derived view.
- Preserve Docling item identifiers and provenance in canonical JSON; do not ask an LLM to invent page numbers or bounding boxes.
- Do not connect conversion to OpenCode or party extraction in this increment.
- Use test doubles only at the Docling dependency boundary; test hashing, gzip handling, persistence, caching, and validation with real filesystem behavior.

---

## File map

| Path | Responsibility |
| --- | --- |
| `pyproject.toml` | Declare Docling and local RapidOCR runtime dependencies |
| `uv.lock` | Lock exact dependency versions and hashes |
| `.gitignore` | Exclude generated conversion artifacts under `tmp/converted/` |
| `src/credit_agreement_extractor/conversion.py` | Validate inputs, hash sources, normalize gzip HTML, run Docling, and persist/cache artifacts |
| `src/credit_agreement_extractor/__init__.py` | Export `convert_document` and `ConversionArtifact` |
| `tests/test_conversion.py` | Exercise the conversion contract without network or model downloads |
| `docs/conversion_pipeline.md` | Explain artifacts and show the Mermaid pipeline diagram |

---

### Task 1: Define the conversion contract and persistence behavior

**Files:**
- Create: `tests/test_conversion.py`
- Create: `src/credit_agreement_extractor/conversion.py`
- Modify: `src/credit_agreement_extractor/__init__.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `source_path: str | Path`, optional `output_root: str | Path`, and an internal injectable converter implementing `convert(path) -> result` where `result.document` provides `export_to_markdown()` and `export_to_dict()`.
- Produces: `convert_document(source_path, output_root="tmp/converted") -> ConversionArtifact` and an immutable `ConversionArtifact` containing source identity and all artifact paths.

- [x] **Step 1: Write failing tests for persisted PDF artifacts and cache reuse**

Create `tests/test_conversion.py` with small fake Docling objects. Assert that converting a non-empty `.pdf` writes `document.md`, `document.docling.json`, and `manifest.json` beneath `<output_root>/<sha256>/`; assert canonical JSON retains a `prov` entry with `page_no`, `bbox`, and `charspan`; invoke conversion again with a converter that raises if called and assert the cached artifact is reused.

- [x] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/test_conversion.py -v
```

Expected: test collection fails because `credit_agreement_extractor.conversion` does not exist.

- [x] **Step 3: Implement minimal validation, hashing, persistence, and caching**

Create `conversion.py` with:

```python
@dataclass(frozen=True, slots=True)
class ConversionArtifact:
    source_path: Path
    source_sha256: str
    source_format: str
    output_directory: Path
    markdown_path: Path
    docling_json_path: Path
    manifest_path: Path
    cached: bool


def convert_document(
    source_path: str | Path,
    output_root: str | Path = Path("tmp/converted"),
    *,
    converter: DocumentConverterLike | None = None,
) -> ConversionArtifact:
    ...
```

Validate `.pdf`, `.html`, and `.htm`, reject missing/directories/empty files, stream the source through `hashlib.sha256`, use the digest as the artifact directory, and serialize UTF-8 Markdown plus indented UTF-8 JSON. The manifest must include schema version, source path/name/hash/format, artifact filenames, Docling package version when available, OCR configuration (`enabled: true`, `engine: rapidocr`, `languages: ["iso:en"]`), gzip-normalization state, and conversion status. Return cached artifacts only when all three files exist and the manifest hash matches.

- [x] **Step 4: Export the public conversion API and ignore generated files**

Export `convert_document` and `ConversionArtifact` from `src/credit_agreement_extractor/__init__.py`. Add `tmp/converted/` to `.gitignore`; do not ignore all of `tmp/` because other project-owned review material may live there.

- [x] **Step 5: Run the focused and full tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_conversion.py -v
uv run pytest -q
```

Expected: the conversion tests pass and all pre-existing tests remain green.

---

### Task 2: Normalize gzip HTML and configure local Docling OCR

**Files:**
- Modify: `tests/test_conversion.py`
- Modify: `src/credit_agreement_extractor/conversion.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Consumes: the Task 1 `convert_document()` contract.
- Produces: transparent gzip-wrapped HTML support and the default locally configured Docling converter.

- [x] **Step 1: Write a failing gzip-HTML behavior test**

Write a `.htm` fixture whose bytes are `gzip.compress(b"<html><body><p>Credit Agreement</p></body></html>")`. Use a recording converter to assert that it receives a temporary `.html` file containing decompressed HTML, then assert that the temporary file no longer exists after conversion and that `manifest.json` records `gzip_normalized: true`.

- [x] **Step 2: Run the gzip test and verify RED**

Run:

```bash
uv run pytest tests/test_conversion.py -k gzip -v
```

Expected: FAIL because gzip input is passed to the converter without normalization.

- [x] **Step 3: Implement temporary gzip normalization**

Detect the gzip magic bytes `1f 8b` only for `.htm` and `.html` sources. Decompress into a `TemporaryDirectory` under the output root, pass that `.html` path to Docling, and guarantee cleanup on both success and failure. Never rewrite or rename the source file.

- [x] **Step 4: Run the gzip test and verify GREEN**

Run:

```bash
uv run pytest tests/test_conversion.py -k gzip -v
```

Expected: PASS.

- [x] **Step 5: Add the local Docling dependency**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv add 'docling[rapidocr]>=2,<3'
```

Expected: `pyproject.toml` and `uv.lock` include Docling and RapidOCR-compatible dependencies; the existing Python 3.11 constraint is unchanged.

- [x] **Step 6: Implement the lazy default Docling adapter**

Create the real converter only when callers do not inject one. Configure `PdfPipelineOptions.do_ocr = True`, set `RapidOcrOptions(lang=["iso:en"])`, and register the resulting options for `InputFormat.PDF` through `PdfFormatOption`. Keep default Docling handling for HTML. Import Docling lazily so importing the package and running fake-based tests does not load document models.

- [x] **Step 7: Run all tests and verify GREEN**

Run:

```bash
uv run pytest -q
```

Expected: all tests pass without network calls or model inference.

---

### Task 3: Document and smoke-test the real conversion path

**Files:**
- Create: `docs/conversion_pipeline.md`
- Generated and ignored: `tmp/converted/<source-sha256>/document.md`
- Generated and ignored: `tmp/converted/<source-sha256>/document.docling.json`
- Generated and ignored: `tmp/converted/<source-sha256>/manifest.json`

**Interfaces:**
- Consumes: `convert_document()` from Tasks 1-2.
- Produces: developer documentation and evidence that real local Docling conversion works on representative corpus inputs.

- [x] **Step 1: Write the pipeline documentation**

Document the public call, artifact meanings, SHA-256 cache behavior, local-only OCR configuration, and the rule that extraction code cites Docling item identifiers before copying verified provenance. Include a Mermaid flow from source detection through PDF/HTML conversion, canonical JSON, Markdown derivation, future LLM extraction, and validated evidence output.

- [x] **Step 2: Convert one representative HTML/HTM agreement locally**

Run `convert_document()` through `uv run python` against a source under `raw_documents/htm/`. Expected: all three artifacts are created under `tmp/converted/<sha256>/`, the source checksum is unchanged before and after, Markdown is non-empty, and canonical JSON includes document content.

- [x] **Step 3: Convert one representative PDF agreement locally**

Run `convert_document()` through `uv run python` against a reasonably small source under `raw_documents/pdf/`. Expected: all three artifacts are created, Markdown is non-empty, canonical JSON contains provenance with a page number and bounding box for at least one text item, and the source checksum is unchanged before and after.

- [x] **Step 4: Verify cache reuse**

Convert the same PDF a second time. Expected: `ConversionArtifact.cached` is `True` and the manifest/artifact modification times do not change.

- [x] **Step 5: Run final verification**

Run:

```bash
uv run pytest -q
git diff --check
```

Expected: all tests pass and `git diff --check` reports no whitespace errors.
