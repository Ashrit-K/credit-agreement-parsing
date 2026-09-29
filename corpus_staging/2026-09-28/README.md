# Recent-vintage credit agreement candidates — 2026-09-28

This staging batch contains 20 English-language agreements dated 2015–2025, selected to expand the corpus's 2015-and-later segment.

## Contents

- 5 PDF files: 1 standalone native SEC exhibit and 4 SEC filing PDFs that embed a complete credit agreement
- 15 standalone SEC HTML exhibits
- 1 direct-private-credit agreement (RxSight / Oxford Finance)
- 1 Blackstone fund-level leverage agreement and several senior-secured or leveraged-loan examples

The four filing-container PDFs are retained in their original form. `agreement_start_page` in `manifest.tsv` identifies where each agreement begins.

## Validation performed

- Confirmed each candidate contains a complete agreement rather than only a financing summary or amendment reference.
- Extracted text and checked substantial agreement structure and operative provisions.
- Rendered and visually inspected the agreement title page in every PDF.
- Compared SHA-256 hashes against `raw_documents/` and `corpus_staging/2026-09-27/`; no exact file duplicates were found.

Rejected search hits—including annual reports, short filing summaries, and filings that merely referenced an agreement—are not included.

## Import status

Following case-by-case review, all 20 candidates were accepted and moved into `raw_documents/` on 2026-09-28. The `documents/` directory is intentionally empty. `import_mapping.tsv` records each original candidate filename, final raw path, verdict, and case-specific basis; `manifest.tsv` preserves source URLs and original hashes.
