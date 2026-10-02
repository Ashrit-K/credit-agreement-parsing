# B3/B4 Passage-Level Topic Evidence Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task. Use superpowers:subagent-driven-development only with explicit authorization. Steps use checkboxes for tracking.

**Goal:** Make the topic map index coherent original passages, separating direct topic evidence from the supporting context needed to interpret it.

**Architecture:** Keep B1 as the unchanged page-first packaging layer and B2 as the provisional topic proposer. In the existing B3 call, classify topic-specific groups of canonical source items; B4 validates and indexes these groups deterministically. The saved reviewer resolves both kinds of items to original text, pages, tables and heading paths.

**Tech Stack:** Python 3.11, uv, existing Pydantic validation, shared Stage C client, pytest and the existing self-contained HTML reviewer. No new dependencies or extra LLM pass.

## Global Constraints

- Status: **Implemented**. Implementation authorized by the user on 2026-10-01; paid calls remain unauthorized. See acceptance evidence below and the user-deferred table-resolver scope.
- Stay on `main` when implementation is authorized; preserve uncommitted concurrency work and unrelated staging documents. Do not commit/push without authorization.
- B1, Stage A canonical artifacts, and `raw_documents/` remain unchanged.
- Preserve original wording and canonical item IDs; no generated summaries, invented sentences, table-cell IDs or page numbers.
- Preserve the approved taxonomy, subtopic parents, model overrides and default model/reasoning settings. Do not introduce scores, a verifier or a second LLM layer.
- Preserve `max_concurrency=5`, independent two-attempt retries, validated checkpoints, source-order output, attempt/span identities and secret-safe debug traces.
- Page boundaries organize navigation and batching; they must not force an incomplete evidence passage.
- Item-level precision is the first increment. Sentence spans within a single item, table-row selection, distant definition resolution and extraction sleeves are outside this build.
- Semantic relevance and context sufficiency remain model judgments. Structural validation is not an accuracy guarantee.
- User scope update (2026-10-01): defer the shared paragraph/table source-item
  resolver to its own backlog entry. B1 currently retains table rendering only
  in joined chunk content. Core table text remains supplied through that content;
  a selected neighboring table without item-level text raises a clear error
  before any model request rather than being silently omitted or expanded into
  unrelated whole-chunk text. Precise neighboring-table rendering is not claimed
  implemented in this increment.

## Approved Direction and Initial Scope Choices

The user approved preserving B1 and making B3 produce topic-specific passage groups with separate evidence/context IDs. The following concrete choices make that direction buildable and are proposed for implementation review:

1. Supply the full target chunk, its existing heading paths, and one neighboring atomic B1 group on each side. Expose `boundary_context_groups=1`; permit nonnegative integers, reject booleans. This is a bounded local window, not an attempt to load every cross-reference.
2. A group must contain at least one direct-evidence item belonging to the target chunk. It may also contain direct evidence or context from explicitly supplied neighbors. This permits genuinely cross-page passages without allowing arbitrary citations from other batch chunks.
3. One chunk can have multiple groups for one topic. Different topics may reuse the same source items; evidence/context roles are topic-relative.
4. Write schema-v2 artifacts beside, not over, existing schema-v1 files. Preserve historical exports and checkpoints; never reinterpret v1 citations as evidence/context classifications.
5. Keep model-facing output small: IDs and grouping only. Resolve text, pages, owners and stable group IDs deterministically after validation.

## Output Contract

### Model-facing B3 output

```json
{
  "classifications": [
    {
      "chunk_id": "chunk-000001",
      "topics": [
        {
          "topic": "interest_and_fees",
          "groups": [
            {
              "evidence_item_ids": ["#/texts/102", "#/texts/103"],
              "context_item_ids": ["#/texts/101"]
            }
          ]
        }
      ]
    }
  ]
}
```

Exactly one row per supplied target chunk, including `topics: []` when none apply. Each listed topic has one or more groups; each group has nonempty evidence and an explicit, possibly empty context list. No extra fields.

Direct evidence states the topic's substantive identity, obligation, amount, timing or restriction. Context is necessary to interpret that evidence without independently stating the selected provision. Select the minimum sufficient context, not every nearby item. A definition or heading can be direct evidence for one topic and context for another.

Do not force fragments into individual classifications: a sentence split across items belongs in one group. Separate unrelated passages into different groups. A neighboring substantive continuation belongs in evidence, not context merely because it sits outside the target chunk.

### Persisted B3 artifact

- Schema version: `2`; prompt version: `b3-passage-reflection-v3`.
- Filename: `document.topic-passages.json`.
- Keep source SHA, completed/final status, taxonomy, policy/input hashes and per-chunk classifications.
- Enrich each group with deterministic `group_id` and `source_chunk_ids`. Canonical ordering governs ID lists and groups. Include evidence pages and context pages separately, derived from B1/A10 provenance; missing HTML pages stay empty.
- Keep `TopicClassificationArtifact.classifications_json_path` as the public path field, pointing to this new file. Do not rename public handles unnecessarily.
- Group IDs hash source identity, taxonomy version, topic and ordered evidence/context IDs. Identical groups across overlapping boundary windows share identity; different roles or topic meanings do not.

### Persisted B4 artifact

- Schema version: `2`; filename: `document.topic-passage-map.json`.
- `topics` maps approved topic IDs to passage-group records with `group_id`, ordered `evidence_item_ids`, ordered `context_item_ids`, and `source_chunk_ids`.
- Preserve source chunk order and explicit unclassified target-chunk IDs.
- Deduplicate only exact group identities. Do not merge partial overlaps or choose a preferred legal provision heuristically.
- Every ID remains resolvable to original canonical content. B4 performs no model call, rewriting, relevance ranking or claim that evidence is complete.
- Keep `TopicMapArtifact.topic_map_json_path` as the public result field.

## Input and Validation Rules

- Build a document-wide canonical item lookup, source-order lookup and item-to-chunk ownership from B1. Heading context is already supplied by A10/B1; do not infer a replacement hierarchy.
- Preserve atomic tables and explicit lists when selecting neighbors. For page-less input use reading order, not fabricated pages.
- Each target packet includes `items`, `heading_path`, `neighbor_items`, `proposed_topics` and its explicit allowed-ID scope. A different chunk sharing the batch is **not** automatically allowed evidence.
- Check every ID is canonical and actually present in the target packet's core, heading or neighbor context.
- Require at least one core direct-evidence item for each group. Inherited headings alone cannot establish a topic for an otherwise irrelevant target chunk.
- Reject unknown topics/chunks, missing/duplicate chunk rows, empty evidence/groups, duplicate IDs, evidence/context overlap within one group, extra fields and unsupported schema versions.
- Normalize all IDs to canonical reading order. Reject supplied items absent from the source-order lookup rather than silently dropping them.
- Subtopics induce parent-topic groups without losing evidence/context roles; deduplicate exact groups if the parent was also explicitly supplied.
- An item may support multiple topics or appear in different groups when warranted. Do not enforce one global evidence/context role or discard duplicate source mentions.
- Preserve all B1 chunks, including unmatched B2 chunks and unclassified B3 targets. Passage selection does not remove source content.
- Cache identity includes the v2 schema, v3 prompt, definition hashes, boundary-context profile and complete serialized packet hash, as well as existing inputs/model/batching settings. Concurrency remains excluded.
- No text truncation. An oversized atomic/context packet runs alone under the existing batching behavior; record oversize diagnostics. Distant dependencies remain unresolved, not invented.

## Task 1: Pure Packet and Passage Validation Contracts

**Files:** Create `src/credit_agreement_extractor/topic_passages.py` and `tests/test_topic_passages.py`. Modify B3 imports only after tests pass.

**Interfaces:**

```python
build_passage_packets(document: dict, proposed: dict[str, list[str]], *,
                      boundary_context_groups: int = 1) -> list[dict]
validate_passage_classifications(data: dict, document: dict,
                                packets: list[dict]) -> list[dict]
```

These are pure transformations. Packet construction must expose grouped canonical neighbor items and explicit per-target allowed IDs; validation returns enriched, ordered group records.

- [x] Write fixtures with four canonical items, page provenance, split-sentence neighbors, inherited headings and a table/list atomic group. Use synthetic source text, not document-specific special cases.
- [x] Write a valid-contract test:

```python
def test_two_topics_select_distinct_passages(document, packets):
    output = {"classifications": [{"chunk_id": "chunk-000001", "topics": [
        {"topic": "parties_and_roles", "groups": [{
            "evidence_item_ids": ["#/texts/0"], "context_item_ids": []}]},
        {"topic": "interest_and_fees", "groups": [{
            "evidence_item_ids": ["#/texts/2"], "context_item_ids": ["#/texts/1"]}]}
    ]}]}
    rows = validate_passage_classifications(output, document, packets)
    assert rows[0]["topics"][0]["groups"][0]["evidence_item_ids"] == ["#/texts/0"]
    assert rows[0]["topics"][1]["groups"][0]["context_item_ids"] == ["#/texts/1"]
```

- [x] Add rejection cases for every validation rule above, particularly an ID supplied only to another batch chunk, an inherited-heading-only group and a neighbor-only group with no core evidence.
- [x] Add cross-page continuation, first/last chunk, page-less input, oversized atomic neighbor, parent-subtopic normalization, source-order sorting and deterministic ID tests. Verify evidence on page 2 and context on page 1 retain their separate provenance.
- [x] Run `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest tests/test_topic_passages.py -q`; verify the new interfaces fail before production code is written.
- [x] Implement strict Pydantic response models and deterministic enrichment using the specified interfaces. Preserve original source text in packets; output only references/provenance.
- [x] Run the focused tests again and review their assertions against the full rejection matrix.

## Task 2: Integrate Passage Selection Into the Existing B3 Call

**Files:** Modify `src/credit_agreement_extractor/topic_reflection.py`, `tests/test_topic_reflection.py`; reuse `topic_passages.py` and `topic_taxonomy.py`.

**Interface:** Extend `reflect_topics(..., boundary_context_groups=1)` while preserving existing debug/run/model/concurrency parameters and its return type.

- [x] Add a fake-client test that inspects full core text, heading paths, neighbor atomic items, B2 proposals and shared topic definitions. Return grouped evidence/context JSON and assert the persisted schema is 2 and the filename is `document.topic-passages.json`.
- [x] Verify the test fails against the current chunk-label implementation.
- [x] Change the B3 prompt to explicitly request all relevant topic-specific groups and minimum necessary context, using the contract above. Do not classify isolated fragments or ask for summaries/reasons/scores.
- [x] Replace packet construction and response validation with Task 1's pure interfaces. Give each target its own citation scope even when multiple targets share a request.
- [x] Add schema/prompt/neighbor-profile/packet hashes to checkpoint identity; persist v2 outputs under the new filename. Existing v1 checkpoint directories remain untouched and cannot satisfy v2 requests.
- [x] Retain bounded concurrency, copied trace contexts, attempt IDs and two-attempt failure behavior. Persist final v2 output only after every target passes validation; never substitute B2 or historical classifications for failed targets.
- [x] Test invalid-output retry, terminal failure, partial resume, definition/neighbor-policy invalidation, model identity checks, out-of-order completion and `max_concurrency=1` equivalence using grouped fake responses.
- [x] Run `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest tests/test_topic_passages.py tests/test_topic_reflection.py tests/test_tracing.py -q`.

## Task 3: Deterministic B4 Passage Map and Legacy Compatibility

**Files:** Modify `src/credit_agreement_extractor/topic_map.py` and `tests/test_topic_map.py`.

**Interfaces:** Preserve `build_topic_map_document(document, classifications)` and `build_topic_map(chunks, classifications, ...)`; dispatch explicitly by schema version.

- [x] Write the v2 index test before implementation:

```python
def test_v2_map_preserves_roles(document, validated_v2):
    mapped = build_topic_map_document(document, validated_v2)
    assert mapped["schema_version"] == 2
    group = mapped["topics"]["interest_and_fees"][0]
    assert group["evidence_item_ids"] == ["#/texts/2"]
    assert group["context_item_ids"] == ["#/texts/1"]
    assert "summary" not in group
```

- [x] Add exact-group deduplication across neighboring windows, nonidentical overlap retention, multiple groups/topic, shared items across topics, parent preservation and unclassified-target tests.
- [x] Verify failures, then implement schema-v2 indexing and `document.topic-passage-map.json` persistence. Revalidate source identity, packet/input hashes and enriched group references; do not trust a completed-status field alone.
- [x] Keep the schema-v1 code path and filename behavior for explicitly supplied old artifacts. Do not promote v1 citations into v2 roles. Reject unsupported versions and mismatched B1 inputs.
- [x] Run `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest tests/test_topic_map.py tests/test_topic_passages.py -q` and compare B3/B4 v2 group IDs and evidence/context sets exactly.

## Task 4: Source-Linked Human Review

**Files:** Modify `src/credit_agreement_extractor/review.py`, `src/credit_agreement_extractor/review.html` and `tests/test_review.py`.

**Interfaces:** Preserve `load_run_review`, `build_topic_review` and `export_run_review`. Extend the disposable view model with passage groups and separate resolved evidence/context items.

- [x] Write tests before implementation for v2 evidence/context resolution, inherited heading context, multi-page groups, canonical tables and exact source wording. Confirm unrelated page text is not part of the default evidence display.
- [x] Preserve v1 review fixtures and explicitly label old citations as legacy supporting citations, not inferred evidence/context roles.
- [x] Change the topic results list to passage groups. Render direct evidence prominently, supporting context in an expandable panel, and each item's actual page/heading; retain full chunk/page context as an optional review action.
- [x] Keep B2's provisional chunk-based rule review separate from B3/B4 passage review. Preserve attempt/span-based model trace pairing and safe source rendering.
- [x] Handle missing/incomplete artifacts honestly; do not fabricate v2 groups or substitute previous runs.
- [x] Run `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest tests/test_review.py -q`; inspect one synthetic multi-topic page and one cross-page group in the browser. Validate desktop readability, citation navigation, raw JSON and legacy export behavior.

## Task 5: Regression Evidence, Documentation and Acceptance

**Files:** Update `README.md`, `AGENTS.md`, `docs/build_backlog.md`, `docs/conversion_pipeline.md`, this plan, and the existing Obsidian project note after build acceptance.

- [x] Run the full suite: `UV_CACHE_DIR=.uv-cache uv run --no-sync pytest -q`. Preserve existing conversion/chunking/concurrency checks; no tests may quietly lose assertions because the schema changed.
- [x] Run `git diff --check` and verify no source documents, credentials or historical run artifacts were modified.
- [ ] Ask for authorization before any paid rerun. If authorized, create a distinct run using `011_credit_agreement.pdf`, the approved model/effort, v3 prompt and debug capture. Do not overwrite the old v1/v2 runs.
- [x] Human acceptance checks: on a multi-topic page, identify party names separately from commitments; on a split passage, retain the clauses needed to understand the provision; on a table, preserve its heading and full canonical content; inspect rejected/out-of-scope citations.
- [x] Evaluate relevance and context sufficiency separately. Record omissions, over-selection and unresolved distant references. A structurally valid output is not enough to claim accuracy.
- [x] Request independent code review; resolve important findings before marking the refinement implemented.
- [x] Only then mark the backlog refinement complete and update the numbered diagram's status. B1 stays implemented unchanged; B5/B6 and extraction sleeves remain pending.
- [x] Update the Obsidian project and daily notes with outcomes and remaining uncertainty. Commit/push only if separately requested.

## Acceptance Boundary

Completion requires strict schema-v2 passage groups through B3 and B4, tested direct/context separation, bounded explicitly supplied local context, stable provenance, correct cached/parallel behavior, legacy artifact readability and a usable source-linked reviewer. A paid corpus benchmark, sentence-level segmentation, distant-reference agent and run-selector UI are not prerequisites and must not be implied complete.

## Acceptance Evidence — 2026-10-01

- Tasks 1–3: `topic_passages.py`, `topic_reflection.py`, `topic_map.py` and their
  tests implement the interfaces above. The initial new-module tests failed on
  missing interfaces; B3 grouped fake responses and B4 v2 indexing then failed
  against the old contracts before integration. New output filenames preserve
  old schema-v1 files. Neighbor-policy and provenance-tampering tests verify
  cache invalidation/rebuild; concurrency/retry/resume tests retain assertions.
- Task 4: source-linked groups keep roles, original wording, actual pages,
  canonical tables and heading paths. The explicitly synthetic developer
  fixture in `tmp/passage-development/review.html` was browser-checked for
  separate parties/commitments, split-page groups, expandable context/full
  chunks and stage/topic switching. A separate export of the completed
  historical GPT-6-Luna run verified genuine legacy-citation display.
- Independent read-only review found no critical/important issues. Its minor
  missing-heading-display finding was fixed and verified in browser/tests.
- Full suite: **228 passed**; `git diff --check` clean. Source corpus and
  historical run artifacts remain unchanged. No credentials were captured,
  no paid requests made, and no commit/push performed.
- Relevance and context sufficiency were checked separately against synthetic
  expected selections, not measured on live agreement classifications. Known
  limits: selections are whole Docling items; distant definitions/references
  remain unresolved; an apparently valid group can omit relevant text or retain
  noise. Human evaluation and a fresh authorized v3 run remain next steps.
- The paid rerun step is intentionally **not performed** (not an acceptance
  prerequisite). Shared canonical paragraph/table resolver is separately
  **deferred by the user**; missing neighboring-table text fails before calls.
