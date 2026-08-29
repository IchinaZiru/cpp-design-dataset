"""Sequential, one-shot seed-sweep runner for the original comment-absent A/B treatment.

The runner does not choose a favourable seed.  It requires an explicitly named
predeclared seed, runs every target and both A/B conditions once for that seed,
and preserves a per-seed report for later comparison.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import canonical_json_bytes, sha256_file
from scripts.rag.roundtrip_ab import RoundtripABError, git_output, load_json, resolve_repository_root, verify_repository
from scripts.rag.roundtrip_ab_formal import build_design_request_v2, load_common_v2, load_formal_manifest, validate_target_v2
from scripts.research import run_comment_ablation_ab as original


SCHEMA = "comment-ablation-seed-sweep-v1"
RUN_ID = "comment-ablation-seed-sweep-v1"


def _path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load(root: Path, config_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]], Path]:
    config = load_json(config_path)
    if config.get("artifact_schema_version") != SCHEMA or config.get("formal_result") is not False:
        raise RoundtripABError("seed-sweep config schema differs")
    if config.get("seeds") != [42, 43, 44, 45, 46] or config.get("conditions") != ["A", "B"]:
        raise RoundtripABError("predeclared seed or condition list differs")
    if config.get("temperature") != 0.1:
        raise RoundtripABError("seed sweep temperature must be 0.1")
    one_shot = config.get("one_shot")
    if not isinstance(one_shot, Mapping):
        raise RoundtripABError("one_shot is missing")
    expected_one_shot = {"design_generation_count": 1, "code_generation_count": 1, "retry": False, "automatic_repair": False, "manual_patch": False, "overwrite": False}
    if any(one_shot.get(key) != value for key, value in expected_one_shot.items()):
        raise RoundtripABError("seed-sweep one-shot policy differs")
    common_path = _path(root, str(config["source_common_path"]))
    manifest_path = _path(root, str(config["source_comment_ablation_manifest_path"]))
    if sha256_file(common_path) != str(config["source_common_sha256"]):
        raise RoundtripABError("source common SHA-256 mismatch")
    if sha256_file(manifest_path) != str(config["source_comment_ablation_manifest_sha256"]):
        raise RoundtripABError("source comment-ablation manifest SHA-256 mismatch")
    manifest = load_json(manifest_path)
    entries = original._entry_map(manifest)
    if len(entries) != 17:
        raise RoundtripABError("source manifest must contain 17 targets")
    frozen_root = _path(root, str(config["frozen_comment_free_artifact_root"])).resolve()
    if not (frozen_root / "derived/comment-ablation-v1/target-inputs/comment_free_manifest.json").is_file():
        raise RoundtripABError("frozen comment-free artifact root is incomplete")
    return config, manifest, entries, frozen_root


def _seed_common(root: Path, config: Mapping[str, Any], seed: int) -> dict[str, Any]:
    common = copy.deepcopy(load_common_v2(_path(root, str(config["source_common_path"])), root))
    generation = dict(common["generation"])
    for key in ("design_options", "code_options"):
        options = dict(generation[key])
        options["seed"] = seed
        options["temperature"] = float(config["temperature"])
        generation[key] = options
    common["generation"] = generation
    if generation["model"] != config["model"]:
        raise RoundtripABError("model differs from predeclared seed sweep model")
    return common


@contextmanager
def _frozen_comment_free_loaders(frozen_root: Path) -> Iterator[None]:
    """Use the byte-verified r02 comment-free inputs without modifying them."""

    load_inputs = original._load_comment_free_inputs
    load_retrieval = original._load_comment_free_retrieval
    copy_retrieval = original._copy_retrieval_artifacts

    def frozen_inputs(_root: Path, target: Mapping[str, Any], entry: Mapping[str, Any], repository: Path):
        return load_inputs(frozen_root, target, entry, repository)

    def frozen_retrieval(_root: Path, target: Mapping[str, Any], common: Mapping[str, Any], entry: Mapping[str, Any]):
        return load_retrieval(frozen_root, target, common, entry)

    def frozen_copy(_root: Path, run_root: Path, entry: Mapping[str, Any], retrieval: Any):
        return copy_retrieval(frozen_root, run_root, entry, retrieval)

    original._load_comment_free_inputs = frozen_inputs
    original._load_comment_free_retrieval = frozen_retrieval
    original._copy_retrieval_artifacts = frozen_copy
    try:
        yield
    finally:
        original._load_comment_free_inputs = load_inputs
        original._load_comment_free_retrieval = load_retrieval
        original._copy_retrieval_artifacts = copy_retrieval


def preflight(root: Path, config_path: Path, seed: int) -> dict[str, Any]:
    config, manifest, entries, frozen_root = _load(root, config_path)
    if seed not in config["seeds"]:
        raise RoundtripABError("seed is not predeclared")
    seed_root = _path(root, str(config["output_root"])) / f"seed-{seed}"
    report = _path(root, str(config["report_root"])) / f"seed-{seed}/batch_execution.json"
    if seed_root.exists() or report.exists():
        raise RoundtripABError("seed output or report already exists; retry/overwrite is forbidden")
    if git_output(root, "status", "--short", "--untracked-files=no"):
        raise RoundtripABError("tracked project changes exist before seed execution")
    common = _seed_common(root, config, seed)
    checked = 0
    with _frozen_comment_free_loaders(frozen_root):
        for target_id, entry in sorted(entries.items()):
            target_path = root / str(entry["source_target_config_path"])
            if sha256_file(target_path) != str(entry["source_target_config_sha256"]):
                raise RoundtripABError(f"source target config SHA-256 mismatch: {target_id}")
            target = load_json(target_path)
            validate_target_v2(target, formal=True)
            repository = resolve_repository_root(target, root)
            verify_repository(target, repository)
            inputs = original._load_comment_free_inputs(root, target, entry, repository)
            retrieval = original._load_comment_free_retrieval(root, target, common, entry)
            a = build_design_request_v2(target, common, root, inputs, condition="A", repository_context=None)
            b = build_design_request_v2(target, common, root, inputs, condition="B", repository_context=retrieval.context)
            if any(a.payload[key] != b.payload[key] for key in ("model", "options", "stream")):
                raise RoundtripABError(f"A/B generation field differs: {target_id}")
            if a.audit["repository_context_injected"] or not b.audit["repository_context_injected"]:
                raise RoundtripABError(f"A/B RAG isolation differs: {target_id}")
            for condition in ("A", "B"):
                if (seed_root / target_id / f"condition-{condition.lower()}").exists():
                    raise RoundtripABError("one-shot condition output already exists")
            checked += 2
    return {"artifact_schema_version": "comment-ablation-seed-sweep-preflight-v1", "status": "pass", "run_id": RUN_ID, "seed": seed, "temperature": config["temperature"], "target_count": 17, "condition_count": 34, "design_prompts_checked": checked, "llm_call_count": 0, "generation_server_contacted": False, "formal_result": False}


def execute_seed(root: Path, config_path: Path, seed: int) -> dict[str, Any]:
    plan = preflight(root, config_path, seed)
    config, manifest, entries, frozen_root = _load(root, config_path)
    common = _seed_common(root, config, seed)
    seed_root = _path(root, str(config["output_root"])) / f"seed-{seed}"
    results: list[dict[str, Any]] = []
    previous_run_id, previous_replica = original.REPLICATION_RUN_ID, original.REPLICATES_RUN_ID
    original.REPLICATION_RUN_ID = f"{RUN_ID}-seed-{seed}"
    original.REPLICATES_RUN_ID = "comment-ablation-v1"
    try:
        with _frozen_comment_free_loaders(frozen_root):
            for target_id, source_entry in sorted(entries.items()):
                entry = copy.deepcopy(source_entry)
                entry["output_root"] = (seed_root / target_id).relative_to(root).as_posix()
                for condition in ("A", "B"):
                    result = original._execute_one(root, manifest, common, entry, condition)
                    results.append({"target_id": target_id, "condition": condition, "status": result["status"], "overall_pass": result["overall_pass"], "stages": result["stages"]})
    finally:
        original.REPLICATION_RUN_ID, original.REPLICATES_RUN_ID = previous_run_id, previous_replica
    summary = {"artifact_schema_version": "comment-ablation-seed-sweep-result-v1", "status": "complete", "run_id": RUN_ID, "formal_result": False, "seed": seed, "temperature": config["temperature"], "retry_performed": False, "automatic_repair_performed": False, "manual_patch_performed": False, "preflight": plan, "results": results, "a_pass": sum(x["overall_pass"] for x in results if x["condition"] == "A"), "b_pass": sum(x["overall_pass"] for x in results if x["condition"] == "B")}
    report = _path(root, str(config["report_root"])) / f"seed-{seed}/batch_execution.json"
    _write_report(report, summary)
    return summary


def _write_report(path: Path, content: Mapping[str, Any]) -> None:
    if path.exists():
        raise RoundtripABError("refusing to overwrite seed report")
    path.parent.mkdir(parents=True, exist_ok=False)
    path.write_bytes(canonical_json_bytes(content))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or run one predeclared seed of the comment-absent A/B sweep.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("configs/rag/comment_ablation_seed_sweep_v1/seed_sweep.json"))
    parser.add_argument("--seed", type=int, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute-seed", action="store_true")
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    config_path = _path(root, str(args.config))
    result = preflight(root, config_path, args.seed) if args.plan_only else execute_seed(root, config_path, args.seed)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
