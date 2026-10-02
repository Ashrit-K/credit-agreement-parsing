# B3 concurrency implementation plan

**Goal:** Run independent B3 batches concurrently, with a configurable positive
integer `max_concurrency` defaulting to 5, and retain the existing evidence,
model settings, validation and checkpoint contracts.

**Architecture:** A bounded thread pool schedules at most `max_concurrency`
batches. Each worker receives a separate copied tracing context and owns its
batch's two-attempt validation/checkpoint lifecycle. The coordinator assembles
results in source order and writes the final artifact only after all batches
validate. On failure, stop scheduling; already running successful calls may
finish and checkpoint. Concurrency is excluded from checkpoint identity.

**Tech stack:** Python 3.11, standard-library concurrent.futures/contextvars,
existing uv-managed `.venv`, pytest, fake clients only.

- [x] Write deterministic barrier/event-based tests for overlapping bounded
  calls, source-order output, default concurrency, invalid limits, sequential
  equivalence, failure/resume, cancellation of unstarted batches, two attempts,
  and B3/C trace ancestry plus unique debug snapshots.
- [x] Observe failures with
  `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest tests/test_topic_reflection.py -q`.
- [x] Implement scheduling in `topic_reflection.py` and synchronize JSONL event
  writes in `tracing.py`, preserving v2 prompt, schema and model overrides.
- [x] Run focused tests, then
  `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest -q`.
- [x] Update README, AGENTS.md, backlog and pipeline explanatory text with
  verified behavior. Preserve component IDs, diagram status and corpus files.

The approved design is implemented in the existing checkout without commit,
push, live model calls, additional worktrees, or changes to B5/B6/review layout.
The saved reviewer received compatibility fixes for interleaved model exchanges:
B3 pairs by attempt ID and C by span ID, with legacy-log support.

Verification: initial focused red run had 14 failures and 19 passes; focused
reflection/tracing checks passed 42 tests after the C snapshot metadata fix.
The integrated full suite passed 175 tests after concurrent-review pairing
changes. Independent review found no remaining important issues; reviewer
JavaScript syntax passed `node --check`. `git diff --check`
passed. The sequential legacy fake explicitly uses `max_concurrency=1`; the
new failure/resume test exercises concurrent in-flight success and failure.
