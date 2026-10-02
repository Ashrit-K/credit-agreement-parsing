# Qwen Messages and xhigh transport increment

Approved scope: enable the five requested configurations for the upcoming 011
model agreement benchmark. No classification run, human-label edit or model
substitution in this increment.

- [x] Test Responses `xhigh` pass-through before implementation.
- [x] Test Qwen Messages payload, cache accounting and thinking-free debug logs.
- [x] Route `qwen3.8-flash` explicitly to `/messages`, with x-api-key and
  anthropic-version headers; keep credentials out of all trace payloads.
- [x] Map Messages `high` to thinking enabled with budget_tokens=16000 and
  max_tokens=32768; `none` disables thinking. Reject other tiers before sending.
- [x] Extend B3's route acceptance and test Messages identity/profile behavior.
- [x] Strip thinking/reasoning blocks, signatures and hidden reasoning fields
  from debug snapshots across all endpoint styles; retain usage counts.
- [x] Test incomplete Messages output still records paid usage once.
- [x] Verify full suite: 242 passed. All five exact requested configurations
  passed tiny live preflights, logging usage and dated workspace cost estimates.
- [x] Update C6 solid implemented box/arrow and backlog without renumbering IDs.

Budget policy source: [OpenCode provider transform](https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/provider/transform.ts),
Messages non-adaptive high variant. A successful request verifies accepted
wire configuration, not the gateway's internal reasoning implementation.

Tiny preflight logs: `tmp/runs/model-effort-checks-20261001/summary.json`.
Estimated total USD 0.00025185 (262 input and 241 output tokens). Saved human
annotations were not read or written by any preflight.
