# B4/B5 Retrieval and Evidence Packaging

Approved in conversation on 2026-10-03; immediate plan/build on main authorized.

## Boundary

The downstream extraction component does any cognitive work of translating a
broad information need into approved topic IDs. B4 accepts those IDs only and
returns every mapped passage group for them. B5 attaches original source text,
separate supporting context, pages, headings and container relationships.
Neither stage calls a model, ranks groups, interprets questions or summarizes.

One public `retrieve_evidence(topic_map, chunks, *, topics, conversion=None,
debug=False, run_id=None, trace_root="tmp/runs")` composes both stages and
returns an `EvidenceArtifact` whose path holds the JSON packet. Explicit topic
IDs may include subtopics; parent expansion is not implicit. Empty matches are
explicit, not an assertion that the agreement lacks a provision.

## Integrity and persistence

Current B3 schema-v2 maps gain a semantic B1 fingerprint. B4 checks that binding,
source/taxonomy/status, approved IDs, canonical citations, group identity and
recomputed provenance. Older schema-v2 maps must be rebuilt by deterministic
B3 without rerunning the LLM. Historical schema-v1 citations remain readable by
the reviewer but are not treated as evidence/context groups by this API.

B5 preserves full original wording; A10-off and page-less inputs are valid.
For tables it uses the existing canonical grid renderer and matching Stage A
hash from B1. No source rewrites or full-page fallback. The deferred shared
paragraph/table resolver for classifier/reviewer remains out of scope.

Packets persist under `evidence/<request-hash>/document.evidence.json` next to
the map, with map/B1/canonical fingerprints. Basic events always log; debug
captures selection, packet and original input artifacts. No cache shortcut or
truncation initially. Failures cannot finalize a partial packet.

## Architecture and review

Current Stage D becomes one abstract pending purple downstream extraction box.
Its internal agent topology/schemas are not frozen. It chooses taxonomy topics,
requests B4/B5 evidence, extracts requested values and validates source citations.
The previously detailed pending sleeve diagram is superseded, not implemented.

B3 provides topic-map structure, B4 selection, B5 readable evidence. The packet
can support a future visual topic explorer; this build does not modify the HTML
reviewer or claim that a new visualization exists.

## Acceptance

Tests cover exact topic selection, explicit empty matches, immutable inputs,
stale/corrupt identity and citations, original/context wording, cross-page
provenance, table cells/hash dependency, trace success/failures and isolated
request paths. Saved source-only 011 output is exercised without paid calls or
ground-truth reads. Full suite and scoped credential checks precede push.
