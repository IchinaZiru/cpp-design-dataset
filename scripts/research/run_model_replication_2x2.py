from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import canonical_json_bytes, sha256_bytes, sha256_file
from scripts.rag.roundtrip_ab import (
    CONDITIONS,
    RoundtripABError,
    _mapping,
    _write_exclusive,
    git_output,
    load_json,
    load_target_inputs,
    resolve_repository_root,
    utc_now,
)
from scripts.rag.roundtrip_ab_formal import (
    build_code_request_v2,
    build_design_request_v2,
    build_retrieval_bundle_v2,
    execute_condition_v2_once,
    load_common_v2,
    load_formal_manifest,
    validate_target_v2,
)
from scripts.research import run_comment_ablation_ab as comment_ablation


BASELINE_COMMIT = "3b451f75dd8d8853fb34815143a9e54acef2b1a4"
MODEL_TAG = "gemma3:27b"
MODEL_ID = "a418f5838eaf"

MANIFEST_SCHEMA = "model-replication-2x2-manifest-v1"
AUTHORIZATION_SCHEMA = "model-replication-2x2-authorization-v1"
PREFLIGHT_SCHEMA = "model-replication-2x2-preflight-v1"

DEFAULT_QWEN_COMMON = Path("configs/rag/roundtrip_ab_v1/common.json")
DEFAULT_SOURCE_FORMAL_MANIFEST = Path(
    "configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json"
)
DEFAULT_SOURCE_COMMENT_MANIFEST = Path(
    "configs/rag/comment_ablation_v1/formal/evaluation_manifest.json"
)
DEFAULT_CONFIG_ROOT = Path("configs/rag/model_replication_v1/gemma3_27b")
DEFAULT_COMMON = DEFAULT_CONFIG_ROOT / "common.json"
DEFAULT_MANIFEST = DEFAULT_CONFIG_ROOT / "evaluation_manifest.json"
DEFAULT_AUTHORIZATION = DEFAULT_CONFIG_ROOT / "execution_authorization.json"
DEFAULT_OUTPUT_ROOT = Path(
    "experiments/rag/model-replication-v1/gemma3-27b/formal"
)
DEFAULT_REPORT_ROOT = Path(
    "reports/rag/model-replication-v1/gemma3-27b/formal"
)

PROTECTED_PATHS = (
    "configs/rag/roundtrip_ab_v1",
    "configs/rag/comment_ablation_v1",
    "derived/comment-ablation-v1",
    "experiments/rag/roundtrip-ab-v1",
    "experiments/rag/comment-ablation-v1",
    "scripts/rag/roundtrip_ab_formal.py",
    "scripts/research/run_comment_ablation_ab.py",
)

EXPECTED_DESIGN_OPTIONS = {
    "num_ctx": 32768,
    "num_predict": 8192,
    "repeat_penalty": 1.1,
    "seed": 42,
    "temperature": 0,
    "top_k": 40,
    "top_p": 0.9,
}
EXPECTED_CODE_OPTIONS = {
    "num_ctx": 32768,
    "num_predict": 16384,
    "repeat_penalty": 1.1,
    "seed": 42,
    "temperature": 0,
    "top_k": 40,
    "top_p": 0.9,
}
CELL_ORDER = (
    ("comments-present", "A"),
    ("comments-present", "B"),
    ("comments-absent", "A"),
    ("comments-absent", "B"),
)


def _project_path(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RoundtripABError(f"JSON root must be object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RoundtripABError(
                f"JSONL record must be object: {path}:{line_number}"
            )
        records.append(value)
    return records


def _target_map(manifest: Mapping[str, Any], *, label: str) -> dict[str, dict[str, Any]]:
    raw_targets = manifest.get("targets")
    if not isinstance(raw_targets, list):
        raise RoundtripABError(f"{label} targets must be an array")
    result: dict[str, dict[str, Any]] = {}
    for raw in raw_targets:
        if not isinstance(raw, dict):
            raise RoundtripABError(f"{label} target must be an object")
        target_id = str(raw.get("target_id", ""))
        if not target_id or target_id in result:
            raise RoundtripABError(f"{label} has duplicate/empty target ID: {target_id!r}")
        result[target_id] = raw
    return result


def _target_ids(manifest: Mapping[str, Any], *, label: str) -> list[str]:
    targets = manifest.get("targets")
    if not isinstance(targets, list):
        raise RoundtripABError(f"{label} targets must be an array")
    return [str(_mapping(item, f"{label} target").get("target_id", "")) for item in targets]


def _deep_diff_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left or key not in right:
                paths.append(path)
            else:
                paths.extend(_deep_diff_paths(left[key], right[key], path))
        return paths
    if isinstance(left, list) and isinstance(right, list):
        paths = []
        if len(left) != len(right):
            paths.append(prefix)
        for index, (left_item, right_item) in enumerate(zip(left, right)):
            paths.extend(
                _deep_diff_paths(left_item, right_item, f"{prefix}[{index}]")
            )
        return paths
    return [] if left == right else [prefix]


def _runner_path(root: Path) -> Path:
    path = root / "scripts/research/run_model_replication_2x2.py"
    if not path.is_file():
        raise RoundtripABError(
            "runner must exist at scripts/research/run_model_replication_2x2.py"
        )
    return path


def _verify_baseline_exists(root: Path) -> None:
    actual = git_output(root, "rev-parse", f"{BASELINE_COMMIT}^{{commit}}")
    if actual != BASELINE_COMMIT:
        raise RoundtripABError("baseline commit cannot be resolved exactly")


def _verify_protected_paths_unchanged(root: Path) -> None:
    _verify_baseline_exists(root)
    committed = git_output(
        root, "diff", "--name-only", BASELINE_COMMIT, "--", *PROTECTED_PATHS
    )
    working = git_output(root, "status", "--short", "--", *PROTECTED_PATHS)
    changes = [line for line in (committed + "\n" + working).splitlines() if line]
    if changes:
        raise RoundtripABError(
            "protected Qwen/comment-ablation paths differ from baseline:\n"
            + "\n".join(changes)
        )


def _present_output_base(target_id: str) -> Path:
    return DEFAULT_OUTPUT_ROOT / target_id / "comments-present"


def _absent_output_base(target_id: str) -> Path:
    return DEFAULT_OUTPUT_ROOT / target_id / "comments-absent"


def _present_plan_root(target_id: str) -> Path:
    return DEFAULT_REPORT_ROOT / target_id / "comments-present" / "plan"


def _condition_root(target_id: str, comment_condition: str, condition: str) -> Path:
    return (
        DEFAULT_OUTPUT_ROOT
        / target_id
        / comment_condition
        / f"condition-{condition.lower()}"
    )


def _runtime_present_config(
    source_config: Mapping[str, Any], target_id: str
) -> dict[str, Any]:
    config = copy.deepcopy(dict(source_config))
    execution = _mapping(config.get("execution"), "execution")
    execution["output_root"] = _present_output_base(target_id).as_posix()
    if "plan_root" in execution:
        execution["plan_root"] = _present_plan_root(target_id).as_posix()
    allowed = ["execution.output_root"]
    if "plan_root" in execution:
        allowed.append("execution.plan_root")
    differences = _deep_diff_paths(source_config, config)
    if differences != sorted(allowed):
        raise RoundtripABError(
            f"runtime present config changed forbidden paths for {target_id}: {differences}"
        )
    return config


def _runtime_absent_entry(
    source_entry: Mapping[str, Any], target_id: str
) -> dict[str, Any]:
    entry = copy.deepcopy(dict(source_entry))
    entry["output_root"] = _absent_output_base(target_id).as_posix()
    differences = _deep_diff_paths(source_entry, entry)
    if differences != ["output_root"]:
        raise RoundtripABError(
            f"runtime absent entry changed forbidden paths for {target_id}: {differences}"
        )
    return entry


def _authorization_bindings(
    root: Path,
    manifest_path: Path,
    common_path: Path,
) -> dict[str, Any]:
    return {
        "baseline_commit": BASELINE_COMMIT,
        "condition_count": 68,
        "gemma_common_sha256": sha256_file(common_path),
        "manifest_sha256": sha256_file(manifest_path),
        "model": MODEL_TAG,
        "model_id": MODEL_ID,
        "runner_sha256": sha256_file(_runner_path(root)),
        "source_comment_ablation_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_COMMENT_MANIFEST
        ),
        "source_formal_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_FORMAL_MANIFEST
        ),
        "source_qwen_common_sha256": sha256_file(root / DEFAULT_QWEN_COMMON),
        "target_count": 17,
    }


def _verify_authorization_bindings(
    root: Path,
    manifest_path: Path,
    common_path: Path,
    auth_path: Path,
) -> dict[str, Any]:
    if not auth_path.is_file():
        raise RoundtripABError("Gemma authorization artifact is missing")
    auth = _read_json(auth_path)
    if auth.get("artifact_schema_version") != AUTHORIZATION_SCHEMA:
        raise RoundtripABError("Gemma authorization schema differs")
    for key, expected in _authorization_bindings(
        root, manifest_path, common_path
    ).items():
        if auth.get(key) != expected:
            raise RoundtripABError(f"Gemma authorization binding differs: {key}")
    return auth


def _load_replication_inputs(
    root: Path,
    manifest_path: Path,
    common_path: Path,
    auth_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_schema_version") != MANIFEST_SCHEMA:
        raise RoundtripABError("model-replication manifest schema differs")
    expected_manifest_values = {
        "baseline_commit": BASELINE_COMMIT,
        "condition_count": 68,
        "formal_target_count": 17,
        "model": MODEL_TAG,
        "model_id": MODEL_ID,
        "source_comment_ablation_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_COMMENT_MANIFEST
        ),
        "source_formal_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_FORMAL_MANIFEST
        ),
        "source_qwen_common_sha256": sha256_file(root / DEFAULT_QWEN_COMMON),
    }
    for key, expected in expected_manifest_values.items():
        if manifest.get(key) != expected:
            raise RoundtripABError(f"model-replication manifest differs: {key}")
    if manifest.get("gemma_common_sha256") != sha256_file(common_path):
        raise RoundtripABError("model-replication Gemma common hash differs")

    gemma_common = load_common_v2(common_path, root)
    qwen_common = load_common_v2(root / DEFAULT_QWEN_COMMON, root)
    source_formal = load_formal_manifest(
        root / DEFAULT_SOURCE_FORMAL_MANIFEST, root
    )
    source_comment, comment_common, comment_source_formal = (
        comment_ablation._load_frozen(root, root / DEFAULT_SOURCE_COMMENT_MANIFEST)
    )
    if comment_common != qwen_common or comment_source_formal != source_formal:
        raise RoundtripABError(
            "comment-ablation frozen sources differ from Qwen formal-r2 sources"
        )
    auth = _verify_authorization_bindings(
        root, manifest_path, common_path, auth_path
    )
    return (
        manifest,
        gemma_common,
        qwen_common,
        source_formal,
        source_comment,
        auth,
    )


def prepare(
    root: Path,
    manifest_path: Path,
    common_path: Path,
    auth_path: Path,
) -> dict[str, Any]:
    destinations = (common_path, manifest_path, auth_path)
    existing = [path for path in destinations if path.exists()]
    if existing:
        raise RoundtripABError(
            "refusing to overwrite existing model-replication config: "
            + ", ".join(str(path) for path in existing)
        )
    _verify_protected_paths_unchanged(root)

    qwen_common = load_common_v2(root / DEFAULT_QWEN_COMMON, root)
    source_formal = load_formal_manifest(
        root / DEFAULT_SOURCE_FORMAL_MANIFEST, root
    )
    source_comment, comment_common, comment_source_formal = (
        comment_ablation._load_frozen(root, root / DEFAULT_SOURCE_COMMENT_MANIFEST)
    )
    if comment_common != qwen_common or comment_source_formal != source_formal:
        raise RoundtripABError(
            "comment-ablation frozen sources differ from Qwen formal-r2 sources"
        )

    formal_ids = _target_ids(source_formal, label="Qwen formal-r2")
    comment_ids = _target_ids(source_comment, label="comment-ablation")
    if formal_ids != comment_ids or len(formal_ids) != 17:
        raise RoundtripABError(
            "source formal/comment-ablation target ID order must match exactly"
        )

    gemma_common = copy.deepcopy(qwen_common)
    _mapping(gemma_common.get("generation"), "generation")["model"] = MODEL_TAG
    if _deep_diff_paths(qwen_common, gemma_common) != ["generation.model"]:
        raise RoundtripABError("Gemma common must differ only at generation.model")
    common_bytes = canonical_json_bytes(gemma_common)

    targets = []
    for source_item in source_formal["targets"]:
        target_id = str(source_item["target_id"])
        targets.append(
            {
                "comments_absent_output_root": _absent_output_base(
                    target_id
                ).as_posix(),
                "comments_present_output_root": _present_output_base(
                    target_id
                ).as_posix(),
                "source_target_config_path": source_item["target_config_path"],
                "source_target_config_sha256": source_item[
                    "target_config_sha256"
                ],
                "target_id": target_id,
            }
        )

    manifest = {
        "artifact_schema_version": MANIFEST_SCHEMA,
        "baseline_commit": BASELINE_COMMIT,
        "code_generation_count_per_condition": 1,
        "code_generation_semantic_input": "final_design_specification_only",
        "comment_conditions": ["comments-present", "comments-absent"],
        "condition_count": 68,
        "conditions": list(CONDITIONS),
        "design_generation_count_per_condition": 1,
        "formal_target_count": 17,
        "gemma_common_path": _rel(root, common_path),
        "gemma_common_sha256": sha256_bytes(common_bytes),
        "model": MODEL_TAG,
        "model_id": MODEL_ID,
        "output_root": DEFAULT_OUTPUT_ROOT.as_posix(),
        "report_root": DEFAULT_REPORT_ROOT.as_posix(),
        "retry": False,
        "automatic_repair": False,
        "manual_patch": False,
        "source_comment_ablation_manifest_path": (
            DEFAULT_SOURCE_COMMENT_MANIFEST.as_posix()
        ),
        "source_comment_ablation_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_COMMENT_MANIFEST
        ),
        "source_formal_manifest_path": DEFAULT_SOURCE_FORMAL_MANIFEST.as_posix(),
        "source_formal_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_FORMAL_MANIFEST
        ),
        "source_qwen_common_path": DEFAULT_QWEN_COMMON.as_posix(),
        "source_qwen_common_sha256": sha256_file(root / DEFAULT_QWEN_COMMON),
        "targets": targets,
    }
    manifest_bytes = canonical_json_bytes(manifest)
    authorization = {
        "artifact_schema_version": AUTHORIZATION_SCHEMA,
        "authorized": False,
        "formal_generation_started": False,
        "baseline_commit": BASELINE_COMMIT,
        "condition_count": 68,
        "gemma_common_sha256": sha256_bytes(common_bytes),
        "manifest_sha256": sha256_bytes(manifest_bytes),
        "model": MODEL_TAG,
        "model_id": MODEL_ID,
        "runner_sha256": sha256_file(_runner_path(root)),
        "source_comment_ablation_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_COMMENT_MANIFEST
        ),
        "source_formal_manifest_sha256": sha256_file(
            root / DEFAULT_SOURCE_FORMAL_MANIFEST
        ),
        "source_qwen_common_sha256": sha256_file(root / DEFAULT_QWEN_COMMON),
        "target_count": 17,
        "note": (
            "Gemma-only authorization. Enable only after reviewing a fresh "
            "no-contact preflight; never reuse Qwen authorization."
        ),
    }

    _write_exclusive(common_path, common_bytes)
    _write_exclusive(manifest_path, manifest_bytes)
    _write_exclusive(auth_path, canonical_json_bytes(authorization))
    return {
        "artifact_schema_version": "model-replication-2x2-prepare-v1",
        "status": "prepared",
        "authorized": False,
        "condition_count": 68,
        "target_count": 17,
        "model": MODEL_TAG,
        "model_id": MODEL_ID,
        "common": _rel(root, common_path),
        "manifest": _rel(root, manifest_path),
        "authorization": _rel(root, auth_path),
    }


def _require_generation_contract(common: Mapping[str, Any]) -> None:
    generation = _mapping(common.get("generation"), "generation")
    expected = {
        "model": MODEL_TAG,
        "stream": False,
        "timeout_seconds": 3600,
        "design_options": EXPECTED_DESIGN_OPTIONS,
        "code_options": EXPECTED_CODE_OPTIONS,
    }
    for key, value in expected.items():
        if generation.get(key) != value:
            raise RoundtripABError(f"Gemma generation contract differs: {key}")
    isolation = _mapping(common.get("input_isolation"), "input_isolation")
    if isolation.get("code_generation_allowed_semantic_inputs") != [
        "final design specification"
    ]:
        raise RoundtripABError(
            "code generation accepts semantic input beyond final design specification"
        )


def _verify_present_frozen_qwen(
    root: Path,
    target_id: str,
    config: Mapping[str, Any],
    qwen_common: Mapping[str, Any],
    gemma_common: Mapping[str, Any],
) -> tuple[list[str], str, int]:
    repository_root = resolve_repository_root(config, root)
    inputs = load_target_inputs(config, repository_root)
    retrieval = build_retrieval_bundle_v2(
        config, gemma_common, root, repository_root
    )
    qwen_root = (
        root / "experiments/rag/roundtrip-ab-v1/formal-r2" / target_id
    )
    dependencies = _read_jsonl(
        qwen_root / "condition-b/retrieval/candidates_selected.jsonl"
    )
    expected_paths = [str(item.get("path")) for item in dependencies]
    actual_paths = [str(item.get("path")) for item in retrieval.dependency_records]
    if actual_paths != expected_paths:
        raise RoundtripABError(
            f"present RAG dependency path/order differs from Qwen formal-r2: {target_id}"
        )
    qwen_context_path = qwen_root / "condition-b/retrieval/actual_rag_context.txt"
    qwen_context_hash = sha256_file(qwen_context_path)
    retrieval_manifest = _read_json(
        qwen_root / "condition-b/retrieval/retrieval_manifest.json"
    )
    if (
        sha256_bytes(retrieval.context.encode("utf-8")) != qwen_context_hash
        or retrieval.manifest.get("context_sha256") != qwen_context_hash
        or retrieval_manifest.get("context_sha256") != qwen_context_hash
    ):
        raise RoundtripABError(
            f"present RAG context hash differs from Qwen formal-r2: {target_id}"
        )

    for condition, context in (("A", None), ("B", retrieval.context)):
        snapshot = _read_json(
            qwen_root
            / f"condition-{condition.lower()}/snapshots/target_config.json"
        )
        if snapshot != config:
            raise RoundtripABError(
                f"present target config differs from Qwen snapshot: {target_id} {condition}"
            )
        qwen_request = build_design_request_v2(
            config,
            qwen_common,
            root,
            inputs,
            condition=condition,
            repository_context=context,
        )
        gemma_request = build_design_request_v2(
            config,
            gemma_common,
            root,
            inputs,
            condition=condition,
            repository_context=context,
        )
        frozen_prompt = (
            qwen_root / f"condition-{condition.lower()}/design/prompt.txt"
        ).read_text(encoding="utf-8-sig")
        if qwen_request.prompt != frozen_prompt or gemma_request.prompt != frozen_prompt:
            raise RoundtripABError(
                f"present target/design prompt differs from Qwen formal-r2: {target_id} {condition}"
            )
        if gemma_request.payload["model"] != MODEL_TAG:
            raise RoundtripABError(f"Gemma design model differs: {target_id} {condition}")
        if gemma_request.payload["options"] != EXPECTED_DESIGN_OPTIONS:
            raise RoundtripABError(
                f"Gemma design options differ: {target_id} {condition}"
            )
    return actual_paths, qwen_context_hash, len(inputs)


def _verify_absent_frozen_inputs(
    root: Path,
    target_id: str,
    config: Mapping[str, Any],
    entry: Mapping[str, Any],
    qwen_common: Mapping[str, Any],
    gemma_common: Mapping[str, Any],
) -> tuple[list[str], str, int]:
    repository_root = resolve_repository_root(config, root)
    inputs = comment_ablation._load_comment_free_inputs(
        root, config, entry, repository_root
    )
    retrieval = comment_ablation._load_comment_free_retrieval(
        root, config, gemma_common, entry
    )
    frozen_paths = [str(item.get("path")) for item in retrieval.dependency_records]
    frozen_hash = str(_mapping(entry.get("comment_free_rag"), "comment_free_rag")["context_sha256"])
    if sha256_bytes(retrieval.context.encode("utf-8")) != frozen_hash:
        raise RoundtripABError(
            f"absent RAG context hash differs from comment-ablation freeze: {target_id}"
        )

    qwen_root = root / "experiments/rag/comment-ablation-v1/formal" / target_id
    for condition, context in (("A", None), ("B", retrieval.context)):
        qwen_request = build_design_request_v2(
            config,
            qwen_common,
            root,
            inputs,
            condition=condition,
            repository_context=context,
        )
        gemma_request = build_design_request_v2(
            config,
            gemma_common,
            root,
            inputs,
            condition=condition,
            repository_context=context,
        )
        frozen_prompt = (
            qwen_root / f"condition-{condition.lower()}/design/prompt.txt"
        ).read_text(encoding="utf-8-sig")
        if qwen_request.prompt != frozen_prompt or gemma_request.prompt != frozen_prompt:
            raise RoundtripABError(
                f"absent target/design prompt differs from frozen comment-ablation: {target_id} {condition}"
            )
        if gemma_request.payload["model"] != MODEL_TAG:
            raise RoundtripABError(f"Gemma absent design model differs: {target_id} {condition}")
        if gemma_request.payload["options"] != EXPECTED_DESIGN_OPTIONS:
            raise RoundtripABError(
                f"Gemma absent design options differ: {target_id} {condition}"
            )
    return frozen_paths, frozen_hash, len(inputs)


def preflight(
    root: Path,
    manifest_path: Path,
    common_path: Path,
    auth_path: Path,
) -> dict[str, Any]:
    # This function intentionally never receives or references a generation-call
    # callback. It only loads frozen files, reconstructs deterministic requests,
    # hashes artifacts, and inspects Git state.
    _verify_protected_paths_unchanged(root)
    (
        manifest,
        gemma_common,
        qwen_common,
        source_formal,
        source_comment,
        auth,
    ) = _load_replication_inputs(root, manifest_path, common_path, auth_path)

    _require_generation_contract(gemma_common)
    common_diff = _deep_diff_paths(qwen_common, gemma_common)
    if common_diff != ["generation.model"]:
        raise RoundtripABError(
            f"Gemma/Qwen common deep diff differs: {common_diff}"
        )

    formal_ids = _target_ids(source_formal, label="Qwen formal-r2")
    comment_ids = _target_ids(source_comment, label="comment-ablation")
    replication_ids = _target_ids(manifest, label="model-replication")
    if not (formal_ids == comment_ids == replication_ids):
        raise RoundtripABError("source/replication target ID order differs")
    if len(formal_ids) != 17:
        raise RoundtripABError("formal target count must be exactly 17")

    formal_map = _target_map(source_formal, label="Qwen formal-r2")
    comment_map = _target_map(source_comment, label="comment-ablation")
    replication_map = _target_map(manifest, label="model-replication")
    target_checks: list[dict[str, Any]] = []
    design_requests_checked = 0
    code_requests_checked = 0

    for target_id in formal_ids:
        formal_entry = formal_map[target_id]
        comment_entry = comment_map[target_id]
        replication_entry = replication_map[target_id]
        config_path = root / str(formal_entry["target_config_path"])
        expected_config_hash = str(formal_entry["target_config_sha256"])
        if sha256_file(config_path) != expected_config_hash:
            raise RoundtripABError(
                f"source target config hash differs: {target_id}"
            )
        if (
            replication_entry.get("source_target_config_path")
            != formal_entry.get("target_config_path")
            or replication_entry.get("source_target_config_sha256")
            != expected_config_hash
            or comment_entry.get("source_target_config_path")
            != formal_entry.get("target_config_path")
            or comment_entry.get("source_target_config_sha256")
            != expected_config_hash
        ):
            raise RoundtripABError(
                f"source target config binding differs across manifests: {target_id}"
            )

        config = load_json(config_path)
        validate_target_v2(config, formal=True)
        runtime_config = _runtime_present_config(config, target_id)
        if sha256_file(config_path) != expected_config_hash:
            raise RoundtripABError(
                f"source target config was mutated while preparing runtime config: {target_id}"
            )
        if runtime_config["execution"]["output_root"] != str(
            replication_entry["comments_present_output_root"]
        ):
            raise RoundtripABError(
                f"present output root binding differs: {target_id}"
            )
        runtime_absent_entry = _runtime_absent_entry(comment_entry, target_id)
        if runtime_absent_entry["output_root"] != str(
            replication_entry["comments_absent_output_root"]
        ):
            raise RoundtripABError(f"absent output root binding differs: {target_id}")

        present_paths, present_context_hash, present_input_count = (
            _verify_present_frozen_qwen(
                root, target_id, config, qwen_common, gemma_common
            )
        )
        absent_paths, absent_context_hash, absent_input_count = (
            _verify_absent_frozen_inputs(
                root,
                target_id,
                config,
                comment_entry,
                qwen_common,
                gemma_common,
            )
        )
        design_requests_checked += 4

        code_request = build_code_request_v2(
            "PREFLIGHT FINAL DESIGN SPECIFICATION SENTINEL",
            gemma_common,
            root,
            expected_units=config["replacement_units"],
        )
        if code_request.payload["model"] != MODEL_TAG:
            raise RoundtripABError(f"Gemma code model differs: {target_id}")
        if code_request.payload["options"] != EXPECTED_CODE_OPTIONS:
            raise RoundtripABError(f"Gemma code options differ: {target_id}")
        if code_request.audit.get("allowed_semantic_inputs") != [
            "final design specification"
        ]:
            raise RoundtripABError(
                f"code generation semantic input isolation differs: {target_id}"
            )
        forbidden_audit_flags = (
            "dependency_header_loaded",
            "fixed_scaffold_loaded",
            "original_target_source_loaded",
            "rag_context_loaded",
            "repository_access_used",
            "test_or_build_result_loaded",
        )
        if any(code_request.audit.get(key) is not False for key in forbidden_audit_flags):
            raise RoundtripABError(
                f"code request loaded forbidden semantic input: {target_id}"
            )
        code_requests_checked += 4

        one_shot = _mapping(config.get("one_shot"), "one_shot")
        expected_one_shot = {
            "automatic_repair": False,
            "code_generation_count": 1,
            "design_generation_count": 1,
            "manual_patch": False,
            "overwrite": False,
            "retry": False,
        }
        if any(one_shot.get(key) != value for key, value in expected_one_shot.items()):
            raise RoundtripABError(f"one-shot policy differs: {target_id}")

        output_roots = [
            _condition_root(target_id, comment_condition, condition)
            for comment_condition, condition in CELL_ORDER
        ]
        used = [path for path in output_roots if (root / path).exists()]
        if used:
            raise RoundtripABError(
                f"model-replication output root already exists: {used[0]}"
            )

        target_checks.append(
            {
                "target_id": target_id,
                "source_target_config_sha256": expected_config_hash,
                "present_target_input_count": present_input_count,
                "present_dependency_paths": present_paths,
                "present_rag_context_sha256": present_context_hash,
                "absent_target_input_count": absent_input_count,
                "absent_dependency_paths": absent_paths,
                "absent_rag_context_sha256": absent_context_hash,
                "output_roots_unused": True,
            }
        )

    tracked = git_output(root, "status", "--short", "--untracked-files=no")
    return {
        "artifact_schema_version": PREFLIGHT_SCHEMA,
        "status": "pass",
        "target_count": 17,
        "condition_count": 68,
        "comments_present_condition_count": 34,
        "comments_absent_condition_count": 34,
        "model": MODEL_TAG,
        "model_id": MODEL_ID,
        "baseline_commit": BASELINE_COMMIT,
        "source_target_id_order": formal_ids,
        "source_target_order_matches_frozen_qwen": True,
        "source_target_config_hashes_match_manifest": True,
        "qwen_common_diff_paths": common_diff,
        "design_options": EXPECTED_DESIGN_OPTIONS,
        "code_options": EXPECTED_CODE_OPTIONS,
        "design_generation_count_per_condition": 1,
        "code_generation_count_per_condition": 1,
        "design_requests_checked": design_requests_checked,
        "code_requests_checked": code_requests_checked,
        "generation_options_match_qwen_baseline": True,
        "code_generation_semantic_inputs": ["final design specification"],
        "code_generation_design_only": True,
        "present_target_sources_match_frozen_qwen": True,
        "present_rag_contexts_match_frozen_qwen": True,
        "absent_inputs_match_frozen_comment_ablation": True,
        "absent_rag_contexts_match_frozen_comment_ablation": True,
        "all_output_roots_unused": True,
        "protected_qwen_artifacts_unchanged": True,
        "parent_repository_tracked_clean": tracked == "",
        "authorization_currently_enabled": auth.get("authorized") is True,
        "retry": False,
        "automatic_repair": False,
        "manual_patch": False,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "target_checks": target_checks,
    }


def authorize(
    root: Path,
    manifest_path: Path,
    common_path: Path,
    auth_path: Path,
) -> dict[str, Any]:
    result = preflight(root, manifest_path, common_path, auth_path)
    auth = _verify_authorization_bindings(
        root, manifest_path, common_path, auth_path
    )
    if auth.get("authorized") is True:
        raise RoundtripABError("Gemma model-replication execution is already authorized")
    auth["authorized"] = True
    auth["formal_generation_started"] = False
    auth["authorized_at_utc"] = utc_now()
    auth_path.write_bytes(canonical_json_bytes(auth))
    result.update(
        {
            "status": "authorized",
            "authorization_path": _rel(root, auth_path),
            "runner_sha256": auth["runner_sha256"],
        }
    )
    return result


def _verify_authorized(
    root: Path,
    manifest_path: Path,
    common_path: Path,
    auth_path: Path,
) -> dict[str, Any]:
    auth = _verify_authorization_bindings(
        root, manifest_path, common_path, auth_path
    )
    if auth.get("authorized") is not True:
        raise RoundtripABError("Gemma model-replication execution is not authorized")
    return auth


def _load_terminal_result(run_root: Path) -> dict[str, Any]:
    for name in ("result.json", "failure.json"):
        path = run_root / name
        if path.is_file():
            return _read_json(path)
    raise RoundtripABError(f"condition has no terminal result: {run_root}")


def _failure_stage(run_root: Path, result: Mapping[str, Any]) -> str | None:
    if result.get("overall_pass") is True:
        return None
    restoration_path = run_root / "evaluation/source_restoration.json"
    if restoration_path.is_file():
        restoration = _read_json(restoration_path)
        if (
            restoration.get("status") != "pass"
            or restoration.get("repository_clean") is not True
        ):
            return "source_restoration"
    stages = result.get("stages")
    if isinstance(stages, dict):
        for stage, status in stages.items():
            if status != "pass":
                return str(stage)
    if not (run_root / "design/final_design.md").is_file():
        return "design_generation"
    if not (run_root / "code/generated_units.json").is_file():
        return "code_generation"
    return "evaluation"


def _ensure_condition_is_not_global_failure(
    run_root: Path, result: Mapping[str, Any]
) -> None:
    restoration_path = run_root / "evaluation/source_restoration.json"
    if not restoration_path.is_file():
        raise RoundtripABError(
            f"global failure: source-restoration evidence is missing: {run_root}"
        )
    restoration = _read_json(restoration_path)
    if (
        restoration.get("status") != "pass"
        or restoration.get("repository_clean") is not True
        or result.get("repository_clean_after_restoration") is not True
    ):
        raise RoundtripABError(
            f"global failure: repository restoration/clean invariant failed: {run_root}"
        )


def _execute_present(
    root: Path,
    target_id: str,
    source_entry: Mapping[str, Any],
    common: Mapping[str, Any],
    condition: str,
) -> dict[str, Any]:
    config_path = root / str(source_entry["target_config_path"])
    expected_hash = str(source_entry["target_config_sha256"])
    if sha256_file(config_path) != expected_hash:
        raise RoundtripABError(
            f"source target config hash differs immediately before execution: {target_id}"
        )
    source_config = load_json(config_path)
    config = _runtime_present_config(source_config, target_id)
    run_root = root / _condition_root(target_id, "comments-present", condition)
    try:
        result = execute_condition_v2_once(
            config, common, root, condition, formal=True
        )
    except Exception:
        if not run_root.exists():
            raise
        result = _load_terminal_result(run_root)
    _ensure_condition_is_not_global_failure(run_root, result)
    return result


def _execute_absent(
    root: Path,
    manifest: Mapping[str, Any],
    target_id: str,
    source_entry: Mapping[str, Any],
    common: Mapping[str, Any],
    condition: str,
) -> dict[str, Any]:
    config_path = root / str(source_entry["source_target_config_path"])
    if sha256_file(config_path) != str(source_entry["source_target_config_sha256"]):
        raise RoundtripABError(
            f"source target config hash differs immediately before absent execution: {target_id}"
        )
    entry = _runtime_absent_entry(source_entry, target_id)
    result = comment_ablation._execute_one(
        root, manifest, common, entry, condition
    )
    run_root = root / _condition_root(target_id, "comments-absent", condition)
    _ensure_condition_is_not_global_failure(run_root, result)
    return result


def _cell_key(comment_condition: str, condition: str) -> str:
    return f"{comment_condition.replace('-', '_')}_condition_{condition.lower()}"


def execute_batch(
    root: Path,
    manifest_path: Path,
    common_path: Path,
    auth_path: Path,
    report_root: Path,
) -> dict[str, Any]:
    preflight_result = preflight(root, manifest_path, common_path, auth_path)
    _verify_authorized(root, manifest_path, common_path, auth_path)
    (
        manifest,
        common,
        _qwen_common,
        source_formal,
        source_comment,
        _auth,
    ) = _load_replication_inputs(root, manifest_path, common_path, auth_path)

    tracked = git_output(root, "status", "--short", "--untracked-files=no")
    if tracked:
        raise RoundtripABError(
            "parent repository has tracked changes immediately before formal execution:\n"
            + tracked
        )
    report_path = report_root / "batch_execution.json"
    if report_path.exists():
        raise RoundtripABError(f"refusing to overwrite batch report: {report_path}")

    formal_map = _target_map(source_formal, label="Qwen formal-r2")
    comment_map = _target_map(source_comment, label="comment-ablation")
    results: list[dict[str, Any]] = []
    for target_id in _target_ids(source_formal, label="Qwen formal-r2"):
        for comment_condition, condition in CELL_ORDER:
            tracked = git_output(
                root, "status", "--short", "--untracked-files=no"
            )
            if tracked:
                raise RoundtripABError(
                    "global failure: parent repository acquired tracked changes:\n"
                    + tracked
                )
            run_root = root / _condition_root(
                target_id, comment_condition, condition
            )
            if run_root.exists():
                raise RoundtripABError(
                    f"one-shot output already exists immediately before condition: {run_root}"
                )
            if comment_condition == "comments-present":
                result = _execute_present(
                    root,
                    target_id,
                    formal_map[target_id],
                    common,
                    condition,
                )
            else:
                result = _execute_absent(
                    root,
                    manifest,
                    target_id,
                    comment_map[target_id],
                    common,
                    condition,
                )
            record = {
                "target_id": target_id,
                "comment_condition": comment_condition,
                "condition": condition,
                "status": "pass" if result.get("overall_pass") is True else "fail",
                "overall_pass": result.get("overall_pass") is True,
                "failure_stage": _failure_stage(run_root, result),
                "error": result.get("error"),
                "llm_call_count": int(result.get("llm_call_count", 0)),
                "retry_performed": False,
                "automatic_repair_performed": False,
                "manual_patch_performed": False,
            }
            results.append(record)
            print(
                f"{target_id} {comment_condition} {condition}: {record['status']}",
                flush=True,
            )

    cells: dict[str, dict[str, int]] = {}
    for comment_condition, condition in CELL_ORDER:
        selected = [
            item
            for item in results
            if item["comment_condition"] == comment_condition
            and item["condition"] == condition
        ]
        passed = sum(1 for item in selected if item["overall_pass"])
        cells[_cell_key(comment_condition, condition)] = {
            "pass": passed,
            "fail": 17 - passed,
        }

    summary = {
        "artifact_schema_version": "model-replication-2x2-batch-v1",
        "status": "complete",
        "model": MODEL_TAG,
        "model_id": MODEL_ID,
        "target_count": 17,
        "condition_count": 68,
        "cells": cells,
        "llm_call_count": sum(item["llm_call_count"] for item in results),
        "retry_performed": False,
        "automatic_repair_performed": False,
        "manual_patch_performed": False,
        "preflight": preflight_result,
        "results": results,
    }
    _write_exclusive(report_path, canonical_json_bytes(summary))
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare, preflight, authorize, or execute the Gemma3 27B "
            "17-target comments x RAG 2x2 model-replication experiment."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--authorize", action="store_true")
    mode.add_argument("--execute-batch", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--common", type=Path, default=DEFAULT_COMMON)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--authorization", type=Path, default=DEFAULT_AUTHORIZATION
    )
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    common_path = _project_path(root, args.common)
    manifest_path = _project_path(root, args.manifest)
    auth_path = _project_path(root, args.authorization)
    report_root = _project_path(root, args.report_root)

    if args.prepare:
        result = prepare(root, manifest_path, common_path, auth_path)
    elif args.preflight:
        result = preflight(root, manifest_path, common_path, auth_path)
    elif args.authorize:
        result = authorize(root, manifest_path, common_path, auth_path)
    else:
        result = execute_batch(
            root,
            manifest_path,
            common_path,
            auth_path,
            report_root,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
