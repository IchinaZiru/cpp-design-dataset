# Formal repository-context RAG round-trip result

- target_id: `echo-web-server-buffer`
- run_id: `rag-v1-formal-echo-web-server-buffer`
- condition_id: `rag-design-context-v1`
- context_sha256: `65ef992a019987084914de65791407c3e32ac7df0fd591d78c4affabd996c692`
- overall: **FAIL**

| stage | result | detail |
|---|---|---|
| configure | PASS | exit=0 |
| build | FAIL | exit=2 |
| direct_test | SKIPPED | previous stage failed |
| full_test | SKIPPED | previous stage failed |

A PASS indicates correctness only within the behavior observed by the frozen tests.
