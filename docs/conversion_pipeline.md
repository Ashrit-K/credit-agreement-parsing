# Document Conversion Pipeline

The conversion layer turns one preserved source agreement into two complementary
representations plus a small operational manifest. It runs locally and does not
call OpenCode or any other LLM service.

## Python entry point

```python
from credit_agreement_extractor import convert_document

artifact = convert_document("raw_documents/pdf/example.pdf")

print(artifact.docling_json_path)
print(artifact.markdown_path)
print(artifact.manifest_path)
```

The default output root is `tmp/converted/`. Each source is placed in a folder
named with its SHA-256 fingerprint. Callers do not calculate or supply this
fingerprint: the function calculates it from the source bytes. Repeating a call
with identical source bytes reuses a complete cached conversion only when its
conversion-profile identifier also matches the current settings.

This cache short circuit is currently a development optimization that reduces
latency while the pipeline is being built and tested. It is not the intended
default production route: absent an explicit production cache policy, a
production run should continue through content-type routing and conversion so
the submitted document is processed in that run.

## Generated artifacts

- `document.docling.json` is the canonical conversion. It retains Docling's
  document items, hierarchy, item identifiers, and available provenance such as
  page numbers, character spans, and bounding boxes.
- `document.md` is a readable derivative. It is useful for manual review and for
  constructing concise LLM input, but it is not the source of truth for page
  geometry.
- `manifest.json` records source identity, converter version, OCR configuration,
  conversion profile, gzip normalization, artifact names, and conversion status.

OCR is enabled only for PDF conversion. The manifest records configuration, not
a claim that OCR was necessary on a particular born-digital page; Docling's
default OCR mode decides which page regions need recognition.

Several SEC-sourced `.htm` files are actually gzip streams. The function detects
the gzip signature from the bytes, creates a temporary plain-HTML copy for
Docling, and removes that copy afterward. It never rewrites the source file.

## Evidence rule

Future extraction code should chunk all text from the canonical JSON while
retaining the corresponding Docling item identifiers, such as `#/texts/17`. A
cheap selector LLM will review every chunk and over-select items that may support
the requested fields. Deterministic structural candidates, such as the opening
party block, definitions, lender tables, guarantor provisions, and signature
blocks, are unioned with the LLM selections so the selector cannot discard those
anchors.

The extraction LLM may cite retained item identifiers, but it must not invent
page numbers or coordinates. Application code will resolve every cited item and
copy its verified provenance into the structured extraction result. Missing or
uncertain required fields trigger broader retrieval and another selector pass.

The selector is designed to improve recall, not guarantee correctness. Its miss
rate must be measured on representative agreements before its output can be used
to exclude evidence permanently.

## Pipeline

Status and cognitive work use separate visual signals:

- Capital letters identify major stages; the number identifies a component or
  decision within that stage, such as `B3`.
- Solid borders and arrows mean implemented and tested.
- Dashed borders and arrows mean pending.
- Purple boxes identify LLM or other cognitive inference steps, regardless of
  implementation status.

The diagram is updated as each increment is completed.

```mermaid
flowchart TD
    subgraph A_GROUP["A — Document intake and conversion"]
        A1[A1 — PDF, HTML, or HTM path] --> A2[A2 — Validate and calculate SHA-256]
        A2 --> A3{A3 — Complete cached artifacts? Development only}
        A3 -->|Yes — temporary development shortcut| A10[A10 — Return ConversionArtifact]
        A3 -->|No — cache miss| A4{A4 — Document format router}
        A2 -.->|Target production route — bypass cache| A4
        A4 -->|PDF| A5[A5 — Docling PDF pipeline and local English OCR]
        A4 -->|Plain HTML| A6[A6 — Docling HTML pipeline]
        A4 -->|Gzip-wrapped HTML| A7[A7 — Temporary local decompression]
        A7 --> A6
        A5 --> A8[A8 — Canonical DoclingDocument]
        A6 --> A8
        A8 --> A9[A9 — Write Docling JSON, Markdown, and manifest]
        A9 --> A10
    end

    subgraph B_GROUP["B — Evidence candidate selection"]
        B1[B1 — Build chunks retaining Docling item IDs]
        B2[B2 — Add mandatory structural candidates]
        B3[B3 — Cheap LLM relevance pass over every chunk]
        B4[B4 — Union candidate evidence set]
        B1 -.-> B2
        B1 -.-> B3
        B2 -.-> B4
        B3 -.-> B4
    end

    subgraph C_GROUP["C — Model routing and transport"]
        C1[C1 — Default: gpt-5.6-luna and medium reasoning]
        C2[C2 — Call-time model, reasoning, and API-style overrides]
        C3[C3 — OpenCode model router]
        C4[C4 — Responses API adapter]
        C5[C5 — Chat Completions API adapter]
        C1 -.-> C3
        C2 -.-> C3
        C3 -.-> C4
        C3 -.-> C5
    end

    subgraph D_GROUP["D — Party extraction and validation"]
        D1[D1 — Party extraction LLM]
        D2[D2 — Normalized LLM result]
        D3[D3 — Decode JSON and validate with Pydantic]
        D4{D4 — Required fields missing or uncertain?}
        D5[D5 — Broaden chunks and rerun selector]
        D6[D6 — Resolve Docling item IDs to verified evidence]
        D7[D7 — Validated borrower and lender JSON]
        D1 -.-> D2
        D2 -.-> D3
        D3 -.-> D4
        D4 -.->|Yes| D5
        D4 -.->|No| D6
        D6 -.-> D7
    end

    A10 -.-> B1
    B4 -.-> C3
    C4 -.-> D1
    C5 -.-> D1
    D5 -.-> B3

    classDef implemented fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1f2937;
    classDef pending fill:#f3f4f6,stroke:#6b7280,stroke-width:2px,stroke-dasharray:6 4,color:#1f2937;
    classDef cognitiveImplemented fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#1f2937;
    classDef cognitivePending fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,stroke-dasharray:6 4,color:#1f2937;

    class A1,A2,A3,A4,A5,A6,A7,A8,A9,A10 implemented;
    class B1,B2,B4,C1,C2,C3,C4,C5,D2,D3,D4,D5,D6,D7 pending;
    class B3,D1 cognitivePending;
```
