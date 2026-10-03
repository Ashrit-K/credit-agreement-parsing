# B4/B5 Evidence Retrieval Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task. The user approved immediate execution on main after writing this plan.

**Goal:** Let downstream extraction request approved topics and receive complete original evidence with verified source references.

**Architecture:** B4 deterministically selects every mapped group for explicit taxonomy IDs. B5 resolves those groups into original text, separate context, pages and heading paths. `retrieve_evidence()` runs both and persists a request-specific packet; downstream agents own broad-topic resolution. No extra LLM, ranking, filtering, summarization or UI build.

**Tech Stack:** Existing Python 3.11/uv environment, standard library, current tracing and atomic JSON persistence.

## Global constraints

- Stay on main; preserve unrelated working changes, sources, historical runs and human labels.
- Taxonomy IDs only, including approved subtopics. Unknown/empty requests fail; duplicates normalize in taxonomy order.
- Preserve evidence/context roles and exact groups. Unmatched requested topics return empty groups, never invented facts.
- B4 requires completed schema-v2 maps with matching taxonomy/source and B1 semantic fingerprint. Old maps missing the fingerprint must be rebuilt with B3, without model calls; schema-v1 roles are not reinterpreted.
- Resolve every selected item; reject stale chunks, broken references, altered group identity/provenance and missing source text. A10-off/page-less artifacts remain usable.
- Tables with no item text require the matching Stage A artifact and canonical-JSON hash recorded by B1. Render canonical grids using existing B1 rendering, never infer cells from a joined page. This is B5 resolution only; deferred shared B2/reviewer resolver stays deferred.
- Debug/basic telemetry follows existing public API conventions. Persist request-hash-specific outputs, not one overwritable global bundle. No ground-truth reads.
- Simplify current Stage D to an abstract pending downstream extraction component; historical plans remain unchanged.

## Task 1 — B4 validated topic retrieval

**Files:** `retrieval.py`, `topic_map.py`, `tests/test_retrieval.py`.

**Interfaces:** `select_topic_groups(document, topic_map, *, topics) -> dict`; add deterministic `chunks_document_sha256` to newly built schema-v2 maps.

- [x] Write tests for approved IDs, multiple topics, empty results, source order, immutable input, schema/taxonomy/source/hash mismatch and corrupt group references/metadata.
- [x] Run `UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest tests/test_retrieval.py -q`; confirm missing API failure.
- [x] Implement B4 selection and map fingerprint. Validate groups by recomputing canonical identity, source owners/pages and ordering; compare, do not trust saved metadata.
- [x] Re-run focused tests and existing map/passages tests.

```python
selection = select_topic_groups(chunks_document, map_document,
                               topics=["parties_and_roles", "interest_and_fees"])
assert selection["requested_topics"] == ["parties_and_roles", "interest_and_fees"]
```

## Task 2 — B5 evidence packet and public composition

**Files:** `evidence.py`, package `__init__.py`, `tests/test_retrieval.py`.

**Interfaces:** `package_topic_evidence(document, selection, *, canonical_document=None) -> dict`; `retrieve_evidence(topic_map, chunks, *, topics, conversion=None, debug=False, run_id=None, trace_root="tmp/runs") -> EvidenceArtifact`.

- [x] Add failing tests for original wording, context separation, cross-page groups, headings, tables, canonical hash mismatch, no truncation, independent request outputs, B4/B5 spans and debug artifacts.
- [x] Run focused tests and confirm failure before implementation.
- [x] Implement packaging with source-item records containing IDs, original text, pages, headings and containers. Table cells remain canonical; do not invoke conversion or a model.
- [x] Compose traced B4/B5 wrappers under one public entry point; atomically save `evidence/<request-hash>/document.evidence.json` adjacent to the map. Return identity/path/request topics; no cache shortcut initially.
- [x] Re-run focused and complete tests. Smoke-test saved 011 artifacts without paid calls or human-label reads.

```python
packet = retrieve_evidence(topic_map, chunks, topics=["parties_and_roles"],
                           conversion=conversion, debug=True)
print(packet.evidence_json_path)
```

## Task 3 — Documentation, review and delivery

**Files:** README, AGENTS, backlog, authoritative pipeline diagram, Obsidian project/daily notes.

- [x] Mark B4/B5 in progress before coding; after acceptance make boxes/arrows solid. Keep abstract D pending and purple; downstream agent chooses taxonomy IDs.
- [x] Document interfaces, packet contract, stale-map rebuild and table dependency. Existing visual reviewer remains unchanged; packet is suitable for a later topic explorer, not a claim of UI implementation.
- [x] Update Obsidian in Ashrit's voice and daily 2026-10-03; preserve existing notes.
- [x] Review diff, run full suite and `git diff --check`; inspect staged files for secrets/generated/human-label data and exclude unrelated changes.
- [ ] Commit scoped changes and push main; verify remote commit. Mark goal complete only after delivery, report actual checks and limits.

## Verification recorded before delivery

- Exact staged snapshot: 298 tests passed. Full working-tree suite: 318 passed,
  including unrelated annotation/default-model/experimental changes not staged.
- Independent review: 68 focused tests; group-order finding reproduced red,
  corrected and re-reviewed with no remaining important issues.
- Saved 011 source-only smoke: 27 groups, 85 evidence records; no model calls,
  original chunks/classifications unchanged. Generated packet/debug data ignored.
- Eleven scoped staged files scanned against local credential values, private-key
  markers and prohibited data paths: no findings. Diff whitespace checks pass.
- Obsidian project and 2026-10-03 daily updated; HTML reviewer unchanged.
