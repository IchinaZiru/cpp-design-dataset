# v4 source-faithful detailed-design evaluation

v4 is a post-hoc refinement/sensitivity evaluation informed by v3 formal failures.
It does not replace v3 formal results.

## Local sequence

Start from the current v3 branch/commit, then create a separate v4 branch.

```powershell
git switch experiment/prompt-preserving-flowchart-rag-v3
git pull
git switch -c experiment/source-faithful-detailed-design-rag-v4
```

After applying the v4 patch/files, generate the 17 disabled configs and run the mechanical plan check:

```powershell
py -3 .\scripts\roundtrip_v4\generate_evaluation_configs_v4.py
py -3 .\scripts\roundtrip_v4\run_evaluation_batch_v4.py
```

The second command is a mechanical preflight only and must report `llm_called: false` and `target_count: 17`.

Before LLM execution, commit only the named v4 implementation/config paths so the parent repository is clean:

```powershell
git add -- .\knowledge\detailed-design\general-v4.md .\docs\experiments\source_faithful_detailed_design_rag_v4_evaluation_protocol.md .\scripts\roundtrip_v4 .\configs\roundtrip_v4\evaluation
git commit -m "feat: prepare source-faithful RAG v4 evaluation"
```

If the plan is correct and the repository/submodules are clean, execute exactly once:

```powershell
py -3 .\scripts\roundtrip_v4\run_evaluation_batch_v4.py --execute
```

Use `--push` only if automatic per-target/result commits should also be pushed.

No retry, repair, or manual generated-code editing is allowed.
