# Jev 011 Classification Benchmark Implementation Plan

> **For agentic workers:** Execute inline with test-driven development. User approved an isolated multi-label benchmark, not a production B3 replacement.

**Goal:** Compare jev-1.13 passage classifications with the six completed 011 configurations using identical offline scoring.

**Architecture:** An experimental System One client accepts source state and independently defined topic questions. It reuses project settings, sanitization, telemetry and cost estimation, but never pretends to generate B3 passage groups. A separate offline scorer alone reads the frozen reference after inference completes.

**Tech Stack:** Python 3.11, existing uv virtual environment, urllib, pytest, project tracing.

## Global constraints

- Keep canonical A/B1, production B3, existing results and human decisions unchanged.
- Model input: frozen source and B3 source context, provisional B2 proposals, approved taxonomy definitions; no human labels.
- Pin jev-1.13; no reasoning tier or model substitution. Record returned version IDs explicitly.
- Independent noul question per topic; yes probability >= 0.5; propagate approved subtopics to parents, matching existing B3 normalization.
- Record raw probabilities, usage, latency, dated public gateway cost estimates and every failed attempt. Unknown cost stays unknown.
- Five concurrent requests, at most two attempts per passage per invocation; hash-keyed checkpoints, process lock, completion only after every source passage.
- No commit/push or unrelated changes.

## Completion — 2026-10-02

All three tasks completed. Ten experimental tests pass; the combined experimental,
transport and B3 suite passes 80 tests; the full suite passes 264 tests. Jev completed 264/264 paid decisions with
zero failed requests. Its offline F1 is 0.68817 and cost estimate USD 0.070463526.
Saved reference labels match both redundant backups byte-for-byte. The original
six-model ranking remains unchanged; comparison lives in `ranking-with-jev.json`.
Initial trace kwargs were omitted by the runner, so original per-call metadata
was consolidated and source requests reconstructed without further paid calls.
Full first-run HTTP envelopes were not debug-captured; probabilities, usage,
cost, latency and response IDs are retained, with this limitation disclosed.

## Task 1: Experimental request and answer contract

Files: `evaluations/jev_benchmark.py`, `tests/test_jev_benchmark.py`.

- [x] Write and run failing tests for target-specific question wording, multi-label thresholding, parent normalization, missing/extra answers and invalid probabilities.
- [x] Implement `make_payload(target, packet)` and `decode_answers(raw, payload)` using the shared topic definitions.
- [x] Test injected HTTP transport, model checking, telemetry and no credential persistence.
- [x] Implement `SystemOneClient.evaluate(payload, debug, run_id, trace_root)` with the configured OpenCode key and explicit application User-Agent.
- [x] Run `uv --cache-dir /private/tmp/uv-credit-agreement run --no-sync pytest tests/test_jev_benchmark.py -q`.

## Task 2: Frozen source runner and paid-call preservation

Files: `tmp/runs/benchmark_011_jev.py`, `evaluations/pricing/opencode-public-2026-10-02-jev.json`.

- [x] Verify frozen chunk hash against the original experiment manifest.
- [x] Build source-only packets via `build_passage_packets()`; target each of the 264 canonical leaves, including tables and headings. Supply full owning core chunk and its existing bounded boundary context.
- [x] Tiny greeting preflight before sending any agreement evidence; retain separately and exclude from document cost.
- [x] Persist request/response snapshots and telemetry; validate and checkpoint by complete request hash. Resume validated checkpoints without calling the provider again.
- [x] Persist source-order `document.item-topics.json`, then finalize status.

## Task 3: Offline comparison and documentation

File: `tmp/runs/score_011_jev.py`.

- [x] Read only completed predictions, then the frozen evaluation reference. Reuse existing `measure()` without invoking any provider code.
- [x] Save Jev disagreements and a new seven-model ranking; preserve the original six-model ranking.
- [x] Compare frozen reference and redundant backup byte hashes; verify the current human decisions remain unchanged.
- [x] Report metrics, complete/unknown cost and experiment comparability limitations; update backlog/pipeline notes without depicting Jev as a production component.
