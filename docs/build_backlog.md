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
- **Deferred:** intentionally parked; not a current build dependency.

## Registry

| ID | Status | Component | Frozen outcome | Dependencies | Implementation plan |
| --- | --- | --- | --- | --- | --- |
| A5 | Implemented | Docling PDF conversion pipeline | Run local English OCR, enable Docling's built-in heading-hierarchy inference and parsed-page generation, and record the configuration in the conversion profile and manifest. Do not add a custom document-layout parser. | A4 document format router | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Task 1 |
| A10 | Implemented | Build versioned hierarchy sidecar mapping | Transform unchanged canonical Docling JSON into a schema-versioned mapping keyed by canonical item IDs, with generic heading paths, page provenance, and the four frozen warning codes. Preserve source content and reading order; treat broken references and cycles as errors. | A5 and A9 canonical output | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Task 2 |
| A11 | Implemented | Persist sidecar and finalize Stage A artifact | Call A10 after canonical serialization, write `document.hierarchy.json`, finalize the manifest only after all artifacts exist, return an enriched `ConversionArtifact`, and require the sidecar for cache completeness. | A10 | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Tasks 3-4 |
| B1 | Implemented | Build page-first provenance-preserving chunks | Consume the completed Stage A canonical JSON and hierarchy sidecar through a pure chunk builder plus persistence wrapper. Write `tmp/stage_b/<source-sha256>/document.chunks.json`; use page boundaries for paged documents and a 12,000-character reading-order fallback for page-less documents; keep canonical leaves, tables, and explicit Docling lists atomic; preserve item IDs, source wording, hierarchy context, and deterministic neighbor links without overlap or invented provenance. | A11 completed Stage A artifact | [B1 page-first chunking plan](superpowers/plans/2026-09-30-b1-page-first-chunking.md) |

| B2 | Implemented | Propose topic labels with preset phrase rules | Classify every B1 chunk using the agreed eight topics and two subtopics; retain exact wording, rule IDs and cited source items without scoring match strength. B3 will refine the guesses into final labels. | B1 | [B2 topic signals plan](superpowers/plans/2026-10-01-b2-topic-signals.md) |
| B3 | Implemented | Batched LLM topic reflection | All chunks, Luna/high, validated labels/citations, resumable batches, local telemetry/debug; v2 prompt with shared definitions and definition-sensitive caching. | B1, B2, Stage C | [B3/B4 plan](superpowers/plans/2026-10-01-b3-topic-reflection.md) |
| B4 | Implemented | Topic map | Deterministic topic-to-chunk/item index; no summaries or LLM calls. | B3 | [B3/B4 plan](superpowers/plans/2026-10-01-b3-topic-reflection.md) |
| C1–C5 | Implemented | Shared OpenCode transport | Routing, Responses/Chat adapters, overrides, local telemetry. | Credentials | [B3/B4 plan](superpowers/plans/2026-10-01-b3-topic-reflection.md) |
| B5/B6 | Pending | Retrieval and evidence bundles | Retrieve original topic-specific evidence for requested extraction sleeves. | B4 | — |
| Observability: Phoenix | Deferred | Trace UI | Revisit later; no B3/B4 dependency. | Local telemetry | — |
| Human review HTML | Implemented | Saved-run stage/evidence reviewer | Review A/B1–B4/C inputs, artifacts and traces, with original text/pages next to classifications and clickable source citations; no fabricated data or paid calls. Live execution dashboard remains deferred. | Debug snapshots | [Saved-run review plan](superpowers/plans/2026-10-01-saved-run-html-review.md) |
| Telemetry restart correlation | Pending | Distinguish executions within one run ID | Correlate failed classifications with their exact call/span rather than only source/batch/attempt, so restarting a run does not mark a later successful response failed. | Local events | — |

## Verification evidence

### B3 topic-definition refinement — 2026-10-01

- 156 full-suite tests passed. New checks prove every approved topic definition
  reaches B3 and edits to definitions invalidate its validated checkpoints.
- `b3-reflection-v2` uses shared `credit-topic-definitions-v1` meanings with
  explicit boundaries. B2 rules, topic IDs, and B4 indexing remain unchanged.
- The saved Amerigo run used v1: B2 proposed 98 chunk-topic assignments; B3
  retained 51, removed 47, and added 9, leaving 60. B4 preserved all B3 labels
  and citation sets across all 29 chunks. Agreement is not accuracy.
- No paid v2 rerun yet. The HTML still shows the original saved run; manually
  reviewed additions/removals and a fresh v2 comparison remain next steps.

### Saved-run human review — 2026-10-01

- 154 full-suite tests passed, including 12 review tests for saved-file loading,
  path restrictions, missing-data behavior, source wording/pages, heading
  resolution, canonical table cells, unclassified chunks, safe script embedding with punctuation
  round-tripping, and distinct argument versus artifact snapshots.
- Real Amerigo export contains 29 chunks, 9 final interest chunks and 2
  unclassified chunks. Browser checks covered A artifact selection, B1/B2/B4
  views, source-citation focus, chunk navigation, C transport snapshots,
  pending-stage display, narrow-panel switching and desktop side-by-side layout.
- Snapshot content came entirely from the existing run. No new conversion,
  model calls or source edits; exported HTML contained no API key.
- This is read-only saved-run review, not live progress tracking or persisted
  reviewer judgments. A1–A11 were not independently instrumented in that run.

### B3/B4 and Stage C — 2026-10-01

- 142 full-suite tests passed. New checks cover routing, secret masking,
  debug snapshots, malformed provider envelopes, strict taxonomy/citations,
  exact chunk coverage, parent topics, batching, invalid-output/transient retries,
  auth failure without retry, checkpoint resume after partial failure,
  settings/input invalidation, model-substitution rejection, deterministic B4
  order including inherited headings, and local analytics.
- One live synthetic B3/B4 run returned `gpt-5.6-luna` and `effort=high`:
  423 input tokens, 110 output tokens (including 53 reasoning tokens), one
  request, 3.16 seconds. Interest and maturity labels cited the correct source
  items. These are wiring checks, not a corpus classification benchmark.
- The gateway returned no actual billed cost. Its recorded attempt remains
  unknown; the subsequently verified 2026-10-01 Luna rate snapshot estimates
  this usage at USD 0.0002166, not a billing assertion. Unknown models/tiers
  remain unknown unless explicit rates are supplied.
- Responses is live-verified; Chat Completions has fake-HTTP coverage only.
- Debug capture is available across existing and new public pipeline APIs.
  Local events and snapshots are under ignored `tmp/runs/`; keys never logged.
- Phoenix deferred. B5/B6 and Stage D are not implemented. Source corpus and
  existing staging imports were not modified; no paid corpus sweep performed.

## B2 build entry — 2026-10-01

- **Status:** Implemented.
- **Outcome:** Versioned eight-topic heuristic classification with PIK toggle
  and call-protection subtopics, unscored heuristic signals, source IDs,
  exact matched wording, and provisional labels for every B1 chunk.
- **Dependency:** B1; B3's LLM reflection is now implemented.
- **Plan:** [B2 topic signals](superpowers/plans/2026-10-01-b2-topic-signals.md).
- **Verification:** 29 focused tests and 98 full-suite tests passed. Real B1
  artifacts produced 180 PDF classifications (3 unmatched) and 11 HTM
  classifications (0 unmatched); every signal's item IDs resolved.
- **Observed limitation:** Common role and rate words label many chunks. These
  are unscored initial guesses, subject to B3's LLM reflection.


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
