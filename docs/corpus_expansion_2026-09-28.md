# Credit agreement corpus expansion — 2026-09-28

## Outcome

Twenty additional English-language agreements dated 2015–2025 were initially staged in `corpus_staging/2026-09-28/`. After case-by-case review, all 20 were accepted and moved into `raw_documents/`.

| Format | Count | Qualification |
| --- | ---: | --- |
| PDF | 5 | One standalone exhibit; four filing PDFs containing the complete agreement |
| HTM | 15 | Complete standalone SEC exhibits |
| Total | 20 | No exact duplicates against the raw corpus or prior staging batch |

The earlier 2026-09-27 batch contained one PDF, 68 HTM files, and 31 plain-text files. It was therefore not entirely HTML/plain text.

## Vintage impact

The prior staged batch contained 26 agreements dated 2015 or later. This follow-up adds 20 more, raising reviewed recent-vintage coverage across raw and staging to 46 agreements. The raw corpus now contains 72 distinct agreements; approving the separate 100-document 2026-09-27 staging batch would raise the combined total to 172.

| Agreement year | Added |
| --- | ---: |
| 2015 | 1 |
| 2018 | 1 |
| 2020 | 1 |
| 2021 | 1 |
| 2022 | 5 |
| 2023 | 1 |
| 2024 | 8 |
| 2025 | 2 |

## PDF findings

Native standalone PDF credit-agreement exhibits are uncommon in the SEC archive. Search results frequently point to annual reports or filing PDFs that only summarize a facility. Five PDF candidates survived full-document screening:

1. Designer Brands (2022): standalone 223-page credit-agreement PDF.
2. Edward Jones (2018): full agreement embedded in a 10-Q PDF, beginning on PDF page 48.
3. Radio One (2015): full agreement embedded in an 8-K PDF, beginning on PDF page 123.
4. Denbury (2020): full agreement embedded in an 8-K PDF, beginning on PDF page 58.
5. Blackstone Private Equity Strategies vehicle (2024): full agreement embedded in a 10-Q PDF, beginning on PDF page 63.

All five agreement title pages were rendered and visually checked, and their extracted text was reviewed for complete agreement structure.

## Private credit and leveraged lending

- RxSight / Oxford Finance (2023) is a direct-private-credit loan and security agreement.
- The Blackstone Private Equity Strategies vehicle agreement (2024) is a fund-level leverage example.
- Radio One, Denbury, CIRCOR, Bandwidth, Magnite, and Genesis Energy provide senior-secured, leveraged, or restructuring-oriented examples.

The exact source URLs, fingerprints, dates, page offsets, and validation notes are recorded in `corpus_staging/2026-09-28/manifest.tsv`. The case-by-case decisions are in `docs/corpus_import_review_2026-09-28.md`, and the final raw paths are in `corpus_staging/2026-09-28/import_mapping.tsv`.
