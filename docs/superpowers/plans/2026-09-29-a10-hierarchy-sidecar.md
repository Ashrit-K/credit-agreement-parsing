# A10 Hierarchy Sidecar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Docling's built-in PDF heading-hierarchy inference and add A10,
which derives a versioned, provenance-preserving hierarchy sidecar from the
unchanged canonical Docling JSON.

**Architecture:** The PDF converter asks Docling to recover as much heading
structure as it can. A10 then traverses canonical `$ref` relationships in body
reading order, records Docling container ancestry, maintains a generic active
heading stack, and writes `document.hierarchy.json`. The sidecar enriches each
canonical item ID without copying the whole document or pretending inferred
headings are authoritative. A11 writes the final manifest last and returns an
enriched `ConversionArtifact`. Stage B remains responsible for page-first
chunking and topic-map construction.

**Tech Stack:** Python 3.11, Docling 2.129.x, standard-library JSON/dataclasses,
pytest, uv

## Global constraints

- Treat `raw_documents/pdf/` and `raw_documents/htm/` as immutable.
- Keep `document.docling.json` canonical and unchanged after export.
- Do not build a custom PDF layout or heading-detection engine.
- Do not interpret heading text as legal concepts such as Article, Section, or
  Clause; retain Docling's numeric levels as generic depths.
- Never drop, reorder, or summarize source items because hierarchy is missing
  or suspicious.
- Build the sidecar from serialized canonical JSON, not private Docling object
  state, so A10 is independently testable and reproducible.
- Preserve canonical item IDs and page provenance. Do not invent pages,
  coordinates, headings, or parent relationships.
- Limit the initial warning taxonomy to `no_headings`, `flat_levels`,
  `skipped_levels`, and `non_monotonic_pages`.
- Treat unresolved references, malformed heading levels, and reference cycles
  as validation errors, not warnings.
- Keep page-first chunking, neighbor overlap, table/list chunk policy, topic
  labeling, and LLM calls out of A10.
- Use TDD: write each focused failing test, observe the expected failure, then
  add the minimum implementation needed to pass it.

## Frozen sidecar contract

The sidecar filename is `document.hierarchy.json`. Its initial shape is:

```json
{
  "schema_version": 1,
  "source_sha256": "<full source digest>",
  "generator": {
    "name": "credit-agreement-parser-a10",
    "strategy": "docling-tree-plus-heading-stack"
  },
  "warnings": [
    {
      "code": "skipped_levels",
      "message": "Heading depth jumped from 1 to 3.",
      "item_ids": ["#/texts/12", "#/texts/18"],
      "pages": [4, 5],
      "details": {"from_depth": 1, "to_depth": 3}
    }
  ],
  "reading_order": ["#/texts/12", "#/texts/17", "#/texts/18"],
  "items": {
    "#/texts/18": {
      "item_type": "text",
      "reading_order_index": 2,
      "parent_id": "#/body",
      "container_path": ["#/body"],
      "pages": [5],
      "heading_path": [
        {"item_id": "#/texts/12", "depth": 1, "text": "ARTICLE II"},
        {"item_id": "#/texts/18", "depth": 3, "text": "Interest"}
      ]
    }
  }
}
```

Contract details:

- `reading_order` contains every non-container body item encountered after
  recursively expanding Docling groups. Tables, pictures, form items, and
  key-value items are retained when present; their content is not flattened
  into synthetic text.
- `items` may also contain group/container entries so native Docling parentage
  is addressable. Leaf entries include their nearest `parent_id`, full
  `container_path`, unique sorted page numbers from canonical `prov`, and the
  active `heading_path`.
- A heading item's path includes itself. Later items inherit that active path
  until an equal or shallower heading replaces the relevant stack entries.
- Heading path text is the only source wording copied into the sidecar; it is
  included to make paths readable. All substantive document text stays in the
  canonical JSON.
- Warning order follows reading order, making output deterministic.
- `no_headings`: zero usable `section_header` items were encountered.
- `flat_levels`: at least two headings were encountered and all have one depth.
- `skipped_levels`: the first heading starts below depth 1, or a later heading
  increases by more than one depth relative to the preceding heading.
- `non_monotonic_pages`: a heading's first canonical page is lower than the
  preceding heading's first canonical page. Missing page provenance does not
  fabricate a warning.

## File map

| Path | Responsibility |
| --- | --- |
| `src/credit_agreement_extractor/conversion.py` | Enable Docling heading inference; persist and cache the sidecar; finalize A11 manifest/artifact |
| `src/credit_agreement_extractor/hierarchy.py` | Pure canonical-JSON traversal, validation, warning generation, and sidecar construction |
| `src/credit_agreement_extractor/__init__.py` | Export only public hierarchy types/functions that callers actually need |
| `tests/test_conversion.py` | Verify Docling configuration, profile invalidation, persistence order, manifest, and cache contract |
| `tests/test_hierarchy.py` | Verify A10 traversal, generic heading paths, provenance, warnings, and hard failures |
| `docs/conversion_pipeline.md` | Move A5.1, A10, and A11 to implemented only after verification |
| `docs/build_backlog.md` | Update backlog statuses and link verification evidence |

---

### Task 1: Enable Docling heading hierarchy during PDF extraction (A5.1)

**Files:**
- Modify: `tests/test_conversion.py`
- Modify: `src/credit_agreement_extractor/conversion.py`

**Interfaces:**
- Consumes: the existing lazy `_default_converter()` configuration.
- Produces: PDF `PdfPipelineOptions` with Docling heading inference enabled and
  parsed pages available to that stage.

- [ ] **Step 1: Write the failing converter-configuration assertions**

Extend `test_default_docling_converter_uses_local_english_rapidocr()` to assert:

```python
assert pdf_options.generate_parsed_pages is True
assert pdf_options.heading_hierarchy_options.enabled is True
```

Also assert that the completed PDF manifest records an explicit hierarchy
configuration block, while HTML records that PDF inference was not run.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run pytest tests/test_conversion.py \
  -k "default_docling_converter or persists_canonical" -v
```

Expected: FAIL because heading hierarchy and parsed-page generation are not yet
enabled or recorded.

- [ ] **Step 3: Configure Docling and invalidate prior conversion caches**

Import `HeadingHierarchyOptions` from
`docling.datamodel.pipeline_options`. Construct PDF options with:

```python
PdfPipelineOptions(
    do_ocr=True,
    ocr_options=RapidOcrOptions(lang=["iso:en"]),
    heading_hierarchy_options=HeadingHierarchyOptions(enabled=True),
    generate_parsed_pages=True,
)
```

Bump `_CONVERSION_PROFILE` from `docling-json-v1-rapidocr-en` to a profile name
that explicitly captures heading inference, for example
`docling-json-v2-rapidocr-en-heading-hierarchy`. Add this manifest block:

```json
"heading_hierarchy": {
  "enabled": true,
  "provider": "docling",
  "generate_parsed_pages": true
}
```

For HTML, set `enabled` and `generate_parsed_pages` to `false`; A10 still uses
any hierarchy already present in Docling's HTML canonical export.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command again. Expected: PASS.

---

### Task 2: Build and validate the pure A10 sidecar transformation

**Files:**
- Create: `tests/test_hierarchy.py`
- Create: `src/credit_agreement_extractor/hierarchy.py`

**Interfaces:**
- Consumes: `canonical: Mapping[str, Any]` and `source_sha256: str`.
- Produces: `build_hierarchy_sidecar(canonical, source_sha256=...) -> dict[str, Any]`.
- Raises: `InvalidHierarchyInputError` when canonical structure cannot be
  traversed safely.

- [ ] **Step 1: Write a minimal representative canonical fixture**

In `tests/test_hierarchy.py`, build a small in-memory canonical document with:

- `#/body` children that refer to a heading, a paragraph, a group, and a table;
- the group containing another heading and paragraph;
- valid `self_ref`, `label`, `level`, `text`, and `prov.page_no` fields;
- heading depths that demonstrate replacement of equal-depth headings and
  inheritance by later text/table items.

Do not use a live Docling conversion in unit tests.

- [ ] **Step 2: Write failing happy-path tests**

Assert that the builder:

- recursively resolves body/group `$ref` values in deterministic reading order;
- records group ancestry separately from heading ancestry;
- includes a heading in its own `heading_path`;
- attaches the active heading path to paragraphs and tables beneath it;
- retains canonical item IDs and unique sorted page numbers;
- does not mutate the input mapping (compare with a deep copy);
- emits no substantive paragraph/table text in the sidecar; and
- produces identical dictionaries for repeated calls with identical input.

- [ ] **Step 3: Run the happy-path tests and verify RED**

Run:

```bash
uv run pytest tests/test_hierarchy.py -k "reading_order or heading_path" -v
```

Expected: test collection fails because `hierarchy.py` does not exist.

- [ ] **Step 4: Implement reference indexing and guarded traversal**

Implement these internal responsibilities as small pure functions:

```python
class InvalidHierarchyInputError(ValueError): ...

def _index_canonical_items(canonical: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]: ...
def _walk_body_refs(index: Mapping[str, Mapping[str, Any]]) -> Iterator[TraversedItem]: ...
def _canonical_pages(item: Mapping[str, Any]) -> list[int]: ...
def build_hierarchy_sidecar(
    canonical: Mapping[str, Any], *, source_sha256: str
) -> dict[str, Any]: ...
```

Index `body`, `groups`, `texts`, `tables`, `pictures`, `form_items`, and
`key_value_items` when present. Resolve children recursively from `#/body`.
Track the active recursion path to detect cycles. A group is structural context;
only non-container items enter `reading_order`.

- [ ] **Step 5: Implement the generic heading stack**

When a traversed item has `label == "section_header"`:

1. Require a positive integer `level`.
2. Remove active headings whose depth is greater than or equal to that level.
3. Add the current heading at its Docling-provided depth.
4. Save the resulting sorted stack as the heading's own path.

For every later item, copy the current stack into its sidecar entry. Do not
renumber levels or infer missing ancestors.

- [ ] **Step 6: Write failing warning-taxonomy tests**

Use separate tiny fixtures and assert exact warning codes, involved item IDs,
pages, and details for:

- no headings;
- two or more headings all at one level;
- a first heading deeper than level 1 and a later downward jump greater than
  one level; and
- consecutive headings whose first page numbers move backward.

Also assert that warning order follows reading order and no extra warning code
can appear.

- [ ] **Step 7: Implement only the four warning rules**

Keep warning construction separate from traversal. Warnings are observations,
not reasons to discard hierarchy paths or canonical content.

- [ ] **Step 8: Write failing hard-validation tests**

Assert `InvalidHierarchyInputError` for:

- a child `$ref` not present in the canonical index;
- a group reference cycle;
- a `section_header` with a missing, boolean, zero, negative, or non-integer
  level; and
- an item whose `self_ref` conflicts with the collection/index position used by
  its `$ref`.

- [ ] **Step 9: Implement hard validation and verify Task 2 GREEN**

Run:

```bash
uv run pytest tests/test_hierarchy.py -v
```

Expected: all A10 unit tests pass without loading Docling or touching disk.

---

### Task 3: Persist A10 and finalize the Stage A artifact through A11

**Files:**
- Modify: `tests/test_conversion.py`
- Modify: `src/credit_agreement_extractor/conversion.py`
- Modify: `src/credit_agreement_extractor/__init__.py`

**Interfaces:**
- Extends: `ConversionArtifact` with `hierarchy_json_path: Path`.
- Extends: `manifest.json` with the sidecar filename, hierarchy configuration,
  hierarchy schema version, and emitted warning codes/count.
- Changes: cache completeness to require all four artifact files and matching
  conversion profile.

- [ ] **Step 1: Upgrade the fake canonical test document**

Change `FakeDoclingDocument.export_to_dict()` in `tests/test_conversion.py` to
return a small valid Docling-like body tree with canonical `$ref`, `self_ref`,
heading level, paragraph, and provenance data. Keep the fake independent of the
real Docling runtime.

- [ ] **Step 2: Write failing Stage A persistence tests**

Assert that conversion:

- writes `document.hierarchy.json` beside the canonical JSON and Markdown;
- exposes it as `artifact.hierarchy_json_path`;
- records `hierarchy_json` in `manifest["artifacts"]`;
- records sidecar schema version and warning summary;
- writes a `status == "completed"` manifest only after all artifact files exist;
- leaves the serialized canonical JSON equal to the fake's exported dictionary;
  and
- invalidates a cache entry when its sidecar is missing, malformed, has a
  different source SHA-256, or has an unsupported schema version.

- [ ] **Step 3: Run the focused integration tests and verify RED**

Run:

```bash
uv run pytest tests/test_conversion.py \
  -k "hierarchy or cache or persists_canonical" -v
```

Expected: FAIL because the artifact, manifest, and cache do not yet know about
the sidecar.

- [ ] **Step 4: Integrate the A10 builder after canonical serialization**

Add `hierarchy_json_path` in `_artifact_paths()`. After exporting and writing
canonical JSON, call `build_hierarchy_sidecar()` with that canonical mapping and
the source SHA-256. Serialize the returned mapping to
`document.hierarchy.json` using the same deterministic UTF-8/indented JSON
convention as the canonical output.

Keep construction in `hierarchy.py`; `conversion.py` should only orchestrate
and persist it.

- [ ] **Step 5: Make A11 the completion boundary**

Build `manifest.json` only after Markdown, canonical JSON, and hierarchy JSON
have been written successfully. Include:

```json
"hierarchy_sidecar": {
  "schema_version": 1,
  "warning_count": 0,
  "warning_codes": []
}
```

Return the enriched `ConversionArtifact` only after the completed manifest is
on disk. If A10 fails, propagate the validation error and do not leave a
completed manifest that can be mistaken for a valid cache entry.

- [ ] **Step 6: Tighten cache validation**

Require all four artifact paths, the current conversion profile, matching
source SHA-256, sidecar schema version 1, and matching sidecar source SHA-256.
An old three-file cache is a miss and is regenerated; do not attempt an implicit
in-place migration.

- [ ] **Step 7: Run Task 3 tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_conversion.py tests/test_hierarchy.py -v
```

Expected: all focused tests pass.

---

### Task 4: Validate representative agreements and close the backlog entries

**Files:**
- Modify after successful verification: `docs/conversion_pipeline.md`
- Modify after successful verification: `docs/build_backlog.md`
- Generated and ignored: `tmp/converted/<source-sha256>/...`

**Interfaces:**
- Consumes: completed A5.1/A10/A11 conversion flow.
- Produces: regression evidence across materially different agreements and
  accurate architecture/backlog status.

- [ ] **Step 1: Run all automated tests**

Run:

```bash
uv run pytest -q
git diff --check
```

Expected: all tests pass and no whitespace errors are reported.

- [ ] **Step 2: Convert representative PDF shapes**

Run `convert_document()` into a fresh temporary output root for these existing
corpus files:

- `raw_documents/pdf/032_d35588dex101.pdf` — short waiver with sparse headings;
- `raw_documents/pdf/011_credit_agreement.pdf` — compact credit agreement with
  tables and multiple heading levels;
- `raw_documents/pdf/002_Facility_Agreement.pdf` — long facility agreement; and
- `raw_documents/pdf/051_ACCO_Brands_Third_Amended_Credit_Agreement.pdf` — long
  composite filing with noisy/deep inferred structure.

For each result, verify source SHA-256 is unchanged, all four artifacts exist,
the sidecar source SHA-256 matches the manifest, every sidecar ID resolves in
canonical JSON, and table items retain heading/container context where Docling
provided it.

- [ ] **Step 3: Inspect warning behavior rather than imposing a quality gate**

Record counts for the four warning codes. Sparse or noisy hierarchy is not a
conversion failure if references are valid: the downstream page-first fallback
must remain available. Do not add document-specific repairs based on these four
examples.

- [ ] **Step 4: Verify cache reuse under the new profile**

Convert one representative PDF again. Expected: `cached is True`, the converter
is not invoked, and none of the four artifact modification times change.

- [ ] **Step 5: Update architecture and backlog status**

Only after Steps 1-4 pass:

- change A5.1, A10, and A11 to solid implemented boxes/arrows in
  `docs/conversion_pipeline.md`;
- remove the obsolete A3.1 current-artifact shortcut if implementation now
  returns only through A11; and
- mark A5.1 and A10 `Implemented` in `docs/build_backlog.md`, adding the exact
  test commands and representative-document results as verification evidence.

## Definition of done

A10 is done only when the canonical export is unchanged, the deterministic
sidecar is independently tested, invalid references fail loudly, all four
warnings have exact tests, cache completeness includes the sidecar, and the
representative-document checks demonstrate that imperfect hierarchy never
removes access to canonical page-first content.
