# Credit Agreement Corpus Audit — 2026-09-27

## Outcome

The preserved corpus contains 52 distinct agreement records, represented by 52 PDFs and 35 matching HTM source files. The 35 HTM files are not additional agreements because every HTM basename has a corresponding PDF basename.

A separate staging set now contains 100 additional English-language agreements. If all staged candidates are approved for import, the corpus would contain approximately 152 distinct agreements. Nothing in `raw_documents/` was changed.

## Existing corpus integrity

| Check | Result |
| --- | ---: |
| PDFs | 52 |
| PDFs readable by `pdfinfo` | 52 |
| HTM files | 35 |
| HTM files with matching PDFs | 35 |
| Gzip-encoded files carrying an `.htm` suffix | 25 |
| Ordinary HTML files | 10 |
| Gzip streams that fail integrity testing | 0 |
| Gzip streams that do not reveal recognizable agreement/HTML content after decompression | 0 |

The HTM files that display as binary junk are valid gzip streams saved with an `.htm` filename. This is a content-encoding/extension mismatch, not source-document corruption. A loader should sniff the gzip magic bytes and decompress before parsing; the preserved sources should not be renamed or rewritten.

Two PDFs are valid but contain essentially no extractable text in their first ten pages:

- `008_BAA_Redacted_Facility_Agreement.pdf`
- `050_Cirrus_Logic_Credit_Agreement.pdf`

Both rendered correctly during visual inspection and appear to be image-based scans. They need OCR rather than PDF repair.

## New staging set

Location: `corpus_staging/2026-09-27/`

| Selection | Count |
| --- | ---: |
| Broad SEC agreement selections (87 distinct registrant CIKs) | 90 |
| Named private-credit manager targets | 8 |
| Additional older European/cross-border examples | 2 |
| Total staged | 100 |

Formats are 68 HTM, 31 TXT, and 1 PDF. SEC originals were retained instead of converting them to PDF so that provenance remains direct and transformations stay outside the source corpus.

### Vintage coverage

| Agreement-date/filing-date bucket | Count |
| --- | ---: |
| 2007 and earlier | 56 |
| 2008–2014 | 18 |
| 2015 and later | 26 |

> Follow-up: a 2026-09-28 search found 20 additional agreements from 2015–2025, including five PDFs. All 20 passed case-by-case review and were imported into `raw_documents/`. The table above describes only the 2026-09-27 batch; see `docs/corpus_expansion_2026-09-28.md` for the follow-up.

For the 90 broad SEC selections, the date is the filing date. For the ten targeted private-credit and European examples, the date is the agreement date. This distinction is explicit in the manifest.

### Private-credit targets

| Manager | Agreement example | Classification |
| --- | --- | --- |
| Ares | Tempus Labs credit agreement (2022) | Direct lending to an operating company |
| Blackstone | GeneDx loan agreement (2026) | Direct lending to an operating company |
| AB Private Credit | Senior secured credit agreement (2025) | Fund-level corporate revolver |
| New Mountain | First amended and restated credit agreement (2024) | Fund leverage / warehouse |
| Goldman Sachs Private Middle Market | Second amended and restated loan and security agreement (2024) | Fund leverage / warehouse |
| FS KKR | Senior secured revolving credit agreement (2020) | Fund-level corporate revolver |
| Adams Street | Redwire/Cosmos credit agreement (2020) | Direct lending to an operating company |
| Partners Group | Facility agreement (2024) | Fund leverage / warehouse |

Public filings disclose fund-level financing more often than private operating-company loans. The manifest therefore separates `direct_lending_operating_company` from fund-level revolvers and warehouse facilities rather than treating them as one category.

### Leveraged-loan coverage

Forty-seven of the 90 broad SEC selections passed a conservative keyword screen requiring both:

1. a secured/term-loan signal such as `senior secured`, `first lien`, `second lien`, or `term loan agreement`; and
2. a leveraged-finance mechanic such as `excess cash flow`, `leverage ratio`, or `mandatory prepayment`.

This is a screening label, not a legal conclusion. The manifest records `likely_keyword_signal` so these agreements can be reviewed as a leveraged-loan subset without hiding the heuristic.

### European and cross-border coverage

The added targeted examples are:

- a 2006 senior facility agreement involving a Polish borrower, Netherlands entities, and Royal Bank of Scotland, embedded in a valid SEC-filed PDF; and
- a 2009 term loan credit agreement with Global Payments U.K. Ltd. as a borrower.

The broader selection also includes cross-border issuers such as Signet Jewelers, Novelis, Macquarie Infrastructure, and GLG Partners. Geography and governing law should be labeled independently in a later review; an EU or UK party does not by itself make an agreement EU- or English-law governed.

## Validation and provenance

Each staged file has a source URL, source format, byte size, SHA-256 digest, validation status, and selection rationale in `manifest.tsv`. The 90 broad candidates were required to have substantial extracted text, an agreement title near the beginning, and full-agreement structural markers. Amendment-only and waiver-only hits were excluded. Exact-content fingerprints were also checked against the 52 current PDFs and no exact duplicates were found.

## Import decision

The staged files are intentionally outside `raw_documents/`. Importing them into the preserved corpus requires explicit approval and should use stable identifiers plus the manifest, without overwriting or renaming existing source files.
