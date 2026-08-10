# Design-only C++ Round-trip A/B Protocol v2.1 intended comparison repair

Status: the first authorized campaign is excluded because Condition A incorrectly received treatment-only detailed-design knowledge. Its artifacts are preserved and are not formal results. The repaired formal campaign remains unauthorized at `0/17` until a formal-excluded pilot is accepted.

## Frozen comparison

Both conditions receive the same target-owned implementation/declaration, minimal base design prompt, model, deterministic generation parameters, context settings, code-generation protocol, replacement boundary, evaluation commands, and one-shot policy.

- Condition A is the normal/minimal baseline: minimal base design prompt + target-owned source only. It does not receive V4/V5 detailed-design guidance, round-trip completeness knowledge, or repository retrieval context.
- Condition B is the proposed composite treatment: it receives the same base prompt and target-owned source plus the frozen V4/V5 detailed-design guidance, frozen round-trip completeness knowledge, and `RAG_CONTEXT` containing complete one-hop project-local dependency headers selected from direct quoted includes in the target-owned inputs.

Therefore this experiment estimates the effect of the complete proposed method relative to the minimal baseline; it does not isolate retrieval alone. Treatment knowledge is frozen centrally in `configs/rag/roundtrip_ab_v1/common.json`, injected only into Condition B, and cannot be overridden per target.

The V4/V5 guidance is copied verbatim from the prior experiment wording. It is not summarized, rewritten, ranked, feature-selected, or Top-K selected. The round-trip completeness knowledge contains no Instruction implementation facts. The runner verifies both file and normalized-content SHA-256 values before request construction.

## Target-owned and retrieval boundaries

The same target implementation and target-owned declaration are supplied to A and B. A target may be a complete file, several module files, a complete class span, or a complete function-definition span. Replacement units and their source hashes/byte boundaries are frozen before execution.

Dependency retrieval is deterministic and one-hop only. Eligible items are direct project-local quoted includes (`#include "..."`); system includes are excluded. Target-owned files and paths containing tests, benchmarks, build output, generated output, experiments, reports, or logs are excluded. Selected dependency headers are injected in full. Includes, comments, callable bodies, concepts, requires-clauses, and templates are not removed or rewritten. Only UTF-8 BOM handling and newline normalization are permitted. Path, source SHA-256, normalized content SHA-256, and the exact context are saved.

Target-specific manual queries, prompt changes, knowledge replacement, retrieval Top-K changes, and per-target generation settings are prohibited.

## Shared generation settings

The model is `qwen2.5-coder:32b`, whose frozen model evidence records a native context length of 32,768 tokens. Exact local Qwen tokenizer preflight over all 17 targets produced a largest Condition-B design input of 20,578 tokens (`echo-web-server-log`). The common settings are therefore:

- design generation: `num_ctx=32768`, `num_predict=8192`;
- code generation: `num_ctx=32768`, `num_predict=16384`;
- both stages: seed 42, temperature 0, top-k 40, top-p 0.9, repeat penalty 1.1;
- settings are identical for A/B and are not adjustable per target.

The design maximum for the largest B request remains below the native context limit. Code preflight conservatively reserves a final design document up to the full design output allowance before adding the code-output allowance.

## Design-only code regeneration

The final design specification is the only target-specific semantic input to code generation. Code generation must not receive original source, target-owned headers, dependency headers, raw RAG context, a fixed scaffold, a source-derived include list, tests, expected outputs, build results, error feedback, previous generated code, or repository access.

Only generic instructions, the JSON Schema, and opaque replacement unit IDs are additional non-semantic protocol inputs. Output IDs and count are schema-constrained and independently validated. A function unit is a complete function definition including return type, qualified/name spelling, parameters, qualifiers, and body; a class span is the complete class/struct definition; full-file/module units are complete files.

## INIWriter correction

The prior function-body-only boundary depended on a fixed scaffold and used a stale source hash. It is not reused. The new Design-Only target replaces the complete current `INIWriter::write` inline member definition, including its documentation, full signature, default argument, braces, and body, in `ini/ini.h`. The current file SHA-256 is `30dfffabdda27182ddf2351193c9224b533b42349e9186a4cecf40f781b0c7f1`. Exact byte offsets and span hashes are frozen in the target config and are identical for A/B. Historical V1-V6 artifacts remain unchanged.

## Formal population and development gate

The formal evaluation manifest freezes 17 targets: ten Echo-Web-Server targets, INIWriter and INIReader, and Instruction, Memory, Parser, Register, and RegisterFile. Instruction is a formal target and will be newly generated after freeze. Existing dev01-dev04 results are not reused. The post-context-setting Instruction run is dev05 and also remains formal-excluded development evidence.

Before authorization, dev05 must demonstrate request fit, complete B context, non-truncated design/code responses, design-only isolation, replacement/restoration, and end-to-end configure/build/direct/full-test execution. Generic settings may change only before this development gate is accepted; target-specific tuning remains prohibited.

## One-shot formal execution

Formal execution uses `scripts/rag/run_roundtrip_ab_formal.py`, not the development runner. It verifies the frozen 17-target allowlist, manifest hash, common-config hash, common-knowledge hashes, target-config hash, repository commit, source hashes, and absence of the condition output directory. A separate authorization artifact is initially `authorized=false`; plan/preflight cannot contact the generation server.

For each target/condition the runner permits exactly one design request and one code request. The attempt marker is written before contact. Retry, repair, manual patch, feedback regeneration, overwrite, and reuse of a failed run ID are unavailable. Formal A and B must both be new executions.

## Artifacts and restoration

Each execution preserves common/target snapshots, actual design prompt/request/response/final design, retrieval query/candidates/exact applied context/manifest, actual code prompt/request/response/generated units, evaluation stage results, restoration result, artifact SHA-256 map, and aggregate-run entry. Condition A stores an explicit empty/not-applied RAG artifact.

Exact source restoration is attempted after success, stage failure, timeout, or exception. Restoration failure is itself recorded as terminal failure evidence. The source cannot be treated as restored merely because the main evaluation failed.

New files remain under `configs/rag/roundtrip_ab_v1`, `reports/rag/roundtrip-ab-v1`, `rag/retrieval/roundtrip-ab-v1`, and `experiments/rag/roundtrip-ab-v1`. Existing V1-V6, fixed non-RAG results, prior RAG formal results, retrieval-v2 artifacts, and Instruction development histories are not overwritten.
