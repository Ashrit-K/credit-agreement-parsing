# Stage B core implementation report

Task 1 implemented on the shared main checkout, preserving existing work.

- A10 now defaults enabled; explicit disabled mode and separated Stage A/B1 caches remain supported.
- Removed `topic_signals.py`, heuristic public exports, phrase/context rules, signals inputs, `use_b2`, proposed-label prompt guidance, and current packet proposal fields. Shared topic IDs, definitions, parent topics, model/reasoning defaults and citation roles remain intact.
- Moved lossless B1 validation to `chunk_validation.py` and reusable tiny B1 fixtures to `tests/chunk_fixtures.py`. Annotation inputs fail before any model call, including annotation fields attached to otherwise valid B1 JSON.
- Current classification emits B2 traces with prompt `b2-passage-classification-v1`; map construction emits B3 traces. `stage-b-v2` appears in classification profile/result, map result, and basic telemetry even when classification fails before completion. Removed obsolete telemetry bypass logic.
- Current classification/map filenames stay unchanged within a new `stage-b-v2` directory beside B1; checkpoints use its `b2-checkpoints` directory. Existing historical files remain byte-for-byte intact. Layout/prompt/packet identity prevents old checkpoint reuse.
- Pure map validation keeps schema-v1 citations and unmarked schema-v2 saved proposals readable. Historical proposal fields are reconstructed only for packet hash validation; no heuristic implementation runs and historical results are not relabeled.
- Migrated classification/map/annotation/tracing/heading-ablation tests to chunks-only calls while retaining concurrency, retry, citation, definition hash and ablation coverage. No evaluation Python caller required migration. No corpus, human decisions, reports, provider requests or network calls were used.

Red-first evidence: initial contract tests failed 3/3 for A10 default, heuristic exports and signals arguments; historical-file isolation tests failed 2/2 before directory isolation; failed-basic-run telemetry test failed before layout events; annotated-valid-B1 input test failed before rejection. Each subsequently passed.

Validation:

```text
UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest tests/test_topic_reflection.py tests/test_topic_passages.py tests/test_topic_map.py tests/test_optional_hierarchy.py tests/test_annotation.py tests/test_tracing.py tests/test_conversion.py -q
137 passed in 3.28s

UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest tests/test_stage_b_simplification.py -q
7 passed in 0.10s

UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest -q
277 passed in 3.59s

git diff --check
clean
```

Scope note: reviewer and documentation changes are owned by other agents; this report's full-suite run includes their shared-tree changes. Existing ignored `tmp/scripts/check_passage_review.py` still references historical heuristics and was intentionally untouched. No staging, commit or push was performed by this worker.
