# OpenCode LLM Adapters Design

## Goal

Add a small provider boundary that can call OpenCode Zen through either the
Responses API or the Chat Completions API while returning one normalized result
to downstream extraction code. Callers can choose a model per request; project
configuration supplies practical defaults.

This increment establishes and tests the LLM transport layer. It does not yet
select agreement paragraphs, define the borrower/lender prompt, resolve evidence
references, or replace the `not_implemented` behavior in `extract_parties()`.
Those behaviors remain separate pipeline increments.

## Decisions

- Use the existing `LlmClient` protocol as the internal middleware boundary.
- Do not add AI Suite or another provider-routing framework.
- Implement `ResponsesApiAdapter` for OpenCode models using `/responses`.
- Implement `ChatCompletionsApiAdapter` for OpenCode models using
  `/chat/completions`.
- Do not implement the Anthropic-style Messages API in this increment.
- Default to model `gpt-5.6-luna` with reasoning effort `medium`.
- Permit call-time overrides for model, reasoning effort, and API style.
- Maintain an explicit, tested model-to-API-style registry because OpenCode's
  model-list endpoint identifies models but does not expose their API style.
- Keep normal tests offline by injecting an HTTP transport or fake `LlmClient`.

## Configuration and precedence

The environment-backed defaults are:

```env
OPENCODE_MODEL=gpt-5.6-luna
OPENCODE_REASONING_EFFORT=medium
OPENCODE_BASE_URL=https://opencode.ai/zen/v1
OPENCODE_API_STYLE=responses
```

The API key remains required only for a live request:

```env
OPENCODE_API_KEY=
```

Each live call resolves settings in this order:

1. Explicit call argument.
2. Environment-backed setting.
3. Project default shown above.

The adapter-level call supports:

```python
client.generate_structured(
    prompt=prompt,
    json_schema=schema,
    model="deepseek-v4-pro",
    api_style="chat_completions",
)
```

`api_style` is optional for models in the registry. It is an escape hatch for a
new OpenCode model that the local registry does not yet know. A conflicting
explicit style overrides the registry only when the caller supplies it
deliberately.

Reasoning effort applies to the Responses API. The Chat Completions adapter does
not send a reasoning field unless a future model-specific capability explicitly
requires one.

## Components

### Model registry

The registry maps supported model IDs to `responses` or `chat_completions`. It
contains the models we actively test, rather than attempting to mirror every
model returned by OpenCode.

The initial registry includes at least:

| Model | API style |
| --- | --- |
| `gpt-5.6-luna` | `responses` |
| `gpt-5.6-sol` | `responses` |
| `gpt-5.6-terra` | `responses` |
| `deepseek-v4-pro` | `chat_completions` |
| `glm-5.3` | `chat_completions` |
| `kimi-k3` | `chat_completions` |

An unknown model without an explicit API style raises a clear routing error. It
must not be guessed from a name prefix and must not be tried against multiple
billable endpoints.

### API adapters

Each adapter owns both halves of its wire protocol:

1. Construct the correct HTTP endpoint, headers, and request body.
2. Extract generated content and usage metadata from that API's response body.

`ResponsesApiAdapter` sends the prompt through the Responses API and includes
the selected reasoning effort. `ChatCompletionsApiAdapter` sends system/user
messages through Chat Completions without an unsupported reasoning field.

Both return the same internal result:

```python
class LlmResult(BaseModel):
    text: str
    model: str
    api_style: ApiStyle
    input_tokens: int | None = None
    output_tokens: int | None = None
```

Raw provider payloads are useful for debug logging but are not part of the
stable public result and must never include the API key.

### OpenCode client

`OpenCodeLlmClient` implements the project `LlmClient` protocol. It resolves
configuration, chooses an API adapter through the registry or explicit style,
executes the HTTP request, and returns structured data for downstream Pydantic
validation.

The protocol gains optional `model`, `reasoning_effort`, and `api_style`
arguments. Tests and later providers can still implement it without depending
on OpenCode classes.

## Structured output and validation

Transport normalization and legal-data validation are separate concerns:

1. The selected API adapter extracts model-generated text.
2. The OpenCode client decodes the text as JSON.
3. The client returns a dictionary through the existing `LlmClient` contract.
4. A later party-extraction stage validates that dictionary with Pydantic.
5. A later evidence stage verifies cited Docling item identifiers against the
   canonical conversion JSON.

Pydantic validation checks structure and data types. It does not establish that
an extracted fact is true. Evidence resolution remains required before a future
party extraction can be considered completed.

## Errors

The transport layer exposes distinct failures so callers do not need to parse
provider error strings:

- Missing live credentials.
- Unknown model without an API-style override.
- Unsupported API style, including `messages` in this increment.
- Authentication or authorization failure.
- Rate limiting.
- Timeout or network failure.
- Non-success provider response.
- Provider response missing generated content.
- Generated content that is not valid JSON.

Failure against the party-extraction Pydantic schema belongs to the later
extraction stage rather than this transport increment.

Error messages may name the model, API style, and HTTP status but must not expose
the API key or complete agreement text.

## Testing

All standard tests are deterministic and make no external requests. Injected
HTTP transports provide representative Responses and Chat Completions payloads.

Tests cover:

- Default model and medium reasoning configuration.
- Call-time override precedence.
- Registry routing for both API styles.
- Explicit API-style routing for an unknown model.
- Responses request and response normalization.
- Chat Completions request and response normalization.
- Confirmation that Chat Completions does not receive a reasoning field.
- Token-usage normalization when usage data is present or absent.
- Missing credentials, authentication, rate limit, timeout, malformed envelope,
  invalid JSON, and unsupported Messages-style requests.
- API-key masking in representations and errors.

Optional live smoke tests are manually invoked and excluded from the normal test
suite. One uses `gpt-5.6-luna` through Responses; one uses a configured open
model through Chat Completions. They send a tiny synthetic prompt rather than a
credit agreement.

## Pipeline status diagram

The maintained diagram lives in `docs/conversion_pipeline.md`. Solid arrows mean
the connected stages are implemented and tested. Dashed arrows mean the stage or
connection remains pending. When this increment is implemented, the model
router and both API adapters become solid; paragraph selection, party prompting,
Pydantic party validation, evidence resolution, and final extraction remain
dashed.
