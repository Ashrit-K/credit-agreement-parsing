# Credit Agreement Parser Clean-Slate Reset Implementation Plan

> **For agentic workers:** Implement this plan task-by-task inline, with verification checkpoints. Do not delegate file deletion or corpus preservation.

**Goal:** Remove legacy parser artifacts and Golden Set while preserving every downloaded PDF/HTML source, establishing root project guidance, and recording the restart in Obsidian.

**Architecture:** Keep Git history and `.gitignore`. Materialize Golden Set symlink targets into their original raw paths before deleting Golden Set. Then remove selected legacy files, create `AGENTS.md`, and update the existing Obsidian project and daily notes.

**Tech Stack:** Filesystem operations, Markdown, Git, Obsidian-flavored Markdown; no parser code or dependencies.

## Global Constraints

- Preserve all 52 PDF paths under `raw_documents/pdf/` and all 35 HTML paths under `raw_documents/htm/`.
- Never alter source-document bytes; replace links with copies of their targets before removing `raw_documents/golden_set/`.
- Keep `.git/`, `.gitignore`, the approved reset spec, and this plan.
- Remove both source CSVs, `.env`, `.claude/`, caches, `.venv/`, old scripts, and `raw_documents/golden_set/` per strict-reset choice.
- Do not commit or change parser architecture/schema.

---

## Files and Responsibilities

- `raw_documents/pdf/`: keep all downloaded PDF inputs; materialize 10 Golden Set symlinks here.
- `raw_documents/htm/`: keep all downloaded HTML inputs; materialize 4 Golden Set symlinks here.
- `raw_documents/golden_set/`: remove after preservation verification.
- Root `AGENTS.md`: project goals, source-data safeguards, evidence/generalization rules, and Obsidian project-note link.
- `docs/superpowers/specs/2026-09-27-credit-agreement-parser-reset-design.md`: approved baseline scope; retain.
- `docs/superpowers/plans/2026-09-27-clean-slate-reset.md`: execution checklist; retain.
- Obsidian `Projects/Credit Agreement Parser.md`: record clean-slate restart and outcome focus.
- Obsidian `Daily/2026-09-27.md`: log project reset work for local date.

## Task 1: Capture Pre-Reset Corpus Inventory

**Files:** Read only.

- [x] Record the 10 Golden Set PDF names from `golden_set_manifest.json` and the 4 HTML symlink names from `raw_documents/golden_set/htm/`.
- [x] Confirm each matching path under `raw_documents/pdf/` or `raw_documents/htm/` is a symlink targeting `../golden_set/...`.
- [x] Capture SHA-256 hashes of all 14 Golden Set source targets and verify their target paths exist.
- [x] Confirm starting path counts: 52 PDFs and 35 HTML files.

Expected PDF names to restore:

```text
003_first-lien-bridge-credit-agreement.pdf
008_BAA_Redacted_Facility_Agreement.pdf
010_KYN-Term-Loan-Agreement-Dated-8.6.21.pdf
011_credit_agreement.pdf
012_tmb-20250627xex10d1.pdf
022_exhibit101-revolvingcredit.pdf
029_exhibit101-firstamendmentt.pdf
039_exhibit103-ablcreditagreem.pdf
049_Revolving_Facility_Agreement.pdf
8-K-Term-Loan-Agreement-for-website.pdf
```

Expected HTML names to restore:

```text
012_tmb-20250627xex10d1.htm
022_exhibit101-revolvingcredit.htm
029_exhibit101-firstamendmentt.htm
039_exhibit103-ablcreditagreem.htm
```

## Task 2: Materialize Golden Set Inputs

**Files:** Modify 10 PDF paths and 4 HTML paths under `raw_documents/`.

- [x] For each listed path, remove only the symlink at the raw path, then copy the corresponding target file from `raw_documents/golden_set/` to that exact raw path.
- [x] Confirm each destination is a regular file, not a symlink.
- [x] Recompute SHA-256 for all 14 restored destinations and compare with Task 1 hashes.
- [x] Confirm raw path counts remain 52 PDFs and 35 HTML files.

Do not run the old downloader or converter scripts during this reset; they can overwrite, regenerate, or add corpus files.

## Task 3: Remove Legacy Workspace Artifacts

**Files:** Delete only the approved paths.

- [x] Delete `raw_documents/golden_set/` after Task 2 verification.
- [x] Delete root `corporate_credit_agreements.csv` and `corporate_credit_agreement_source_urls_50.csv`.
- [x] Delete root `.env`, `.claude/`, `.venv/`, `.pytest_cache/`, and `.DS_Store`.
- [x] Delete `raw_documents/.DS_Store`.
- [x] Delete `scripts/` and any remaining legacy `app/`, `src/`, `tests/`, and old `docs/` content. Preserve the two fresh `docs/superpowers/` files listed above.
- [x] Keep `.git/` and `.gitignore`.

## Task 4: Establish Root Project Guidance

**Files:** Create `AGENTS.md`.

- [x] State the project outcome: PDF input, structured JSON output covering borrower/lender, interest/payment, principal/repayment, call protection, covenants, and other material terms.
- [x] State that LLM participation is intended while pipeline-versus-agent architecture remains open.
- [x] Protect raw PDFs/HTML from deletion, overwrite, or silent transformation.
- [x] Require source evidence for extracted facts when available, explicit uncertainty, and validation across varied documents to avoid overfitting.
- [x] Require incremental design decisions, focused tests, and verifiable changes.
- [x] Add a Markdown file link to the existing Obsidian note:
  `file:///Users/ashrit/Library/Mobile%20Documents/iCloud~md~obsidian/Documents/Obsidian_ashrit/Projects/Credit%20Agreement%20Parser.md`.

## Task 5: Update Obsidian Project Record

**Files:** Modify existing project note; create local-date daily note from its template.

- [x] In `Projects/Credit Agreement Parser.md`, record the September 27, 2026 clean-slate restart after cleanup is complete.
- [x] Update Overview to the new outcome focus; state that old tools/research are historical context, not selected architecture.
- [x] Keep prior research available as history; clear `tech_stack` because no implementation stack is selected.
- [x] Update `What's Next` to start with defining the first JSON fields and validating them across representative agreements; leave agent-vs-pipeline choice open.
- [x] Create `Daily/2026-09-27.md` from `Templates/Daily Note.md` if absent. Fill actual frontmatter values and add a bullet under `## Projects Worked On` summarizing the restart and preservation of the raw corpus.
- [x] Follow vault link-propagation rules for any newly introduced wikilinked entities; do not create People/Organization pages for simple name mentions.

## Task 6: Verify Reset

- [x] Confirm `raw_documents/golden_set/`, `.env`, `.claude/`, `.venv/`, source CSVs, and legacy code/script directories are absent.
- [x] Confirm `raw_documents/pdf/` still contains exactly 52 readable PDF files and `raw_documents/htm/` exactly 35 readable HTML files.
- [x] Confirm no raw-document symlink points into the removed Golden Set.
- [x] Confirm the 14 restored file hashes match their pre-reset hashes.
- [x] Confirm `.git/`, `.gitignore`, `AGENTS.md`, the approved spec, and this plan remain.
- [x] Read back the Obsidian project and daily notes and confirm restart wording and local date.
- [x] Report expected Git deletions and new files; do not stage or commit.

Validation note: `pdfinfo` accepted all 52 PDFs. `raw_documents/pdf/002_Facility_Agreement.pdf` emits a non-fatal Poppler warning: `Invalid number of shared object groups`.
