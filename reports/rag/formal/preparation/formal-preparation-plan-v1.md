# Formal RAG Preparation Plan v1

## 1. Scope and status

This is a plan-only artifact for preparing the formal 17-target RAG experiment. It does not authorize or perform retrieval, context generation, design generation, code regeneration, source replacement, Docker execution, build, test, or formal-target execution.

- Repository: `IchinaZiru/cpp-design-dataset`
- Branch: `agent/rag-protocol-v0-9`
- Preparation baseline: `69b539921635d5051d9362ed3148fc1568c48d4c`
- Formal target count: `17`
- Initial target state: all targets `enabled=false`
- Enablement rule: after the complete formal audit passes, enable exactly one target in an explicit, isolated commit
- LLM calls during this preparation task: `0`
- Retrieval executed during this preparation task: `false`
- Formal target executed during this preparation task: `false`
- Source replaced during this preparation task: `false`

The completed yaml-cpp mechanics pilot is evidence only that the replacement/configure/build/test/restoration mechanics can complete. It is not a formal result, a RAG treatment result, or evidence of RAG improvement.

## 2. Evidence frozen for this plan

| Artifact | SHA-256 | Use |
|---|---|---|
| `docs/rag_experiment_protocol.md` | `83f95da429f8d98b630a251fdee7d3c0d93d5de9cce235e75df3584b4feec69d` | Current protocol and all current TBD locations |
| `configs/rag/pilot/yaml_cpp_retrieval_pipeline_v2.json` | `02a15ea95318c917e8763b32a40fdbc56396134d5388f81c96028037a0b5c028` | Pilot-frozen retrieval values and implementation versions |
| `rag/retrieval/external-pilot/yaml-cpp/retrieval-v2/yaml-cpp-yaml-node-d2929956c2cd/retrieval_manifest.json` | `f924003cc66de2f5d29dd1c13c597aa6f889cbfa389f77e7178010b67dff2343` | Successful deterministic retrieval/context evidence |
| `reports/rag/pilot/external/yaml-cpp/yaml-node-run01-postmortem.json` | `28bd2db045c25e3f4790b2188315bb4ecf6ccc1e75b6118fae0cfca868b10274` | Immutable run01 limits and the reason for a separate mechanics pilot |
| `experiments/rag/pilot/mechanics/yaml-cpp/rag-mechanics-v1-yaml-cpp-yaml-node-replacement-eval-run01/mechanics_result.json` | `2deafc20bc66e74f419c92cebdf925530000eed6410729922c6e398d3a696f61` | Mechanics-only PASS and exact restoration evidence |
| `rag/environment/rag_environment_manifest.json` | `46b52712802ff9b4b630a44ab7e47edf91f11fe12fe24cdb7caebb2a60e0b4f1` | CPython and Tree-sitter package versions |
| `configs/rag/retrieval_v1.json` | `6723c18d1239c2ba588cc016852d3fd16a1878425bfef04f331430ba1a807fa1` | Parser package/version and common corpus/index rules |
| `reports/rag/pilot/external/yaml-cpp/candidate-selection-v2/external_pilot_selection.json` | `660eafc27072e4d04df321abe2c509ce063c61d154e625c214016cdbf3ef4170` | Five frozen external-pilot target IDs |
| `configs/rag/query_targets_v1.json` | `0b7653ea956302bde236adc8d60c326ed8fa08aa81c6c678084b1fb153c6e1a5` | Frozen 17-target registry |
| `configs/rag/query_v1.json` | `b2711084a80e13876c822a7b587520a14ba7cff262eba3e776c88072f5e4ade9` | Deterministic query policy |
| `scripts/rag/external_retrieval.py` | `f8bb1a42f232788aee72e785a713e74aeb78ddf93ff303901b485f36ac538545` | In-repository BM25/retrieval implementation |

## 3. Values to freeze identically for all 17 targets

| Field | Frozen value |
|---|---|
| `retrieval_top_k` | `12` |
| `context_budget_tokens` | `6000` |
| Tier 0 quota | `4` |
| Tier 1 quota | `4` |
| Tier 2 quota | `3` |
| Tier 3 quota | `1` |
| `token_counter_version` | `cpp-lexical-token-count-v1` |
| `context_format` | `combined-path-role-v1` |
| per-target override | prohibited |
| target-specific manual query | prohibited |
| formal target count | `17` |

`retrieval_top_k=12` and the tier quotas are selection caps. A context may contain fewer than 12 chunks only when deterministic filtering, eligible-candidate exhaustion, or the common token budget prevents filling all slots; the exact shortfall reason must be recorded and audited. No target-specific compensation is permitted.

## 4. Protocol update procedure: pre-pilot to post-pilot formal freeze

The future protocol-only commit must make the following evidence-backed edits to `docs/rag_experiment_protocol.md` without changing the experiment after formal results are observed:

1. Change protocol version from `0.9.1` to `1.0`, protocol status from `pre-pilot freeze` to `post-pilot formal freeze`, and retain `Formal execution status: not started`.
2. Complete the 1.0 revision-history row with the frozen pilot target IDs, format, top-k, budget, quotas, token counter, parser/runtime versions, and in-repository BM25 implementation version.
3. Replace the four `TBD_AFTER_PILOT` values in section 10 with the values in section 3 of this plan.
4. Freeze `context_format=combined-path-role-v1` and the five external-pilot target IDs from the candidate-selection artifact.
5. Replace the resolvable `TBD_IMPLEMENTATION` values with `tree-sitter==0.26.0`, `tree-sitter-cpp==0.23.4`, `in-repository-bm25-okapi-v1`, and `CPython 3.13.5`.
6. Do not invent an upstream Tree-sitter C++ grammar commit. Either revise the protocol field to explicitly freeze the installed distribution version `tree-sitter-cpp==0.23.4`, or add separately verified package-to-upstream-commit provenance before the formal freeze. Until one of these is recorded, the formal audit is blocked.
7. Record the yaml-cpp run01 limitation: retrieval and prompt isolation were validated, but code normalization failed before source replacement and semantic evaluation; the run must remain immutable.
8. Record the separate mechanics result as a non-RAG, non-formal mechanics validation only. It must not be counted as a formal result or RAG-effect evidence.
9. Re-run a textual audit confirming no `TBD_AFTER_PILOT` or `TBD_IMPLEMENTATION` remains before any target is enabled.

## 5. Complete current TBD inventory

The repository-wide search at the preparation baseline finds exactly eight uppercase TBD occurrences, all in `docs/rag_experiment_protocol.md`.

| Marker/location | Planned resolution | Existing artifact source | Status |
|---|---|---|---|
| `TBD_IMPLEMENTATION`, line 174, Tree-sitter Python package | `tree-sitter==0.26.0` | `rag/environment/rag_environment_manifest.json`; `configs/rag/retrieval_v1.json` | Resolved by evidence |
| `TBD_IMPLEMENTATION`, line 175, C++ grammar version/commit | `tree-sitter-cpp==0.23.4`; no upstream commit is recorded | Same two artifacts | Package version resolved; upstream commit is a blocker if retained as mandatory |
| `TBD_IMPLEMENTATION`, line 338, BM25 library/version | `in-repository-bm25-okapi-v1`; implementation file SHA-256 `f8bb1a42f232788aee72e785a713e74aeb78ddf93ff303901b485f36ac538545`; no third-party BM25 package | Pilot retrieval config, retrieval manifest, `scripts/rag/external_retrieval.py`, and absence from `requirements/rag.in` | Resolved by evidence |
| `TBD_AFTER_PILOT`, line 430, retrieval top-k | `12` | Pilot retrieval config and YAML::Node retrieval manifest | Resolved by evidence |
| `TBD_AFTER_PILOT`, line 431, total context token budget | `6000` | Pilot retrieval config and YAML::Node retrieval manifest | Resolved by evidence |
| `TBD_AFTER_PILOT`, line 432, category quota | Tier 0/1/2/3 = `4/4/3/1` | Pilot retrieval config and YAML::Node retrieval manifest | Resolved by evidence |
| `TBD_AFTER_PILOT`, line 433, token counter/version | `cpp-lexical-token-count-v1` | Pilot retrieval config and YAML::Node retrieval manifest | Resolved by evidence |
| `TBD_IMPLEMENTATION`, line 789, CPython | `CPython 3.13.5` | `rag/environment/rag_environment_manifest.json` | Resolved by evidence |

Related post-pilot fields that do not use an uppercase TBD marker must also be frozen:

- `context_format=combined-path-role-v1`, from the pilot retrieval config and manifest.
- Five pilot target IDs, from `external_pilot_selection.json`:
  - `yaml-cpp-yaml-node-d2929956c2cd`
  - `yaml-cpp-yaml-detail-get-idx-key-typename-std-enable-if-s-50aa23319a5e`
  - `yaml-cpp-yaml-detail-remove-idx-key-typename-std-enable-i-b8aacd8b022d`
  - `yaml-cpp-yaml-convert-std-string-3825140d3f5f`
  - `yaml-cpp-yaml-decodebase64-625c9379f8bd`

## 6. Planned configuration paths

Common formal retrieval configuration:

- `configs/rag/formal_retrieval_pipeline_v1.json`

All target configs must initially contain `enabled=false`:

- `configs/rag/targets/echo-web-server-block-deque.json`
- `configs/rag/targets/echo-web-server-buffer.json`
- `configs/rag/targets/echo-web-server-config.json`
- `configs/rag/targets/echo-web-server-heap-timer.json`
- `configs/rag/targets/echo-web-server-http.json`
- `configs/rag/targets/echo-web-server-io.json`
- `configs/rag/targets/echo-web-server-ip.json`
- `configs/rag/targets/echo-web-server-log.json`
- `configs/rag/targets/echo-web-server-thread-pool.json`
- `configs/rag/targets/echo-web-server-util.json`
- `configs/rag/targets/ini-cpp-ini-writer.json`
- `configs/rag/targets/ini-cpp-inireader.json`
- `configs/rag/targets/riscv-simulator-instruction.json`
- `configs/rag/targets/riscv-simulator-memory.json`
- `configs/rag/targets/riscv-simulator-parser.json`
- `configs/rag/targets/riscv-simulator-register.json`
- `configs/rag/targets/riscv-simulator-registerfile.json`

Each target config is derived from its frozen non-RAG config and may change only the fields allowed by protocol section 17. It must pin the common formal config hash, frozen query hash, context path/hash, source locators/hashes, one-shot markers, and `enabled=false`.

## 7. Deterministic generation of all 17 retrieval contexts

No step in this section was run by this task. The future preparation workflow is:

1. Verify the protocol 1.0 freeze commit, common config hash, target-registry hash, query-policy hash, environment manifest, exact repository commits, clean worktrees, and frozen target source hashes/ranges.
2. Validate the existing per-target `rag/query/<target-id>/query.json` and `query_validation.json` against the registry and source. Rebuild only when the formal preparation implementation explicitly requires an independent deterministic comparison; never add manual target-specific terms.
3. Use the same common retrieval configuration for every target: top-k 12, budget 6000, quotas 4/4/3/1, the frozen token counter and context format, no overrides.
4. Apply filters before ranking: forbidden paths, target-source overlap, previous LLM output, experiment/report/generated/test content, then duplicate content/range removal.
5. Run exact-symbol retrieval, allowed one-hop dependencies, AST-confirmed usage/call sites, and auxiliary in-repository BM25 in the frozen tier order and tie-break order.
6. Serialize each candidate set, selected set, context, corpus snapshot, query snapshot, and manifest canonically under `rag/retrieval/formal/<target-id>/`.
7. Independently regenerate each target from the same commit/config/environment in a separate temporary output. Compare query, corpus/index, candidate order, selected IDs/order, serialized context bytes, and every declared SHA-256.
8. Publish only byte-identical deterministic outputs. Preserve mismatching attempts as failure evidence outside the canonical output and stop the whole formal batch.
9. Keep all 17 target configs disabled throughout generation and audit.

## 8. Per-context validation

Every formal context must pass all of the following before publication:

- Token budget: `context_token_count <= 6000` using exactly `cpp-lexical-token-count-v1`.
- Top-k: `selected_chunk_count <= 12`; any count below 12 has an explicit deterministic shortfall reason.
- Category quota: Tier 0/1/2/3 selected counts do not exceed `4/4/3/1`, and selection order follows the common tier/ranking rules.
- Target source overlap: selected path/ranges have zero overlap with the frozen half-open target ranges; `module_files` excludes the complete target files.
- Forbidden path: zero selected test, benchmark, build, generated, report/log, experiment, previous-LLM, README/docs, vendor/third-party/external content.
- Duplicate content: no repeated chunk ID or content SHA-256, no equivalent overlapping range, and every intentionally retained declaration/definition pair has a recorded reason.
- Leakage: no verbatim target source, test answer, expected output, prior generated output, prior report, or formal result in `context.txt`.
- Deterministic regeneration: two independent builds match in query hash, corpus/index hashes, candidate order, selected IDs/order, context bytes, and manifest content hashes.
- SHA-256: every artifact hash is computed from exact bytes, cross-linked, and reverified after publication; paths are repository-relative POSIX and no local absolute path or timestamp enters a content hash.

Any failed check is a formal-batch stop, not an invitation to tune a target-specific query, quota, budget, or override.

## 9. Design/code input isolation

Design generation receives only:

1. the frozen design instruction/output constraints;
2. a clearly delimited frozen target-source section; and
3. a separately delimited, pre-generated `context.txt` whose path and SHA-256 are pinned in the target config.

Code regeneration receives only:

1. the single frozen design document from that target's one-shot design call; and
2. the fixed scaffold derived and hashed before the code-generation call.

Code regeneration must not receive target source bodies, retrieved context, selected chunks, candidate lists, query artifacts, repository files, design-generation prompt/request, audit findings, or prior outputs. The plan and request artifacts must record direct-input paths and hashes so an audit can prove this separation before enabling a target.

## 10. Commit strategy: all-disabled to one-enabled

1. `docs(rag): freeze formal protocol after pilot` — update only the protocol and resolve every TBD/blocker supported by evidence.
2. `feat(rag): add disabled formal target configs` — add the common config and all 17 target configs, each `enabled=false`; validate that the enabled count is zero.
3. `feat(rag): add formal preparation tooling` — add deterministic formal retrieval/context and audit tooling with unit tests; do not run retrieval in this commit.
4. `experiment(rag): freeze formal retrieval contexts` — after two-build determinism and all context audits pass, add the 17 frozen context artifact sets and aggregate audit report while enabled count remains zero.
5. `experiment(rag): enable formal target <target-id>` — isolated commit changing exactly one audited target from `enabled=false` to `enabled=true`; assert enabled count is exactly one and every other target remains false.
6. Execute that one target once under its new run ID and commit immutable results separately. On a target-level generation/build/test failure, record FAIL and continue only according to protocol; never retry the same run ID.
7. Before the next target, make an isolated commit returning the completed target to disabled/all-disabled state, verify result immutability, then make another isolated one-target enable commit. At no point may more than one formal target be enabled.

No force push, rebase, reset, history rewrite, bulk `git add .`, or result repair is permitted.

## 11. Formal pre-execution audit checklist

- Protocol is version 1.0/post-pilot formal freeze and contains no TBD markers.
- The grammar provenance blocker is resolved without guessing.
- Common config has the exact values in section 3 and a stable SHA-256.
- Exactly 17 target configs exist; all are initially disabled and reference the common config hash.
- Target IDs, repositories, commits, granularities, source paths/ranges/hashes, tests, model/generation settings, Docker settings, and retry/repair policies match frozen non-RAG evidence except for protocol-permitted RAG fields.
- All repositories and submodules are at pinned commits and clean.
- Environment manifest and locked dependencies match; no unrecorded package/version is used.
- Each query is deterministic, LLM-free, registry-linked, and contains no manual target-specific addition.
- Every formal context passes every check in section 8 and has two-build deterministic evidence.
- Aggregate audit confirms one common setting across all 17 targets and zero per-target overrides.
- Design prompts include exactly separated source/context sections and pin exact input hashes.
- Code prompts exclude original source, retrieval/context/query/repository artifacts, and design audit additions.
- One-shot attempt/failure/result markers and no-retry/no-repair/no-manual-patch policies are present.
- Replacement backup/finally-restoration and exact-byte/hash/clean-worktree checks match the validated mechanics pipeline.
- Non-RAG results and immutable yaml-cpp run01 hashes are unchanged.
- LLM, Ollama, Docker, source replacement, build, and tests have not run during preparation.
- Enabled formal target count is zero before the explicit enable commit, and exactly one after it.

## 12. Expected future artifacts

Preparation/freeze artifacts:

- Updated `docs/rag_experiment_protocol.md`
- `configs/rag/formal_retrieval_pipeline_v1.json`
- The 17 target configs listed in section 6
- Formal preparation tooling and unit tests under `scripts/rag/` and `tests/rag/`
- `reports/rag/formal/preparation/formal-context-audit-v1.json`
- `reports/rag/formal/preparation/formal-context-audit-v1.md`

For each target, `rag/retrieval/formal/<target-id>/`:

- `corpus_manifest.json`
- `query.json`
- `candidates.jsonl`
- `selected_chunks.jsonl`
- `context.txt`
- `retrieval_manifest.json`

For each one-shot formal execution, `experiments/rag/rag-v1-formal-<target-id>/`:

- frozen design prompt/request/attempt/contact/response/result and `design_document.md`
- frozen scaffold and code prompt/request/attempt/contact/response/result
- source backup and replacement/restoration evidence
- configure/build/direct/full stdout, stderr, exit code, timeout, and status records
- immutable target result manifest

Aggregate formal outputs:

- `reports/rag/formal/formal-results-v1.json`
- `reports/rag/formal/formal-results-v1.md`
- paired transition and seven-stage diagnosis artifacts under `reports/rag/analysis/`
- updated `manifests/rag_targets.csv` and `manifests/rag_runs.csv`

## 13. Stop conditions and current blockers

Stop before enabling any formal target if any of the following is true:

- branch, local/remote HEAD, required ancestor, or clean-worktree checks fail;
- any referenced evidence/config/source/query/index/context hash differs;
- the upstream grammar commit remains mandatory but unverified;
- any TBD marker remains in the formal-freeze protocol;
- common settings differ across targets, an override exists, or a manual target query exists;
- target count is not exactly 17 or an ID/commit/source/test/non-RAG setting differs;
- a repository/submodule is dirty or at the wrong commit;
- context budget, top-k, quota, overlap, forbidden-path, duplicate, leakage, determinism, or SHA-256 validation fails;
- design/code input isolation cannot be proven from exact stored bytes and hashes;
- non-RAG results or immutable yaml-cpp run01 evidence changed;
- more than one target is enabled, or any target is enabled before the aggregate audit passes;
- an attempt/result marker already exists for the proposed run ID;
- source restoration or clean-worktree verification fails;
- an action would require retry, repair, overwrite, manual patch, or reuse of a run ID.

Current blockers to formal execution are expected and intentional: protocol 1.0 is not yet edited; the grammar commit provenance question is unresolved; the common/17 target formal configs do not yet exist; formal contexts have not been generated or audited; and all targets must remain disabled. This plan does not clear those blockers—it defines how to clear them before execution.

## 14. Planned commit split

The future preparation work should use the five preparation commits in section 10, followed by isolated per-target enable/result/deactivate commits. The present task itself creates only this Markdown plan and its JSON counterpart, staged by exact path, with commit message:

`experiment(rag): plan formal preparation`
