# Pipeline Workbench Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development. Independent task delegation is permitted by superpowers:subagent-driven-development; review task boundaries and the combined implementation. Build on main as requested. Steps use checkbox syntax.

**Goal:** Run a corpus PDF through A/B/D and inspect truthful live progress and
saved evidence using the existing HTML review surface.

**Architecture:** A loopback Python HTTP server controls one background job and
serves a new HTML shell. Trace-backed view models and the reused saved reviewer
provide inspection without changing canonical artifacts or extraction logic.

**Tech Stack:** Existing Python 3.11/uv environment, standard-library HTTP/threading,
existing Pydantic/trace/reviewer APIs, vanilla HTML/CSS/JavaScript. No new dependencies.

## Global constraints

- Build on main; preserve unrelated dirty work; stage exact task files/hunks only.
- No source modifications, ground-truth reads, paid UI QA or hidden reasoning capture.
- Bind 127.0.0.1; registered PDF IDs only; reject symlink/traversal/path escapes.
- Poll real events; never synthesize substep progress or provider completion percent.
- Single background document job; fresh run IDs; saved failed jobs remain reviewable.
- D2 defaults DeepSeek V4 Pro/high; B2 UI defaults DeepSeek V4 Flash/medium.
- [Approved design](../specs/2026-10-04-pipeline-workbench-design.md) governs scope.

## Task 1: Trace projection and loopback run controller

Create `workbench.py`, `workbench_data.py`, `tests/test_workbench.py`.
Interfaces: `Workbench(project_root, trace_root=None, pipeline=None)`;
`documents()->list[dict]`, `runs()->list[dict]`, `start_job(settings:dict)->dict`,
`run_data(run_id)->dict`, `snapshot(run_id,name)->dict`, `source_path(document_id)->Path`.
`make_server(workbench, port=0)->ThreadingHTTPServer`; CLI
`uv run python -m credit_agreement_extractor.workbench --port 60900`.

- [x] Write failing tests for corpus listing, traversal/symlinks, single active job,
  independent settings, persisted success/failure/interrupted state, historical logs,
  unfinished JSONL tail, nested/concurrent stage statuses and snapshots.
  Representative assertion: `assert workbench.start_job({'document_id': '011_credit_agreement.pdf'})['settings']['model'] == 'deepseek-v4-pro'`.
- [x] Run `UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest tests/test_workbench.py -q`; observe missing functionality.
- [x] Implement background job delegation to real `run_pipeline`, absolute generated
  roots, fail-safe sanitized records, one-worker lock and historical run enumeration.
  Return job fields `run_id,status,document_id,settings,started_at,error_type`;
  run data fields `run_id,job,events,stages,snapshots,summary,result,batches`.
- [x] Implement read-only GET `/api/documents`, `/api/runs`, `/api/runs/<id>`,
  `/api/runs/<id>/snapshots/<name>`, `/api/runs/<id>/review`, `/api/documents/<id>/pdf`;
  GET `/api/config` returns routes/defaults/token; POST `/api/runs` starts work.
  Root serves `workbench.html`. Unknown routes fail. Enforce Origin and token for POST.
- [x] Verify fake-worker HTTP tests make no provider calls; real saved logs remain unchanged.

## Task 2: Stage A substeps and D2 defaults

Modify `tracing.py`, `conversion.py`, `runner.py`, `orchestrator.py`,
`extraction_specialist.py`; create `tests/test_workbench_tracing.py`.
Add `trace_step(stage, inputs=None)` context manager returning output recorder;
emit started/finished and debug input/output plus artifact snapshots, restoring parent span.

- [x] Write red tests for real conversion/cache A1–A11 boundaries, failures,
  A10-off skips and unselected format paths. Existing converter test doubles suffice.
- [x] Trace actual format routing/converter setup/convert/export/write/hierarchy/finalize
  boundaries. A5/A6 mark converter setup, A8 actual Docling processing; preserve all
  byte/hash/cache contracts. A3.1 captures returned cached artifact, not a replay.
- [x] Write red tests for runner/orchestrator/specialist Pro/high defaults and overrides.
  Defaults explicitly select extraction model independent of general C `.env` default.
- [x] Set only D defaults; general C and B2 implementation defaults remain untouched.
- [x] Run conversion/tracing/runner/orchestrator tests including both A10 modes.

## Task 3: Reuse reviewer and implement HTML workbench

Modify `review.py` / `review.html`; create `workbench.html`; extend `test_review.py`.

- [x] Write red tests for D1–D4/B5/A-substep snapshot allowlists, actual source-evidence
  extraction inspection, current/historical labels and safe untrusted text.
- [x] Extend read-only reviewer without deleting historical behavior; stage query selects
  relevant current stage; B4/B5/D display recorded artifacts instead of pending placeholders.
- [x] Build shell controls/connected rail/inspector with text-safe DOM creation. Poll
  selected run only; guard out-of-order responses on run switches. Show source PDF,
  clickable source passages/citations, formatted JSON/Markdown, trace snapshots,
  batch active/completed/reused counts, latency/tokens/cost with unknowns preserved.
- [x] Download only allowlisted snapshot/final data; iframe saved reviewer for topic/source
  inspection. Never trigger work on run selection/poll/refresh. Keep debug on by default.
- [x] Browser-check actual saved 011 traces, run switching and PDF/page links;
  responsive CSS is implemented, but a separate narrow-viewport browser check is
  not available in this browser harness. Offline controller tests cover live
  progression without paid work.

## Task 4: Review and delivery

- [x] Independent scoped review; reproduce/fix important findings before claiming completion.
- [x] Run full suite and `git diff --check`; test exact staged snapshot and secret scan.
- [x] Update authoritative diagram/backlog, README/AGENTS and Obsidian project/daily notes.
  Add workbench as an interface outside stages, preserve numbered/purple/status conventions.
- [x] Deliver scoped changes on main through the associated commit/push; final SHA
  and goal completion are verified after publication.

## Execution ledger

2026-10-04: Implemented and independently re-reviewed. Working-tree suite: 410 passed;
exact staged snapshot: 390 passed. Credential scan and whitespace checks passed.
Browser checks use actual saved 011 runs; offline A/B/D integration validates wiring.
No paid calls. Git history records the associated main delivery; unrelated changes remain unstaged.
