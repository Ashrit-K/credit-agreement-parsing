# Human topic annotation implementation plan

User-approved layout: original source left; current passage and source JSON
upper right; multi-select topics lower right; Save / Save & next; previous and
next passage arrows; ordered approved golden documents. Initial queue: 011,
002, 003, 008, 012, 010, 057, 067, confirmed on 2026-10-01.

## Scope and data boundary

- Review units are original canonical Docling leaves (paragraphs, headings,
  list items, tables), in A10 reading order, with pages and heading context.
- `annotation.py` and `annotation.html` form a separate local annotation app.
  Model guesses are not loaded. Source conversions are prepared locally on demand.
- `evaluations/golden_documents.json` contains only approved source paths.
- Human decisions persist only under ignored `evaluations/ground_truth/`.
  Records contain source and passage-catalog fingerprints, taxonomy version,
  canonical item ID, reviewed status, topics, notes, revision, and timestamp.
- Empty reviewed labels differ from missing/unreviewed labels. Unknown topics,
  duplicate topics, foreign item IDs, and stale revisions are rejected.
- Model pipeline modules never import the human store or read its files. No
  labels enter prompts, B2 guesses, converted artifacts, or model checkpoints.
  Evaluation scoring may read labels only after an independent run finishes.
- Preserve source corpus and existing dirty changes. No model calls, commits,
  or pushes are required for this annotation build.

## Completed tasks

- [x] Add approved eight-document manifest and passage view builder.
- [x] Add atomic label persistence and revision-conflict handling.
- [x] Add localhost-only source/annotation endpoints and local conversion jobs.
- [x] Add source PDF page rendering via installed Poppler, sandboxed original
  HTML preview, page reading view, multi-topic controls and navigation.
- [x] Add tests for original text/pages/table order, persistence, reviewed-empty,
  invalid labels/IDs, stale saves, conversion-catalog isolation, identical B3
  requests before/after writing human labels, and pipeline rejection of label files.
- [x] Verify browser saves and reloads using a disposable test store; leave the
  real human label store empty. Verify working original PDF rendering.
- [x] Update docs and backlog. Full suite: 184 passing tests.

## Follow-up

Scoring candidate models is a separate next increment. Human labels are at
passage level; current B3 predictions are at chunk level with item citations.
A scorer must state its comparison grain explicitly and exclude incomplete
human review from negative-label assumptions. Do not silently equate unreviewed
passages with the absence of a topic.
