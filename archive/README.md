# Legacy project archives

This directory holds recoverable snapshots of superseded project work that is
not part of the active parser implementation.

The local, Git-ignored `credit_agreement_parsing_codex.bundle` preserves every
branch and commit from the former
`/Users/ashrit/Desktop/credit_agreement_parsing_codex` repository. The bundle is
intentionally not pushed to the active project's remote.
Its ignored `raw_documents/` directory was not bundled because every one of its
45 PDF documents was verified byte-for-byte against the active corpus before
the former workspace was retired.

To inspect the legacy history without restoring the old Desktop directory:

```bash
git bundle list-heads archive/credit_agreement_parsing_codex.bundle
```

To restore it into a temporary checkout:

```bash
git clone archive/credit_agreement_parsing_codex.bundle /tmp/legacy-credit-parser
```
