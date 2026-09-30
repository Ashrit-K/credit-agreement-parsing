# B1 Page-First Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build B1 as a deterministic, provenance-preserving transformation from a completed Stage A conversion artifact to a cached `document.chunks.json` Stage B artifact.

**Architecture:** A pure `build_chunk_document()` function validates already-loaded canonical and hierarchy mappings, renders atomic source units, and partitions them without overlap. A separate `build_chunks()` wrapper validates Stage A files, hashes its inputs, reuses or atomically replaces the persisted Stage B artifact, and returns a typed `ChunkArtifact`.

**Tech Stack:** Python 3.11, uv, pytest, standard-library dataclasses/pathlib/hashlib/json; no new runtime dependency and no LLM call.

## Global Constraints

- Work on `main`; do not create a worktree or feature branch.
- Use `uv run --frozen` for all Python and pytest commands.
- Keep `raw_documents/` immutable; generated output belongs under `tmp/stage_b/`.
- Preserve every canonical leaf in A10 reading order exactly once and in order.
- Never invent page numbers, overlap source items, summarize source wording, or split an atomic canonical item, explicit Docling list, or table.
- Use a 12,000-character model-independent target and permit explicitly marked atomic overages.
- Keep B2 through B6 and all Stage D behavior out of this implementation.

## Implementation status

Completed on 2026-09-30. The final implementation passed 23 focused B1 tests,
69 full-suite tests, and real-document verification on
`002_Facility_Agreement.pdf` and `012_tmb-20250627xex10d1.htm`. The checkboxes
below preserve the originally approved execution sequence; authoritative
completion evidence lives in `docs/build_backlog.md`.

---

## File Structure

- Create `src/credit_agreement_extractor/chunking.py`: B1 models, validation, rendering, pure chunk builder, persistence, and cache contract.
- Create `tests/test_chunking.py`: focused pure-builder and filesystem/cache tests.
- Modify `src/credit_agreement_extractor/__init__.py`: export B1's public API and exception.
- Modify `docs/conversion_pipeline.md`: make B1 and A11-to-B1 solid only after acceptance checks pass; document the artifact contract.
- Modify `docs/build_backlog.md`: move B1 from Pending to In progress at implementation start and Implemented only after verification.
- Modify `README.md`: add the Stage A-to-B1 Python example and generated artifact location.
- Modify `AGENTS.md`: update the architecture snapshot and Stage B status.
- Modify the Obsidian project note after project files and tests reflect the final state.

### Task 1: Pure input validation and source rendering

**Files:**
- Create: `src/credit_agreement_extractor/chunking.py`
- Create: `tests/test_chunking.py`

**Interfaces:**
- Consumes: canonical Docling `Mapping[str, Any]`, A10 hierarchy `Mapping[str, Any]`, source and input SHA-256 strings.
- Produces: `InvalidChunkInputError`; internal canonical index and deterministic item/table-rendering helpers used by Task 2.

- [ ] **Step 1: Write failing validation and rendering tests**

Add focused fixtures that use canonical Docling references rather than loading Docling. The initial tests must prove:

```python
def test_retains_normalized_and_original_text_and_renders_original():
    result = build_chunk_document(
        canonical_with_items(
            text_item(0, text="Borrower", orig="(1) Borrower", page=1)
        ),
        matching_hierarchy("#/texts/0", page=1),
        source_sha256=SOURCE_SHA,
        docling_json_sha256=DOCLING_SHA,
        hierarchy_json_sha256=HIERARCHY_SHA,
    )

    item = result["chunks"][0]["items"][0]
    assert item["text"] == "Borrower"
    assert item["original_text"] == "(1) Borrower"
    assert result["chunks"][0]["content"] == "(1) Borrower"


def test_renders_table_grid_deterministically():
    result = build_chunk_document(
        canonical_with_items(table_item(0, [["Name", "Amount"], ["A", "$10"]])),
        matching_hierarchy("#/tables/0", page=1),
        source_sha256=SOURCE_SHA,
        docling_json_sha256=DOCLING_SHA,
        hierarchy_json_sha256=HIERARCHY_SHA,
    )

    assert result["chunks"][0]["content"] == "Name\tAmount\nA\t$10"
```

Also test malformed canonical collections, hierarchy/source mismatch,
unresolved reading-order IDs, duplicate reading-order IDs, malformed item
metadata, broken group references, and group cycles.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --frozen pytest tests/test_chunking.py -v
```

Expected: collection fails because `credit_agreement_extractor.chunking` does not exist.

- [ ] **Step 3: Implement the validation and rendering foundation**

Create these public contracts and constants:

```python
class InvalidChunkInputError(ValueError):
    """Raised when Stage A artifacts cannot produce trustworthy B1 chunks."""


@dataclass(frozen=True, slots=True)
class ChunkArtifact:
    source_sha256: str
    output_directory: Path
    chunks_json_path: Path
    schema_version: int
    chunking_profile: str
    cached: bool


_CHUNK_SCHEMA_VERSION = 1
_CHUNKING_PROFILE = "page-first-v1"
_DEFAULT_TARGET_CHARACTERS = 12_000
```

Implement helpers that:

- index `groups`, `texts`, `tables`, `pictures`, `form_items`, and `key_value_items` by their canonical `self_ref`;
- require hierarchy schema version 1 and a matching source SHA-256;
- require a duplicate-free hierarchy reading order whose IDs resolve to non-group canonical leaves;
- validate every canonical group child reference and reject cycles;
- copy only item ID/type, `text`, `original_text`, verified pages, heading path, parent ID, and container path;
- render text from non-empty `orig`, falling back to `text`; and
- render canonical table `data.grid` as tab-separated rows with embedded tabs/newlines normalized to spaces.

Do not copy bounding boxes or character spans into chunks.

- [ ] **Step 4: Run Task 1 tests and confirm GREEN**

Run the focused command from Step 2. Expected: all Task 1 tests pass.

- [ ] **Step 5: Review the Task 1 diff**

Run:

```bash
git diff --check -- src/credit_agreement_extractor/chunking.py tests/test_chunking.py
git diff -- src/credit_agreement_extractor/chunking.py tests/test_chunking.py
```

Confirm the module performs no filesystem access and contains no topic or LLM logic.

### Task 2: Atomic units and deterministic chunk assembly

**Files:**
- Modify: `src/credit_agreement_extractor/chunking.py`
- Modify: `tests/test_chunking.py`

**Interfaces:**
- Consumes: validated canonical index, hierarchy items, and ordered leaf IDs from Task 1.
- Produces: `build_chunk_document(canonical, hierarchy, *, source_sha256, docling_json_sha256, hierarchy_json_sha256, target_characters=12_000) -> dict[str, Any]`.

- [ ] **Step 1: Add failing boundary and invariant tests**

Cover these exact outcomes:

```python
def test_paged_content_starts_a_new_chunk_at_each_page():
    result = build_representative_result(pages=(1, 1, 2))
    assert [chunk["item_ids"] for chunk in result["chunks"]] == [
        ["#/texts/0", "#/texts/1"],
        ["#/texts/2"],
    ]
    assert result["chunks"][0]["next_chunk_id"] == "chunk-000002"
    assert result["chunks"][1]["previous_chunk_id"] == "chunk-000001"


def test_explicit_list_is_atomic_across_pages_and_target():
    result = build_list_result(target_characters=10)
    assert result["chunks"][0]["item_ids"] == ["#/texts/0", "#/texts/1"]
    assert result["chunks"][0]["atomic_group_ids"] == ["#/groups/0"]
    assert result["chunks"][0]["oversized_reason"] == "atomic_list"


def test_every_reading_order_item_occurs_exactly_once_and_in_order():
    result = build_mixed_result()
    flattened = [item_id for chunk in result["chunks"] for item_id in chunk["item_ids"]]
    assert flattened == result["source_reading_order"]
    assert len(flattened) == len(set(flattened))
```

Also test a same-page split between leaves, an oversized single item, a multi-page table, leading and later page-less items in a paged document, a fully page-less document, heading-aware page-less packing, no overlap, empty-rendering non-text leaves, deterministic IDs, and exact character counts.

- [ ] **Step 2: Run Task 2 tests and confirm RED**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --frozen pytest tests/test_chunking.py -v
```

Expected: the new boundary assertions fail because chunk assembly is incomplete.

- [ ] **Step 3: Implement atomic-unit construction**

Build an internal ordered atomic-unit sequence:

- a canonical table or ordinary leaf is one atomic unit;
- consecutive leaves sharing the same outermost explicit Docling `list` container form one atomic unit;
- a list group reappearing after another unit is an input error;
- unit pages are the sorted union of verified child pages;
- unit content joins non-empty item renderings with newlines; and
- unit metadata retains ordered item IDs and list group IDs.

- [ ] **Step 4: Implement paged partitioning**

For any document containing at least one verified page:

- buffer leading page-less units into the first paged chunk;
- start a new ordinary chunk when the next paged unit's first page differs from the current page anchor;
- split an oversized page only between units;
- attach later page-less units to the current preceding-page chunk;
- let atomic units exceed the target and label them `atomic_list` or `atomic_item`; and
- never add the same unit to two chunks.

- [ ] **Step 5: Implement fully page-less partitioning**

Create heading-led semantic blocks from the A10 heading path and canonical
`section_header` label. Pack complete blocks toward 12,000 characters. When a
single block exceeds the target, split it only between atomic units. This makes
new chunks begin at headings when possible without producing overlap or
violating atomicity.

- [ ] **Step 6: Finalize deterministic chunk records**

Assign one-based zero-padded IDs after partitioning, then add zero-based sequence indexes, previous/next IDs, sorted verified chunk pages, character counts, ordered item records, joined content, and oversized reasons. Include `source_reading_order` at document level so the exact-once invariant can be validated without reopening A10.

- [ ] **Step 7: Run Task 2 tests and confirm GREEN**

Run the focused test file. Expected: all pure-builder tests pass.

- [ ] **Step 8: Run the existing hierarchy regression tests**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --frozen pytest tests/test_hierarchy.py tests/test_chunking.py -v
```

Expected: all tests pass; B1 does not change A10 behavior.

### Task 3: Persistence, cache validation, and public API

**Files:**
- Modify: `src/credit_agreement_extractor/chunking.py`
- Modify: `src/credit_agreement_extractor/__init__.py`
- Modify: `tests/test_chunking.py`

**Interfaces:**
- Consumes: `ConversionArtifact` from `conversion.py`.
- Produces: `build_chunks(conversion_artifact, output_root=Path("tmp/stage_b"), *, target_characters=12_000) -> ChunkArtifact`, exported from the package root.

- [ ] **Step 1: Add failing filesystem and cache tests**

Use `tmp_path` and a minimal valid `ConversionArtifact` fixture. Test that:

```python
first = build_chunks(conversion, output_root=tmp_path / "stage_b")
second = build_chunks(conversion, output_root=tmp_path / "stage_b")

assert first.cached is False
assert second.cached is True
assert second.chunks_json_path == first.chunks_json_path
```

Also assert the exact output path, completed status, input hashes, stable file modification time on a cache hit, cache invalidation for changed canonical bytes, changed hierarchy bytes, wrong schema/profile/source, malformed JSON, and absence of a completed output after a forced build failure.

- [ ] **Step 2: Run persistence tests and confirm RED**

Run the focused test file. Expected: failures because `build_chunks()` is not implemented or exported.

- [ ] **Step 3: Implement the persistence wrapper**

`build_chunks()` must:

1. require the four completed Stage A paths and a manifest with `status == "completed"`;
2. calculate SHA-256 for the canonical and hierarchy files;
3. derive `tmp/stage_b/<source-sha256>/document.chunks.json`;
4. reuse only a valid completed schema/profile/source/input-hash match;
5. load JSON and call the pure builder on a cache miss;
6. write UTF-8 indented JSON plus a trailing newline to a temporary sibling path;
7. validate the serialized result before `Path.replace()` atomically installs it; and
8. clean the temporary path on every failure.

Target-character overrides must affect the chunking profile or cache identity so a 12,000-character cache is never reused for a different target.

- [ ] **Step 4: Export the public API**

Update the package root to export:

```python
from .chunking import (
    ChunkArtifact,
    InvalidChunkInputError,
    build_chunks,
)
```

Add the three names to `__all__` without removing existing Stage A or scaffold exports.

- [ ] **Step 5: Run Task 3 tests and confirm GREEN**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --frozen pytest tests/test_chunking.py tests/test_conversion.py -v
```

Expected: all B1 persistence/cache tests and Stage A conversion tests pass.

- [ ] **Step 6: Run the full regression suite**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --frozen pytest -q
```

Expected: zero failures.

### Task 4: Real-document verification and project-state documentation

**Files:**
- Modify: `docs/conversion_pipeline.md`
- Modify: `docs/build_backlog.md`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `/Users/ashrit/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian_ashrit/Projects/Credit Agreement Parser.md`

**Interfaces:**
- Consumes: the tested `convert_document()` and `build_chunks()` public APIs.
- Produces: verified PDF and HTML B1 artifacts plus synchronized architecture/status documentation.

- [ ] **Step 1: Mark B1 In progress before real-document execution**

Change only B1's backlog status from Pending to In progress. Keep its Mermaid box and A11-to-B1 arrow dashed until every acceptance check passes.

- [ ] **Step 2: Build and inspect a real PDF chunk artifact**

Run the public API through `uv run --frozen` for:

```text
raw_documents/pdf/002_Facility_Agreement.pdf
```

Write B1 output under the default `tmp/stage_b/` root. Verify completed status, exact-once reading-order coverage, deterministic neighbor links, page-first boundaries, and at least one retained explicit list or table.

- [ ] **Step 3: Build and inspect an accepted HTM chunk artifact**

Use an accepted corpus HTM file with absent page provenance. Verify the 12,000-character fallback, heading-led boundaries where available, empty page arrays, exact-once coverage, and no invented coordinates or page numbers.

- [ ] **Step 4: Re-run both calls to verify cache hits**

Confirm both returned artifacts report `cached=True` and their output modification times remain unchanged.

- [ ] **Step 5: Run final automated verification**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run --frozen pytest -q
git diff --check
```

Expected: zero test failures and no whitespace errors.

- [ ] **Step 6: Update the authoritative pipeline and backlog**

Only after Step 5 succeeds:

- change B1 and the A11-to-B1 Mermaid connection from dashed to solid;
- leave B1-to-B2 and every later Stage B connection dashed;
- document `document.chunks.json`, `build_chunks()`, the cache/profile boundary, and the no-overlap rule;
- set B1 to Implemented in `docs/build_backlog.md`;
- link this plan from the B1 registry row; and
- record exact focused/full test counts and real-document observations under B1 verification evidence.

- [ ] **Step 7: Update README, AGENTS, and Obsidian**

Add the public Stage A-to-B1 usage example and current implementation status. Preserve the authoritative roles of the pipeline diagram and backlog. Update the Obsidian project note with the same concise snapshot and next step: design B2's deterministic topic taxonomy/signals.

- [ ] **Step 8: Review all changes before commit**

Run:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Confirm no source document or secret-bearing file is staged, generated `tmp/` files remain ignored, and unrelated user changes are preserved.

- [ ] **Step 9: Commit and push `main`**

Stage only intended source, tests, plans, and documentation. Use concise conventional commits, then run:

```bash
git push origin main
```

Verify local `main` and `origin/main` resolve to the same final commit.
