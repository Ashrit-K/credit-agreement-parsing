# Party Extraction Scaffold Design

**Date:** 2026-09-28  
**Status:** Approved for implementation planning

## Objective

Build the smallest reviewable Python application that establishes the user experience and software boundaries for extracting borrower, lender, parent-company, and relationship information from credit-agreement PDFs.

The first version is scaffolding, not a production extractor. It must accept a PDF through a browser interface, run it through an explicit pipeline boundary, and display validated JSON. Until PDF parsing and model extraction are implemented in later increments, the result must clearly report that extraction is not implemented. It must never fabricate party information.

## User experience

The application will use Streamlit and present:

1. A PDF file uploader.
2. An optional instruction field that resembles the beginning of a chatbot interaction.
3. Clear copy explaining that instructions do not alter v0.1 behavior.
4. An **Extract parties** button.
5. A JSON result panel showing the pipeline response.

The application will accept one PDF at a time in v0.1. Conversation history, multiple-file processing, HTML ingestion, authentication, persistence, and asynchronous jobs are outside this increment.

## Provisional output contract

The schema is deliberately provisional. It supports multiple borrowers and lenders because credit agreements frequently contain co-borrowers, subsidiary borrowers, syndicated lenders, and agents.

```json
{
  "document_name": "example.pdf",
  "status": "not_implemented",
  "borrowers": [
    {
      "name": "Example Borrower, Inc.",
      "role": "borrower",
      "is_primary": true,
      "parent": {
        "name": "Example Holdings, Inc.",
        "relationship": "Example Holdings, Inc. is the direct parent of Example Borrower, Inc."
      },
      "evidence": []
    }
  ],
  "lenders": [],
  "errors": []
}
```

For v0.1, `borrowers` and `lenders` will be empty and `status` will be `not_implemented`. The example above illustrates the intended later shape only. Missing parent information must be represented as `null`; absence must not be converted to an empty assertion or guessed value.

Each future party record will contain:

- `name`: the agreement's name for the legal entity.
- `role`: the entity's contractual role, such as borrower, co-borrower, lender, administrative agent, or collateral agent.
- `is_primary`: whether the agreement identifies the party as the primary borrower or primary lender/agent for display purposes.
- `parent`: an optional parent-company record containing the parent's name and the relationship stated or supported by evidence.
- `evidence`: a list reserved for document, page, section, and concise source excerpts in later increments.

## Architecture

The code will be divided into small replaceable units:

- **Streamlit application:** owns presentation, upload handling, button state, and JSON display. It does not parse PDFs or call models directly.
- **Configuration:** reads environment settings, validates required values only when a live model client is requested, and never logs secrets.
- **Domain models:** define the provisional JSON contract and distinguish missing values from empty collections.
- **PDF text extractor protocol:** defines the future PDF-to-text boundary. v0.1 supplies a non-fabricating placeholder implementation.
- **LLM client protocol:** defines the future structured-generation boundary without selecting a permanent model vendor or SDK.
- **Party extractor protocol:** accepts document text and returns validated party records. v0.1 supplies a placeholder that returns `not_implemented`.
- **Pipeline orchestrator:** accepts an uploaded document and coordinates the interfaces. It remains independent of Streamlit so it can later support a CLI, API, batch process, or agent.

The interfaces will use Python protocols and dependency injection. Tests can therefore provide simple fakes without network access, API keys, or PDF-processing dependencies.

## OpenCode configuration

The repository will contain a tracked `.env.example` and an ignored local `.env`. The files will expose:

```dotenv
OPENCODE_API_KEY=
OPENCODE_MODEL=
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_API_STYLE=responses
```

`OPENCODE_API_STYLE` is explicit because OpenCode Zen currently exposes different models through Responses, Messages, and Chat Completions endpoints. The scaffold will validate the configuration vocabulary but will not make a network request in v0.1. A later implementation can place endpoint-specific behavior behind the LLM client protocol without changing the pipeline or UI.

Reference: <https://opencode.ai/v2/docs/console/models/>

## Python project standards

- Use `uv` for project initialization, dependency management, locking, and command execution.
- Pin a compatible Python version according to the local Python-development standard.
- Create and use `.venv/`.
- Maintain `pyproject.toml`, `uv.lock`, and `.python-version`.
- Add Streamlit and Pydantic as runtime dependencies and pytest as a development dependency.
- Keep `.env`, `.venv/`, `.uv-cache/`, Python bytecode, and pytest caches ignored.
- Use type hints and focused module docstrings throughout.

## Commenting standard

The code is intended for close user review. Comments and docstrings will explain:

- why each architectural boundary exists;
- what each model field represents in credit-agreement terms;
- how data flows from upload to pipeline result;
- why placeholder behavior refuses to invent extraction results;
- where PDF parsing and live model calls will be added later.

Comments will emphasize intent and decisions rather than restating obvious Python syntax line by line.

## Error handling

The scaffold will produce clear, structured errors for:

- no uploaded file;
- a filename that does not end in `.pdf`;
- empty uploaded content;
- invalid environment configuration when live-model configuration is explicitly loaded;
- unexpected pipeline failures, shown to the user without revealing secrets.

The uploaded file will remain in memory for v0.1. The application will not write uploaded agreements into `raw_documents/` or any persistent directory.

## Testing

Implementation will follow test-driven development. Tests will cover:

- JSON serialization of the provisional output model;
- preservation of `null` for unknown parent information;
- rejection of empty or non-PDF uploads;
- pipeline orchestration using injected fake components;
- placeholder behavior returning `not_implemented` with no invented parties;
- environment parsing without exposing or requiring a real API key;
- a lightweight Streamlit application import/smoke check where practical.

Tests will not call OpenCode or any other external service.

## Acceptance criteria

The scaffold is acceptable when:

1. `uv run pytest` passes in the pinned virtual environment.
2. `uv run streamlit run app.py` launches the interface.
3. A user can upload a PDF and receive valid JSON with the document name, `not_implemented` status, empty party lists, and no fabricated values.
4. The optional instruction field does not change the result and the UI says so.
5. `.env.example` documents every supported OpenCode setting while `.env` remains ignored.
6. UI code, orchestration, domain models, configuration, and future provider behavior are separated into independently testable modules.

## Deferred decisions

The following decisions require evidence from representative agreements and are intentionally deferred:

- PDF parsing or OCR library selection;
- prompt design and chunking strategy;
- OpenCode model selection and endpoint adapter;
- final party taxonomy and final JSON schema;
- rules for choosing a primary lender among lenders, agents, arrangers, and bookrunners;
- confidence scoring and evidence granularity;
- HTML ingestion;
- persistence, batch processing, and agent behavior.
