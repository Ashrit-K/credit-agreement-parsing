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
- Component IDs are stable within their explicit layout. Current `stage-b-v2`
  uses B1 chunks, B2 LLM classification, B3 map, B4 retrieval and B5 packaging.
  Historical unmarked runs keep B2 heuristics, B3 classification and B4 map;
  old B3 → new B2, old B4 → new B3, old B5 → new B4, old B6 → new B5.
  Deleted heuristic B2 has no current counterpart. Preserve historical plans/reports.

Implemented Stage A behavior currently includes:

- Python 3.11 and uv-based development.
- `convert_document(path)` support for PDF, HTML, and HTM input.
- Local Docling conversion, with English RapidOCR available for PDFs.
- A5's Docling PDF pipeline includes heading-hierarchy inference and parsed-page
  generation, recorded in the manifest and conversion profile.
- Gzip magic-byte detection and temporary decompression for compressed SEC `.htm` files.
- Canonical JSON, Markdown and final manifest under
  `tmp/converted/<source-sha256>/` by default, including versioned
  `document.hierarchy.json`: A10 defaults on. Explicit
  `convert_document(..., use_hierarchy=False)` writes three artifacts under
  `tmp/converted/<source-sha256>/a10-disabled/`.
- A development-only cache shortcut keyed by source SHA-256 and conversion
  profile/mode that validates three disabled-mode or four enabled-mode artifacts.
  Disabled manifests explicitly declare the sidecar disabled and its filename
  null; `hierarchy_json_path=None`. Never bypass a missing enabled sidecar.
- A10's pure, independently tested canonical-JSON hierarchy transformation in
  `hierarchy.py`.
- A11's integration of A10 after canonical serialization, deterministic
  sidecar persistence, manifest-last completion boundary, and enriched
  `ConversionArtifact` return contract.

Implemented Stage B behavior currently includes:

- B1's pure `build_chunk_document()` transformation and public
  `build_chunks(conversion_artifact)` persistence wrapper in `chunking.py`.
- Separate schema-versioned output under
  `tmp/stage_b/<source-sha256>/document.chunks.json` when enabled, or its
  `a10-disabled/` subdirectory when disabled, separate from Stage A artifacts.
- Page-first PDF chunks, a 12,000-character heading-aware fallback for
  page-less HTML, and no overlapping source items.
- Atomic canonical leaves, tables, and explicit Docling lists, with original
  and normalized source wording, page provenance, A10 heading paths, container
  ancestry, deterministic chunk IDs, and neighbor links.
- A development cache keyed by source identity, chunking profile/mode, canonical
  JSON hash and nullable hierarchy hash. B1's canonical-reference fallback
  retains reading order, original content, pages and container/list ancestry
  with empty heading paths; it never invokes the A10 builder. B2/B3 and
  saved review support either mode. Human annotation explicitly enables A10 to
  keep existing catalogs stable. A5 inference is unchanged; this toggle is not
  a fix for fragmented text or an accuracy claim.

For A10:

- Preserve Docling container ancestry, reading order, generic numeric heading paths, and canonical page provenance.
- Keep `document.docling.json` canonical and unchanged; do not build a replacement document or custom PDF-layout parser.
- Treat hierarchy as optional context that can never discard, reorder, or summarize source content.
- Limit initial hierarchy warnings to `no_headings`, `flat_levels`, `skipped_levels`, and `non_monotonic_pages`.
- Treat broken references, malformed heading levels, and cycles as errors rather than warnings.

B1, B2 and B3 are implemented. `reflect_topics(chunks, *, ...)` performs
B2 LLM passage classification directly from B1 source chunks: Luna/high by default,
up to five chunks/24,000 evidence characters per batch, verified item citations,
bounded retries and hash/settings-keyed validated checkpoints. Current APIs remove
`classify_chunks`, `TopicSignalsArtifact`, phrase rules, signals inputs and `use_b2`.
The shared versioned nine-topic vocabulary and subtopics remain in `topic_taxonomy.py`.
Profiles/results and checkpoint identity declare `pipeline_layout='stage-b-v2'`;
current checkpoints use `b2-checkpoints` and never silently reuse historical ones.
Current classification/map files live under `tmp/stage_b/<source-sha256>/stage-b-v2/`
or `<source-sha256>/a10-disabled/stage-b-v2/`; B1 retains its parent location and
historical classifier/map files remain untouched.

Independent batches run with configurable `max_concurrency=5` by default;
`max_concurrency=1` runs sequentially. Each batch has at most two attempts.
Failure stops scheduling, preserves successful in-flight checkpoints, and never
finalizes partial output. Classifications remain in source order; concurrency
does not invalidate policy checkpoints. Copied trace contexts and serialized
JSONL writes preserve batch/attempt attribution, with unique debug attempt IDs.
Sanitized `_trace` snapshot metadata retains run/span/stage/batch/attempt
identity. The saved reviewer pairs B2 exchanges by attempt ID and C boundaries
by span ID; it must not pair concurrent calls by log adjacency.
B2's `b2-passage-classification-v1` prompt consumes shared, versioned topic definitions
from `topic_taxonomy.py`; definition hashes invalidate checkpoint
reuse independently of unchanged topic IDs.
No possible-label bucket or Jev/verifier layer. B3's
`build_topic_map()` validates classifications and persists a deterministic
topic-to-passage index, not summaries. B4/B5 are implemented through
`retrieve_evidence(topic_map, chunks, *, topics, conversion=None, ...)`.
Only approved taxonomy IDs are accepted; downstream extraction owns cognitive
topic resolution. Retrieve all exact mapped groups without ranking/truncation;
return empty matches explicitly. B5 resolves original evidence/context wording,
pages, headings and containers. Tables require matching hash-verified canonical
Stage A JSON. No new model call, no source rewrite, no question interpretation.
New schema-v2 maps bind semantic B1 JSON with `chunks_document_sha256`; old
schema-v2 maps must be rebuilt offline by B3. Schema-v1 remains reviewer-only
and is not reinterpreted. Request-specific packets persist adjacent to the map
under `evidence/<request-hash>/document.evidence.json`; basic/debug traces cover
B4/B5 and the `topic_evidence` composition. No cache shortcut initially.

The original passage-level refinement (historical B3/B4 numbering) is documented in
`docs/superpowers/plans/2026-10-01-b3-b4-passage-evidence.md`.
Keep B1 packaging unchanged; use the existing B2 call to select coherent
topic-specific groups with separate direct-evidence and supporting-context
IDs, then let B3 index them. Schema-v2 outputs are `document.topic-passages.json`
and `document.topic-passage-map.json`; historical schema-v1 citations and files
remain unchanged and readable, not reinterpreted as passage roles. Default
`boundary_context_groups=1` supplies neighboring atomic groups without text
truncation; every group needs core direct evidence and canonical per-target
scope. Packet/schema/boundary hashes invalidate checkpoints; B3 recomputes
provenance and deduplicates exact groups only. The reviewer foregrounds original
evidence with separate expandable context, full chunks and heading/page metadata.
Do not add another classification layer without approval.

The shared paragraph/table source-item resolver is deferred in the backlog.
Core tables use B1 joined content; missing selected neighboring-table text is
an explicit pre-call input error. Do not silently discard it or expand into an
unapproved whole-neighbor-chunk fallback. B1 and canonical Stage A stay unchanged.

Stage C is a cross-cutting LLM interface, not a sequential document-processing stage. It routes OpenCode requests through explicit, tested model-to-API mappings. The agreed default is `gpt-5.6-luna` with medium reasoning, with call-time overrides for model, reasoning effort, and API style. Support Responses, Chat Completions and Qwen Messages adapters. Qwen Messages supports none/high; high maps explicitly to a 16,000-token thinking budget with a 32,768 total output cap. Reject unsupported Messages tiers. Responses/Chat accept xhigh without substitution; Claude support is not required. Every purple LLM box uses this shared transport contract with its own system prompt, evidence, and response schema; do not route document artifacts through C in the pipeline diagram.

Stage C's `OpenCodeClient` is implemented. Responses/Luna/high was checked live;
Chat Completions and Qwen Messages now have tiny live access checks at the
requested high effort; GPT-5.6 Luna/xhigh also passed. Strip hidden thinking,
reasoning text and signatures from provider debug snapshots. Normalize Messages
cache buckets into total input usage without double charging. Use the explicit
application User-Agent; the default Python client was blocked by Cloudflare.
Do not silently substitute models. All public file/pipeline APIs support
`debug`, `run_id`, and `trace_root`: local basic JSONL telemetry always persists;
debug adds intermediate artifacts, prompts/responses, and sanitized validation
diagnostics. Never capture keys, authorization headers, or hidden reasoning.
`summarize_run()` provides local analytics. Estimates use dated gateway rates;
unknown costs remain unknown. Phoenix is deferred, not a build dependency.

Stage D's initial fixed Python orchestrator is implemented through
`extract_credit_terms(topic_map, chunks, *, conversion=None, ...)`. Only this
entry accepts D jobs and returns document JSON. One bounded specialist covers
parties, facility amounts and interest/fees, calling shared B4/B5 retrieval and C
transport. No additional orchestration/resolver LLM or autonomous loop. Defaults
follow Stage C; model/effort/API-style overrides remain available. Parent-child
links are separate from agreement roles; role casing/spacing is normalized.
Preserve IDs, numeric fraction rates, stated rate periods, explicit unknowns and
source citations. Typed Decimal calculations never execute free-text formulas.
Validate every numeric total, citation and entity/facility reference; missing
amounts cannot allow uncited facilities. Maximum two attempts; authentication,
configuration and model/style substitutions fail without silent fallback.
`run_pipeline(path, ...)` chains A/B1/B2/B3 and directly triggers D after B3
success, with a `topic_map_ready` event. Standalone B3 never initiates extraction.
Persist unique execution results under `tmp/stage_d/<source-sha256>/` and write
the provenance manifest last; never overwrite successful historical runs.
D1 orchestration, D2 specialist, D3 validation and D4 completion have basic/debug
traces, original evidence/context, source lookup and sanitized retry diagnostics.
The saved HTML reviewer has not gained a Stage D view. Human extraction evals,
new specialists and unbounded evidence broadening remain later work.

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
separate from pipeline execution. Use actual logged A/B1–B3/C inputs, outputs
and events; join item IDs to original text/pages/table cells/heading context.
Current B2/B3 review uses final citations; historical unmarked runs retain
old B2 saved rule matches and B3/B4 labels, and
unclassified chunks stay visible. Never substitute sample data or infer
unrecorded substep progress. The live progress dashboard remains parked.

- `docs/conversion_pipeline.md` is the authoritative architecture and status diagram.
- `docs/build_backlog.md` is the registry for agreed but unimplemented components.
- `docs/superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md` is the approved A5/A10/A11 implementation plan.
- `docs/superpowers/plans/2026-09-30-b1-page-first-chunking.md` is the approved B1 implementation plan.
- `docs/superpowers/plans/2026-10-01-b3-topic-reflection.md` records the B3/B4 and local telemetry build.
- When a tracked component begins or finishes, update the backlog and pipeline diagram in the same change.

## Human ground truth boundary

The separate `annotation.py` / `annotation.html` app reviews the approved sources
in `evaluations/golden_documents.json`. Human passage labels persist only under
ignored `evaluations/ground_truth/`. Never read these labels in conversion,
chunking, classification, mapping, model transport, prompts, retrieval, or
extraction. Candidate runs use only source artifacts, shared taxonomy and source
evidence. Evaluation scoring may compare saved results with human labels only
after model execution. Do not seed classification or a model request with reviewed labels.
Unreviewed passages are not negative labels. Keep source/catalog fingerprints
and taxonomy versions attached to all human decisions.
Taxonomy v2 adds `contract_definitions`. Preserve legacy v1 labels and all
record fields; `reviewed_topics` explicitly records coverage. Old reviews do
not establish a negative for the new category. Loading is read-only; saves
require current taxonomy and revision checks. Never reset human review data
when changing the taxonomy. Back up and verify existing records first.

## Project Note

Maintain project context in the Obsidian note: [Credit Agreement Parser](file:///Users/ashrit/Library/Mobile%20Documents/iCloud~md~obsidian/Documents/Obsidian_ashrit/Projects/Credit%20Agreement%20Parser.md).
