from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import canonical_json_bytes, sha256_file
from scripts.rag.roundtrip_ab import RoundtripABError, _write_exclusive, git_output, load_json
from scripts.rag.roundtrip_ab_formal import execute_condition_v2_once, load_common_v2, load_formal_manifest
from scripts.research import run_comment_ablation_ab as absent
from scripts.research import run_comment_ablation_seed_sweep as sweep


RUN_ID = "seed43-cross-model-comment-matrix-v1"
CONFIG = Path("configs/rag/seed43_cross_model_comment_matrix_v1/matrix.json")
STATE = Path("configs/rag/seed43_cross_model_comment_matrix_v1/runtime-v2")
OUTPUT = Path("experiments/rag/seed43-cross-model-comment-matrix-v1")
REPORT = Path("reports/rag/seed43-cross-model-comment-matrix-v1")
FORMAL_MANIFEST = Path("configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json")
ABSENT_MANIFEST = Path("configs/rag/comment_ablation_v1_replication_02/formal/evaluation_manifest.json")
BASE_COMMON = Path("configs/rag/roundtrip_ab_v1/common.json")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RoundtripABError(f"JSON root must be object: {path}")
    return value


def _target_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    targets = manifest.get("targets")
    if not isinstance(targets, list) or len(targets) != 17:
        raise RoundtripABError("source manifest must have exactly 17 targets")
    result = {str(x["target_id"]): dict(x) for x in targets if isinstance(x, dict)}
    if len(result) != 17:
        raise RoundtripABError("source manifest target IDs are not unique")
    return result


def _common(root: Path, model: str, matrix: Mapping[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(load_common_v2(root / BASE_COMMON, root))
    generation = value["generation"]
    generation["model"] = model
    for key in ("design_options", "code_options"):
        generation[key]["seed"] = matrix["seed"]
        generation[key]["temperature"] = matrix["temperature"]
    return value


def _state_paths(root: Path) -> tuple[Path, Path, Path]:
    base = root / STATE
    return base / "qwen_common.json", base / "devstral_common.json", base / "authorization.json"


def prepare(root: Path) -> dict[str, Any]:
    matrix = _read(root / CONFIG)
    if matrix.get("run_id") != RUN_ID or matrix.get("seed") != 43 or matrix.get("temperature") != 0.1:
        raise RoundtripABError("matrix must remain frozen at seed=43, temperature=0.1")
    qwen_path, devstral_path, auth_path = _state_paths(root)
    for path in (qwen_path, devstral_path, auth_path):
        if path.exists():
            raise RoundtripABError(f"refusing to overwrite frozen runtime file: {path}")
    qwen = _common(root, str(matrix["models"]["qwen"]), matrix)
    devstral = _common(root, str(matrix["models"]["devstral"]), matrix)
    _write_exclusive(qwen_path, canonical_json_bytes(qwen))
    _write_exclusive(devstral_path, canonical_json_bytes(devstral))
    auth = {"artifact_schema_version": "seed43-cross-model-comment-matrix-authorization-v1", "authorized": False,
            "matrix_sha256": sha256_file(root / CONFIG), "qwen_common_sha256": sha256_file(qwen_path),
            "devstral_common_sha256": sha256_file(devstral_path), "runner_sha256": sha256_file(root / Path(__file__).relative_to(root)),
            "retry": False, "automatic_repair": False, "manual_patch": False}
    _write_exclusive(auth_path, canonical_json_bytes(auth))
    return {"status": "prepared", "llm_call_count": 0, "generation_server_contacted": False}


def _load(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    matrix = _read(root / CONFIG)
    qwen_path, devstral_path, auth_path = _state_paths(root)
    qwen, devstral, auth = _read(qwen_path), _read(devstral_path), _read(auth_path)
    runner = root / Path(__file__).resolve().relative_to(root.resolve())
    if auth.get("matrix_sha256") != sha256_file(root / CONFIG) or auth.get("qwen_common_sha256") != sha256_file(qwen_path) or auth.get("devstral_common_sha256") != sha256_file(devstral_path) or auth.get("runner_sha256") != sha256_file(runner):
        raise RoundtripABError("frozen runtime binding differs")
    return matrix, qwen, devstral, auth, _read(root / ABSENT_MANIFEST)


def preflight(root: Path) -> dict[str, Any]:
    matrix, qwen, devstral, auth, absent_manifest = _load(root)
    formal = load_formal_manifest(root / FORMAL_MANIFEST, root)
    formal_map, absent_map = _target_map(formal), _target_map(absent_manifest)
    if set(formal_map) != set(absent_map):
        raise RoundtripABError("present/absent target sets differ")
    used: list[str] = []
    for target_id, item in formal_map.items():
        if sha256_file(root / str(item["target_config_path"])) != str(item["target_config_sha256"]):
            raise RoundtripABError(f"target config hash differs: {target_id}")
        for model_key, comment in (("qwen", "comments-present"), ("devstral", "comments-present"), ("devstral", "comments-absent")):
            for condition in ("a", "b"):
                path = root / OUTPUT / model_key / comment / target_id / f"condition-{condition}"
                if path.exists(): used.append(str(path))
    if used:
        raise RoundtripABError(f"one-shot output already exists: {used[0]}")
    return {"artifact_schema_version": "seed43-cross-model-comment-matrix-preflight-v1", "status": "pass", "run_id": RUN_ID,
            "target_count": 17, "new_cell_count": 6, "condition_count": 102, "expected_llm_call_count": 204,
            "seed": matrix["seed"], "temperature": matrix["temperature"], "qwen_model": qwen["generation"]["model"],
            "devstral_model": devstral["generation"]["model"], "target_config_hashes_match": True,
            "all_output_roots_unused": True, "authorization_currently_enabled": auth.get("authorized") is True,
            "llm_call_count": 0, "generation_server_contacted": False}


def authorize(root: Path) -> dict[str, Any]:
    result = preflight(root)
    _, _, _, auth, _ = _load(root)
    if auth.get("authorized"):
        raise RoundtripABError("already authorized")
    auth["authorized"] = True
    _state_paths(root)[2].write_bytes(canonical_json_bytes(auth))
    result["status"] = "authorized"
    return result


def _present_config(root: Path, source: Mapping[str, Any], output_root: Path) -> dict[str, Any]:
    config = copy.deepcopy(load_json(root / str(source["target_config_path"])))
    config["execution"]["enabled"] = True
    config["execution"]["output_root"] = output_root.as_posix()
    return config


def _terminal(path: Path) -> dict[str, Any]:
    for name in ("result.json", "failure.json"):
        if (path / name).is_file(): return _read(path / name)
    raise RoundtripABError(f"no terminal result: {path}")


def _run_present(root: Path, source: Mapping[str, Any], common: Mapping[str, Any], model_key: str, target: str, condition: str) -> dict[str, Any]:
    base = OUTPUT / model_key / "comments-present" / target
    config = _present_config(root, source, base)
    run = root / base / f"condition-{condition.lower()}"
    try:
        return execute_condition_v2_once(config, common, root, condition, formal=True)
    except Exception:
        return _terminal(run)


def _run_absent(root: Path, manifest: Mapping[str, Any], source: Mapping[str, Any], common: Mapping[str, Any], target: str, condition: str) -> dict[str, Any]:
    entry = copy.deepcopy(dict(source))
    entry["output_root"] = (OUTPUT / "devstral" / "comments-absent" / target).as_posix()
    run = root / entry["output_root"] / f"condition-{condition.lower()}"
    try:
        return absent._execute_one(root, manifest, common, entry, condition)
    except Exception:
        return _terminal(run)


def execute(root: Path) -> dict[str, Any]:
    plan = preflight(root)
    matrix, qwen, devstral, auth, absent_manifest = _load(root)
    if auth.get("authorized") is not True: raise RoundtripABError("execution is not authorized")
    if git_output(root, "status", "--short", "--untracked-files=no"):
        raise RoundtripABError("tracked worktree changes are not allowed")
    formal = load_formal_manifest(root / FORMAL_MANIFEST, root)
    formal_map, absent_map = _target_map(formal), _target_map(absent_manifest)
    results: list[dict[str, Any]] = []
    frozen_root = root.parent / "qwen-ca-r02"
    with sweep._frozen_comment_free_loaders(frozen_root):
        for target in [str(x["target_id"]) for x in formal["targets"]]:
            for model_key, comment, common in (("qwen", "comments-present", qwen), ("devstral", "comments-present", devstral), ("devstral", "comments-absent", devstral)):
                for condition in ("A", "B"):
                    result = _run_present(root, formal_map[target], common, model_key, target, condition) if comment == "comments-present" else _run_absent(root, absent_manifest, absent_map[target], common, target, condition)
                    results.append({"target_id": target, "model": model_key, "comment_condition": comment, "condition": condition,
                                    "overall_pass": result.get("overall_pass") is True, "status": result.get("status"),
                                    "stages": result.get("stages", {}), "error": result.get("error"), "llm_call_count": result.get("llm_call_count", 0)})
                    print(f"{target} {model_key} {comment} {condition}: {result.get('status')}", flush=True)
    cells = {}
    for model_key, comment in (("qwen", "comments-present"), ("devstral", "comments-present"), ("devstral", "comments-absent")):
        for condition in ("A", "B"):
            selected=[x for x in results if x["model"]==model_key and x["comment_condition"]==comment and x["condition"]==condition]
            cells[f"{model_key}_{comment}_{condition}"]={"pass":sum(x["overall_pass"] for x in selected),"fail":17-sum(x["overall_pass"] for x in selected)}
    summary={"artifact_schema_version":"seed43-cross-model-comment-matrix-result-v1","status":"complete","formal_result":False,"purpose":matrix["purpose"],"run_id":RUN_ID,"preflight":plan,"results":results,"cells":cells,"retry_performed":False,"automatic_repair_performed":False,"manual_patch_performed":False}
    _write_exclusive(root / REPORT / "batch_execution.json", canonical_json_bytes(summary))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Seed-43 temperature-0.1 exploratory cross-model/comment matrix.")
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare",action="store_true"); mode.add_argument("--preflight",action="store_true"); mode.add_argument("--authorize",action="store_true"); mode.add_argument("--execute",action="store_true")
    parser.add_argument("--project-root",type=Path,default=Path.cwd()); args=parser.parse_args(argv); root=args.project_root.resolve()
    result=prepare(root) if args.prepare else preflight(root) if args.preflight else authorize(root) if args.authorize else execute(root)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
