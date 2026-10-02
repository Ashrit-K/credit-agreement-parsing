# Stage B Simplification Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development with scoped file ownership; run tests before implementing each behavior and review the integrated result. User approved scope and implementation on main, followed by a safe commit and push.

**Goal:** Default A10 on, remove heuristic classification, and renumber Stage B without corrupting historical saved runs.

**Architecture:** New layout `stage-b-v2` is B1 chunks → B2 LLM passage classification → B3 topic-map construction → pending B4 evidence retrieval → pending B5 evidence packaging. Keep existing `reflect_topics` and `build_topic_map` function names and passage schema-v2 roles. Profiles and outputs identify the layout; historical unmarked runs retain their old B2 heuristics/B3 classification/B4 map numbering in the reviewer.

**Tech Stack:** Python 3.11, uv, pytest, existing JSONL/debug persistence and self-contained HTML reviewer; no new dependencies.

## Global Constraints

- Stay on main and preserve unrelated working changes. Do not stage all files blindly.
- Preserve immutable raw sources, human ground truth and historical artifacts. No paid model run is necessary.
- A10 defaults enabled; retain explicit `use_hierarchy=False` for later ablations and separate caches.
- Fully remove `classify_chunks`, `TopicSignalsArtifact`, heuristic matching/rule implementation and the `use_b2`/signals inputs from current APIs. Preserve shared input validation outside the deleted heuristic module.
- Keep topic IDs/definitions, model/reasoning defaults, citation roles, concurrency, retries and debug redaction unchanged.
- New layout must be explicit in profiles/results and checkpoint identity; do not relabel historical saved logs or reuse old classification checkpoints silently.
- New classifications, maps and checkpoints live under B1's `stage-b-v2/` subdirectory, preserving old latest-artifact files as well as saved run logs. Original filenames stay unchanged.
- Historical review may interpret already-saved heuristic JSON but must not execute heuristic code.
- Update backlog and authoritative diagram, project instructions, README and Obsidian checkpoint. Historical plans/evaluation reports remain history, clearly identified where necessary.
- Commit only verified scoped code/docs and required dependencies after a staged-content secret scan. Never stage `.env`, keys, authorization headers, human decisions or debug model traces.

## Task 1 — Current pipeline and tests

Files: `conversion.py`, `topic_reflection.py`, `topic_map.py`, `topic_passages.py`, `topic_taxonomy.py`, `__init__.py`; new `chunk_validation.py`; affected A10/reflection/map/annotation/tracing tests and shared test fixture.

Interfaces:

```python
convert_document(path, *, use_hierarchy=True, ...)
reflect_topics(chunks, *, client=None, model='gpt-5.6-luna', reasoning_effort='high', ...)
build_topic_map(chunks, classifications, ...)
```

- [x] Write and run failing tests proving default A10 enabled, heuristic public API absent, classification needs only chunks, and new trace/profile layout.
- [x] Move lossless B1 document validation to `chunk_validation.py` without importing heuristic code; reject human-label files at the classification boundary.
- [x] Remove heuristic source module and obsolete heuristic-only tests, moving reusable tiny B1 fixtures to a neutral helper. Delete phrase/context matching rules while preserving topic definitions and approved IDs.
- [x] Remove signals/use_b2 arguments, proposed-label prompt guidance and packet payload fields. Build packets from source only; preserve legacy packet revalidation where required to consume historical classification objects without executing rules.
- [x] Emit `pipeline_layout='stage-b-v2'`, B2 classification traces and `stage-b-v2/b2-checkpoints` under a distinct profile. Write new classification/map files under that layout directory and assert older parent files remain byte-identical. Emit B3 map traces/results. Historical unmarked classification objects remain readable by pure map validation, not relabeled.
- [x] Update affected tests/callers to chunks-only classification. Keep all concurrency/retry/citation/heading-ablation tests. Ensure evaluation utilities still run against saved inputs without human-label leakage.
- [x] Run `UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest tests/test_topic_reflection.py tests/test_topic_passages.py tests/test_topic_map.py tests/test_optional_hierarchy.py tests/test_annotation.py tests/test_tracing.py tests/test_conversion.py -q`.

## Task 2 — Historical/current review layouts

Files: `review.py`, `review.html`, `tests/test_review.py`.

- [x] Add failing fixtures for marked current B1/B2/B3 runs, historical heuristic runs, and unmarked historical B2-skipped runs. Assert historical traces are not reinterpreted by new numbering.
- [x] Detect layout from explicit classification profile/result metadata, not by assuming B2 means classification. Select stage snapshot prefixes, model exchanges and displayed labels by layout.
- [x] Current review shows B1 chunks, B2 classification and B3 map; pending B4/B5. No heuristic controls or stale suggestions appear in current review. Historical views retain their original labels and saved rule evidence.
- [x] Pair both layouts' concurrent exchanges by attempt ID, never adjacency; preserve sanitized snapshots and original source joins. A10 disabled runs still render available artifacts only.
- [x] Run `uv run --no-sync python -m pytest tests/test_review.py -q`; inspect generated current and legacy HTML/JavaScript using existing local browser tooling if available, with disposable fixtures only.

## Task 3 — Documentation and delivery

Files: `AGENTS.md`, `README.md`, `docs/conversion_pipeline.md`, `docs/build_backlog.md`, this plan and Obsidian project/daily notes.

- [x] Add registry entry In progress, then Implemented only when acceptance passes. Replace current architecture with numbered new layout and remove heuristic bypass/box; use solid implemented arrows and purple classification box, dashed pending retrieval/package stages; keep C isolated.
- [x] Document A10-on default, chunks-only API, new IDs and explicit historical mapping; reported 011 evals motivate choice but do not prove universal improvement.
- [x] Run full `uv run --no-sync python -m pytest -q`, `git diff --check`, independent scoped review and a tiny offline through-map test. Record actual test counts; no paid calls.
- [x] Update Obsidian project/daily checkpoint without modifying labels or linked historical findings.
- [x] Resolve commit scope from `git status` and dependencies; scan staged blobs for secrets, generated traces and prohibited labels. Inspect tracked `.env`/ignored files and diff stat. Commit on main with a concise conventional message, then `git push origin main` and verify local/remote commit identity. Report any preexisting changes intentionally left unstaged.

## Acceptance

Implementation verified on main, 2026-10-02: 271 delivery-scope tests passed
(`--ignore=tests/test_jev_benchmark.py`); full local workspace 281 passed.
39 reviewer tests include completed/failed standalone map telemetry. Independent
review finding fixed and re-reviewed with no unresolved defects. JavaScript
syntax and disposable DOM execution passed; real-browser local-file navigation
was rejected, so visual inspection remains unverified. No paid calls or source/
human-label mutation. Implementation committed on main as `6c70420`; push to
origin/main succeeded and `git ls-remote` verified the full matching commit.
42 staged nondeleted files were scanned against configured credential values,
key patterns and excluded data paths with no findings. Credentials, ground
truth, generated runs, corpus staging and standalone experimental files were
not staged. This final documentation checkpoint records that delivery.

Default conversion produces A10 hierarchy. Current public API cannot enable heuristics and classification works directly from B1 through the topic map. New traces are B2/B3 with explicit layout identity; old files are readable under their original B3/B4 meanings. Model outputs and evidence/context validation remain unchanged. All affected tests and full suite pass, docs reflect current layout, and only secret-screened reviewed changes are committed/pushed.
