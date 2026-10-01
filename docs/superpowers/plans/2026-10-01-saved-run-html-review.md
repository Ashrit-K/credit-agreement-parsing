# Saved-run HTML review implementation plan

**Goal:** Replace fabricated browser data with the logged Amerigo run. Let the
user review every implemented stage's inputs/outputs and inspect source wording
beside B2/B3 classifications and B4 topic assignments, without paid reruns.

**Architecture:** A read-only Python exporter reads one existing run's events and
allowlisted debug snapshots and embeds them in a self-contained HTML inspector.
Regenerating the page reloads current saved logs. This is historical inspection,
not a new job-launching UI or fine-grained conversion instrumentation.

**Constraints:** Stay on main; preserve sources, logs and unrelated edits; no
external browser assets, API keys, new dependencies, model calls or guessed
substep statuses. Preserve numbered pipeline IDs, cognitive purple and dashed
pending components. Log text must render as text, never executable HTML.

## Tasks

- [x] Add tests in `tests/test_review.py`: reads events and snapshots; rejects
  path traversal; filters unknown files; escapes embedded script delimiters;
  joins original wording/pages, inherited headings, labels and unmatched chunks;
  exposes actual stage boundary inputs/outputs and absent-data states. Run with
  `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest tests/test_review.py -q` and
  observe missing implementation fail.
- [x] Implement `src/credit_agreement_extractor/review.py` with
  `load_run_review(run_id, trace_root)` and `export_run_review(run_id, destination,
  trace_root)`. Read allowlisted stage/artifact/model snapshots from debug and
  event history; use last completed stage result while preserving all events
  and failed attempts. Embed JSON with script-safe escaping in package template
  `review.html`. Source IDs/evidence text remain unchanged.
- [x] Build a stage selector (A/B1/B2/B3/B4/C and pending B5/B6/D), topic filter,
  source-chunk list, readable source text/pages/table cells, and classification
  pane. Highlight B2 rule matches or B3 cited items according to selected stage.
  Resolve clicked citations directly to source paragraphs or inherited headings.
  Include unclassified chunks, stage argument/input/output artifact snapshots,
  chronological events, conversion Markdown/JSON/hierarchy/manifest, and saved
  model attempts. Raw JSON sections render lazily and source/model text uses
  DOM textContent, never injected HTML. A1–A11 microstep progress is unavailable,
  not invented. The connected pipeline/progress dashboard is parked.
- [x] Run focused and full tests. Export actual run into existing browser
  preview directory; verify actual 29-chunk/7-batch data, B3 retry selection,
  Markdown, and no illustrative content. Save browser screenshot. Document
  reproducible export command in README; leave conversion pipeline unchanged.

No commits or pushes are included in this request.

## Completion evidence

154 tests pass (12 review tests). Browser interactions verified topic/stage
selection, B2 versus B4 filtering, chunks, heading/citation focus, unclassified
review, A hierarchy output, C provider captures, pending-stage notices, narrow
source/results switching and desktop side-by-side layout. Actual export audit:
29 chunks, 9 interest chunks, 2 unclassified, six implemented stage views,
exact API arguments, no API key, unchanged source fingerprint. Review fixes
excluded artifact captures from API-argument/return selectors; punctuation
round-tripping is regression-tested. No paid rerun was needed.
