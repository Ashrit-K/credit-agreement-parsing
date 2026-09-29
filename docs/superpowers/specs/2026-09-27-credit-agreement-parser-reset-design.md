# Credit Agreement Parser Clean-Slate Design

**Status:** Approved design; implementation pending
**Date:** 2026-09-27

## Purpose

Reset the project workspace so future development starts from a small, explicit baseline. Preserve the downloaded PDF and HTML corpus as source material. Remove the previous parser implementation and Golden Set workflow rather than carrying forward undocumented assumptions.

## Project outcome

The eventual system accepts a credit agreement PDF and emits structured JSON. Initial information areas include:

- Borrower and lender details
- Interest rates, payment timing, and other interest terms
- Principal, repayment, and amortization terms
- Call protection
- Covenants and other material agreement terms

LLMs are expected to participate in extraction and parsing. Whether the system is a document pipeline, an agentic loop, or a hybrid remains an open design decision for later, incremental work. This reset does not prescribe implementation language, model provider, agent topology, or final JSON schema.

## Reset boundary

### Preserve

- Git repository history (`.git`)
- `.gitignore`
- `raw_documents/pdf/`
- `raw_documents/htm/`
- New root `AGENTS.md`
- This fresh baseline design document

### Remove

- `raw_documents/golden_set/`, including manifests, expected outputs, labels, and review notes
- Existing application, parser source, tests, API docs, implementation plan, and download/evaluation scripts
- Root source-list CSVs
- `.env` and `.claude/` local settings, per selected strict-reset scope
- `.venv/`, `.pytest_cache/`, and `.DS_Store` artifacts

### Preserve Golden Set source files

Golden Set currently owns physical copies of 10 PDFs and 4 HTML files. Their original paths in `raw_documents/pdf/` and `raw_documents/htm/` are symlinks into Golden Set. Before deleting that directory, replace each link with a regular file containing the linked source bytes. Verify all 52 PDF paths and 35 HTML paths remain available under the raw directories, then remove Golden Set. No source document is to be discarded as part of the reset.

## Initial `AGENTS.md` guidance

The root instructions file will establish these project rules:

1. Treat PDFs and HTML under `raw_documents/` as immutable input corpus; do not delete, overwrite, or silently transform originals.
2. Keep project goal centered on PDF input and structured JSON output, with the information areas listed above.
3. Require extracted facts to retain source evidence such as page/section and a short text excerpt when the source supports it.
4. Represent missing or uncertain values explicitly; do not invent facts or confuse absence with zero/false.
5. Avoid document-specific hardcoding. Validate changes across varied agreements and add representative cases as the corpus grows.
6. Make architecture and LLM/agent choices incrementally; capture decisions before broad implementation.
7. Prefer small, verifiable changes with focused tests and clear data-flow boundaries.
8. Link to the existing Obsidian project note: [Credit Agreement Parser](file:///Users/ashrit/Library/Mobile%20Documents/iCloud~md~obsidian/Documents/Obsidian_ashrit/Projects/Credit%20Agreement%20Parser.md).

## Obsidian project record

After the workspace reset is complete, update the existing `Projects/Credit Agreement Parser.md` note to record that the project is starting over after the slate-clean reset. Preserve prior tool research as historical context, not as current architecture decisions. Record the new outcome focus and that pipeline-versus-agent design remains open. Update the local-date daily note per vault workflow.

## Success criteria

- Golden Set directory and old implementation artifacts are absent from the working tree.
- `raw_documents/pdf/` contains 52 usable regular PDFs; `raw_documents/htm/` contains 35 usable regular HTML sources.
- No retained raw-document path depends on `raw_documents/golden_set/`.
- Git history and `.gitignore` remain.
- Root `AGENTS.md` and this fresh design document describe the agreed project outcome and guardrails.
- No parser architecture or schema is implemented during reset.
