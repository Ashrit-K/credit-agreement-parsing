# B2 Deterministic Topic Signals Implementation Plan

**Status:** Implemented on 2026-10-01. 29 focused tests and 98 full-suite tests
passed. Existing PDF and HTM B1 artifacts yielded 180 and 11 classifications,
with source coverage and all signal citations verified.

**Goal:** Classify every B1 chunk with the agreed eight-topic vocabulary and
two subtopics, retaining inspectable evidence for B3's later reflection.

**Architecture:** A versioned vocabulary registry supplies phrase and contextual
rules to a pure classifier. A file wrapper consumes `ChunkArtifact` and writes
`document.topic-signals.json` beside the chunks. The classification is provisional;
B3 will review original evidence and may add or remove labels.

## Frozen scope

- Eight topics: parties and roles; facility and commitment terms; interest and
  fees; maturity, termination, and extension; repayment and prepayment;
  covenants; guarantees and security; events of default and remedies.
- Subtopics: interest-and-fees PIK toggle and repayment-and-prepayment call
  protection. A qualifying subtopic also proposes its parent.
- Case-insensitive, whole-phrase matching, singular/plural role variants,
  optional articles, hyphen/space equivalence, and bounded loan/facility phrases.
- Every matching rule proposes its topic; there are no strength scores,
  confidence values, or strength categories. These are initial guesses for B3.
- Every chunk survives classification, including chunks with no matches.
- Signals carry rule ID, topic, source kind, exact matched wording,
  and supporting item IDs. No probability/confidence claim.
- Match original and normalized item text and inherited headings. Match joined
  content for tables and phrase combinations, identifying chunk-level evidence
  with all contributing item IDs rather than fabricating cell provenance.
- Benchmark aliases include current and historical vocabulary. This is an
  expandable registry, not a guarantee of exhaustive world-wide coverage.
- No model calls, final topic map, or extraction behavior in this increment.

## Tasks

1. Write failing tests in `tests/test_topic_signals.py` for all eight topics,
   broad-word guesses, PIK/call parent propagation, role variants, bounded wildcard
   phrases, contextual interest timing, inherited heading evidence, table text,
   deterministic output, input immutability, and malformed IDs.
2. Create `topic_taxonomy.py` with immutable topic/rule records and the agreed
   vocabulary. Retain broad-word guesses; add phrase combinations for payment
   timing, pricing grids, parties, and covenant restrictions.
3. Create `topic_signals.py` with `classify_chunk_document(document)` and
   `classify_chunks(artifact)`. Validate completed B1 schema, unique chunk/item
   references and exact source coverage. Preserve input order. Write an atomic
   UTF-8 JSON artifact recording source identity, taxonomy/rule version and B1
   file hash. Do not modify the B1 artifact.
4. Run `UV_CACHE_DIR=.uv-cache uv run --frozen pytest tests/test_topic_signals.py -q`
   and the full suite. Exercise the existing PDF and HTM B1 artifacts, verify
   every chunk has a provisional result and every cited ID resolves.
5. Update backlog, pipeline diagram (B2 solid, B3 purple/dashed), README and
   AGENTS with public usage, status, observed limitations and test evidence.

## Acceptance

Tests verify transparent rule behavior, not legal classification accuracy.
Real corpus runs are coverage and provenance smoke checks; expert-reviewed
classification ground truth remains future work. B3 receives all chunks and
the B2 suggestions, independently assesses evidence, and returns final labels.
