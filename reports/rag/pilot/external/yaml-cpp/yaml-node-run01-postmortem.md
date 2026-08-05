# yaml-cpp YAML::Node external RAG pilot run01 postmortem

## Scope and immutable outcome

This is a read-only postmortem of these immutable runs:

- Design: `rag-v1-external-pilot-yaml-cpp-yaml-node-design-run01`
- Code: `rag-v1-external-pilot-yaml-cpp-yaml-node-code-run01`
- Target: `yaml-cpp-yaml-node-d2929956c2cd` (`YAML::Node`)
- Repository commit: `3eb39d5808c33aa93a113cb6c668fa2435ff3ecd`
- Code result: `failed_without_retry_or_repair`

No response or evidence was modified, normalized, repaired, replaced, or regenerated for this postmortem. No run ID was reused.

## Artifact validation

Every existing regular file under both run roots was read and hashed without modification. Every JSON artifact parsed successfully, and declared request, response, design-document, plan-artifact, stage-log, call-count, and status cross-links were checked.

| Run | Files discovered | Files validated | Hash mismatches | JSON parse failures | Cross-link mismatches |
|---|---:|---:|---:|---:|---:|
| Design run | 8 | 8 | 0 | 0 | 0 |
| Code run | 30 | 30 | 0 | 0 | 0 |

Key validated hashes:

- Design document: `692d4328639916f425137b9254b8ee21db2a9d00b34d7f95cffbf330f1e3f796`
- Design request: `0ed13ad3fd440dce9dbb7c62af4d91b82f1427e7e7857347dfcb586cc77fd050`
- Code request: `5f86303abf50358b60e58173ebe0ffe699f3ec76e17c223b11db4b013920e2d0`
- Code response file: `c937681569052834cc9ca04809721f6dc7f9bc21b6277e6ff83be48dfc156078`
- Code response text: `78d3998264e539dd27357b16a51df3352f776a3631c59b43faca6a2a6fb6c105`
- Code failure record: `59ebeb1e10e5c650eb463e565fa33a877dbdd4abb1e0fd3cda1ee34cc16e3ee2`

The complete per-file inventory and SHA-256 values are in `yaml-node-run01-postmortem.json`.

## Retrieval-stage observations

The frozen retrieval-v2 manifest remained unchanged and validated as deterministic/pass:

- Manifest SHA-256: `f924003cc66de2f5d29dd1c13c597aa6f889cbfa389f77e7178010b67dff2343`
- Context SHA-256: `9d4345e151390ae65df9d915046cdbfada1de1191c9278365c055b0bcff75dd9`
- Context tokens: 2,169
- Selected chunks: 11 (`tier 0: 4`, `tier 1: 4`, `tier 2: 3`)
- Leakage validation: pass
- Target-source overlaps in selected context: 0
- Verbatim target source in context: false

This proves the recorded retrieval preparation and leakage controls passed. It does not prove that retrieval improved or harmed generated-code semantics because semantic evaluation was never reached.

## Design-document observations

The design generation completed with exactly one call and no retry or repair. Its response text exactly matches the stored design document.

The document records the class responsibility, most public interface groups, private state, dependencies, and proposed invariants. Read-only inspection also found limitations:

- It does not enumerate every overload preserved by the fixed scaffold, including the `Node`-key `operator[]` and `remove` overloads.
- It contains behavioral and invariant assertions not independently validated by the run, including an undefined-behavior statement and a claimed relationship between `m_isValid` and `m_pNode`.
- No audit finding was added to or used to enrich the code-regeneration prompt.

These observations are not assigned as the failure cause. Compilation and semantic evaluation never occurred, so the effect of the document’s contents on build or behavior is unknown.

## Code-regeneration observations

The code request was sent exactly once. The generation stage completed successfully as a transport/generation stage and recorded:

- Model: `qwen2.5-coder:32b`
- `done`: true
- `done_reason`: `stop`
- `prompt_eval_count`: 2,869
- `eval_count`: 717
- `num_predict`: 8,192
- Retry: false
- Repair: false
- Manual patch: false

The response ended immediately after the `m_pNode` field declaration. It did not contain the closing brace for `class YAML::Node`.

This was **not output-length truncation**: `done_reason` was `stop`, `eval_count` was 717, and the configured `num_predict` ceiling was 8,192. The stored response was not terminated by the output-token ceiling.

## Structural-validation failure

- Failure stage: `normalization_structural_validation` (stored stage record: `normalization`)
- Primary failure category: `generated_code_missing_closing_brace`
- Recorded error: `Matching closing brace was not found`
- Error type: `ValueError`

The validator found the target class opening brace but could not locate its matching closing brace. Adding that brace would be a prohibited manual repair. It was not performed and must not be performed for this immutable run.

## Stages not reached

Structural validation stopped the pipeline before source backup or mutation.

| Stage | Started | Outcome |
|---|---:|---|
| Source backup | No | Not reached |
| Source replacement | No | `source_replaced=false` |
| Configure | No | Skipped |
| Build | No | Skipped |
| Direct test | No | Skipped |
| Full test | No | Skipped |
| Restoration | No | Skipped because replacement never occurred |

Build success and semantic behavior were therefore **not evaluated**.

## Next-pilot options

The decision criterion is whether this pilot sufficiently validated the pipeline mechanics—not which option appears more likely to yield passing code.

### Option A: next frozen target, unchanged protocol

Advantages:

- Preserves direct comparability across frozen targets.
- Avoids introducing a mechanism after observing the first result.
- Shows whether the same structural failure recurs on another independently frozen target.

Disadvantages:

- Replacement, configure/build, direct/full tests, and restoration may remain unvalidated if the next output also fails structurally.
- Consumes another frozen target while a material part of the pipeline remains unexercised.
- Mixes treatment behavior with unresolved pipeline-mechanics uncertainty.

### Option B: separately identified mechanics/sensitivity pilot

Advantages:

- Separates mechanics validation from the immutable treatment outcome.
- Permits a predeclared study of structural-output sensitivity and the downstream replacement/build/test/restoration path under a new protocol identity.
- Preserves run01 as an unmodified failure.

Disadvantages:

- Is not directly interchangeable with unchanged-protocol runs.
- Introduces a new experimental factor requiring separate documentation and analysis.
- Requires additional preparation and cannot reclassify, repair, or supersede run01.

## Recommendation

Recommend **Option B**: define a separate mechanics/sensitivity pilot with a new run ID and an explicit protocol revision. Do not implement it as a retry, repair, or replacement of run01.

The rationale is pipeline identifiability. This pilot validated retrieval preparation, prompt isolation, one-shot reservation/contact, evidence capture, and safe rejection before source mutation. It did not validate source replacement, configure/build, direct/full tests, restoration after replacement, or semantic evaluation. Option B is recommended to resolve that mechanics uncertainty, not to make the next generated implementation more likely to pass.

## Postmortem execution boundaries

- Additional generation-server contacts: 0
- Design LLM call count remains: 1
- Code LLM call count remains: 1
- Source replacement during postmortem: false
- Docker configure/build/test during postmortem: false
- Retry, repair, or manual patch: false
