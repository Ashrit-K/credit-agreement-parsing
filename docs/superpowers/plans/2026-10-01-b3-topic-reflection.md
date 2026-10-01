# B3/B4 Topic Reflection and Map Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task with test-first checks. Build on main as requested; do not modify the corpus.

**Goal:** Refine B2's provisional topic labels against original B1 evidence,
with observable LLM usage and costs.

**Status:** Implemented and verified. Python 3.11 with uv.
Phoenix is deferred. Local telemetry/debug capture replaces it for this build.

## Agreed B3 scope

- Review every B1 chunk, including chunks with no B2 labels.
- Use the existing eight-topic taxonomy and PIK/call-protection subtopics.
- Supply original item text and IDs, available heading context, and B2's
  proposed labels. Keep hashes, rule versions, and verbose rule-match signals
  out of the LLM-facing evidence packet.
- Allow the model to retain, remove, or add topics and cite supporting item IDs.
- Use small batches: up to five chunks per call, subject to an input-size cap.
- Keep each chunk's classification separate; do not summarize away evidence.
- Use the shared Stage C transport, not provider-specific calls embedded in B3.

## Deferred observability: Phoenix

Phoenix is NOT a dependency of this build. Its future requirements below remain
reference material. This build persists local JSONL telemetry and opt-in detailed
debug artifacts, without an observability service. Stage C records individual
calls; all public pipeline APIs record stage inputs/outputs when debug is enabled.

### Trace structure

- One root trace per document run, with a distinct run ID for repeated runs.
- Child spans for B3 batches, each LLM attempt (including retries), and response
  validation. Record final batch failure as well as individual attempt failures.
- Attach document fingerprint, stage ID, batch/chunk IDs, model, API style,
  prompt version, start/end times, duration, status, and sanitized error type.
- Record provider-returned input/output tokens and cached/reasoning token
  details when available. Do not double-count reasoning tokens already included
  in output totals. Missing usage remains unknown.

### Cost accounting

- Prefer provider-reported cost when available; otherwise calculate an estimate
  from a versioned, dated OpenCode pricing configuration for the selected model.
- Do not assume OpenCode prices equal a model vendor's direct API prices.
- Distinguish reported, estimated, and unknown cost; record currency and pricing
  source/version. Never represent unavailable cost as zero.
- Attribute usage/cost to each attempt when returned, including failed attempts
  and retries. Do not invent usage for failures without provider usage data.
- Support inspection/aggregation by document run, stage, and model: request and
  retry counts, tokens, known cost, unknown-cost calls, failures, and latency.
  Do not label the sum of known costs as a complete bill if costs are missing.

### Operational boundaries

- Phoenix is optional and enabled through configuration. No connection or
  exporter failure may fail classification or trigger another paid LLM call.
- Bound export overhead; provide a shutdown/flush path for short Python runs.
- Preserve telemetry across local Phoenix restarts using persistent storage.
- Never emit API keys, authorization headers, or secrets. Full prompts/source
  text are excluded by default; content capture requires explicit opt-in.
- Cost observability is not a spending limit. Budget enforcement is a separate
  design decision, not implicitly included in this work.

### Required verification before marking observability implemented

- [ ] Fake transport tests verify a batch with a retry creates distinct attempt
  spans and keeps document/batch/model/prompt context consistent.
- [ ] Known-usage fixtures verify token accounting and reported versus estimated
  costs; missing usage/pricing remains unknown.
- [ ] Secret-redaction tests inspect exported attributes and sanitized errors.
- [ ] Disabled/unreachable Phoenix tests confirm identical classification
  results and no extra LLM requests.
- [ ] Local Phoenix smoke test confirms trace nesting, persistence, token/latency
  visibility, and inspectable cost attributes without requiring a paid model.
- [ ] A separately authorized live document trial records actual provider usage
  and clearly states whether costs are reported, estimated, or unavailable.
- [ ] Update the authoritative diagram and backlog only after acceptance passes.

## Frozen implementation defaults

- B3 default: `gpt-5.6-luna`, high reasoning; shared transport default: medium.
- Explicit Responses/Chat Completions routing; no Claude adapter or silent substitution.
- Batch limit: five chunks and 24,000 serialized evidence characters. Atomic
  oversized chunks run alone without truncation. Output allowance: 8,192 tokens.
- One final topic list per chunk, no possible-topic bucket or confidence scores.
  Known taxonomy only; each topic has nonempty cited item IDs from the supplied
  chunk/heading context. Parent labels added for approved subtopics.
- Require exact batch coverage. At most two attempts; retry transient transport
  errors and invalid JSON/schema, never auth/permission errors.
- Validated batch checkpoints keyed by input hashes, model/API/reasoning,
  prompt/schema version and batching settings. `force=True` bypasses reuse.
- B3 output: `document.topic-classifications.json`; B4 output:
  `document.topic-map.json`, beside B1. Incomplete B3 runs never finalize.
- B4 indexes approved topics -> chunk/item IDs in source order, with an explicit
  unclassified-chunk list. No summaries, LLM calls, B5/B6 retrieval, or corpus edits.
- Public pipeline/file APIs accept `debug=False`, `run_id=None`,
  `trace_root='tmp/runs'`. Shared run IDs link separately called stages.
  Basic status/timing and LLM usage/cost always persist; debug adds intermediate
  inputs/outputs and requests/responses. Never log credentials or hidden reasoning.
- Unknown costs stay unknown unless returned by provider or calculated from
  explicit dated model rates. Cached/reasoning tokens must not be double-counted.

## Execution tasks

### Task 1: Local traces and public hooks

Files: new `tracing.py`, `tests/test_tracing.py`; wrappers in `api.py`,
`conversion.py`, `chunking.py`, `topic_signals.py`.

- [x] Write failing tests for basic events, debug files, linked runs, error
  capture, redaction, and keyword-compatible public APIs.
- [x] Implement context-local JSONL stage events and uniquely named debug JSON
  snapshots, keeping existing return values unchanged.
- [x] Run focused tests and existing wrapper regression tests.

### Task 2: Shared Stage C

Files: new `llm.py`, `tests/test_llm.py`.

- [x] Write failing fake-HTTP tests for routing/defaults/overrides, User-Agent,
  usage normalization, costs, and transient/permanent error distinction.
- [x] Implement `OpenCodeClient.complete(system, evidence, *, model,
  reasoning_effort, api_style)` returning normalized text/usage/metadata.
- [x] Verify Responses and Chat payloads without credentials/network.

### Task 3: B3 reflection

Files: new `topic_reflection.py`, `tests/test_topic_reflection.py`.

- [x] Write failing tests for batch limits, original/table evidence, exact chunk
  coverage, taxonomy/citation validation, parent normalization, retry bounds,
  checkpoint resume and settings/input invalidation.
- [x] Implement `reflect_topics(chunks, signals, *, client=None, model=...
  reasoning_effort='high', api_style=None, force=False, debug=False, ...)` with
  validated atomic checkpoints and final JSON artifact.
- [x] Verify failure/resume preserves successful calls and input bytes.

### Task 4: B4 map

Files: new `topic_map.py`, `tests/test_topic_map.py`; package exports.

- [x] Write failing tests for exact source-order indexes, unmatched chunks,
  stale identities/input hashes, malformed B3 outputs and deterministic results.
- [x] Implement pure `build_topic_map_document()` plus public
  `build_topic_map(chunks, classifications, *, debug=False, ...)` persistence.
- [x] Run fake end-to-end B1/B2/B3/B4 checks without an LLM.

### Task 5: Acceptance and docs

- [x] Run `UV_CACHE_DIR=.uv-cache uv run --frozen pytest -q` and `git diff --check`.
- [x] Run one tiny synthetic Luna/high B3/B4 smoke test with debug capture,
  recording usage and latency. No corpus sweep or classification accuracy claim.
- [x] Update backlog, README, AGENTS, solid/purple diagram, and project note.
  Keep Phoenix, B5/B6, and extraction sleeves pending.

No commit/push is included in this request. Keep changes available for review.

## Completion evidence

142 tests passed. A live synthetic Luna/high run returned the requested model
and high reasoning: 423 input/110 output tokens, 3.16 seconds, one request,
correct source-linked interest/maturity labels and a completed B4 map.
No corpus accuracy claim or live open-model trial is implied. Debug files,
checkpoint artifacts, and a local usage summary remain under ignored `tmp/`.
Review findings on malformed response normalization, trace context cleanup,
model substitutions, and analytics were addressed with regression tests.

## Reference

- Phoenix: https://github.com/Arize-ai/phoenix
- Local storage: https://arize.com/docs/phoenix/self-hosting/deployment

## Approved prompt refinement — 2026-10-01

Replace the v1 instructions with the user-approved simpler evidence-oriented
prompt and explicit topic meanings. Maintain definitions in `topic_taxonomy.py`,
not a second embedded copy in the system prompt. Keep topic IDs, B2 rules,
output schema, model settings, and deterministic B4 indexing unchanged.

- [x] Add regression checks proving each approved topic definition reaches the
  injected LLM client and definition edits invalidate checkpoint reuse.
- [x] Observe the new checks fail before implementation.
- [x] Add shared `credit-topic-definitions-v1` meanings and `b3-reflection-v2`.
  Snapshot definitions into each request and hash them into the B3 profile.
- [x] Verify B2/B3/B4 regression tests and update architecture/backlog/API docs.

Do not rerun a paid document classification or rewrite saved v1 artifacts as
part of this change. Prompt quality remains unmeasured until a fresh evaluation.
The completed refinement passes all 156 project tests, including checks for
definition delivery and definition-sensitive checkpoint invalidation.
