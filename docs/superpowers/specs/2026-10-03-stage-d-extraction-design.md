# Stage D: orchestrated credit-term extraction

Approved direction: one public orchestrator, one specialist, three field
families: parties, facility amounts and interest. Build on `main`; preserve
unrelated changes. This specification records the 2026-10-03 discussion.

## Architecture

Use fixed Python coordination, not another orchestration LLM or framework.
One specialist makes a combined extraction request for the three overlapping
families. Its source access is a narrow retrieval tool wrapping existing B4/B5.
The orchestrator alone accepts the job and returns the final document JSON.
This is a bounded extraction pipeline, not an autonomous multi-agent loop.

- D1: validate job/readiness and coordinate the specialist.
- D2: specialist obtains original topic evidence and calls shared Stage C.
- D3: validate output, citations, entity references and supported rate arithmetic.
- D4: persist the completed result and provenance manifest; return JSON.

B3 completion triggers D1 through a direct call from a new composed Python
runner. `topic_map_ready` is an observable event, not a queue or polling service.
Standalone B3 must stay free of hidden paid calls. Saved completed maps can be
passed directly to the orchestrator. B4/B5 remain shared demand-driven tools;
they are not moved or renumbered. C remains an isolated cross-cutting interface.

## Public boundaries

`extract_credit_terms(topic_map, chunks, *, conversion=None, client=None,
model=None, reasoning_effort="medium", api_style=None, output_root="tmp/stage_d",
debug=False, run_id=None, trace_root="tmp/runs") -> dict` is the Stage D entry.
It accepts source artifact handles, not a new PDF or reference answers.

`run_pipeline(path, *, client=None, model=None, reasoning_effort="medium",
classification_model=None, classification_reasoning_effort="medium",
use_hierarchy=True, debug=False, run_id=None, trace_root="tmp/runs") -> dict`
chains A → B1 → B2 → B3 → D. Extraction and classification overrides are
independent; defaults of existing A/B/C calls do not change. All work shares a
run ID. Retain the old `extract_parties()` scaffold without changing its contract.

## Specialist and evidence policy

The initial specialist requests approved topics explicitly: `parties_and_roles`,
`facility_and_commitment_terms`, `interest_and_fees`, `contract_definitions`,
plus the interest PIK subtopic if present in the vocabulary. Use actual taxonomy
IDs from `topic_taxonomy.py`, never broad phrases or guessed IDs.
All matching groups are delivered intact, with evidence/context distinctions,
original text, pages, headings and canonical table data. No source summaries,
truncation, full-document fallback or ground-truth reads.

One combined model request minimizes repeated context and identity reconciliation.
Maximum two attempts for retryable transport or output-validation failures;
authentication and model substitution stop immediately. Validation feedback
contains concise machine diagnostics, not model reasoning or secrets.
No additional classification/verifier layer, automatic evidence broadening or
unbounded tool loop in this increment. Empty retrieval returns empty collections
and an explicit missing-information note without a paid call.

## Result contract

Keep the agreed top-level `document_id`, `parties`, `relationships`, `facilities`
and `interest`. Add `schema_version`, `status`, and `issues` for lifecycle and
missing/uncertain fields without treating an empty list as proof of absence.

- Parties have local `party_id`, name, agreement roles, status and evidence IDs.
  A parent with no agreement role has `roles=[]`. No `borrower_parent` role.
- Relationships use only `parent_party_id` and `child_party_id`, status and
  evidence IDs. Both parties must exist; self-links and cycles are rejected.
- Facilities have `facility_id`, nullable type/currency, a supported or explicitly
  missing/uncertain amount record and lender commitments using party references.
  Amount records retain kind: commitment, outstanding, original or amended.
- Interest records link to a facility. Rates are finite JSON numbers expressed
  as fractions (`0.04` means 4%), never numeric strings or percentage-unit numbers.
  Preserve benchmark, margin, benchmark floor, readable formula, payment
  frequency, day count and evidence IDs. Separate alternative rate options.
  Preserve `rate_period` and `term_kind` (interest versus fee); do not annualize
  a monthly percentage or confuse a one-time charge with a loan interest rate.
- `supported`: evidence establishes the value; not a correctness guarantee.
  `missing`: selected evidence does not establish it; not proof it does not exist.
  `uncertain`: relevant evidence is ambiguous; give a concise issue.
  `not_applicable`: evidence establishes that it does not apply.
- Total rate has value, status, missing inputs. `missing_inputs` means the
  formula is known but an applicable numeric input/condition is not available.
  Never fetch current benchmark rates or assume a pricing-grid row.

The model does not provide document identity or schema lifecycle metadata;
Python attaches them. The model receives the output schema and returns only
the extraction sections plus issues. Do not make it repeat topic definitions.
Every nonempty entity/fact record must cite supplied original items. Citation
existence checks cannot establish whether the legal interpretation is correct.
Record-level citations are the agreed initial scope; per-attribute provenance
is a future refinement, not implied by validation.

## Rate calculation

Never evaluate the readable formula as Python. Use a typed optional calculation
record with `kind` (`fixed` or `benchmark_plus_margin`), fixed/benchmark/margin/
floor rates, applicability evidence IDs and missing inputs. Python computes
with `Decimal(str(number))`, then emits a JSON number. Fixed supported rates
can be reported; floating totals require all applicable inputs and a source
establishing their applicability. No calculation is attempted from a free-text
formula or incomplete/conditional grid. Reject contradictory model totals.
The normalized calculation record stays in the result for reproducibility.
Python fills a missing total from complete applicable cited inputs, but never
overrides uncertainty. Any numeric total, including an uncertain candidate,
must agree with the typed calculation. Facility identity needs its own or nested
amount/commitment citations even when the amount itself is missing.

## Validation and completion

Pydantic v2 models reject extra fields, strings for numbers, booleans as numbers,
nonfinite/negative amount or rate values, empty names/IDs, unsupported statuses
and malformed collections. Entity references must resolve uniquely; duplicate
IDs/names and nonexistent facility references fail. Lender commitments must
reference a party with the lender role. Citation IDs must resolve within the
retrieved packet, not merely somewhere in the document. Verify map/B1/Stage A
bindings using existing B4/B5 validation before the first call.

Save only validated completed outputs, atomically, in a unique execution folder
under `tmp/stage_d/<source-sha256>/`. The manifest includes source inputs,
topic/evidence fingerprints, model/effort, prompt/schema version and result hash.
Write manifest last. Failed executions retain debug diagnostics but never
overwrite historical successful results or return a partial completed object.

Basic traces always record D1–D4 boundaries, readiness, attempts, usage, latency
and cost through shared C. Debug traces add evidence packets, exact prompts,
visible responses, validation diagnostics and final artifacts. No keys, hidden
reasoning, authorization headers or human reference labels are captured.

## Acceptance and non-goals

Test schema/rates/citations/relationships independently, inject fake clients for
orchestration and retry tests, test the composed readiness handoff and A10 modes.
Run full regressions. Run one source-only saved 011 extraction without rerunning
classification; retain real output/telemetry for human review. This smoke proves
wiring, not legal accuracy. Do not build a new HTML surface, Phoenix integration,
ground-truth authoring, corporate research, new agents/frameworks or all-field
extraction. Update backlog, diagram, README, AGENTS and Obsidian after acceptance.
