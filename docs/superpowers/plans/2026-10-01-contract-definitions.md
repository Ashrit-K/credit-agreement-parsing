# Contract definitions — additive taxonomy update

Approved scope: add `contract_definitions` as a multi-label topic for explicit
definitions, not merely occurrences of defined terms. Preserve all saved human
decisions and keep them outside model execution.

## Implementation and acceptance

- [x] Pause annotation writes and make two byte-identical backup copies under
  `tmp/runs/definitions-backup-20261001/{primary,redundant}/`.
- [x] Test legacy load compatibility and preservation before implementation.
- [x] Version taxonomy, B2 phrase rules, and B3 shared definitions to v2.
- [x] Add per-record `reviewed_topics`; legacy records cover only v1 topics.
  Loading returns an additive in-memory view without rewriting saved files.
  Saving one passage persists coverage for current topics, retains other records,
  and uses existing revision checks and atomic writes.
- [x] Require the browser's taxonomy version on save; reject stale pre-update
  tabs so unseen topics cannot silently become negative ground truth.
- [x] Preserve previous labels and completed-review progress. Following user
  correction, topic additions do not force re-review or reset completed status;
  per-topic coverage remains separate evaluation metadata.
- [x] Verify full test suite, live API, and every original record against both
  backups; restart on port 60901 without refreshing the user's browser.

No corpus edits, model calls, or ground-truth-to-pipeline connections. Existing
model runs remain historical v1 results; fresh runs use v2 and cannot reuse
old taxonomy/rule/definition checkpoints.

Verification: 233 tests passed; HTML JavaScript syntax checked; live API exposes
v2 and the new topic. All 163 saved records' existing fields are unchanged and
the live JSON still matches both backups byte-for-byte. Server restarted on
60901; user's browser was not refreshed and no real review was test-written.
