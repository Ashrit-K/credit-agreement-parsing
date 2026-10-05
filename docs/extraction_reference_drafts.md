# AI-assisted extraction reference — 2026-10-04

An offline first pass covers **all eight approved golden documents**, with
**97 proposed facts** across parties, facility amounts and interest/fees.
Coverage within each document is partial, with remaining questions explicitly
listed. These drafts are not approved ground truth or an accuracy benchmark.

Local artifacts (intentionally Git-ignored):

- `evaluations/ground_truth/extraction_drafts/2026-10-04/review.html` — read-only
  agreement selector, proposed values and expandable original source evidence.
- `reference.draft.json` in that directory — machine-readable proposals,
  stable fact IDs, source/canonical hashes, citations and review status.
- `verification.json` — source/citation checks and annotation-preservation hashes.
- `final-preservation.json` — final record-level preservation audit, allowing
  additive saves made in the annotation UI during preparation.
- `existing-annotations.backup.zip` — verified redundant copy of the 12 existing
  annotation JSON files and review notes (eight JSON files plus four notes).
- `existing-annotations.final-snapshot.zip` — second snapshot preserving new
  concurrent saves as well as the original records.

| Golden document | Proposed facts |
| --- | ---: |
| 011 Amerigo | 14 |
| 002 Informa | 11 |
| 003 American Axle | 13 |
| 008 BAA | 13 |
| 012 Conagra | 10 |
| 010 KYN | 11 |
| 057 Radio One | 8 |
| 067 RxSight/Oxford | 17 |

## How to review

Use the separate local review app, not the historical static `review.html`:

```bash
uv run --no-sync python -m credit_agreement_extractor.extraction_review --port 60902
```

Open http://127.0.0.1:60902/. Select an agreement and fact, inspect the original
source and cited wording, then choose **Approve original**, **Edit & approve**,
**Reject**, or **Unsure**. Add notes and press **Save review** or **Save & next**.
**Add missing fact** records an extra field/value with source evidence. PDF page
numbers are one-based; HTML uses source locators without invented page numbers.

Decisions persist under `evaluations/ground_truth/extraction_reviews/` in a
draft-hash-keyed SQLite database. Transactional revision checks prevent stale
tabs from overwriting newer saves; every saved version remains in history.
Reload restores saved decisions. Unsaved edits require confirmation on navigation.
The immutable AI draft and existing passage-labeling app remain unchanged.
**Export saved reviews** downloads a separate evaluation-only JSON packet.

Every proposed fact is `unreviewed_ai_draft`; the bundle has
`scoring_eligible=false`. Review both the proposed value and its support, and
check for omissions. Unlisted fields are **unassessed**, not negative labels.
Unknown/redacted values are distinct from zero. Rates are numeric fractions
with explicit annual/monthly/per-advance periods.

Human approval controls are implemented; actual human review, reference promotion
and a field-level scorer remain pending. Approval does not automatically make the
entire export scoring-eligible. Later scoring
must use a separate frozen, approved snapshot after independent model execution.
Drafts, approved answers and reviewer corrections must never enter conversion,
classification, retrieval, extraction or provider prompts.

## Preparation and limitations

Codex drafted from original canonical source items and targeted independent PDF
checks, without reading Stage D predictions or using topic labels as answers.
No paid OpenCode requests were made. Existing label files were copied for backup
and hashed for integrity only. All 12 protected files were byte-identical before
and after initial packaging; source and canonical hashes were also verified.
The final audit found additive saves in 067 during this work and verified all
pre-existing annotation records remained exactly unchanged. Those additions
were preserved in a second snapshot; no old backup was restored over live data.

Citation resolution establishes traceability, not semantic correctness. This is
an initial, selective reference rather than an exhaustive inventory of every
lender, parent link, facility, pricing condition or fee.

Specific review findings:

- **011:** 1.5% interest is monthly; the 1% standby fee is annual and the 1.5%
  drawdown fee is per advance. Shareholding/adviser roles do not prove parenthood.
- **002:** the arranger and original lender have different legal names. Ticking
  fee percentages multiply the margin; they are not standalone interest rates.
- **003:** the bridge facility must remain separate from existing and second-lien
  debt. Total Cap and fee-letter terms still need review.
- **008:** both margins are visibly blacked out on PDF page 16. Missing pricing
  must remain unknown rather than receiving plausible invented rates.
- **012:** preserve the full rating grid without guessing the active rating.
  The pricing columns were checked against PDF page 7.
- **010:** the inspected canonical text omits the fixed-rate tranche. Direct PDF
  checks recover USD25m under Clause 2.1(a), 1.735% annual fixed interest and
  day-count wording. These citations use physical PDF pages, without inventing
  Docling IDs. Conversion-gap diagnosis/fixing is separate work.
- **057:** the PDF contains multiple instruments. This draft uses the credit
  agreement exhibit, not the indenture's separate note coupon.
- **067:** USD60m is aggregate conditional commitments, not initial funded debt.
  Fund management is not automatically a corporate-parent relationship.

The saved script uses exclusive file creation: rerunning cannot overwrite the
packet or backup. Do not rerun it over reviewed work; produce a new version for
future revisions. The historical static HTML lacked editing controls. The new
local review app was browser-tested with isolated fixture saves/reloads, explicit
null edits and added facts; the real eight-document view and PDF preview were
also checked without saving fabricated decisions. Focused review/annotation
tests passed (38). A separate pre-change backup and preservation audit live under
`evaluations/ground_truth/review_backups/extraction-review-20261005-93e160db/`.
