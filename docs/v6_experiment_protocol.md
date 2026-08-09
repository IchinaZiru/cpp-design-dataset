# Deterministic Exact-Contract Round-Trip v6 Protocol

## 1. Status

- Protocol family: `deterministic-exact-contract-v6`
- Development branch: `experiment/deterministic-exact-contract-v6`
- Base outer commit: `9f56d995734202a684f2f8b146c09824774699c9`
- Formal execution status: **not started**
- v5 artifacts remain frozen and are not overwritten.
- v6 pilot artifacts are development evidence only and are not formal results.

The deterministic extraction rules described in this document are frozen before
formal v6 execution. Formal PASS/FAIL results must not be used to tune these
rules.

## 2. Motivation

Failure investigation of v5 separated the pipeline into:

1. corpus availability;
2. retrieval;
3. selected context;
4. design-artifact information preservation;
5. code-regeneration use/adherence;
6. build and test.

Development pilots showed that useful exact facts could exist in the target
source or retrieved repository context but be abstracted away before code
regeneration.

v6 therefore augments the LLM-produced design document with deterministic,
machine-extracted exact facts.

The deterministic contracts are part of **design-artifact construction**.
They are not direct original-source or retrieved-context injection into the
code-regeneration request.

## 3. Research comparison

v6 contains a paired control and treatment.

### v6 non-RAG control

```text
target source
  -> ordinary design-document generation without repository retrieval
  -> deterministic Source-local Implementation Contract
  -> augmented design artifact
  -> unchanged code regeneration
  -> build/test
```

### v6 RAG treatment

```text
target source
  + repository retrieval during design generation
  -> RAG-assisted design-document generation
  -> deterministic Source-local Implementation Contract
  + deterministic Dependency API Contract
       derived from the selected RAG repository context
       and target-source call usages
  -> augmented design artifact
  -> unchanged code regeneration
  -> build/test
```

The source-local contract is common to both conditions.

The dependency API contract is present only in the RAG treatment because its
declarations are derived from repository context retrieved during the design
stage.

## 4. Fairness rule

For each paired target, keep fixed:

- repository commit;
- target source and granularity;
- target locator;
- test files and test filters;
- Docker image and image ID;
- model ID;
- temperature;
- seed;
- `num_ctx`;
- `num_predict`;
- `top_k`;
- `top_p`;
- repeat penalty;
- generation count;
- retry policy;
- automatic-repair policy;
- normalization;
- code-regeneration prompt structure;
- evaluation commands and expected test counts.

The treatment difference is repository retrieval during design generation and
the dependency contract deterministically derived from that retrieved context.

The common source-local contract is applied identically to non-RAG and RAG.

## 5. Model and generation policy

The v6 method pilot does not justify changing the regeneration model.

Use the same Qwen2.5 regeneration model/settings inherited from the matched
v4/v5 target configuration unless a pre-formal configuration audit detects an
already-existing per-target frozen value that must be preserved.

For every formal target and stage:

- exactly one design-generation call;
- exactly one code-regeneration call;
- no retry;
- no automatic repair;
- no manual generated-code edit;
- no selection among multiple generations.

A timeout or malformed generation is retained as the formal outcome.

## 6. Contract extractor

Implementation:

```text
scripts/roundtrip_v6/contract_extractor.py
```

Frozen parser dependencies:

```text
tree-sitter==0.26.0
tree-sitter-cpp==0.23.4
```

Extractor version:

```text
v6-ast-contract-1
```

The extractor is deterministic and does not call an LLM.

### 6.1 Target parsing

The extractor parses raw C/C++ target source, not serialized prompt text.

For `module_files`, all configured target source files are parsed.

For target-span granularity, the frozen `roundtrip_v2` locator is reused to
identify the exact configured class/function span, and that raw C++ span is
parsed.

Any Tree-sitter `ERROR` node is a preparation-blocking error.

### 6.2 Source-local Implementation Contract

The extractor records:

1. exact local `declaration` nodes below a `compound_statement`;
2. exact top-level `call_expression` text.

Nested call expressions are used internally for dependency matching, but are
not separately repeated in the rendered source-local call list when already
contained in an outer call expression.

Stable first-occurrence ordering is retained.

The contract does not copy complete function bodies or control-flow
statements.

The regeneration constraint is generic:

- preserve exact declaration types, containers, initializers, and literals;
- preserve exact call targets and arguments;
- do not substitute a merely similar representation or accessor;
- treat listed facts as exact constraints rather than pseudocode.

No target-specific extraction or instruction rules are permitted.

### 6.3 Dependency API Contract

This contract exists only in the RAG treatment.

Inputs are:

- target-source call expressions;
- files selected by the frozen RAG retrieval manifest.

The extractor does not perform a new semantic search.

Candidate repository declarations are collected from:

- `declaration`;
- `field_declaration`;
- `function_definition`;
- `template_declaration`.

For a function definition, only the declaration/signature preceding the body
is retained; the dependency implementation body is not copied.

Matching uses:

1. exact terminal callable name;
2. compatible call arity;
3. default parameters when determining compatible arity.

Generic exclusions before dependency matching:

- `std::...` qualified calls;
- plain calls whose names are defined by the target itself;
- explicit `this->...` calls.

If multiple compatible declarations remain, all are retained in deterministic
order. Formal results must not be used to choose a target-specific overload.

The rendered dependency contract preserves:

- exact declaration text;
- exact target-source usage expression.

Its generic regeneration constraints prohibit inventing replacement APIs,
overloads, adapters, or consuming a `void` result as a value.

## 7. RAG stage boundary

RAG is restricted to design-artifact construction.

Allowed for RAG design generation:

```text
target source
+ selected repository context
```

Allowed for deterministic dependency-contract construction:

```text
target-source call facts
+ selected repository dependency files/context
```

Allowed for code regeneration:

```text
augmented design artifact
+ fixed scaffold
+ ordinary dependency/include context
```

Forbidden for code regeneration:

- original target implementation;
- raw selected RAG context;
- retrieval candidates;
- tests;
- expected outputs;
- previous generated code;
- compiler/test failure evidence.

The dependency contract is part of the finalized design artifact, not a
separate retrieval payload sent to regeneration.

## 8. Contract artifacts

Each prepared v6 target stores at least:

```text
contracts/
  source_local_contract.md
  dependency_api_contract.md     # RAG only
  combined_contract.md
  contract_manifest.json
```

`contract_manifest.json` records:

- extractor/schema version;
- target and pair IDs;
- repository commit;
- Tree-sitter package versions;
- target fragment hashes;
- selected dependency paths and file hashes;
- local declaration and call counts;
- matched dependency symbols;
- overload sets;
- unmatched diagnostic symbols;
- contract hashes and sizes;
- retrieval manifest/context hashes for RAG;
- `llm_called=false`;
- `deterministic=true`.

Unmatched candidate symbols are diagnostic information and are not themselves
a formal blocking condition because C/POSIX APIs, library members, and
non-repository calls may legitimately be unmatched.

## 9. Development evidence used before freeze

The exact-contract development pilots are not formal evidence.

Observed development progression:

```text
v5 Qwen2.5:
  io            FAIL
  RegisterFile  FAIL
  thread-pool   FAIL

Qwen3 regeneration-only sensitivity:
  0/3 became PASS

deterministic exact-contract development:
  RegisterFile  PASS
  thread-pool   PASS
  io            PASS after source-local exact declarations were also preserved
```

This supports testing the information-preservation method formally, but does
not replace a formal paired experiment.

## 10. AST dry-run freeze evidence

The final pre-freeze AST dry-run covered all 17 configured targets.

Recorded result:

```text
targets                           = 17
targets_with_parse_errors         = 0
total_dependency_symbols_matched  = 53
targets_with_overload_sets        = 4
targets_not_conservatively_within_ctx = 0
targets_with_unknown_ctx_budget   = 1
```

Dry-run summary:

```text
analysis/v6-contract-dryrun-ast-v2/summary.json
SHA-256:
CB1501C33E7017DE43551655EF28137F04465826A6A093628DE786E56137DA17
```

Critical regression checks passed for:

- `io`
  - `std::array<std::byte, 0x10000> ext_bytes`
  - `const std::array bufs`
  - exact `readv(...)`
  - exact `write(...)`
  - Buffer dependency interfaces including `WritableSize`, `HasWritten`,
    `WritableBytes`, and `ReadableBytes`
- `thread-pool`
  - `Create`
  - `Log`
  - `Event::Create`
- `RegisterFile`
  - `debug_immediate`
  - `Immediate v`
  - `next[j]`

No LLM, Docker, build, or test execution was performed by this dry run.

## 11. Context-budget status

The pre-formal context-budget rule is now fixed as:

```text
assembled_code_regeneration_input_tokens + num_predict <= num_ctx
```

Apply this rule identically to all 17 targets and to both v6 conditions.
The token counter is the `Qwen/Qwen2.5-Coder-32B-Instruct` tokenizer through
`transformers` `apply_chat_template(..., add_generation_prompt=True)`.

The pre-formal environment used `transformers==4.57.6`. The tokenizer/template
was validated against all 17 saved v2 Ollama `prompt_eval_count` values and
matched exactly:

```text
samples        = 17
max_abs_delta  = 0
mean_abs_delta = 0.0
```

The frozen v5 code-regeneration request could be reconstructed exactly for all
16 targets that have a saved request. Token counts also matched the corresponding
saved Ollama `prompt_eval_count` values for all 16. `echo-web-server-log` has no
saved v5 code-regeneration request because that frozen v5 run timed out before a
usable request/metadata pair was recorded; its request is therefore reconstructed
with the same frozen v2/v5 prompt builder that matched the other 16 targets.

A no-LLM sizing proxy used each frozen v5 design artifact plus the deterministic
v6 contracts. It is not a v6 formal result and is not proof of the exact length
of the future one-shot v6 design generation.

```text
source-contract proxy budget PASS = 17/17
RAG-contract proxy budget PASS    = 17/17
minimum source headroom after reserving num_predict = 5296 tokens
minimum RAG headroom after reserving num_predict    = 4052 tokens
```

For `echo-web-server-log`:

```text
reconstructed v5 code-regeneration input = 8152 tokens
source-contract proxy input              = 11088 tokens
source headroom after num_predict reserve = 5296 tokens
RAG-contract proxy input                 = 12332 tokens
RAG headroom after num_predict reserve    = 4052 tokens
```

Therefore the prior `log` budget uncertainty is cleared for **pre-formal sizing**,
and v6 may proceed to disabled configuration preparation. It is not cleared by
character/byte counting; it is cleared by the validated Qwen2.5 tokenizer proxy.

During the actual formal run, after the one-shot design generation and deterministic
contract append, count the **actual assembled code-regeneration request** with the
same tokenizer before making the code-regeneration LLM call. If the fixed rule
fails, stop that target before code regeneration, preserve the generated design and
all audit artifacts, and do not retry, shorten, repair, or regenerate it.

Recorded no-LLM audit artifacts:

```text
analysis/v6-preformal-budget-audit/summary.json
analysis/v6-preformal-budget-audit/v6_preformal_budget_audit.csv
analysis/v6-preformal-budget-audit/audit_driver.py
```

The audit made no LLM, Ollama, Docker, build, or test call.
## 12. Formal preparation

Before enabling any formal v6 target:

1. validate exact parser package versions;
2. verify all repository commits;
3. verify all target configurations and locators;
4. verify baseline source/test readiness without LLM calls;
5. generate contracts deterministically;
6. verify contract hashes by repeated extraction;
7. freeze RAG retrieval artifacts and hashes;
8. assemble final augmented design-artifact format;
9. perform the fixed prompt/context-budget audit;
10. verify non-RAG/RAG paired fields;
11. keep all formal configs disabled;
12. commit preparation;
13. separately enable the exact formal set in an enable-plan commit.

## 13. Formal stop rules

Stop before or during formal execution on:

- repository commit mismatch;
- tracked source changes before execution;
- Tree-sitter package-version mismatch;
- parser error;
- target-source overlap in RAG dependency paths;
- test/generated/report leakage;
- nondeterministic contract hash;
- retrieval/context hash mismatch;
- fixed context-budget rule violation;
- original source restoration hash mismatch;
- retrieved raw context entering code regeneration;
- retry, repair, or manual generated-code modification;
- reuse of a completed formal run ID.

A failure of generated code to build or pass tests is an experimental result,
not a reason to repair or rerun it.

## 14. Freeze rule

After the protocol/implementation preparation commit:

- do not add target-specific extractor rules;
- do not change extraction because of formal target outcomes;
- do not choose overloads based on compiler failures;
- do not modify code-regeneration rules in response to v6 formal failures;
- do not replace a formal v6 result with a pilot or sensitivity result.

A genuine pre-formal mechanical implementation bug may be corrected only
before formal enablement, with the correction documented in a separate
preparation commit and the complete no-LLM dry-run repeated.

## 15. Formal interpretation

Primary paired outcomes are:

```text
non-RAG PASS / RAG PASS
non-RAG PASS / RAG FAIL
non-RAG FAIL / RAG PASS
non-RAG FAIL / RAG FAIL
```

Report full-pipeline PASS rates and an exact McNemar comparison for the same
17 target IDs.

Test PASS means only that the frozen existing tests observed acceptable
behavior. It does not establish complete semantic equivalence.
