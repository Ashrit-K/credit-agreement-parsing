# Stage B reviewer compatibility report

Task 2 completed against the shared working tree. No historical saved artifacts,
source documents, human labels or heuristic implementation were read or modified.

## Compatibility decisions

- Explicit `pipeline_layout='stage-b-v2'` in B2 entry events, captured classification
  profiles or result metadata selects current numbering, including failed runs
  without debug outputs. Source document metadata cannot change stage meanings.
- Current runs use B2 classification snapshots/exchanges and B3 topic maps.
  Their selector exposes pending B4 retrieval/B5 packaging, and renders no heuristic
  controls, proposals or rule-evidence panels. Stale captured heuristic artifacts
  do not enter current classification artifact details.
- Unmarked runs retain B2 heuristics/B3 classification/B4 map. Existing `use_b2=False`
  saved results continue to hide stale guesses and show their historical bypass.
  Historical schema-v1 citations stay distinct from schema-v2 evidence/context roles.
- Both layouts pair concurrent classification exchanges by attempt ID; legacy
  batch/attempt restart boundaries and Stage C span pairing remain unchanged.
- Existing original-text/table/page/heading joins, snapshot allowlists, redaction,
  script-delimiter escaping and explicit missing-output behavior are preserved.

## Verification

- Added fixtures first and observed expected failures before implementing the
  layout selection, new exchange prefixes and stale-artifact filtering.
- `UV_CACHE_DIR=/private/tmp/credit-parser-uv-cache uv run --no-sync python -m pytest tests/test_review.py -q`
  passed: **35 tests**.
- Two of these tests execute the exported standalone JavaScript with a disposable
  minimal DOM via existing Node: original source appears in both layouts; current
  controls and passage text say B2/B3 and contain no heuristic/proposal controls;
  historical passage text remains B3/B4 with saved proposal details.
- Extracted reviewer JavaScript passed `node --check`.
- Scoped `git diff --check` passed.
- In-app browser connected, but its URL policy rejected disposable `file://` HTML
  navigation (only HTTP/HTTPS allowed). No browser-policy workaround was attempted.
  Real browser visual/interaction inspection remains unverified; syntax and DOM
  execution checks above passed. No dependencies or paid model calls were added.

Only `review.py`, `review.html`, `tests/test_review.py` and this report were edited
for Task 2. Existing dirty changes in those files were preserved. Nothing staged
or committed by this worker.

## Independent review follow-up

The independent reviewer identified that standalone B3 map calls can log layout
metadata without classification snapshots. Trusted `pipeline_layout` entry events
now select the current layout under either B2 or B3, including a standalone map
completion or failure before debug snapshots. Other event types and source-stage
events cannot relabel a historical run. Added red-first fixtures for these cases;
the two standalone-map fixtures failed before the fix. Focused reviewer verification
now passes **39 tests**. Missing captured outputs remain absent.
