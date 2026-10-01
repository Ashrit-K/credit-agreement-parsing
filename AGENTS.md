# Credit Agreement Parser — Project Instructions

## Mission

Build a system that accepts a credit agreement PDF and returns structured JSON. Target information includes:

- Borrower and lender details
- Interest terms and interest-payment terms
- Principal, repayment, and amortization terms
- Call protection
- Covenants and other material agreement terms

LLMs are intended to participate in topic classification and legal-term extraction. The current architecture is a staged pipeline; autonomous-agent or hybrid orchestration remains an open later decision and must not be assumed.

## Current Architecture Snapshot

The authoritative numbered architecture and implementation status live in `docs/conversion_pipeline.md`. Preserve its conventions:

- Solid boxes and arrows are implemented and tested.
- Dashed boxes and arrows are pending.
- Purple boxes are LLM or other cognitive steps.
- Component IDs such as `A10` and `B3` are stable review references. Do not silently renumber them.

Implemented Stage A behavior currently includes:

- Python 3.11 and uv-based development.
- `convert_document(path)` support for PDF, HTML, and HTM input.
- Local Docling conversion, with English RapidOCR available for PDFs.
- A5's Docling PDF pipeline includes heading-hierarchy inference and parsed-page
  generation, recorded in the manifest and conversion profile.
- Gzip magic-byte detection and temporary decompression for compressed SEC `.htm` files.
- Canonical `document.docling.json`, derived `document.md`, versioned
  `document.hierarchy.json`, and final `manifest.json` artifacts under
  `tmp/converted/<source-sha256>/`.
- A development-only cache shortcut keyed by source SHA-256 and conversion
  profile that requires and validates all four artifacts.
- A10's pure, independently tested canonical-JSON hierarchy transformation in
  `hierarchy.py`.
- A11's integration of A10 after canonical serialization, deterministic
  sidecar persistence, manifest-last completion boundary, and enriched
  `ConversionArtifact` return contract.

Implemented Stage B behavior currently includes:

- B1's pure `build_chunk_document()` transformation and public
  `build_chunks(conversion_artifact)` persistence wrapper in `chunking.py`.
- Separate schema-versioned output under
  `tmp/stage_b/<source-sha256>/document.chunks.json` so Stage A's four-artifact
  contract remains unchanged.
- Page-first PDF chunks, a 12,000-character heading-aware fallback for
  page-less HTML, and no overlapping source items.
- Atomic canonical leaves, tables, and explicit Docling lists, with original
  and normalized source wording, page provenance, A10 heading paths, container
  ancestry, deterministic chunk IDs, and neighbor links.
- A development cache keyed by source identity, chunking profile, and the
  SHA-256 hashes of both Stage A JSON inputs.

For A10:

- Preserve Docling container ancestry, reading order, generic numeric heading paths, and canonical page provenance.
- Keep `document.docling.json` canonical and unchanged; do not build a replacement document or custom PDF-layout parser.
- Treat hierarchy as optional context that can never discard, reorder, or summarize source content.
- Limit initial hierarchy warnings to `no_headings`, `flat_levels`, `skipped_levels`, and `non_monotonic_pages`.
- Treat broken references, malformed heading levels, and cycles as errors rather than warnings.

B1 and B2 are implemented. `classify_chunks()` writes provisional topic guesses
and cited rule evidence in `document.topic-signals.json`. The eight-topic
vocabulary and PIK/call-protection subtopics are versioned in
`topic_taxonomy.py`. Every matching rule proposes a label without scores or
strength categories. B3 independently assesses source evidence and refines
the guesses into final classifications; all chunks remain eligible, including
unmatched ones. B3's `reflect_topics()` is implemented: Luna/high by default,
up to five chunks/24,000 evidence characters per batch, approved final labels
with verified item citations, bounded retries and hash/settings-keyed validated
checkpoints. B3's `b3-reflection-v2` prompt consumes shared, versioned topic
definitions from `topic_taxonomy.py`; definition hashes invalidate checkpoint
reuse independently of unchanged topic IDs and B2 phrase rules.
No possible-label bucket or Jev/verifier layer. B4's
`build_topic_map()` validates classifications and persists a deterministic
topic-to-chunk/item index, not summaries. B5 and B6 remain pending and will retrieve and package
original topic-specific evidence for extraction sleeves.

Stage C is a cross-cutting LLM interface, not a sequential document-processing stage. It routes OpenCode requests through explicit, tested model-to-API mappings. The agreed default is `gpt-5.6-luna` with medium reasoning, with call-time overrides for model, reasoning effort, and API style. Support Responses and Chat Completions adapters; Claude/Messages support is not currently required. Every purple LLM box uses this shared transport contract with its own system prompt, evidence, and response schema; do not route document artifacts through C in the pipeline diagram.

Stage C's `OpenCodeClient` is implemented. Responses/Luna/high was checked live;
Chat Completions is fake-HTTP tested, not live-verified. Use the explicit
application User-Agent; the default Python client was blocked by Cloudflare.
Do not silently substitute models. All public file/pipeline APIs support
`debug`, `run_id`, and `trace_root`: local basic JSONL telemetry always persists;
debug adds intermediate artifacts, prompts/responses, and sanitized validation
diagnostics. Never capture keys, authorization headers, or hidden reasoning.
`summarize_run()` provides local analytics. Estimates use dated gateway rates;
unknown costs remain unknown. Phoenix is deferred, not a build dependency.

Planned Stage D is sleeve-based LLM extraction. Each independently testable sleeve owns one coherent field family, system prompt, output schema, topic-map evidence packet, and validation rules. Initial sleeves cover parties, interest terms, maturity and extension, covenants, and repayment terms; add further field-family sleeves without redesigning the pipeline. Run only the sleeves requested for a job. Require a shared result envelope with structured values, uncertainty, and cited Docling item IDs. Validate each sleeve independently, broaden topic-map retrieval only for affected sleeves, resolve citations to verified evidence, and merge validated sleeves into the requested document-level JSON.

## Source Documents

- `raw_documents/pdf/` and `raw_documents/htm/` are the preserved source corpus and ground truth.
- Treat source documents as immutable. Do not delete, rename, overwrite, or silently transform them.
- Put generated text, intermediate files, and extraction results outside `raw_documents/`.
- Ask before adding, replacing, or removing corpus documents.

## Extraction Quality

- Keep evidence with extracted facts when available: document, page, section, and concise source excerpt.
- Distinguish missing, uncertain, and not-applicable values; do not invent values or confuse absence with zero or false.
- Prefer transparent normalization while retaining source wording needed to verify the result.
- Avoid document-specific hardcoding. Check behavior across materially different agreements before treating a rule as general.

## Working Method

- Work in small, reviewable steps; define and validate one outcome at a time.
- For material behavior or architecture changes, clarify requirements and agree on a short design before implementation.
- Keep PDF parsing, legal-term extraction, LLM reasoning, JSON validation, and evidence capture as independently testable concerns where practical.
- Use representative documents and regression checks as the corpus grows; report uncertainty and observed failure cases.
- Do not treat a pending diagram component as implemented until its acceptance checks pass and the diagram and backlog are updated.
- Do not select a final extraction schema or agent topology before evidence and user agreement support that decision.

## Build Tracking

The saved-run HTML reviewer (`review.py` / `review.html`) is read-only and
separate from pipeline execution. Use actual logged A/B1–B4/C inputs, outputs
and events; join item IDs to original text/pages/table cells/heading context.
B2 review uses provisional rule matches, B3/B4 use final citations, and
unclassified chunks stay visible. Never substitute sample data or infer
unrecorded substep progress. The live progress dashboard remains parked.

- `docs/conversion_pipeline.md` is the authoritative architecture and status diagram.
- `docs/build_backlog.md` is the registry for agreed but unimplemented components.
- `docs/superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md` is the approved A5/A10/A11 implementation plan.
- `docs/superpowers/plans/2026-09-30-b1-page-first-chunking.md` is the approved B1 implementation plan.
- `docs/superpowers/plans/2026-10-01-b3-topic-reflection.md` records the B3/B4 and local telemetry build.
- When a tracked component begins or finishes, update the backlog and pipeline diagram in the same change.

## Project Note

Maintain project context in the Obsidian note: [Credit Agreement Parser](file:///Users/ashrit/Library/Mobile%20Documents/iCloud~md~obsidian/Documents/Obsidian_ashrit/Projects/Credit%20Agreement%20Parser.md).
