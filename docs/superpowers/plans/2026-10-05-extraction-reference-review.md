# Extraction reference review implementation plan

**Goal:** Make the agreed approve/edit/reject/skip, notes, save-and-next and
missing-fact workflow persistent for the eight-document draft reference.

**Agreed design:** A separate loopback Python review app reads the immutable
draft JSON and allowlisted original sources. Human decisions live in a
draft-hash-keyed SQLite database under ignored `evaluations/ground_truth/`.
Transactions enforce revisions across tabs/processes and retain every decision
version. No provider or pipeline imports, no promotion/scoring, no modification
to the topic-label editor. Existing static HTML remains a historical artifact.

**Tech:** Python 3.11/uv, standard-library SQLite/HTTP, plain HTML/JS. No packages.

## Tasks and acceptance

- [x] Back up existing annotation/draft files and record hashes before changes.
- [x] Add `tests/test_extraction_review.py`: save/reopen all decision types,
  stale-revision rejection, preserved history, custom facts with evidence,
  draft/source mismatch, HTTP write protection and source allowlisting.
- [x] Implement `extraction_review.py`: immutable draft loader, revisioned store,
  loopback routes, original-source preview and JSON decision export. Saves require
  exact origin, token, draft fingerprint, valid document/fact and explicit revision.
- [x] Implement `extraction_review.html`: document/fact navigation, evidence/source
  preview, editing, notes, save/save-next, add missing fact, progress, dirty-form
  protection and visible save/error/conflict states. Never advance on failed saves.
- [x] Run focused tests then existing annotation/boundary regression checks.
- [x] Browser-check a separate test fixture so QA never approves real draft facts.
- [x] Launch real review app, verify it loads original eight documents with no
  fabricated reviews; link user to the live page. Preserve old static HTML.
- [x] Update README, backlog, pipeline status prose and Obsidian context; verify
  original records/source/draft preservation before marking goal complete.

Approval means a human review decision, not automatic inclusion in a benchmark.
Export remains evaluation-only. Rejected/skipped facts are not approved reference
values, and unlisted fields remain unassessed. No paid model calls or commits.

Final verification: 39 tests passed (38 review/annotation plus backlog formatting).
Browser fixture verified approval reload, edited null reload and added-fact save;
real app verified eight documents and rendered original PDF. All preexisting
records preserved: 20 protected files byte-identical, one annotation file gained
21 records without changing/removing its earlier 321 records. Both backup ZIPs
verified; audit saved under `evaluations/ground_truth/review_backups/`.
