# Full-source design RAG v2 formal protocol

## Purpose

Compare a new full-source non-RAG condition with a full-source design-knowledge RAG condition on the same 17 frozen C++ targets.

The old non-RAG result set (`N=17`, `PASS=6`, `FAIL=11`) remains frozen. It is retained as historical background and is not rerun, overwritten, or treated as the direct control because the design-generation observation scope changed.

## Formal comparison

For each target, both conditions use the same:

- repository commit;
- source and observation files;
- replacement granularity and locator;
- model and generation options;
- Docker image and test commands;
- fixed-interface scaffold construction;
- code-regeneration prompt structure;
- single design generation and single code regeneration;
- no retry, no automatic repair, and no manual generated-code edit.

The only experimental treatment difference is design-generation knowledge:

- non-RAG: no additional design knowledge;
- RAG: `knowledge/detailed-design/general-v2.md` is inserted during design generation as required additional artifacts.

RAG context and the original source are not supplied during code regeneration. Code regeneration receives only the generated design document, fixed-interface scaffold, and dependency/include context.

## Formal target inventory

### `module_files` — 11 targets

1. `echo-web-server-block-deque`
2. `echo-web-server-buffer`
3. `echo-web-server-config`
4. `echo-web-server-heap-timer`
5. `echo-web-server-http`
6. `echo-web-server-io`
7. `echo-web-server-ip`
8. `echo-web-server-log`
9. `echo-web-server-thread-pool`
10. `echo-web-server-util`
11. `riscv-simulator-instruction`

### `class_span` — 5 targets

1. `ini-cpp-inireader`
2. `riscv-simulator-memory`
3. `riscv-simulator-parser`
4. `riscv-simulator-register`
5. `riscv-simulator-registerfile`

### `function` — 1 target

1. `ini-cpp-iniwriter` (`INIWriter::write`)

`Session` is excluded from the formal 17. Its pilot artifacts are mechanics evidence only.

## Model settings

Both formal conditions use `qwen2.5-coder:32b` with the v2 mechanics-pilot context/output settings:

- temperature: `0`;
- seed: `42`;
- `num_ctx`: `16384`;
- `num_predict`: `8192`;
- generations per stage: `1`;
- retry: `false`;
- automatic repair: `false`.

The remaining canonical model options are inherited from each target config.

## Run and artifact rules

- All committed formal configs are disabled.
- Execution uses a temporary enabled copy; committed configs are not modified.
- Every condition has a unique `experiment_id` and `run_id`.
- An existing experiment directory is never overwritten or rerun.
- A terminal failure is preserved as a formal artifact.
- Source restoration and tracked-clean state are verified after every attempt.
- A newly encountered pipeline failure stops the batch after its artifact is committed and pushed. Re-running the batch skips that terminal artifact and continues with untouched run IDs.
- Behavioral evaluation failure (`overall_pass=false`) is a valid result and does not trigger repair or retry.

## Result interpretation

A PASS means the configured build and tests passed after regenerated code replacement and exact source restoration. It is evidence only for behavior observed by those tests, not proof of complete semantic equivalence.

The paired final analysis reports:

- `FAIL -> PASS`;
- `PASS -> FAIL`;
- `PASS -> PASS`;
- `FAIL -> FAIL`.

The principal statistical comparison is exact McNemar on the 17 paired targets, with the limitations of the small sample and test-suite coverage stated explicitly.
