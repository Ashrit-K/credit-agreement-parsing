# Stage D Extraction Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans and test-driven-development. Execute inline on main as requested; use an independent reviewer before delivery. Steps use checkbox syntax.

**Goal:** Return cited, validated parties, facility amounts and interest from a completed topic map through one public orchestrator.

**Architecture:** Fixed Python orchestration coordinates one specialist with a B4/B5 retrieval tool and shared C transport. A composed runner hands off directly after B3; validation and arithmetic are independently testable. Preserve old APIs and saved runs.

**Tech Stack:** Existing Python 3.11, uv, Pydantic v2, Decimal and local JSONL tracing; no new dependencies.

## Global Constraints

- Source corpus, canonical Docling JSON and human labels are immutable.
- No ground-truth reads, external rates, source summaries or silent substitutions.
- Build on main; do not stage unrelated working changes.
- Every public API accepts debug/run_id/trace_root; basic traces always persist.
- Full design: [Stage D design](../specs/2026-10-03-stage-d-extraction-design.md).

## File boundaries

- `extraction_models.py`: strict result schemas, entity/citation validation and rate calculation.
- `extraction_specialist.py`: topic tool, simple extraction prompt/schema, bounded model attempts.
- `orchestrator.py`: sole D entry point, readiness, validation, atomic result/manifest completion.
- `runner.py`: composed A/B/D handoff, no changes to standalone B3 behavior.
- `tests/test_extraction_models.py`, `tests/test_orchestrator.py`, `tests/test_runner.py`: pure and fake-client checks.
- `__init__.py`: public orchestrator/runner exports; retain scaffold exports.

## Task 1: Strict domain contract and deterministic validation

- [x] Write tests for agreed JSON shape; parent without role; decimal numeric rates;
  supported/missing/uncertain/not-applicable values; bogus citations; duplicate and
  cyclic identities; nonexistent references; boolean/string/nonfinite numbers.
- [x] Run red: `UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest tests/test_extraction_models.py -q`.
- [x] Implement `CreditTerms.model_validate(payload)`,
  `validate_extraction(payload: dict, allowed_ids: set[str]) -> dict` and
  `calculate_total_rate(calculation: RateCalculation) -> float | None`.
  Strict model config is `ConfigDict(extra="forbid", strict=True)`.
  Calculation uses Decimal inputs, never `eval`:
  `float(max(Decimal(str(base)), Decimal(str(floor or 0))) + Decimal(str(margin)))`.
- [x] Verify a base of 0.035, floor 0.01 and margin 0.04 produces 0.075;
  missing base never produces a fabricated numeric total.
- [x] Run green focused tests; inspect comments and schema semantics.

## Task 2: Specialist, orchestrator and durable traces

Interfaces:
`extract_credit_terms(topic_map, chunks, *, conversion=None, client=None,
model=None, reasoning_effort="medium", api_style=None, output_root="tmp/stage_d",
debug=False, run_id=None, trace_root="tmp/runs") -> dict`.
Specialist receives a retrieval callback, obtains a validated packet, sends
`client.complete(system, {"evidence": packet, "output_schema": CreditTerms.model_json_schema()}, ...)`.
Validate visible response with `json.loads(response.text)` and then the pure validator.

- [x] Write red fake-client tests: one combined request; evidence text reaches
  the model; schema attached; model/effort forwarded; invalid JSON/citations
  bounded to two attempts; retryable LlmError retries; auth stops; different
  returned model fails; empty topics make no paid call.
- [x] Test hash mismatch fails before calling client; missing canonical table
  data fails; both A10 modes work; debug/basic traces and failed attempts persist.
- [x] Implement D1 coordination, D2 specialist, D3 validation and D4 persistence.
  Retrieve via existing `retrieve_evidence`; derive citation allowlist from
  its original evidence/context records. Inject fake `complete` clients using
  the real `LlmResponse` boundary, without monkeypatching domain validation.
- [x] Use a UUID execution folder so repeated run IDs never overwrite results.
  `atomic_json(result_path, result)` then `atomic_json(manifest_path, manifest)`.
  Snapshot both paths; do not return completed output on any failure.
- [x] Run focused tests and full suite; address regressions before integration.

## Task 3: Explicit B3 completion handoff

- [x] Write red runner tests using module-boundary fakes for A/B/C only.
  Assert call order A/B1/B2/B3/D, same run ID, model overrides independent,
  hierarchy forwarded, B3 failure never triggers D.
- [x] Implement `run_pipeline` exactly as specified; emit `topic_map_ready`
  after successful B3 return and call only public D orchestrator. Add exports.
- [x] Verify standalone `build_topic_map` has no new model behavior and existing
  `extract_parties` tests remain unchanged.

## Task 4: Saved 011, review, documentation and delivery

- [x] Verify only source artifacts are selected from saved 011. Use existing
  source-bound map and canonical conversion; rebuild B3 offline if binding absent.
  Do not rerun paid B2 or read offline scoring/human reference files.
- [x] Execute one debug extraction, capture real model/effort/cost/latency and
  retained final JSON location. Report any unknown cost or validation failure.
- [x] Dispatch read-only independent code review using this plan and focused
  files. Fix important findings using failing regression tests first.
- [x] Update README examples, AGENTS snapshot, backlog D1–D4 status, pipeline
  solid/dashed boxes and purple LLM logic, and plan checkboxes from actual evidence.
- [x] Update existing Obsidian project/daily notes from Ashrit's perspective.
- [x] Run full tests and `git diff --check`; scan staged files for exact local
  secret values and prohibited paths without printing credentials.
- [x] Verify scoped staged snapshot tests, commit on main and push origin/main;
  verify remote SHA matches. Preserve unrelated edits and all historical runs.

## Execution evidence — 2026-10-04

Baseline 318 tests; final full local suite 372, including 54 new focused tests.
The exact scoped Git-index snapshot passes 352 tests; the 20-test difference
is unrelated working-tree evaluation/annotation work excluded from this commit.
All 14 staged files pass the local-secret/prohibited-path scan and whitespace check.
Feature commit `0b64eeb` was pushed to `origin/main`; the local and remote-tracking
SHAs matched after the successful push. Unrelated working changes remain unstaged.
Independent review's five validation/telemetry findings each have red/green
regressions. Additional live-discovered role casing and rate-period/fee distinctions
are tested. B4/B5 source bindings, canonical table data and both A10 modes pass.
Two source-only 011 live checks used four total GPT-5.6 Luna/medium requests,
estimated combined $0.0547862. Initial output completed; revised responses failed
on capitalized role labels before normalization. The second revised actual saved
response was revalidated offline afterward against identical system/schema/evidence,
without a new provider request. Final six entities/one facility/three interest-fee
entries and explicit replay provenance are retained separately. Human labels and
original source artifacts were not modified/read as extraction inputs.
