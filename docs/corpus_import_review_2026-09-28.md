# Case-by-case import review — 2026-09-28

## Decision standard

A candidate was accepted if it contains a substantive, identifiable credit or loan agreement with operative terms—not merely a financing summary, amendment notice, term sheet, or press release. Review checked title and parties, operative provisions, agreement structure, execution/signature evidence, exhibits or schedules, file integrity, and duplication against the existing raw corpus.

All 20 candidates passed. No candidate was held back.

## PDF candidates

| Candidate | Case-specific assessment | Verdict |
| --- | --- | --- |
| Radio One (2015) | The SEC 8-K PDF contains the complete executed credit agreement beginning on PDF page 123. It has a distinct title page, extensive operative sections, signature material, and exhibits. Later pages return to filing material, but the embedded agreement itself is complete. | Import |
| Edward Jones (2018) | The SEC 10-Q PDF contains complete Exhibit 10.1 beginning on PDF page 48: a $500 million agreement among the Jones entities, lenders, and JPMorgan. Operative provisions, signatures, and exhibits are present. | Import |
| Denbury (2020) | The SEC 8-K PDF contains the complete restructuring/exit credit agreement beginning on PDF page 58. It includes extensive operative provisions, lender and agent terms, signatures, and exhibits. | Import |
| Designer Brands (2022) | This is a standalone 223-page native exhibit PDF rather than a filing container. The agreement runs from its title page through schedules and exhibits and is structurally complete. | Import |
| Blackstone PES vehicle (2024) | The SEC 10-Q PDF contains complete Exhibit 10.1 beginning on PDF page 63. It is a valid fund-level leverage agreement for BXPE US Aggregator, with complete operative provisions and exhibits. | Import |

All five PDFs passed `pdfinfo`, text extraction, structural-marker review, and visual inspection of their agreement title pages. The four filing-container PDFs are retained as useful real-world parser stress cases; their filenames identify the container type.

## HTML candidates

| Candidate | Case-specific assessment | Verdict |
| --- | --- | --- |
| CIRCOR (2021) | Complete executed credit agreement with definitions, facilities, covenants, defaults, signatures, and exhibits. | Import |
| AT&T (2022) | Complete amended and restated $7.35 billion term-loan agreement. Lender signature pages are intentionally omitted and expressly labeled, a normal SEC filing convention; the operative agreement is complete. | Import |
| Amazon (2022) | Complete executed 364-day revolving credit agreement, including operative articles, signature pages, and exhibits. | Import |
| Bandwidth (2022) | Complete senior-secured credit facilities agreement with extensive operative sections, security-related terms, signatures, and exhibits. | Import |
| Hyatt (2022) | Complete executed revolving credit agreement with full operative terms and lender signatures. | Import |
| RxSight / Oxford Finance (2023) | Complete loan and security agreement and a strong direct-private-credit example. Limited confidential information is omitted under Regulation S-K and clearly disclosed; this does not make the agreement unusable or incomplete for corpus purposes. | Import |
| Alexandria Real Estate (2024) | Complete third amended and restated agreement with operative articles, signatures, and exhibits. | Import |
| Comcast (2024) | Complete executed credit agreement with operative provisions, signatures, and exhibits. | Import |
| Magnite (2024) | Complete leveraged/senior-secured credit agreement with extensive provisions, signatures, and exhibits. | Import |
| Cummins (2024) | Complete second amended and restated agreement with operative provisions, signatures, and schedules. | Import |
| Genesis Energy (2024) | Complete seventh amended and restated leveraged credit agreement with operative provisions, signatures, and exhibits. | Import |
| Petroleum Heat and Power (2024) | Complete seventh amended and restated agreement with operative provisions, signatures, and exhibits. | Import |
| Spire (2024) | Complete second amended and restated loan agreement with operative provisions, signatures, and exhibits. | Import |
| CBRE 364-day facility (2025) | Complete $1 billion 364-day revolver. It is not a duplicate of existing raw document `013_cbre-ex10_1.htm`, which is the separate $3.5 billion five-year companion revolver executed on the same date. | Import |
| Hershey (2025) | Complete five-year revolving credit agreement with operative provisions, signatures, and exhibits. | Import |

## Import result

The accepted files are mapped to stable, descriptive raw-corpus filenames in `corpus_staging/2026-09-28/import_mapping.tsv`. Original hashes and source URLs remain in `corpus_staging/2026-09-28/manifest.tsv`.
