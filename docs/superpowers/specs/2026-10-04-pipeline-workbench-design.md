# Local Pipeline Workbench Design

Approved in chat on 2026-10-04. This is a local single-user tool for executing
and investigating the real pipeline, not a production service or accuracy claim.

## Scope

Repurpose `review.html` as a source/topic inspector embedded in a new HTML
workbench served by a small Python standard-library backend. The backend owns
one document worker at a time and delegates computation to `run_pipeline`.
The browser never receives credentials and never invokes a provider itself.

Select an immutable PDF from `raw_documents/pdf/`. No arbitrary filesystem path
or upload in v1. Every execution gets a fresh identifier and a persisted job
record; changing runs never reruns a model. History includes known saved trace
runs, with explicit historical layout and missing metadata. A restarted server
marks its unfinished jobs interrupted rather than pretending they still run.

B2 starts at `deepseek-v4-flash` / `medium`, D2 at `deepseek-v4-pro` / `high`.
Independent model/effort controls remain available. D2 remains one combined
call with at most two attempts; B2 keeps five concurrent batches. No model
selection eval is part of this UI build. A10 defaults on and remains selectable.

## UI

Top controls: source PDF, independent model/effort controls, hierarchy toggle,
debug toggle and an explicit run button labelled as potentially paid work.
Run history switches the entire displayed run. Document identity and run ID
remain visible. Source preview always follows the selected run, not stale input.

Connected A -> B -> D stage rail with clickable numbered components. C is
cross-cutting, not in the document-processing chain. Status uses text/icons
independent of purple cognitive coloring: waiting, running, completed, cached,
failed, skipped, interrupted or unrecorded for historical substeps.
Substeps within A are instrumented at real boundaries. B2 shows completed,
reused and active batches with recorded chunk/page scope where available.
Do not equate wall-clock time with completion percent or guess model token progress.

The inspector offers source PDF, stage inputs/outputs, rendered Markdown,
original source passages/tables/pages, topic groups, extraction results and
actual LLM prompt/request/visible response/retry diagnostics. Raw JSON remains
available with download. Clicking extraction citations resolves to verified
`source_evidence`, with page navigation in the PDF. No synthetic examples.

Debug mode adds full intermediate artifacts and model exchanges. With it off,
basic progress/telemetry and durable final results remain available; absent
snapshots are labelled unavailable, never reconstructed as actual model inputs.
Historical runs remain readable without applying new numbering to old logs.

## Backend and durability

Bind only 127.0.0.1. Strict registered-document IDs, validated run IDs and
allowlisted debug snapshot names; reject traversal and symlink escapes.
Never serve a generic filesystem root, `.env`, ground truth or arbitrary paths
from logged payloads. Source PDF serving is read-only. POST requires same-origin
checks plus a per-server token so another site cannot initiate paid model work.
One background thread allows browser progress polling while the pipeline runs.
Failure keeps events/intermediates, sets a sanitized error type and never
manufactures a completed extraction. No cancellation/automatic restart in v1.

View models are disposable human-review projections of existing events and
artifacts, not new canonical pipeline contracts. Pair concurrent exchanges
by span/attempt identity, not adjacency. Poll partial JSONL safely; ignore only
an incomplete final line, not corrupt completed records. Read large artifacts
on demand rather than embedding the entire trace in every poll.

## Verification

Offline tests cover controller single-job exclusion, defaults, immutable source
selection, failed/interrupted jobs, progressive snapshots, race-safe events,
trace-status projection, historic compatibility, source/citation resolution,
safe downloads and HTTP origin/path boundaries. Browser QA uses actual saved
011 traces and a clearly identified offline worker test; no paid agreement
rerun is necessary for UI verification. Full suite and exact staged snapshot
must pass. Update backlog/diagram, README/AGENTS and Obsidian project context.
