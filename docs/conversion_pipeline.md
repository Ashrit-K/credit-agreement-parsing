# Document Conversion and Extraction Pipeline

This document is the authoritative view of the credit-agreement pipeline. The
diagram distinguishes what exists today from the architecture we have agreed to
build next.

## Python entry point

```python
from credit_agreement_extractor import build_chunks, convert_document

artifact = convert_document("raw_documents/pdf/example.pdf")
chunks = build_chunks(artifact)

print(artifact.docling_json_path)
print(artifact.hierarchy_json_path)  # A10 enabled by default; opt out with use_hierarchy=False
print(artifact.markdown_path)
print(artifact.manifest_path)
print(chunks.chunks_json_path)
```

The default output root is `tmp/converted/`. Each source is placed in a folder
named with its SHA-256 fingerprint. Callers do not calculate or supply this
fingerprint: the function calculates it from the source bytes. Repeating a call
with identical source bytes reuses a complete cached conversion only when its
conversion-profile identifier also matches the current settings.

The cache short circuit is currently a development optimization. A10 is
optional and enabled by default under `tmp/converted/<source-sha256>/`.
Explicit `use_hierarchy=False` outputs live under
`tmp/converted/<source-sha256>/a10-disabled/`. Mode-sensitive profiles and
manifest declarations prevent cross-mode reuse. Enabled mode requires all four
files and a valid schema-version-1 sidecar with the same source fingerprint;
disabled mode requires three files and an explicitly disabled sidecar record.
Production cache policy remains a separate decision.

## Conversion artifact contract

The completed Stage A artifact contains four files by default, three with A10 disabled:

- `document.docling.json` is the canonical conversion. It remains unchanged
  after Docling exports it and retains Docling item identifiers and available
  provenance such as page numbers, character spans, and bounding boxes.
- `document.md` is a readable derivative for manual review and debugging. It is
  not the downstream source of truth.
- Optional `document.hierarchy.json` is the A10 sidecar. It adds generic heading
  paths and hierarchy-quality warnings keyed by canonical Docling item IDs. It
  does not copy or rewrite the complete document.
- `manifest.json` records source identity, converter version, OCR and heading-
  hierarchy configuration, conversion profile, gzip normalization, artifact
  names, and final conversion status.

Both modes are implemented and tested. When enabled, A10 builds and persists the
hierarchy mapping after canonical serialization; otherwise A9 routes directly
to A11. A11 writes the completed manifest last after every mode-required output
exists. Disabled mode returns `hierarchy_json_path=None` and records
`hierarchy_sidecar={"enabled": false, "status": "disabled"}` with a null
`artifacts.hierarchy_json`. A missing enabled sidecar is an error, not a bypass.

OCR is enabled only for PDF conversion. The manifest records configuration, not
a claim that OCR was necessary on a particular born-digital page; Docling's OCR
mode decides which page regions need recognition.

Several SEC-sourced `.htm` files are actually gzip streams. The function detects
the gzip signature from the bytes, creates a temporary plain-HTML copy for
Docling, and removes that copy afterward. It never rewrites the source file.

## Frozen hierarchy design

Optional-A10 ablation is implemented; see the [implementation plan](superpowers/plans/2026-10-02-optional-a10.md).
A10 now defaults on; use `convert_document(path, use_hierarchy=False)` to
run the explicit ablation without added heading paths.
This toggle does not disable A5's Docling inference or repair fragmented text.
Its accuracy benefit remains an evaluation question, not an implementation claim.
The completed 2026-10-02 011 joint A10/B2 ablation observed lower F1 for all
three tested models with both disabled than with only B2 disabled. This is
single-document evidence, with size-bounded batch packing also changing;
see the completed experiment in [build backlog](build_backlog.md). These observations motivate the A10-on default, but do not establish a
corpus-wide accuracy improvement.

Within A5, Docling's built-in heading-hierarchy inference is enabled for PDF
conversion so the canonical export contains all structure Docling can recover.
A5 also enables parsed-page generation, records both settings in the manifest,
and uses a distinct conversion profile so older caches are not reused.

A10's pure builder consumes the canonical JSON and produces the in-memory
sidecar mapping with:

- generic heading depths and ancestor paths rather than legal-specific labels
  such as `Article`, `Section`, or `Clause`;
- mappings keyed by canonical IDs such as `#/texts/17` and `#/tables/3`;
- page provenance copied from the referenced canonical items;
- one small warning taxonomy: `no_headings`, `flat_levels`,
  `skipped_levels`, and `non_monotonic_pages`;
- explicit validation failures for broken references or cycles rather than
  treating corrupt structure as a warning.

Hierarchy is useful context, not an authority that can discard content. The
builder does not alter reading order, rewrite source text, infer legal meaning,
or remove items. When hierarchy is sparse or imperfect, Stage B still has the
canonical page-first reading order. Persisting this mapping as
`document.hierarchy.json` and adding it to Stage A's cache/artifact contract are
implemented through A11.

## B1 chunk artifact contract

B1 is implemented as a separate Stage B operation:

```python
chunks = build_chunks(artifact)
```

It reads canonical Docling JSON and the optional A10 sidecar and writes:

```text
tmp/stage_b/<source-sha256>/document.chunks.json
tmp/stage_b/<source-sha256>/a10-disabled/document.chunks.json  # explicit opt-out mode
```

The chunk artifact is schema-versioned and records its source fingerprint,
chunking profile, `inputs.use_hierarchy`, the canonical JSON hash and nullable
hierarchy JSON hash. It contains
deterministic chunk IDs, neighbor links, exact canonical item IDs, verified
pages, source wording, table renderings, hierarchy paths, and container/list
relationships. It does not duplicate bounding boxes or character spans; those
remain resolvable from canonical JSON through each retained item ID.

Without A10, B1 walks validated canonical body/group references for reading
order, pages and container/list ancestry. Heading items stay in source content,
but `heading_path=[]`. Broken references, cycles and repeated references still
fail. B2/B3 and saved-run review work in both modes; their outputs inherit
the separate B1 directory and input fingerprints. Annotation preparation stays
explicitly enabled to avoid changing existing human source catalogs.

PDFs use page-first boundaries. Large pages split only between atomic units,
while individual leaves, tables, and explicit Docling lists remain intact.
Fully page-less documents use heading-aware reading-order chunks targeting
12,000 characters. B1 creates no overlap and never fabricates page provenance.

The persisted file also acts as a development cache. A source, profile, schema,
or Stage A input-hash mismatch rebuilds only B1 and does not rerun Docling.

## Topic-map and evidence rule

The current layout is explicitly `stage-b-v2`: B1 chunks → B2 LLM passage
classification → B3 topic-map construction → pending B4 evidence retrieval →
pending B5 packaging. `reflect_topics(chunks, *, ...)` consumes source chunks
without heuristics; `classify_chunks`, `TopicSignalsArtifact`, phrase rules,
signals inputs and `use_b2` have been removed. Topic IDs/definitions, model
settings and passage evidence/context roles remain unchanged.

Historical unmarked runs keep their original IDs and saved labels: old B2
heuristics (or skipped), B3 classification and B4 map. The explicit mapping is
old B3 → current B2, old B4 → current B3, old pending B5 → current B4 and old
pending B6 → current B5; deleted heuristic B2 has no current counterpart.
Historical plans and evaluation reports retain their numbering. Profiles/results
include `pipeline_layout='stage-b-v2'` and current `b2-checkpoints` have distinct
identity; historical checkpoints are never silently reused.

## B2/B3 contracts and local observability

Human reference labels are authored in the separate local `annotation.py` /
`annotation.html` app, using original canonical passages from the approved golden
documents. They persist only in `evaluations/ground_truth/`; no processing stage
or purple LLM step reads them. Future evaluation compares completed independent
model runs with human labels afterward. The annotation surface is outside the
document-processing diagram; it does not change B1/B2/B3 contracts.
Shared taxonomy v2 adds `contract_definitions` as a ninth top-level topic.
Explicit definitions can also carry substantive labels. Human annotation
coverage is per-topic: legacy reviews retain all saved decisions and leave the
new topic unknown until reviewed. No component IDs or implementation-status
lines change for this additive vocabulary update.

`reflect_topics(chunks, *, ...)` is implemented. It sends up to five chunks
per batch, bounded by 24,000 serialized packet characters (oversized packets
run alone), using `gpt-5.6-luna` with high reasoning by default. Model,
reasoning effort, and API style can be overridden. Source text, table content,
heading context and bounded source neighbors reach the model.
The `b2-passage-classification-v1` prompt uses shared, versioned topic definitions from
`topic_taxonomy.py`, including boundaries between incidental party mentions,
payment defaults, interest terms, and prepayment premiums. Both the prompt and
definition hashes participate in checkpoint identity. Topic IDs and definitions are unchanged. Historical schema-v1 runs (including the original Amerigo run
and the later GPT-6-Luna/medium v2-prompt run) remain historical evidence, not
evaluations of schema-v2 passage selection. No live passage-level quality
improvement has been measured yet.

B2 validates one result per target chunk, approved topics only, and groups of
direct-evidence and supporting-context IDs in that target's explicit core,
heading and bounded-neighbor scope. Every group requires core direct evidence;
another target in the same request does not expand allowed IDs. It adds parents for approved
subtopics. There are no possible-topic buckets, confidence scores, Jev gates,
or second opinions. Two attempts maximum handle transient API or invalid-output
failures; authentication errors and model substitutions stop immediately.

Independent batches run in a bounded thread pool with `max_concurrency=5`
by default. A positive integer controls simultaneous batches; booleans are
rejected, and `max_concurrency=1` preserves sequential execution. Each batch
owns its two-attempt lifecycle and validated checkpoint. Copied trace contexts
retain B2 parent spans, batch/attempt settings and nested C attribution;
serialized JSONL appends and unique snapshot/attempt IDs support concurrent
debug exchanges. Injected clients must allow concurrent `complete()` calls.
Debug dictionaries and serialized dataclasses carry sanitized `_trace`
run/span/stage/batch/attempt metadata. The reviewer pairs B2 model attempts by
attempt ID and C boundaries by span ID, including out-of-order responses.
Final classifications are validated and persisted in source order, independent
of completion order. Failure stops new scheduling and cancels unstarted work;
in-flight calls may finish and save successful checkpoints. No partial final
artifact replaces a completed result. Concurrency changes do not invalidate
checkpoints, because evidence, batching and classification policy are unchanged.

Validated batches are checkpointed by input hashes and settings. Repeated calls
reuse matching checkpoints; `force=True` requests fresh classification. A failed
new run does not replace the last successfully completed result. B2 persists
`document.topic-passages.json` under `tmp/stage_b/<source-sha256>/stage-b-v2/`;
explicit A10 opt-out uses `<source-sha256>/a10-disabled/stage-b-v2/`.
B1 stays in its original parent directory. `build_topic_map(chunks,
classifications)` revalidates it and writes `document.topic-passage-map.json`
in the same layout directory, preserving historical files.
B3 indexes topic -> original passage groups in source order, deduplicating exact
group identities only. Both retain an explicit unclassified-target list. Legacy
schema-v1 input dispatch still writes `document.topic-map.json`; it does not
invent direct/context roles. B3 neither summarizes nor calls an LLM.

### Implemented B2/B3 passage-level refinement

The solid B2/B3 components now implement schema-v2 topic-specific groups with
separate `evidence_item_ids` and `context_item_ids`. B1 packaging and the single
B2 call remain unchanged. The default `boundary_context_groups=1` supplies one
atomic neighbor on each side; no text is truncated. Source-order IDs, stable
group identity, owner chunks and evidence/context pages are derived and verified
in code. Parent subtopics retain the same group roles. B3 recomputes provenance
and packet identity, retains nonidentical overlaps and indexes exact groups.
Review foregrounds selected passages with pages/headings and expandable context
and full source chunks. Schema, complete packet, boundary, prompt and definition
hashes prevent legacy checkpoint reuse. Implementation details are in the
[implementation plan](superpowers/plans/2026-10-01-b3-b4-passage-evidence.md).
No new numbered processing stage or additional LLM pass is introduced.

The shared paragraph/table source-item resolver is separately **deferred**.
It will reuse canonical Stage A cells for precise B2 table context and human
review without changing B1 or adding a table-processing stage. Until then,
missing neighboring-table text is an explicit input error, not silently omitted
context. Core tables retain B1's full joined rendering.

Stage C's shared `OpenCodeClient` implements explicit model routing, Responses,
Chat Completions and Qwen Messages adapters, and the application User-Agent required by the
tested gateway. Its general reasoning default is medium; B2 explicitly selects
high. Unknown model routes need an explicit supported API-style override.
Tiny live checks passed for GPT-6 Luna/high, GPT-5.6 Luna/xhigh, DeepSeek V4
Flash/high, DeepSeek V4.1 Flash/high and Qwen3.8 Flash/high. These verify access,
not classification accuracy or a provider's internal effort implementation.
Responses/Chat forward `xhigh` unchanged. Qwen Messages supports `none` or
`high`; high explicitly uses a 16,000-token thinking budget and 32,768 total
output allowance, matching OpenCode's budget-style high variant. Unsupported
Messages tiers fail before requests. Model identities must match B2 requests.
Messages cache-read/write tokens are included in normalized input totals and
priced once. All response debug snapshots omit hidden reasoning and signatures.
`OpenCodeClient(timeout_seconds=60)` exposes a positive finite transport timeout.
The five-model 011 benchmark uses 300 seconds for high-effort responses; changing
this transport limit does not change model/prompt/evidence checkpoint identity.
Responses and Chat output allowances are configurable via
`OpenCodeClient(max_output_tokens=8192)`. The benchmark's GPT-5.6/xhigh and
DeepSeek V4.1/high recoveries use 32,768 after recorded outputs exhausted the
original allowance entirely on reasoning. Effective request limits and any
machine-only retry feedback are saved in recovery policies and C request traces;
the benchmark must disclose these interventions when comparing cost/accuracy.

The 2026-10-02 `jev-1.13` classification benchmark uses a separate experimental
System One transport in `evaluations/jev_benchmark.py`, not a production B2/C
adapter or a new diagram component. Each source item has independent approved
topic questions with a fixed 0.5 yes-probability cutoff, full owning-chunk context
and existing boundary context. No human labels enter those requests; scoring is
offline only. Native item decisions are compared with B2 direct-evidence item
labels, not claimed to reproduce B2 passage/context grouping. All probabilities
and measured usage persist; first-run trace consolidation and missing original
HTTP-envelope snapshots are explicitly documented in the saved recovery record.

All public pipeline/file APIs accept `debug=False`, `run_id=None`, and
`trace_root='tmp/runs'`. Use one run ID across separately called stages to link
them. Metadata and LLM usage/latency/cost are always appended to
`tmp/runs/<run-id>/events.jsonl`; `debug=True` also copies intermediate artifacts,
prompts, responses, and validation diagnostics under `debug/`. Secrets and
authorization headers are excluded; hidden model reasoning is not captured.
`summarize_run(run_id)` aggregates requests, retries, usage, costs, failures,
and latency by model/stage/document. Costs are reported only for explicit
amount/currency objects, otherwise estimated from dated gateway rates or unknown.
The default pricing snapshot covers Luna inputs up to 272K tokens, checked
2026-10-01; other models/tiers need explicit rates. Reasoning tokens are already
included in output totals and are not charged twice. These estimates are not bills.

Phoenix is deferred and is not a runtime dependency. B4/B5 retrieval and Stage D
extraction sleeves remain pending. Small smoke tests verify wiring, not legal
classification accuracy across the corpus.

Implemented B1 begins from canonical Docling items and builds page-first chunks. Page
boundaries guide chunk starts and ends, while tables remain atomic where
practical and lists are not split midway. Each chunk keeps its item IDs, page
numbers, neighboring chunk links, and any A10 heading path.

Every chunk reaches B2's batched LLM passage classification directly from B1.
Its final labels feed B3's provenance-preserving topic map;
neither may replace the underlying
source text with a summary. The map retrieves likely evidence for a requested
field, and request assembly sends that original evidence and its identifiers to
the extraction model.

The extraction model may cite retained item identifiers, but it must not invent
page numbers or coordinates. Application code resolves cited identifiers and
copies verified provenance into the structured result. Missing or uncertain
required fields trigger broader retrieval from the topic map.

Stage D uses independently testable extraction sleeves. Each sleeve owns one
coherent field family, its system prompt, response schema, topic-map evidence
packet, and validation rules. Initial sleeves cover parties, interest terms,
maturity and extension, covenants, and repayment terms. A run may invoke only
the sleeves required by the requested output, and additional sleeves can be
added without redesigning the rest of the pipeline.

Sleeves return a common result envelope containing structured values,
uncertainty, and cited Docling item IDs. Each sleeve is validated independently;
only a failed or incomplete sleeve broadens its evidence retrieval. Validated
sleeve results are then merged into the requested document-level JSON.

Stage C is a cross-cutting interface rather than a step in the document data
flow. Every purple LLM box uses the shared routing and transport contract in
Stage C, while supplying its own system prompt, evidence, and response schema.
The diagram therefore keeps C isolated instead of routing document artifacts
through its adapter boxes.

## Pipeline

### Human review surface

The implemented read-only HTML exporter in `review.py` is an inspection surface,
not a new document-processing stage. It loads an existing debug run and exposes
A conversion artifacts, B1 source chunks, B2 final classifications and model
attempts, B3 topic assignments, and C
provider payloads/responses. Original source text, pages, tables and heading
context are displayed beside labels; clicking a citation focuses its source.
Unclassified chunks remain reviewable. Current B2/B3 runs show final passage
groups with direct evidence
prominent and supporting context/full chunks expandable. Historical runs show
explicitly legacy supporting citations without fabricated roles. Heading paths
are source provenance, displayed separately from model-selected context. Raw inputs, output artifacts
and events are expandable. Narrow browser panels use source/results switching;
wide browsers show them side-by-side.

Exports are snapshots, refreshed by rerunning the export command in README.
They do not run conversion/models or invent outputs for B4/B5/D. Stage A's
substeps were not separately traced in the current evaluation run. The full
live pipeline/progress dashboard is parked; Phoenix remains deferred.

### Architecture diagram

Status and cognitive work use separate visual signals:

- Capital letters identify major stages; numbers identify components within a
  stage, such as `A10` or `B2`.
- Solid borders and arrows mean implemented and tested.
- Dashed borders and arrows mean pending.
- Amber boxes identify provisional planned steps whose design is still subject
  to change.
- Purple boxes identify LLM or other cognitive inference steps, regardless of
  implementation status.

A10, A11, and B1 are implemented and tested. Their boxes and the A11-to-B1
connection are solid. B1-to-B2-to-B3 is solid; B2 is purple because it
uses an LLM. B3-to-B4 and later connections remain dashed: retrieval and
extraction are pending. Shared C1–C6 transport is implemented and tested.

```mermaid
flowchart TD
    subgraph A_GROUP["A — Document intake and conversion"]
        A1[A1 — PDF, HTML, or HTM path] --> A2[A2 — Validate and calculate SHA-256]
        A2 --> A3{A3 — Complete cached artifacts? Development only}
        A3 -->|Yes — current shortcut| A3_1[A3.1 — Return current ConversionArtifact]
        A3 -->|No — cache miss| A4{A4 — Document format router}
        A2 -.->|Target production route — bypass cache| A4
        A4 -->|PDF| A5[A5 — Docling PDF pipeline: local English OCR and heading-hierarchy inference]
        A4 -->|Plain HTML| A6[A6 — Docling HTML pipeline]
        A4 -->|Gzip-wrapped HTML| A7[A7 — Temporary local decompression]
        A7 --> A6
        A5 --> A8[A8 — Canonical DoclingDocument]
        A6 --> A8
        A8 --> A9[A9 — Write canonical Docling JSON and readable Markdown]
        A9 -->|use_hierarchy=true: default| A10[A10 — Hierarchy sidecar: on by default]
        A9 -->|use_hierarchy=false| A11
        A10 --> A11[A11 — Finalize manifest and return enriched ConversionArtifact]
    end

    subgraph B_GROUP["B — Topic-map construction and evidence retrieval"]
        B1[B1 — Build page-first chunks retaining Docling item IDs]
        B2[B2 — LLM passage selection: direct evidence and supporting context; up to 5 parallel batches]
        B3[B3 — Build provenance-preserving topic-to-passage map]
        B4[B4 — Retrieve topic-specific source evidence]
        B5[B5 — Assemble topic-evidence bundle with source IDs]
        B1 --> B2
        B2 --> B3
        B3 -.-> B4
        B4 -.-> B5
    end

    subgraph C_GROUP["C — Shared LLM interface logistics — cross-cutting"]
        C1[C1 — Default model and reasoning configuration]
        C2[C2 — Call-time model, reasoning, and API-style overrides]
        C3[C3 — OpenCode model router]
        C4[C4 — Responses API adapter]
        C5[C5 — Chat Completions API adapter]
        C6[C6 — Qwen Messages API adapter]
        C1 --> C3
        C2 --> C3
        C3 --> C4
        C3 --> C5
        C3 --> C6
    end

    subgraph D_GROUP["D — Sleeve-based LLM extraction and validation"]
        D1[D1 — Select requested extraction sleeves and schemas]
        D2[D2 — Dispatch topic-map evidence to selected sleeves]
        D3_1[D3.1 — Parties extraction sleeve]
        D3_2[D3.2 — Interest terms extraction sleeve]
        D3_3[D3.3 — Maturity and extension extraction sleeve]
        D3_4[D3.4 — Covenants extraction sleeve]
        D3_5[D3.5 — Repayment terms extraction sleeve]
        D3_6[D3.6 — Additional field-family sleeves]
        D4[D4 — Normalize sleeve result envelopes]
        D5[D5 — Validate each sleeve schema and citations]
        D6{D6 — Any sleeve missing, uncertain, or unsupported?}
        D7[D7 — Broaden evidence for affected sleeves only]
        D8[D8 — Resolve cited Docling item IDs to verified evidence]
        D9[D9 — Merge validated sleeves into requested-data JSON]
        D1 -.-> D2
        D2 -.-> D3_1
        D2 -.-> D3_2
        D2 -.-> D3_3
        D2 -.-> D3_4
        D2 -.-> D3_5
        D2 -.-> D3_6
        D3_1 -.-> D4
        D3_2 -.-> D4
        D3_3 -.-> D4
        D3_4 -.-> D4
        D3_5 -.-> D4
        D3_6 -.-> D4
        D4 -.-> D5
        D5 -.-> D6
        D6 -.->|Yes| D7
        D6 -.->|No| D8
        D8 -.-> D9
    end

    A11 --> B1
    B5 -.-> D1
    D7 -.-> B4

    classDef implemented fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1f2937;
    classDef pending fill:#f3f4f6,stroke:#6b7280,stroke-width:2px,stroke-dasharray:6 4,color:#1f2937;
    classDef provisionalPending fill:#fff7ed,stroke:#ea580c,stroke-width:2px,stroke-dasharray:6 4,color:#1f2937;
    classDef cognitiveImplemented fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#1f2937;
    classDef cognitivePending fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,stroke-dasharray:6 4,color:#1f2937;

    class A1,A2,A3,A3_1,A4,A5,A6,A7,A8,A9,A10,A11 implemented;
    class B1,B3,C1,C2,C3,C4,C5,C6 implemented;
    class B2 cognitiveImplemented;
    class B4,B5,D1,D2,D4,D5,D6,D7,D8,D9 pending;
    class D3_1,D3_2,D3_3,D3_4,D3_5,D3_6 cognitivePending;
```

The development cache shortcut returns through A3.1 only when all mode-required
files and their recorded identities validate. On a cache miss, A9 writes canonical
JSON and Markdown, optionally A10 builds the sidecar, and A11 writes the
completed manifest last before returning the enriched artifact.

B1 runs separately through `build_chunks()`. It reuses a validated Stage B
artifact when possible; otherwise it deterministically rebuilds
`document.chunks.json` from canonical JSON and optional hierarchy. B1 is the solid
handoff from completed conversion into implemented B2/B3 topic mapping.
