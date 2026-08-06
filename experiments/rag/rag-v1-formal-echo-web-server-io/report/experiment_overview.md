# Formal repository-context RAG round-trip result

- target_id: `echo-web-server-io`
- run_id: `rag-v1-formal-echo-web-server-io`
- condition_id: `rag-design-context-v1`
- context_sha256: `f716328af65833ba64f75b2bec8b615324f4b5952ab1a5b6526181ab704570b3`
- overall: **FAIL**

| stage | result | detail |
|---|---|---|
| configure | PASS | exit=0 |
| build | FAIL | exit=2 |
| direct_test | SKIPPED | previous stage failed |
| full_test | SKIPPED | previous stage failed |

A PASS indicates correctness only within the behavior observed by the frozen tests.
