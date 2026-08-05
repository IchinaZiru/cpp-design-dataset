# Formal context attempt 01 failure

## Status

- Attempt: `formal-context-attempt-01`
- Source HEAD: `5f038fd945241cdf81cbd760729f1600fcfa159d`
- Exit code: `2`
- Status: `failed_transaction`
- Formal experiment result: `false`
- Retry permitted for this attempt: `false`
- Canonical output published: `false`
- LLM calls: `0`
- Formal targets executed: `0`

## Failure

The aggregate formal-context audit rejected selected chunks with
overlapping byte ranges in the same committed source file.

The failed transaction did not publish canonical contexts, update target
configs, contact a generation server, execute Docker, replace source
code, or run a formal target.

## Diagnostics

- Initial selected chunks checked: 149
- Source ranges matching committed source: 149
- Source SHA-256 mismatches: 0
- Selected overlap pairs: 56
- Initially affected targets: 10
- Post-fix overlap-excluded candidates: 216
- Post-fix affected targets: 12
- Remaining selected overlaps: 0
- Independent build mismatches: 0
- Read-only audit passes: 17/17
- RAG tests: 137 passed, 4 skipped

## Preservation

- Archive: `cpp-rag-formal-context-attempt-01-failure.zip`
- Archive SHA-256: `aef7a08a905e0f0f7c02ba24d6c8f7dde32ab2235f5e4056a1f99ebe5952a569`
- Inventory files: 205
- Inventory payload SHA-256: `cafab8056a4110bf1d0438ae55ff1eb2c5188b1cfe0c5b18cdd9cb504adbd1a8`
- Mismatch evidence SHA-256: `869d6abd91c03cfb065df7e0a7b199516e854070ab7b360db9a65491e3ad3d00`

The ZIP archive is stored outside the Git repository. The tracked
inventory and mismatch evidence identify the preserved failed
transaction. A later context-generation execution is a separately
authorized new attempt, not a retry of attempt 01.
