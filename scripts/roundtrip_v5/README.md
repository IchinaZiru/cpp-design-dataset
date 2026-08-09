# v5 Direct-Include Repository-Context RAG

v5 is a post-hoc refinement of the frozen v4 evaluation. It keeps the v4 prompt, model, source scope, code-regeneration inputs, test commands, retry policy, and output-contract behavior unchanged. The intended treatment difference is only repository-context retrieval.

## Retrieval rule

For every configured `source_file`:

1. Extract only `#include "..."` directives.
2. Resolve the included path against tracked files in the pinned repository.
3. If the resolved file is already one of the target `source_files`, do not retrieve it again.
4. Otherwise add the entire resolved repository file to design-generation context.
5. Deduplicate by repository-relative path.
6. Do not follow includes from retrieved files. Retrieval depth is exactly one hop.
7. Never use an LLM to choose queries, files, or ranking.
8. Ambiguous or unresolved quoted includes block formal execution until the general resolver is fixed; do not add target-specific exceptions.

Angle-bracket includes such as `<string>` are intentionally not retrieved.

## Local sequence

Create a new branch from the frozen v4 HEAD before copying these files into the repository.

```powershell
git switch experiment/source-faithful-detailed-design-rag-v4
git pull --ff-only
git switch -c experiment/source-faithful-detailed-design-direct-include-rag-v5
```

Generate disabled v5 configs:

```powershell
py -3 .\scripts\roundtrip_v5\generate_evaluation_configs_v5.py
py -3 .\scripts\roundtrip_v5\run_evaluation_batch_v5.py
```

The second command is plan-only and must report `llm_called: false` and `target_count: 17`.

Run retrieval-only audit. This calls no LLM, Docker, CMake, build, or test:

```powershell
py -3 .\scripts\roundtrip_v5\audit_direct_include_retrieval_v5.py
```

Review `analysis/retrieval_v5/preflight_summary.json`. Formal execution is allowed only when `go_for_formal: true`. Also spot-check the selected paths and `context.txt` for representative targets such as Instruction, ThreadPool, and Parser.

The preflight records the exact combined-context SHA-256 for every target. Formal execution recomputes retrieval and refuses to run a target if its context hash differs from the frozen preflight.

Before formal execution, commit only the named v5 preparation paths. Do not use `git add .`.

```powershell
git add -- `
  .\docs\experiments\source_faithful_detailed_design_direct_include_rag_v5_evaluation_protocol.md `
  .\scripts\roundtrip_v5 `
  .\configs\roundtrip_v5\evaluation `
  .\analysis\retrieval_v5

git commit -m "feat(rag): add direct-include repository context v5"
```

Then execute exactly once:

```powershell
py -3 .\scripts\roundtrip_v5\run_evaluation_batch_v5.py --execute
```

Use `--push` only if automatic per-target/result commits should also be pushed.

No retry, automatic repair, or manual generated-code editing is allowed.
