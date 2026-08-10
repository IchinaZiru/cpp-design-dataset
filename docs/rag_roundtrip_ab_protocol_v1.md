# Design-only C++ Round-trip A/B Protocol v1

Status: implementation and retrieval-only pilot preparation. Formal 17-target generation is not authorized.

## Research comparison

The experiment compares two newly generated conditions over the same target-owned implementation/declaration inputs. Historical V1-V6 outputs and the frozen 6/17 non-RAG result are read-only references, not the control for this experiment.

### Condition A: non-RAG

Design generation receives only:

- target implementation;
- target-owned header/declaration;
- the common minimal design-generation prompt.

Project-local dependency headers are not expanded.

### Condition B: RAG

Condition B uses the byte-identical common prompt, target-owned inputs, model, and generation options used by Condition A. Its sole additional input is `RAG_CONTEXT`, composed deterministically from:

1. retrieved general design-specification knowledge from `design_knowledge_index_v1.json`;
2. declaration-oriented content from directly referenced project-local dependency headers.

The knowledge entries are retrieval records, not text embedded in a B-only prompt. The target-owned header is excluded from dependency retrieval because it is already common A/B input.

## Common design prompt

The canonical prompt is `configs/rag/roundtrip_ab_v1/prompts/design_generation.txt`. No fixed list of V1-V6 design sections is appended to either condition. Input units and the optional RAG context are protocol envelopes around the same prompt.

## Target-owned boundary

Target-owned inputs are frozen explicitly per target. A project-local header included by those files is a dependency and is not recursively added to Condition A. Direct dependency retrieval is rule-based, has no target-specific manual query, excludes target-owned files, and serializes declaration-oriented header content with hashes and paths.

## Code regeneration isolation

Condition A and B use the same code-generation prompts, model options, and JSON Schema. The final design specification is the only semantic input. The code-generation request must not load or inject:

- original target source or target-owned headers;
- RAG context or dependency headers;
- fixed scaffold or a separate include list;
- tests, build results, previous generated artifacts, or repository access.

The runner validates the opaque `(file_id, unit_id)` set after generation. Repository paths and replacement spans remain private runner data.

## Replacement granularity

- `function`: replace the complete frozen function definition span.
- `class_span`: replace the complete frozen class/struct span.
- `module_files`: replace the complete frozen target files.

Backups and SHA-256 values are recorded before replacement. Restoration runs after success, failure, exception, or timeout, and exact restored bytes are verified.

## One-shot rules

Each condition permits one design-generation request and one code-generation request. Attempt evidence is created before contact. Empty, truncated, invalid-JSON, schema-invalid, missing-unit, build, or test failures are terminal for that run ID. Retry, automatic repair, manual patch, overwrite, and feedback-based regeneration are prohibited.

## Retrieval leakage rules

Dependency retrieval excludes target-owned inputs and paths containing tests, benchmarks, build output, generated output, experiments, reports, logs, or previous LLM artifacts. Only project-local quoted includes are eligible. Retrieved headers are normalized to declarations; callable bodies are not included. Every selected item records path, source SHA-256, normalized SHA-256, and selection reason.

## Pilot gates

Before any formal 17-target generation:

1. retrieval-only `riscv-simulator-instruction` must retrieve the direct definition of `Immediate` through generic rules;
2. retrieval-only `echo-web-server-io` must retrieve the `Buffer` dependency interface through generic rules;
3. one formal-excluded pilot must exercise A/B design generation, design-only code regeneration, JSON validation, replacement, configure/build/test, and restoration;
4. the prompt-isolation, leakage, determinism, serialization, replacement, and restoration tests must pass.

Prompt and retrieval settings are frozen only after these gates pass. Formal results must never be used for target-specific tuning.

## Artifact separation

New artifacts use only these roots:

```text
configs/rag/roundtrip_ab_v1/
rag/retrieval/roundtrip-ab-v1/
reports/rag/roundtrip-ab-v1/
experiments/rag/roundtrip-ab-v1/
```

Existing V1-V6, frozen non-RAG, prior RAG formal, retrieval-v2, and fixed result artifacts are never overwritten or edited.
