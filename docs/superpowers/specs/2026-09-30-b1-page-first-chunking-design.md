# B1 Page-First Chunking Design

## Status

Approved in design discussion on 2026-09-30. This specification defines the
scope that must be reflected in the B1 implementation plan before coding
begins.

## Goal

Build B1 as the first independently testable component of Stage B. B1 consumes
the completed Stage A conversion artifact and produces deterministic,
provenance-preserving chunks for later topic classification and evidence
retrieval.

B1 does not classify topics, call an LLM, retrieve evidence, or assemble an
extraction request. Those responsibilities remain in B2 through B6.

## Public workflow

The intended public workflow is:

```python
conversion = convert_document(source_path)
chunks = build_chunks(conversion)
```

`convert_document()` remains a Stage A operation and does not automatically run
B1. A later top-level pipeline function may orchestrate A, B, and D without
coupling their independently testable APIs.

The returned `ChunkArtifact` records:

- source SHA-256;
- output directory;
- `document.chunks.json` path;
- chunk schema version;
- chunking profile; and
- whether a valid persisted B1 artifact was reused.

## Separation of responsibilities

B1 has two layers.

### Pure chunk builder

`build_chunk_document()` accepts already-loaded canonical Docling JSON, the A10
hierarchy sidecar, and the source identity. It returns a JSON-serializable
Python mapping. It does not read or write files, call Docling, or call an LLM.

This layer owns:

- canonical item indexing and validation;
- reading-order traversal;
- atomic-unit construction;
- page-first and page-less boundary rules;
- item and table rendering;
- heading and container context;
- deterministic chunk identifiers; and
- neighbor-link construction.

### Persistence wrapper

`build_chunks()` accepts a completed `ConversionArtifact`. It validates and
loads the Stage A JSON artifacts, invokes the pure builder, persists the B1
result, and returns a `ChunkArtifact`.

This layer owns:

- filesystem validation;
- Stage A input identity hashing;
- Stage B output-path construction;
- development cache validation;
- atomic JSON persistence; and
- the completed artifact return contract.

## Artifact location and cache boundary

B1 writes outside the Stage A artifact directory:

```text
tmp/stage_b/<source-sha256>/document.chunks.json
```

This preserves Stage A's four-artifact completion contract. The persisted B1
artifact also acts as the development cache entry. B1 reuses it only when all
of the following agree with the current invocation:

- completed status;
- source SHA-256;
- B1 schema version;
- chunking profile;
- canonical Docling JSON SHA-256; and
- hierarchy-sidecar SHA-256.

Changing Stage B rules invalidates only the B1 artifact and does not force
Docling reconversion. This is a development optimization, not a final
production cache policy.

## Document-level schema

The schema-version-1 artifact contains at least:

```json
{
  "schema_version": 1,
  "status": "completed",
  "source_sha256": "...",
  "chunking_profile": "page-first-v1",
  "inputs": {
    "docling_json_sha256": "...",
    "hierarchy_json_sha256": "..."
  },
  "generator": {
    "name": "credit-agreement-parser-b1",
    "target_characters": 12000
  },
  "chunks": []
}
```

The exact field order is deterministic. The implementation plan may add
non-substantive generator metadata, but it must not change the agreed boundary
rules or introduce topic-classification fields.

## Chunk contract

Each chunk contains at least:

- deterministic `chunk_id`, such as `chunk-000001`;
- zero-based `sequence_index`;
- verified page numbers represented by the chunk's items;
- previous and next chunk identifiers;
- ordered canonical item IDs;
- ordered atomic group IDs where applicable;
- character count for the joined evidence content;
- an explicit oversized reason or `null`;
- ordered item records; and
- a joined `content` string for later model input.

Every item record contains:

- canonical Docling item ID and item type;
- canonical `text` where available;
- canonical `orig` exposed as `original_text` where available;
- verified page numbers or an empty list;
- A10 heading path;
- immediate parent ID; and
- full container path.

B1 does not duplicate bounding boxes or character spans. Those remain in
`document.docling.json` and are recoverable through the retained item ID when a
later extraction result needs full evidence provenance.

## Evidence rendering

For text-like items, B1 retains both normalized `text` and `original_text` when
Docling provides them. The joined chunk `content` uses non-empty
`original_text` first and falls back to `text`. This preserves list numbering
and legally meaningful punctuation without discarding Docling's normalized
form.

Tables receive a deterministic plain-text or Markdown representation derived
from canonical table-cell data. B1 does not ask an LLM to interpret or
summarize the table.

Every canonical leaf in A10 reading order remains represented. Non-textual
items retain their IDs and available metadata even when they contribute no
renderable text.

## Page-first boundary rules

For documents with usable page provenance:

1. A page boundary starts a new ordinary chunk.
2. Ordinary content from adjacent pages is not combined merely to fill a
   target size.
3. A page exceeding 12,000 rendered characters may split only between atomic
   units.
4. B1 never splits a single canonical leaf item.
5. Explicit Docling `list` containers remain atomic even when they cross pages
   or exceed 12,000 characters.
6. Multi-page tables remain atomic.
7. No source item appears in more than one chunk. B1 introduces no overlap.

The 12,000-character value is a model-independent target rather than a token
limit. Atomic content may exceed it. Oversized chunks identify whether an
atomic item or atomic list caused the overage.

## Page-less fallback

When the entire document lacks usable page provenance, B1 accumulates atomic
units in reading order toward 12,000 rendered characters. It prefers beginning
a new chunk at a detected heading but never violates list, table, or item
atomicity.

Items continue to report `pages: []`; B1 never fabricates page numbers.

When only isolated items in an otherwise paged document lack page provenance:

- leading page-less items remain before the first paged item in the first
  chunk; and
- later page-less items join the immediately preceding paged chunk.

The items themselves retain empty page arrays. This preserves reading order
without creating false provenance or disconnected one-item chunks.

## Hierarchy and container behavior

B1 uses A10 hierarchy as optional context, not as permission to remove or
reorder content. Heading paths are copied by item ID. The canonical Docling
JSON remains authoritative for source content and container labels.

Only explicit Docling `list` groups receive list atomicity. B1 does not make an
entire section or generic container atomic merely because it appears in the
container path.

## Neighbor context

Chunks contain deterministic previous and next identifiers. B1 does not copy
overlapping evidence into neighboring chunks. Later retrieval and bundle
assembly may deliberately include adjacent chunks when a sleeve needs broader
context.

## Validation and failure behavior

B1 raises an explicit input-validation error rather than persist plausible but
incomplete output when:

- a required Stage A artifact is missing or malformed;
- the hierarchy source SHA-256 differs from the conversion artifact;
- a hierarchy or reading-order reference cannot be resolved;
- reading order contains duplicate item IDs;
- a list contains a broken or cyclic child reference; or
- construction drops, duplicates, or reorders a canonical reading-order item.

Persistence writes a temporary file and atomically replaces the final path
only after the completed output validates. A failed build must not leave a
cache entry with completed status.

## Acceptance checks

Focused tests must cover:

- ordinary one-chunk-per-page behavior;
- an oversized page split only between items;
- multi-page and oversized list atomicity;
- atomic table rendering;
- fully page-less HTML chunking;
- mixed paged and page-less items;
- normalized and original Docling text;
- heading and container context;
- deterministic IDs and neighbor links;
- every reading-order item appearing exactly once;
- cache hits and invalidation after input or profile changes; and
- malformed or mismatched input rejection.

Real-document verification must include:

- `raw_documents/pdf/002_Facility_Agreement.pdf`; and
- an accepted HTML/HTM credit agreement exercising the page-less fallback.

The tests and verification must not modify preserved files in
`raw_documents/`.

## Explicitly deferred work

B1 does not include:

- preset topic taxonomy or deterministic topic signals (B2);
- LLM topic classification (B3);
- topic-map construction (B4);
- topic-specific retrieval (B5);
- topic-evidence bundle assembly (B6);
- extraction sleeves (Stage D); or
- a final production cache policy.
