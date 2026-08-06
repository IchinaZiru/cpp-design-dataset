# Formal repository-context RAG round-trip result

- target_id: `echo-web-server-config`
- run_id: `rag-v1-formal-echo-web-server-config`
- condition_id: `rag-design-context-v1`
- context_sha256: `2ead46be7511cd0bb847363803cb2852208a53e8864a400cdd4f4adc35a95da8`
- overall: **FAIL**

| stage | result | detail |
|---|---|---|
| configure | PASS | exit=0 |
| build | FAIL | exit=2 |
| direct_test | SKIPPED | previous stage failed |
| full_test | SKIPPED | previous stage failed |

A PASS indicates correctness only within the behavior observed by the frozen tests.
