# Golden Set

This directory contains a curated review set for manual QA and regression checks.

Selection goals:
- cover common agreement shapes
- include at least one amendment
- include SEC/HTML-derived documents
- include large and small agreements
- include known extraction edge cases for parties and facility parsing

Selected PDFs:
- `011_credit_agreement.pdf`: small, straightforward baseline credit agreement
- `010_KYN-Term-Loan-Agreement-Dated-8.6.21.pdf`: preamble-defined parties and investment manager edge case
- `022_exhibit101-revolvingcredit.pdf`: revolving credit agreement in SEC exhibit format
- `029_exhibit101-firstamendmentt.pdf`: amendment document
- `008_BAA_Redacted_Facility_Agreement.pdf`: large redacted UK facility, multi-tranche style
- `003_first-lien-bridge-credit-agreement.pdf`: large bridge credit agreement
- `039_exhibit103-ablcreditagreem.pdf`: asset-based lending agreement
- `8-K-Term-Loan-Agreement-for-website.pdf`: investor-relations term loan agreement
- `049_Revolving_Facility_Agreement.pdf`: very large revolving facility agreement
- `012_tmb-20250627xex10d1.pdf`: modern SEC/HTML-derived agreement with regenerated PDF

Manifest:
- `golden_set_manifest.json` contains per-document review focus and expected count thresholds
- expected thresholds are used by `scripts/evaluate_golden_set.py` to flag extraction anomalies
- `expected_outputs.json` is the human-labeled ground truth file (optional but recommended)
  used for exact mismatch checks (missing expected parties, unexpected parties, count mismatches)

Notes:
- Files are physically moved here from `raw_documents/pdf/` and `raw_documents/htm/`.
- Symlinks are left behind at the original locations so existing code paths continue to work.
- Matching `.htm` files are included when the source exists.

Quick evaluation run:
```bash
venv/bin/python scripts/evaluate_golden_set.py --fail-on-anomaly
```

Annotation app (Phase 1):
```bash
venv/bin/streamlit run app/golden_set_labeler.py
```

Annotation outputs:
- per-document labels: `raw_documents/golden_set/labels/<pdf-stem>.json`
- exported expected outputs: `raw_documents/golden_set/expected_outputs.json`
- each labeled row carries provenance fields (`doc_id`, `page`, `block`, `line`, `provenance_id`, `text_snippet`)

Labeling notes:
- Populate `expected_outputs.json` one file at a time.
- `expected_parties` expects exact `{name, role}` pairs.
- `expected_counts` can include any of: `parties`, `facilities`, `covenants`, `amendments`.
