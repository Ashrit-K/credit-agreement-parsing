# Credit Agreement Parser Build Backlog

This registry tracks agreed components that have not yet been implemented. The
component IDs match the authoritative diagram in
[`conversion_pipeline.md`](conversion_pipeline.md).

## Status vocabulary

- **Pending:** design is sufficiently settled to plan or build, but the code is
  not implemented.
- **In progress:** implementation has started but has not met its acceptance
  criteria.
- **Implemented:** acceptance criteria and focused regression checks pass, and
  the pipeline diagram has been updated to a solid box and solid connections.
- **Blocked:** implementation cannot proceed without a named dependency or
  decision.
- **Deferred:** intentionally parked; not a current build dependency.

## Registry

| ID | Status | Component | Frozen outcome | Dependencies | Implementation plan |
| --- | --- | --- | --- | --- | --- |
| A5 | Implemented | Docling PDF conversion pipeline | Run local English OCR, enable Docling's built-in heading-hierarchy inference and parsed-page generation, and record the configuration in the conversion profile and manifest. Do not add a custom document-layout parser. | A4 document format router | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Task 1 |
| A10 | Implemented | Build versioned hierarchy sidecar mapping | Transform unchanged canonical Docling JSON into a schema-versioned mapping keyed by canonical item IDs, with generic heading paths, page provenance, and the four frozen warning codes. Preserve source content and reading order; treat broken references and cycles as errors. | A5 and A9 canonical output | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Task 2 |
| A11 | Implemented | Persist sidecar and finalize Stage A artifact | Call A10 by default after canonical serialization; retain explicit opt-out. Finalize the manifest after all mode-required artifacts exist, return a nullable hierarchy path, and validate mode-aware caches. | A9; optional A10 | [A10 hierarchy-sidecar plan](superpowers/plans/2026-09-29-a10-hierarchy-sidecar.md), Tasks 3-4 |
| B1 | Implemented | Build page-first provenance-preserving chunks | Consume the completed Stage A canonical JSON and optional hierarchy sidecar through a pure chunk builder plus persistence wrapper. Write mode-isolated chunks under `tmp/stage_b/<source-sha256>/`; use page boundaries for paged documents and a 12,000-character reading-order fallback for page-less documents; keep canonical leaves, tables, and explicit Docling lists atomic; preserve item IDs, source wording, hierarchy context, and deterministic neighbor links without overlap or invented provenance. | A11 completed Stage A artifact | [B1 page-first chunking plan](superpowers/plans/2026-09-30-b1-page-first-chunking.md) |

| B2 | Implemented | Batched LLM passage classification | `reflect_topics(chunks, *, ...)` consumes B1 source evidence directly; Luna/high, schema-v2 direct/context groups, bounded retries, default five concurrent batches and validated checkpoints under explicit `stage-b-v2` identity. No heuristic proposals. | B1, Stage C | [Stage B simplification](superpowers/plans/2026-10-02-stage-b-simplification.md); historical [passage plan](superpowers/plans/2026-10-01-b3-b4-passage-evidence.md) |
| B3 | Implemented | Topic map | Deterministic topic-to-passage index with verified roles/provenance and exact deduplication; historical schema-v1 remains readable; no summaries or LLM calls. | B2 | [Stage B simplification](superpowers/plans/2026-10-02-stage-b-simplification.md) |
| B2/B3 passage refinement | Implemented | Topic-specific passage groups | Preserve B1 packaging and direct-evidence/supporting-context roles. Classification selects coherent groups; map verifies and indexes them. Historical schema-v1 runs remain unchanged; no extra LLM pass. | B1, B2/B3, shared tracing | Historical [passage plan](superpowers/plans/2026-10-01-b3-b4-passage-evidence.md) |
| Shared source-item resolver | Deferred | Uniform paragraph/table evidence rendering | Reuse canonical source text/cells with Docling IDs, pages and headings in B2 input preparation and review. Keep B1 unchanged; agree on hash-verified Stage A contract before implementation. | Stage A, B1 provenance, B2, reviewer | User requested deferral on 2026-10-01 |
| Optional A10 ablation | Implemented | Explicit hierarchy opt-out with downstream fallback | A10 defaults on. `convert_document(..., use_hierarchy=False)` retains mode-aware A11/cache, canonical-reference B1 fallback and separate output paths without altering human-label catalogs. | A9, A11, B1, reviewer | [Optional A10 history](superpowers/plans/2026-10-02-optional-a10.md); [current simplification](superpowers/plans/2026-10-02-stage-b-simplification.md) |
| Stage B simplification | Implemented | A10-on default, remove heuristics and renumber B | B1 chunks → B2 LLM classification → B3 map; pending B4 retrieval / B5 packaging. Explicit current layout and historical run compatibility; preserve A10 opt-out. Acceptance passed: 271 commit-scope tests; historical/current reviewer coverage and independent review. | A10, classification, map, reviewer | [Implementation plan](superpowers/plans/2026-10-02-stage-b-simplification.md) |
| B2/B3 passage contract simplification | Deferred | Consider topic-specific item groups without evidence/context roles | Evaluate grouped `item_ids` against context interpretation, retrieval and historical compatibility before approval. Keep current roles unchanged. | B2/B3, evaluations | Backlog-only deferral on 2026-10-02; originally named B3/B4 |
| C1–C6 | Implemented | Shared OpenCode transport | Responses/Chat/Qwen Messages adapters, xhigh forwarding, overrides, normalized cache accounting and reasoning-safe telemetry; model defaults unchanged. | Credentials | Historical [transport plan](superpowers/plans/2026-10-01-b3-topic-reflection.md) |
| B4/B5 | Implemented | Strict topic retrieval and evidence packaging | `retrieve_evidence()` validates approved topic IDs and map/B1 fingerprints, retrieves all exact groups, resolves original evidence/context and table cells with verified provenance, and persists request-specific packets with traces. No resolver LLM, ranking or question filtering. | B3, B1; matching Stage A for tables | [Implementation plan](superpowers/plans/2026-10-03-b4-b5-evidence-retrieval.md) |
| D1–D4 | Implemented | Orchestrated parties, facilities and interest extraction | One public fixed-Python orchestrator coordinates one specialist with B4/B5 tools; validates the agreed cited JSON, entity references and decimal-rate arithmetic; persists complete results and debug traces. B3 completion hands off directly, with no orchestration LLM. | B3 readiness; B4/B5, C | [Stage D plan](superpowers/plans/2026-10-03-stage-d-extraction.md) |
| Stage D extraction evaluations | Pending | Human-reviewed field-level reference and error analysis | Compare completed independent extractions with human-authored correct values and supporting source; never supply reference answers to any pipeline/model stage. Test varied agreements before an accuracy claim. | D1–D4, human review | — |
| Stage D richer retrieval/rate policies | Deferred | Additional specialists, field-level citations and conditional calculations | Evaluate targeted evidence broadening, per-attribute citations, negative benchmark rates, pricing-grid applicability and complex formulas before expanding the bounded initial specialist. | D extraction evaluations | — |
| B4/B5 visual topic explorer | Deferred | Human-readable topic-map visualization | Use B3 structure, B4 selections and B5 source text/provenance without new classification. Current saved-run HTML remains unchanged. | B4/B5 packets | — |
| Observability: Phoenix | Deferred | Trace UI | Revisit later; no classification/map dependency. | Local telemetry | — |
| Human topic annotation | Implemented | Golden passage label editor | Approved source queue, durable human saves/reload/export; human labels excluded from pipeline inputs. | Stage A | [Annotation plan](superpowers/plans/2026-10-01-human-topic-annotation.md) |
| Human review HTML | Implemented | Saved-run reviewer | Current A/B1–B3/C review and original historical stage labels, using actual saved source evidence and attempt identities. Live dashboard remains deferred. | Debug snapshots | [Simplification plan](superpowers/plans/2026-10-02-stage-b-simplification.md) |
| Telemetry restart correlation | Pending | Distinguish executions within one run ID | Correlate failures with exact call/span across run restarts. | Local events | — |

Current registry IDs use `stage-b-v2`. Historical unmarked runs and the
verification evidence below retain old B2 heuristics, B3 classification and B4
map labels. Mapping: old B3 → B2, old B4 → B3, old B5 → B4, old B6 → B5;
heuristic B2 is removed from current APIs. The former Optional B2 bypass is
historical: current classification accepts chunks directly and has no `use_b2`.
Saved plans/reports remain history. The 011 ablations motivate this simplification
but do not prove a universal improvement or isolate stochastic/packing effects.

## Verification evidence

### Stage D orchestrated extraction — 2026-10-04

- Fixed D1 orchestration, one D2 specialist for parties/facilities/interest-fees,
  D3 schema/citation/reference/arithmetic checks, D4 unique result and manifest-last
  completion. `run_pipeline` triggers D only after successful B3; standalone B3
  remains unchanged. Models/efforts can be overridden separately for B2 and D.
- 54 focused tests cover numeric fractions, parent-child role separation,
  status/citation/entity checks, deterministic totals, unresolved pricing inputs,
  bounded failures/retries, model/style identity, cost failure attribution,
  manifest persistence, source tables, both A10 modes and readiness handoff.
  Full local suite: 372 passed (includes unrelated working changes).
- Independent review reproduced uncited facilities, parent roles in agreement
  roles and uncertain-total arithmetic gaps; second review found unresolved
  calculation-input promotion and substitution telemetry gaps. Each has a
  failing-then-passing regression. Live smoke exposed role-case normalization,
  also reproduced and corrected with a regression.
- Source-only saved 011 smoke used GPT-5.6 Luna/medium, without reconversion,
  reclassification or human-label reads. Initial prompt completed after one
  validation retry: estimated $0.0271718 and 42.24s provider latency. Revised
  fee/period prompt produced two responses rejected for capitalized `Lender`:
  estimated $0.0276144 and 57.69s. Both live histories remain intact.
- After casing normalization, the second actual saved revised response was
  revalidated offline with exact system/schema/evidence matching; no new request.
  It yields six entities, one facility, monthly interest and annual/one-time fees.
  Total observed estimated spend across the two live checks: $0.0547862; four
  provider calls. Costs are dated gateway estimates, not invoices or accuracy scores.
- Final readable result and offline provenance are under
  `tmp/runs/stage-d-011-smoke-20261004/offline-revalidated/` and
  `offline-revalidation-provenance.json`. All original source/map/chunk/canonical
  artifacts verified byte-identical. Full extraction eval remains pending;
  record-level citations and simple nonnegative rate policies are initial scope.
- Pipeline D1/D3/D4 boxes are solid green; D2 is solid purple. C remains isolated,
  B4/B5 remain shared retrieval tools. The HTML reviewer and Phoenix stay unchanged.


### B4/B5 retrieval and evidence packaging — 2026-10-03

- Strict approved-topic selection, source-bound schema-v2 maps, canonical group
  identity/order/provenance checks and original evidence/context packaging.
- Request-specific persisted packets, separate B4/B5 spans and basic/debug
  public API traces; malformed input and source/table hash failures are covered.
- Saved source-only 011 smoke: 8 parties, 11 facility/commitment and 8 interest
  groups, 85 readable direct-evidence records; no model calls or ground-truth
  reads. Saved chunks/classifications verified byte-identical afterward.
- Exact staged snapshot: 298 passed; full local suite: 318 passed, including
  unrelated working changes left out of the commit. Independent review found a group-order
  validation gap; a failing regression reproduced it, and the correction passed.
- Abstract pending D1 replaces the detailed pending sleeve view. B4/B5 boxes and
  edges are solid; D remains dashed/purple. Existing HTML is unchanged; a visual
  explorer is deferred, supported by the new packet contract.

### Current Stage B simplification — 2026-10-02

- A10 defaults on; source-only B2 classifier replaces deleted heuristics, B3
  builds the map, and B4/B5 retrieval/packaging remain pending. Current profiles,
  outputs and entry telemetry use `stage-b-v2`; its nested output directory
  preserves historical artifacts and checkpoints.
- Current and historical reviewer layouts, failed/basic standalone map runs,
  concurrent exchange pairing and stale-proposal exclusion are regression-tested.
- Commit-scope suite: 271 tests passed. Full local workspace: 281 passed,
  including 10 unrelated experimental tests left outside this commit.
- Independent review's standalone-map layout finding was corrected and verified;
  no unresolved findings. `git diff --check` passed. No paid model calls.
- Reviewer JavaScript syntax/DOM checks passed. Real-browser visual inspection
  was unavailable because local-file navigation was rejected; no workaround used.

### Optional B2 — 2026-10-02

- Public B3 bypass tested without a B2 artifact and with stale/malformed unused
  signals, including debug capture. Enabled mode retains strict validation.
- Checkpoints separate enabled/disabled modes and reuse within a mode; B4
  consumes bypass output without schema changes. Reviewer ignores stale B2
  snapshots and explicitly marks B2 skipped.
- `uv run --no-sync python -m pytest -q`: **275 passed**. Plain `pytest` could
  not import the existing root-level `evaluations` package; module invocation
  includes the workspace root. Reviewer JavaScript syntax and diff checks pass.
- B1, model defaults, prompt/rubric, source corpus and historical runs unchanged;
  no paid calls, commit or push for this build.

### B3/B4 passage refinement — 2026-10-01

- Pure packet/strict response contracts, core direct evidence, role separation,
  parent normalization, stable group identities, separate page provenance,
  packet-sensitive caches and validated deterministic B4 indexing are covered.
- Browser checks on an explicitly synthetic developer fixture verified separate
  party/commitment passages, split-page evidence/context, canonical tables,
  heading paths, optional full chunks, topic/stage switching and raw records.
  A separately exported real historical run remains labeled legacy citations.
- Independent read-only review reported no critical/important issues; its
  heading-path display finding was fixed and checked in the browser.
- Full regression suite: **228 passed**; `git diff --check` clean.
- No paid passage rerun or semantic accuracy benchmark was performed. No
  corpus, historical-run, credential, commit or remote changes were made.
- Shared source-item resolver remains deferred; missing neighboring-table text
  fails before provider calls rather than producing incomplete evidence.

### Human topic annotation — 2026-10-01

Benchmark recovery — 2026-10-02: five-model passage classification experiment
is complete under `tmp/runs/benchmark-011-five-20261002-v2/`. Original
60-second transport timeouts were reproduced; the client now accepts a tested
`timeout_seconds` setting (60 default, 300 for this experiment). Successful B3
checkpoints are reused, citation validation remains strict, and retries are
bounded. Frozen canonical table rendering enriches only isolated benchmark
inputs; the shared source-item resolver above remains deferred. Human labels
have two hash-identical backups outside inference inputs. Offline scores and
costs must not be presented as a full five-model ranking until runs complete.
Recorded incomplete Responses and length-finished Chat outputs also proved an
8,192-token reasoning allowance was insufficient for GPT-5.6/xhigh and DeepSeek
V4.1/high. Tested configurable output limits now permit 32,768 for those runs.
The experiment runner supplies saved model output and machine-only citation
constraints to validation retries, without human labels or extra adapter calls.
Recovery interventions are explicit; final reports must distinguish them from
unmodified initial requests and count failed-attempt/unknown costs.

Benchmark add-on — 2026-10-02: GPT-6.1 Sol/medium completed 18/18 batches on
the same frozen 011 source/taxonomy/base prompt. Five-way batch concurrency,
300-second timeout and 32,768-token allowance; 19 calls including one validation
retry, 107,946 input / 7,811 output tokens. Offline direct-evidence classification
micro-F1 0.70955, exact reviewed-label-set agreement 0.59091 across 264 passages.
Estimated benchmark cost USD 0.3479465 uses dated public OpenCode gateway rates,
not workspace-specific rates; separate tiny preflight cost USD 0.00014. All
requests, visible responses, checkpoints, outputs and disagreements are saved
under `tmp/runs/benchmark-011-five-20261002-v2/gpt-6-1-sol-medium/` and its traces.
These are single-document baseline results, not evidence of corpus-wide quality;
no rubric change or human-label mutation was made.

Jev benchmark add-on — 2026-10-02: completed 264/264 source-item classifications
using native `jev-1.13` System One questions, fixed probability cutoff 0.5 and
existing subtopic-to-parent normalization. Same frozen 011 source/taxonomy and
offline reviewer coverage; native per-item questions differ from generative B3
passage grouping. No production B3/C route or verifier layer was added.
F1 0.68817, precision 0.69565, recall 0.68085, exact match 0.55682: fifth of seven.
264 requests, zero failures/retries, 1,677,703 input / 62,304 output tokens;
dated public gateway estimate USD 0.070463526, excluding tiny preflight.
The first invocation omitted explicit trace kwargs: original per-call event
logs were consolidated without repeating paid calls. Checkpoint probabilities,
usage, latency and response IDs are intact; deterministic requests were
reconstructed, but original full HTTP debug envelopes were not captured.
Recovery provenance is disclosed in `trace-recovery.json`. Source human labels
and both reference backups are byte-identical. Separate `ranking-with-jev.json`
preserves the original six-model ranking. Ten experimental contract tests pass.
Implementation: [Jev benchmark plan](superpowers/plans/2026-10-02-jev-011-benchmark.md).

B2 ablation — completed 2026-10-02: user requested fresh 011 runs for DeepSeek
V4 Flash/high, DeepSeek V4.1 Flash/high and Qwen 3.8 Flash/high without B2.
The existing `reflect_topics(..., use_b2=False)` implementation is used unchanged;
43 B3 tests passed, including disabled-signal reads and checkpoint isolation.
Runs are separate under `tmp/runs/benchmark-011-no-b2-20261002/`, with models
sequential, one in-flight request, five-second post-response spacing and
30-second cooldown on HTTP 429. Preserve original assisted-run results and use
the same frozen source, taxonomy, base prompt, output budgets and offline reference.
All three completed 18/18 batches. DeepSeek V4 Flash: F1 0.71624 → 0.74694,
estimated USD 0.06946948, 18 calls, no retries. DeepSeek V4.1 Flash: F1
0.71343 → 0.75102, USD 0.20250196, 18 calls, no retries. Qwen 3.8 Flash:
F1 0.69474 → 0.72727, USD 0.03568989, 19 calls including one validation retry.
All new-run costs have recorded usage, unlike the incomplete historical cost
coverage. The 55 request snapshots verify empty proposals and no signals files.
Human labels and both frozen backups are byte-identical; original assisted
results remain untouched. Offline comparison and per-model disagreements are
saved under the new root. All three improved on this one document, but these
single draws do not isolate stochastic variation or prove a corpus-wide effect.

Jev B2 ablation — completed 2026-10-02: same native per-item questions and
0.5 cutoff as the earlier Jev run, but no B2 signals are read or supplied.
Separate run ID `jev-1-13-no-b2` under the existing ablation root; 264 source
passages, one in-flight request, five-second spacing, 30-second HTTP 429 cooldown,
bounded retries, debug HTTP exchanges and hash-keyed checkpoints. Earlier Jev
decisions and the three-model comparison remain unchanged. Offline scoring
wrote `comparison-with-jev.json` after completed inference. All 264 passages
completed without failed calls; 264 request snapshots verify empty proposals.
F1 0.68817 with B2 versus 0.68632 without; precision 0.67917, recall 0.69362.
Estimated cost USD 0.070154154, fully accounted, excluding separate preflight.
Human decisions and frozen redundant backups remain byte-identical. Jev's
single-run difference is essentially flat, unlike the improvements observed
for the three generative models; do not infer a corpus-wide causal effect.

Joint A10/B2 ablation — completed 2026-10-02: requested 011 repeats for DeepSeek
V4 Flash/high, DeepSeek V4.1 Flash/high and Qwen 3.8 Flash/high. Use existing B1
`build_chunk_document(canonical, hierarchy=None)` and B3 `use_b2=False` paths;
no production API change or repeat Docling conversion. Frozen canonical JSON
rebuild verifies all 264 source IDs, wording, pages, 29 chunk memberships and
atomic groups equal prior runs, while reconstructed heading paths are empty.
Saved requests verify neither A10 heading context nor B2 proposals are supplied.
Separate root `tmp/runs/benchmark-011-no-a10-no-b2-20261002/`; sequential models.
DeepSeek runs retain one in-flight request. Per the user's subsequent request,
Qwen used `max_concurrency=4`, with thread-safe five-second request-start
spacing, post-response spacing and bounded retries. Handoff waited for the
active model to finish; completed calls/checkpoints were reused without calls.
Retain historical assisted and B2-only-disabled results; score after each
completed model against the same frozen human reference without leaking labels.
Final both-disabled F1/cost estimates: V4 68.61%/$0.055541; V4.1
65.41%/$0.148170; Qwen 64.35%/$0.026385. B2-only-disabled F1 was respectively
74.69%, 75.10% and 72.73%. Both-disabled calls/retries: 13/1, 12/0 and 12/0;
all new-run costs are accounted estimates. Historical both-enabled costs have
1, 3 and 2 unknown-cost calls respectively. All 264 reviewed passages and
2,751 reviewed topic decisions use the same reference; active human labels
and both redundant backups remain byte-identical (SHA-256 `2594e629...ae095`).
Saved comparison: `tmp/runs/benchmark-011-no-a10-no-b2-20261002/offline-evaluation/comparison.json`.
These are single-document observations, not a causal accuracy guarantee:
removing heading context also changed size-bounded packing from 18 to 12
batches. Qwen completed in 154.55 seconds with four workers. Experimental
runner pacing checks plus B3 regression tests: 45 passed. No production
default, source document or human label changed for this benchmark.

Shared transport increment: C6 Qwen Messages and Responses/Chat `xhigh` are
implemented. All five requested model/effort combinations passed tiny live
checks; estimated combined cost USD 0.00025185 from 262 input/241 output tokens.
Logs: `tmp/runs/model-effort-checks-20261001/`. Full suite: 242 passed.
No agreement benchmark or human-label write was performed. Messages high is an
explicit 16k thinking-budget mapping, not a native provider effort guarantee.

Contract definitions update: implemented taxonomy/rules/definitions v2 and
per-topic human review coverage. Verified all 163 existing saved records against
two byte-identical backups; originals remain unchanged. Legacy decisions keep
labels, notes, revisions and timestamps; new-category absence remains unknown.
Stale taxonomy browser saves are rejected. Full suite: 233 passed.
Progress correction: existing saved reviews remain completed when topics are
added. No re-review badge or forced return to old passages; per-topic coverage
remains available for evaluation without resetting the user's progress.
Plan: [Contract definitions](superpowers/plans/2026-10-01-contract-definitions.md).

- Implemented as a separate localhost HTML app; approved eight-document queue,
  source PDF page/HTML preview, passage text/tables/context, multi-label controls,
  Save & next, previous/next, progress, reload and JSON export.
- Nine focused tests and 184 full-suite tests passed. Browser checks covered
  multi-label saves, reviewed-empty saves, navigation and reload using disposable
  labels; the actual human store remains unlabelled. Original PDF rendering works.
- Ground truth stays in `evaluations/ground_truth/`. B3 requests remain identical
  before/after human saves; human-label JSON is rejected as pipeline input.
- Plan: [Human annotation](superpowers/plans/2026-10-01-human-topic-annotation.md).
- Model scoring and any passage-level B3 redesign remain separate work.

### B3 bounded concurrency — 2026-10-01

- 175 integrated full-suite tests passed, including 14 new parameterized B3
  concurrency cases, a parallel C snapshot-identity test and 4 saved-review
  exchange-correlation/boundary-pairing checks.
- `max_concurrency` defaults to 5; positive integers are required, with 1
  providing sequential execution. Batching, v2 prompt, taxonomy, schema and
  model overrides are unchanged. Concurrency does not affect checkpoint reuse.
- Fake-client barriers/events prove overlapping calls bounded at 2, 3 and 5,
  default concurrency, source-order results after out-of-order completion,
  per-batch retry limits, sequential equivalence, failure/resume and preservation
  of the last completed output. No paid API calls were made.
- Failure stops scheduling; already running calls may complete and checkpoint.
  Final output requires all batches. Copied tracing contexts retain B3/C span
  ancestry, JSONL writes are synchronized, and unique attempt IDs correlate
  request/response/validation snapshots. Reserved `_trace` metadata identifies
  raw C exchanges, and the reviewer pairs C boundaries by span rather than
  independent latest values. Telemetry restart analytics remain
  deferred; this change adds durable exchange IDs without altering that summary.

### B3 topic-definition refinement — 2026-10-01

- 156 full-suite tests passed. New checks prove every approved topic definition
  reaches B3 and edits to definitions invalidate its validated checkpoints.
- `b3-reflection-v2` uses shared `credit-topic-definitions-v1` meanings with
  explicit boundaries. B2 rules, topic IDs, and B4 indexing remain unchanged.
- The saved Amerigo run used v1: B2 proposed 98 chunk-topic assignments; B3
  retained 51, removed 47, and added 9, leaving 60. B4 preserved all B3 labels
  and citation sets across all 29 chunks. Agreement is not accuracy.
- No paid v2 rerun yet. The HTML still shows the original saved run; manually
  reviewed additions/removals and a fresh v2 comparison remain next steps.

### Saved-run human review — 2026-10-01

- 154 full-suite tests passed, including 12 review tests for saved-file loading,
  path restrictions, missing-data behavior, source wording/pages, heading
  resolution, canonical table cells, unclassified chunks, safe script embedding with punctuation
  round-tripping, and distinct argument versus artifact snapshots.
- Real Amerigo export contains 29 chunks, 9 final interest chunks and 2
  unclassified chunks. Browser checks covered A artifact selection, B1/B2/B4
  views, source-citation focus, chunk navigation, C transport snapshots,
  pending-stage display, narrow-panel switching and desktop side-by-side layout.
- Snapshot content came entirely from the existing run. No new conversion,
  model calls or source edits; exported HTML contained no API key.
- This is read-only saved-run review, not live progress tracking or persisted
  reviewer judgments. A1–A11 were not independently instrumented in that run.

### B3/B4 and Stage C — 2026-10-01

- 142 full-suite tests passed. New checks cover routing, secret masking,
  debug snapshots, malformed provider envelopes, strict taxonomy/citations,
  exact chunk coverage, parent topics, batching, invalid-output/transient retries,
  auth failure without retry, checkpoint resume after partial failure,
  settings/input invalidation, model-substitution rejection, deterministic B4
  order including inherited headings, and local analytics.
- One live synthetic B3/B4 run returned `gpt-5.6-luna` and `effort=high`:
  423 input tokens, 110 output tokens (including 53 reasoning tokens), one
  request, 3.16 seconds. Interest and maturity labels cited the correct source
  items. These are wiring checks, not a corpus classification benchmark.
- The gateway returned no actual billed cost. Its recorded attempt remains
  unknown; the subsequently verified 2026-10-01 Luna rate snapshot estimates
  this usage at USD 0.0002166, not a billing assertion. Unknown models/tiers
  remain unknown unless explicit rates are supplied.
- Responses is live-verified; Chat Completions has fake-HTTP coverage only.
- Debug capture is available across existing and new public pipeline APIs.
  Local events and snapshots are under ignored `tmp/runs/`; keys never logged.
- Phoenix deferred. B5/B6 and Stage D are not implemented. Source corpus and
  existing staging imports were not modified; no paid corpus sweep performed.

## B2 build entry — 2026-10-01

- **Status:** Implemented.
- **Outcome:** Versioned eight-topic heuristic classification with PIK toggle
  and call-protection subtopics, unscored heuristic signals, source IDs,
  exact matched wording, and provisional labels for every B1 chunk.
- **Dependency:** B1; B3's LLM reflection is now implemented.
- **Plan:** [B2 topic signals](superpowers/plans/2026-10-01-b2-topic-signals.md).
- **Verification:** 29 focused tests and 98 full-suite tests passed. Real B1
  artifacts produced 180 PDF classifications (3 unmatched) and 11 HTM
  classifications (0 unmatched); every signal's item IDs resolved.
- **Observed limitation:** Common role and rate words label many chunks. These
  are unscored initial guesses, subject to B3's LLM reflection.


### A5 PDF hierarchy configuration — 2026-09-30

- `uv run --frozen pytest -q`: 24 tests passed.
- The real `convert_document()` path converted
  `raw_documents/pdf/032_d35588dex101.pdf` with conversion profile
  `docling-json-v2-rapidocr-en-heading-hierarchy`.
- Its manifest recorded hierarchy inference and parsed-page generation as
  enabled for PDF; HTML tests recorded both as disabled.
- The canonical export contained four `section_header` items across levels 1
  and 2, confirming the built-in Docling stage ran.
- The source SHA-256 remained
  `4a04d3830220aee2f07a2074d42a334141e6fe6d7bbc05d15221c2b1e9ecce13`.

### A10 pure transformation — 2026-09-30

- `uv run --frozen pytest tests/test_hierarchy.py -v`: 17 tests passed.
- `build_hierarchy_sidecar()` traverses canonical body/group references without
  loading Docling or touching disk. It preserves reading order, item IDs,
  container ancestry, generic heading paths, and canonical page provenance.
- Exact tests cover `no_headings`, `flat_levels`, `skipped_levels`, and
  `non_monotonic_pages`. Unresolved references, group cycles, malformed heading
  levels, and conflicting `self_ref` values fail validation.
- A read-only check successfully processed all four existing canonical
  artifacts, ranging from 38 to 2,863 reading-order items.
- A10 is **Implemented** and is now invoked by A11 after canonical
  serialization.

### A11 Stage A integration — 2026-09-30

- `UV_CACHE_DIR=.uv-cache uv run --frozen pytest -q`: 46 tests passed.
- `tests/test_conversion.py` verifies deterministic sidecar persistence,
  manifest-last completion, enriched artifact paths, and cache invalidation for
  missing, malformed, mismatched-source, or unsupported-schema sidecars.
- Four materially different PDFs completed with all four artifacts and valid
  source-linked sidecars:
  - `032_d35588dex101.pdf`: 80 reading-order items, 0 tables, 1
    `skipped_levels` warning;
  - `011_credit_agreement.pdf`: 264 reading-order items, 7 tables, 5
    `skipped_levels` warnings;
  - `002_Facility_Agreement.pdf`: 2,863 reading-order items, 9 tables, 14
    `skipped_levels` warnings; and
  - `051_ACCO_Brands_Third_Amended_Credit_Agreement.pdf`: 1,908
    reading-order items, 23 tables, 20 `skipped_levels` warnings.
- The facility agreement was regenerated from an empty cache under conversion
  profile `docling-json-v3-rapidocr-en-hierarchy-sidecar-v1`; a repeated call
  returned `cached=True` without changing any artifact modification time.
- The long composite filing produced a Docling table-matching warning for 3 of
  203 PDF cells. Conversion and hierarchy validation still completed, and the
  warning remains a recorded parser limitation rather than a document-specific
  repair rule.

### B1 page-first chunking — 2026-09-30

- `UV_CACHE_DIR=.uv-cache uv run --frozen pytest tests/test_chunking.py -q`:
  23 focused tests passed.
- `UV_CACHE_DIR=.uv-cache uv run --frozen pytest -q`: 69 tests passed.
- Tests cover source rendering, table grids, page boundaries, same-page splits,
  atomic multi-page lists and tables, page-less attachment, heading-aware HTML
  fallback, exact-once reading order, deterministic neighbor links, malformed
  provenance rejection, atomic persistence, and cache invalidation.
- `002_Facility_Agreement.pdf` produced 180 page-first chunks covering all
  2,863 source items exactly once, including 158 chunks with explicit list
  groups and 9 table items. Five chunks spanned pages because atomic source
  structures crossed page boundaries; no chunk exceeded 12,000 characters.
- `012_tmb-20250627xex10d1.htm` produced 11 page-less chunks covering all
  1,523 source items exactly once. Its largest chunk contained 11,998
  characters and no page number or coordinate was invented.
- Repeated public API calls returned `cached=True` for both documents without
  changing artifact modification times.

## A10 transformation acceptance summary

- `document.docling.json` is byte-for-byte unchanged by A10.
- The returned hierarchy mapping has an explicit schema version and source
  SHA-256.
- Text and table entries refer back to canonical Docling item IDs.
- Heading paths use generic numeric depth; they do not require the agreement to
  use words such as *Article*, *Section*, or *Clause*.
- Warning codes are limited initially to `no_headings`, `flat_levels`,
  `skipped_levels`, and `non_monotonic_pages`.
- Missing or cyclic references fail validation instead of producing a plausible
  but untrustworthy hierarchy.

## Optional A10 acceptance — 2026-10-02

- Default conversion skips A10 and finalizes three artifacts; explicit
  `use_hierarchy=True` retains the historical four-artifact mode and caches.
- B1 traverses canonical references without rebuilding heading paths in off
  mode. Both modes pass through B4 and saved-run review with B2 on or off.
- Modes have separate directories, profiles and fingerprints. Enabled missing
  sidecars fail rather than silently becoming disabled. Annotation preparation
  remains explicitly enabled; no corpus or ground-truth data was changed.
- Saved 011 produced identical 29 chunks and 264 source items in both modes:
  text, page provenance, order and atomic membership stayed unchanged, while
  disabled heading paths were empty. No LLM calls or accuracy claims.
- Verification: `uv run --no-sync python -m pytest -q`: 298 passed.
  Independent review found no critical/important issues; `git diff --check`
  passed. See the optional-A10 plan for implementation details.

## A11 integration acceptance summary

- `document.hierarchy.json` persists the A10 mapping deterministically.
- Enabled cache completeness requires the sidecar and matching profile;
  disabled mode requires its explicit manifest declaration instead.
- Stage A returns a `ConversionArtifact` that includes the sidecar path only
  after the manifest has been finalized successfully.
