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
| A5.1 | Implemented | Enable Docling heading hierarchy during PDF extraction | Configure Docling's built-in heading-hierarchy inference and parsed-page generation so the canonical Docling export retains all structure Docling can recover. Record the configuration in the conversion profile and manifest. Do not add a custom document-layout parser. | Existing A5 PDF conversion | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Task 1 |
| A10 | Pending | Build versioned hierarchy sidecar | Read the unchanged canonical Docling JSON and write `document.hierarchy.json`, keyed by canonical item IDs, with generic heading paths, page provenance, and the four frozen warning codes. Preserve source text and reading order; treat broken references and cycles as errors. | A5.1 and A9 | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md) |

## Verification evidence

### A5.1 — 2026-09-30

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

## A10 acceptance summary

- `document.docling.json` is byte-for-byte unchanged by A10.
- `document.hierarchy.json` has an explicit schema version and source SHA-256.
- Text and table entries refer back to canonical Docling item IDs.
- Heading paths use generic numeric depth; they do not require the agreement to
  use words such as *Article*, *Section*, or *Clause*.
- Warning codes are limited initially to `no_headings`, `flat_levels`,
  `skipped_levels`, and `non_monotonic_pages`.
- Missing or cyclic references fail validation instead of producing a plausible
  but untrustworthy hierarchy.
- Cache completeness requires the sidecar and the matching conversion profile.
- Stage A returns a `ConversionArtifact` that includes the sidecar path only
  after the manifest has been finalized successfully.
