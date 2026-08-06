# Formal repository-context RAG round-trip result

- target_id: `echo-web-server-thread-pool`
- run_id: `rag-v1-formal-echo-web-server-thread-pool`
- condition_id: `rag-design-context-v1`
- context_sha256: `3c135ede05a26751047c65f5d0e76664550a5bd7588c7714534f15a15a852378`
- overall: **FAIL**

| stage | result | detail |
|---|---|---|
| configure | PASS | exit=0 |
| build | FAIL | exit=2 |
| direct_test | SKIPPED | previous stage failed |
| full_test | SKIPPED | previous stage failed |

A PASS indicates correctness only within the behavior observed by the frozen tests.
