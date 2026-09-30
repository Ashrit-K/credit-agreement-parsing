# Credit Agreement Parser Build Backlog

This registry tracks agreed components that have not yet been implemented. The
component IDs match the authoritative diagram in
[`conversion_pipeline.md`](conversion_pipeline.md).

## Status vocabulary

- **Pending:** design is sufficiently settled to plan or build, but the code is
  not implemented.
- **In progress:** implementation has started but has not met its acceptance
  criteria.
- **Implemented:** acceptance criteria and focused regression checks pass, and
  the pipeline diagram has been updated to a solid box and solid connections.
- **Blocked:** implementation cannot proceed without a named dependency or
  decision.

## Registry

| ID | Status | Component | Frozen outcome | Dependencies | Implementation plan |
| --- | --- | --- | --- | --- | --- |
| A5 | Implemented | Docling PDF conversion pipeline | Run local English OCR, enable Docling's built-in heading-hierarchy inference and parsed-page generation, and record the configuration in the conversion profile and manifest. Do not add a custom document-layout parser. | A4 document format router | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Task 1 |
| A10 | Implemented | Build versioned hierarchy sidecar mapping | Transform unchanged canonical Docling JSON into a schema-versioned mapping keyed by canonical item IDs, with generic heading paths, page provenance, and the four frozen warning codes. Preserve source content and reading order; treat broken references and cycles as errors. | A5 and A9 canonical output | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Task 2 |
| A11 | Implemented | Persist sidecar and finalize Stage A artifact | Call A10 after canonical serialization, write `document.hierarchy.json`, finalize the manifest only after all artifacts exist, return an enriched `ConversionArtifact`, and require the sidecar for cache completeness. | A10 | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Tasks 3-4 |
| B1 | Implemented | Build page-first provenance-preserving chunks | Consume the completed Stage A canonical JSON and hierarchy sidecar through a pure chunk builder plus persistence wrapper. Write `tmp/stage_b/<source-sha256>/document.chunks.json`; use page boundaries for paged documents and a 12,000-character reading-order fallback for page-less documents; keep canonical leaves, tables, and explicit Docling lists atomic; preserve item IDs, source wording, hierarchy context, and deterministic neighbor links without overlap or invented provenance. | A11 completed Stage A artifact | [B1 page-first chunking plan](superpowers/plans/2026-09-30-b1-page-first-chunking.md) |

## Verification evidence

### A5 PDF hierarchy configuration — 2026-09-30

- `uv run --frozen pytest -q`: 24 tests passed.
- The real `convert_document()` path converted
  `raw_documents/pdf/032_d35588dex101.pdf` with conversion profile
  `docling-json-v2-rapidocr-en-heading-hierarchy`.
- Its manifest recorded hierarchy inference and parsed-page generation as
  enabled for PDF; HTML tests recorded both as disabled.
- The canonical export contained four `section_header` items across levels 1
  and 2, confirming the built-in Docling stage ran.
- The source SHA-256 remained
  `4a04d3830220aee2f07a2074d42a334141e6fe6d7bbc05d15221c2b1e9ecce13`.

### A10 pure transformation — 2026-09-30

- `uv run --frozen pytest tests/test_hierarchy.py -v`: 17 tests passed.
- `build_hierarchy_sidecar()` traverses canonical body/group references without
  loading Docling or touching disk. It preserves reading order, item IDs,
  container ancestry, generic heading paths, and canonical page provenance.
- Exact tests cover `no_headings`, `flat_levels`, `skipped_levels`, and
  `non_monotonic_pages`. Unresolved references, group cycles, malformed heading
  levels, and conflicting `self_ref` values fail validation.
- A read-only check successfully processed all four existing canonical
  artifacts, ranging from 38 to 2,863 reading-order items.
- A10 is **Implemented** and is now invoked by A11 after canonical
  serialization.

### A11 Stage A integration — 2026-09-30

- `UV_CACHE_DIR=.uv-cache uv run --frozen pytest -q`: 46 tests passed.
- `tests/test_conversion.py` verifies deterministic sidecar persistence,
  manifest-last completion, enriched artifact paths, and cache invalidation for
  missing, malformed, mismatched-source, or unsupported-schema sidecars.
- Four materially different PDFs completed with all four artifacts and valid
  source-linked sidecars:
  - `032_d35588dex101.pdf`: 80 reading-order items, 0 tables, 1
    `skipped_levels` warning;
  - `011_credit_agreement.pdf`: 264 reading-order items, 7 tables, 5
    `skipped_levels` warnings;
  - `002_Facility_Agreement.pdf`: 2,863 reading-order items, 9 tables, 14
    `skipped_levels` warnings; and
  - `051_ACCO_Brands_Third_Amended_Credit_Agreement.pdf`: 1,908
    reading-order items, 23 tables, 20 `skipped_levels` warnings.
- The facility agreement was regenerated from an empty cache under conversion
  profile `docling-json-v3-rapidocr-en-hierarchy-sidecar-v1`; a repeated call
  returned `cached=True` without changing any artifact modification time.
- The long composite filing produced a Docling table-matching warning for 3 of
  203 PDF cells. Conversion and hierarchy validation still completed, and the
  warning remains a recorded parser limitation rather than a document-specific
  repair rule.

### B1 page-first chunking — 2026-09-30

- `UV_CACHE_DIR=.uv-cache uv run --frozen pytest tests/test_chunking.py -q`:
  23 focused tests passed.
- `UV_CACHE_DIR=.uv-cache uv run --frozen pytest -q`: 69 tests passed.
- Tests cover source rendering, table grids, page boundaries, same-page splits,
  atomic multi-page lists and tables, page-less attachment, heading-aware HTML
  fallback, exact-once reading order, deterministic neighbor links, malformed
  provenance rejection, atomic persistence, and cache invalidation.
- `002_Facility_Agreement.pdf` produced 180 page-first chunks covering all
  2,863 source items exactly once, including 158 chunks with explicit list
  groups and 9 table items. Five chunks spanned pages because atomic source
  structures crossed page boundaries; no chunk exceeded 12,000 characters.
- `012_tmb-20250627xex10d1.htm` produced 11 page-less chunks covering all
  1,523 source items exactly once. Its largest chunk contained 11,998
  characters and no page number or coordinate was invented.
- Repeated public API calls returned `cached=True` for both documents without
  changing artifact modification times.

## A10 transformation acceptance summary

- `document.docling.json` is byte-for-byte unchanged by A10.
- The returned hierarchy mapping has an explicit schema version and source
  SHA-256.
- Text and table entries refer back to canonical Docling item IDs.
- Heading paths use generic numeric depth; they do not require the agreement to
  use words such as *Article*, *Section*, or *Clause*.
- Warning codes are limited initially to `no_headings`, `flat_levels`,
  `skipped_levels`, and `non_monotonic_pages`.
- Missing or cyclic references fail validation instead of producing a plausible
  but untrustworthy hierarchy.

## A11 integration acceptance summary

- `document.hierarchy.json` persists the A10 mapping deterministically.
- Cache completeness requires the sidecar and the matching conversion profile.
- Stage A returns a `ConversionArtifact` that includes the sidecar path only
  after the manifest has been finalized successfully.
