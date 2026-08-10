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

1. the complete fixed V4/V5 expanded-design guidance from `prompts/fixed_v4_v5_design_knowledge.txt`;
2. complete content from directly referenced project-local dependency headers.

The fixed guidance is used byte-for-byte for every target. It is not summarized, rewritten, ranked, selected by source features, or limited by Top-K. The removed seven-entry `design_knowledge_index_v1.json` mechanism is not part of this protocol. The target-owned header is excluded from dependency retrieval because it is already common A/B input.

The fixed guidance is the exact V4 prompt section beginning with `# RAGによる追加詳細設計（内容必須・Markdown階層は柔軟）` and ending with `----- END RETRIEVED CONTEXT -----`. Its canonical content SHA-256 is `13ffffe8c5c76b6493f36be79c56332ee2cd8ccfcf9b38685edfd6ab4137636f`. The wording is copied from the actual V4 request recorded at commit `bd7bf7bf399130ef739793fe44a71de61dff0209`; V5 commit `d99c627339b9878dc944d91bfc638869ebe94a66` retained the same V4 prompt/guidance and added direct-include repository context only. The prompt builder that defines the section is frozen at `dd140245ab278636261bc46a0c5fbdb919ef9932`.

## Common design prompt

The canonical common prompt is `configs/rag/roundtrip_ab_v1/prompts/design_generation.txt`. It is byte-identical between A and B. Condition A receives no fixed design-section list. Condition B receives the verbatim V4/V5 expanded-design guidance only inside `RAG_CONTEXT`; this is the treatment, not a change to the common prompt. Input units and the optional RAG context are protocol envelopes around the same prompt.

## Target-owned boundary

Target-owned inputs are frozen explicitly per target. A project-local header included by those files is a dependency and is not recursively added to Condition A. Direct dependency retrieval is rule-based, has no target-specific manual query, excludes target-owned files, and serializes the complete header content with path, source SHA-256, normalized content SHA-256, and byte length.

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

Dependency retrieval is one-hop from target-owned inputs and excludes target-owned inputs and paths containing tests, benchmarks, build output, generated output, experiments, reports, logs, or previous LLM artifacts. Only project-local quoted includes (`#include "..."`) are eligible; system includes (`#include <...>`) are not retrieved. No recursive include expansion is performed.

Each selected dependency header is included in full. The protocol does not summarize, extract, sanitize, or rewrite header content. It does not remove `#include` directives, comments, callable bodies, concepts, requires-clauses, or templates. The only permitted transformation is mechanical UTF-8 BOM handling and CRLF/CR-to-LF newline normalization. Every selected item records its path, original source SHA-256, source byte length, actual context-content SHA-256, context-content byte length, normalization identifier, and selection reason.

The two RAG components are serialized in separate delimited sections: `FIXED V4/V5 DESIGN KNOWLEDGE` and `DIRECT DEPENDENCY HEADER CONTEXT`. Only dependency headers are target-dependent. The fixed design knowledge and its content SHA-256 must be identical for every target.

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
