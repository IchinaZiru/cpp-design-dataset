# Direct-include Repository-Context RAG v5 evaluation results

This is a post-hoc refinement/sensitivity evaluation extending frozen v4.
The only intended treatment change is one-hop whole-file retrieval of repository-local quoted direct includes.

- Terminal runs: 17/17
- v5 PASS: 5/17
- Retry: none
- Automatic repair: none
- Original source in code regeneration: false
- Retrieved context in code regeneration: false

## Reference transitions vs frozen v4

- FAIL->PASS: 1
- PASS->FAIL: 0
- PASS->PASS: 4
- FAIL->FAIL: 12
