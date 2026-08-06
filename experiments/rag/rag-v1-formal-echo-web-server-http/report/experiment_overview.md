# Formal repository-context RAG round-trip result

- target_id: `echo-web-server-http`
- run_id: `rag-v1-formal-echo-web-server-http`
- condition_id: `rag-design-context-v1`
- context_sha256: `aab9e72bdd074dfbabd23adccc2c09c4fe87aed24154a53ecfeee51c7a89dd39`
- overall: **FAIL**

| stage | result | detail |
|---|---|---|
| configure | PASS | exit=0 |
| build | FAIL | exit=2 |
| direct_test | SKIPPED | previous stage failed |
| full_test | SKIPPED | previous stage failed |

A PASS indicates correctness only within the behavior observed by the frozen tests.
