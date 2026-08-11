from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import canonical_json_bytes, sha256_bytes, sha256_file
from scripts.rag.roundtrip_ab import (
    CONDITIONS,
    RetrievalBundle,
    RoundtripABError,
    SourceReplacementTransaction,
    TargetInput,
    _mapping,
    _ollama_text,
    _run_stage,
    _write_exclusive,
    contact_generation_server,
    git_output,
    load_json,
    load_target_inputs,
    resolve_project_path,
    resolve_repository_root,
    utc_now,
    validate_generated_units,
    verify_repository,
)
from scripts.rag.roundtrip_ab_formal import (
    build_code_request_v2,
    build_design_request_v2,
    compose_repository_context,
    load_common_knowledge,
    load_common_v2,
    load_formal_manifest,
    validate_target_v2,
)
from scripts.research.prepare_comment_free_targets import strip_cpp_comments


SCHEMA = "comment-ablation-formal-manifest-v1"
AUTH_SCHEMA = "comment-ablation-execution-authorization-v1"
TARGET_INPUT_FREEZE_COMMIT = "b668cb3018a87861bc67d45e1be7192e695af9f0"

DEFAULT_COMMON = Path("configs/rag/roundtrip_ab_v1/common.json")
DEFAULT_SOURCE_MANIFEST = Path("configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json")
DEFAULT_TARGET_CF_MANIFEST = Path(
    "derived/comment-ablation-v1/target-inputs/comment_free_manifest.json"
)
DEFAULT_RAG_CF_MANIFEST = Path(
    "derived/comment-ablation-v1/rag-context/comment_free_rag_context_manifest.json"
)
DEFAULT_MANIFEST = Path("configs/rag/comment_ablation_v1/formal/evaluation_manifest.json")
DEFAULT_AUTH = Path("configs/rag/comment_ablation_v1/formal/execution_authorization.json")
DEFAULT_OUTPUT_ROOT = Path("experiments/rag/comment-ablation-v1/formal")
DEFAULT_REPORT_ROOT = Path("reports/rag/comment-ablation-v1/formal")


def _project_path(root: Path, value: Path) -> Path:
    return value if value.is_absolute() else root / value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RoundtripABError(f"JSON root must be object: {path}")
    return value


def _normalized_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RoundtripABError(f"JSONL record must be object: {path}:{line_number}")
        records.append(value)
    return records


def _target_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    targets = manifest.get("targets")
    if not isinstance(targets, list):
        raise RoundtripABError("manifest targets must be an array")
    result: dict[str, dict[str, Any]] = {}
    for raw in targets:
        if not isinstance(raw, dict):
            raise RoundtripABError("manifest target must be object")
        target_id = str(raw.get("target_id", ""))
        if not target_id or target_id in result:
            raise RoundtripABError(f"duplicate/empty target id: {target_id!r}")
        result[target_id] = raw
    return result


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _runner_path(root: Path) -> Path:
    expected = root / "scripts" / "research" / "run_comment_ablation_ab.py"
    if expected.is_file():
        return expected
    # Allow --prepare/--preflight from a downloaded copy before placement, but
    # authorization/execution will require the canonical in-repo path.
    return Path(__file__).resolve()


def build_freeze_manifest(root: Path) -> dict[str, Any]:
    common_path = root / DEFAULT_COMMON
    source_manifest_path = root / DEFAULT_SOURCE_MANIFEST
    target_cf_path = root / DEFAULT_TARGET_CF_MANIFEST
    rag_cf_path = root / DEFAULT_RAG_CF_MANIFEST

    common = load_common_v2(common_path, root)
    source_manifest = load_formal_manifest(source_manifest_path, root)
    target_cf = _read_json(target_cf_path)
    rag_cf = _read_json(rag_cf_path)

    if target_cf.get("artifact_schema_version") != "comment-ablation-target-inputs-v1":
        raise RoundtripABError("comment-free target manifest schema differs")
    if rag_cf.get("artifact_schema_version") != "comment-ablation-rag-context-v1":
        raise RoundtripABError("comment-free RAG manifest schema differs")
    if target_cf.get("target_count") != 17 or rag_cf.get("target_count") != 17:
        raise RoundtripABError("comment-free manifests must both contain 17 targets")

    source_map = _target_map(source_manifest)
    target_map = _target_map(target_cf)
    rag_map = _target_map(rag_cf)
    if set(source_map) != set(target_map) or set(source_map) != set(rag_map):
        raise RoundtripABError("17-target ID sets differ across frozen inputs")

    entries: list[dict[str, Any]] = []
    for source_item in source_manifest["targets"]:
        target_id = str(source_item["target_id"])
        target_item = target_map[target_id]
        rag_item = rag_map[target_id]
        rag_dir = root / str(rag_item["output_path"])
        context_path = rag_dir / "actual_rag_context_comment_free.txt"
        selected_path = rag_dir / "candidates_selected_comment_free.jsonl"
        query_path = rag_dir / "query.json"
        retrieval_manifest_path = rag_dir / "retrieval_manifest_comment_free.json"
        for path in (context_path, selected_path, query_path, retrieval_manifest_path):
            if not path.is_file():
                raise RoundtripABError(f"missing frozen RAG artifact: {path}")

        units: list[dict[str, Any]] = []
        raw_units = target_item.get("units")
        if not isinstance(raw_units, list) or not raw_units:
            raise RoundtripABError(f"comment-free target has no units: {target_id}")
        for unit in raw_units:
            if not isinstance(unit, dict):
                raise RoundtripABError(f"invalid comment-free unit: {target_id}")
            output_path = root / str(unit["output_path"])
            if not output_path.is_file():
                raise RoundtripABError(f"missing comment-free target input: {output_path}")
            units.append(
                {
                    "file_id": unit["file_id"],
                    "unit_id": unit["unit_id"],
                    "original_path": unit["original_path"],
                    "scope": unit["scope"],
                    "output_path": unit["output_path"],
                    "output_sha256": sha256_file(output_path),
                    "source_sha256": unit["source_sha256"],
                    "line_comments_removed": int(unit["line_comments_removed"]),
                    "block_comments_removed": int(unit["block_comments_removed"]),
                }
            )

        entries.append(
            {
                "target_id": target_id,
                "source_target_config_path": source_item["target_config_path"],
                "source_target_config_sha256": source_item["target_config_sha256"],
                "comment_free_target_units": units,
                "comment_free_rag": {
                    "dependency_header_count": int(rag_item["dependency_header_count"]),
                    "comments_removed": int(rag_item["comments_removed"]),
                    "context_path": _rel(root, context_path),
                    "context_sha256": sha256_file(context_path),
                    "selected_path": _rel(root, selected_path),
                    "selected_sha256": sha256_file(selected_path),
                    "query_path": _rel(root, query_path),
                    "query_sha256": sha256_file(query_path),
                    "retrieval_manifest_path": _rel(root, retrieval_manifest_path),
                    "retrieval_manifest_sha256": sha256_file(retrieval_manifest_path),
                },
                "output_root": (DEFAULT_OUTPUT_ROOT / target_id).as_posix(),
            }
        )

    return {
        "artifact_schema_version": SCHEMA,
        "purpose": "comment-absent sensitivity analysis using the same 17 formal-r2 targets and A/B design",
        "target_input_freeze_commit": TARGET_INPUT_FREEZE_COMMIT,
        "source_common_path": DEFAULT_COMMON.as_posix(),
        "source_common_sha256": sha256_file(common_path),
        "source_formal_manifest_path": DEFAULT_SOURCE_MANIFEST.as_posix(),
        "source_formal_manifest_sha256": sha256_file(source_manifest_path),
        "comment_free_target_manifest_path": DEFAULT_TARGET_CF_MANIFEST.as_posix(),
        "comment_free_target_manifest_sha256": sha256_file(target_cf_path),
        "comment_free_rag_manifest_path": DEFAULT_RAG_CF_MANIFEST.as_posix(),
        "comment_free_rag_manifest_sha256": sha256_file(rag_cf_path),
        "formal_target_count": 17,
        "formal_condition_count": 34,
        "comment_condition": "comments-absent-from-target-and-selected-rag-code",
        "condition_a": "comment-free target source + unchanged minimal base design prompt",
        "condition_b": "same comment-free target source + unchanged formal-r2 treatment knowledge + frozen same-selection comment-free RAG dependency context",
        "code_generation_semantic_input": "final_design_specification_only",
        "retry": False,
        "automatic_repair": False,
        "manual_generated_code_patch": False,
        "targets": entries,
    }


def prepare(root: Path, manifest_path: Path, auth_path: Path) -> dict[str, Any]:
    if manifest_path.exists() or auth_path.exists():
        raise RoundtripABError("refusing to overwrite existing comment-ablation formal config")
    manifest = build_freeze_manifest(root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(canonical_json_bytes(manifest))

    runner = _runner_path(root)
    if runner.resolve() != (root / "scripts/research/run_comment_ablation_ab.py").resolve():
        runner_sha = None
    else:
        runner_sha = sha256_file(runner)
    auth = {
        "artifact_schema_version": AUTH_SCHEMA,
        "authorized": False,
        "formal_generation_started": False,
        "manifest_sha256": sha256_file(manifest_path),
        "common_config_sha256": manifest["source_common_sha256"],
        "runner_sha256": runner_sha,
        "target_input_freeze_commit": TARGET_INPUT_FREEZE_COMMIT,
        "note": "Authorize only after preflight review; do not change experiment inputs after authorization.",
    }
    auth_path.write_bytes(canonical_json_bytes(auth))
    return {
        "status": "prepared",
        "target_count": 17,
        "condition_count": 34,
        "manifest": _rel(root, manifest_path),
        "authorization": _rel(root, auth_path),
        "authorized": False,
    }


def _load_frozen(root: Path, manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_schema_version") != SCHEMA:
        raise RoundtripABError("comment-ablation formal manifest schema differs")
    if manifest.get("formal_target_count") != 17 or manifest.get("formal_condition_count") != 34:
        raise RoundtripABError("comment-ablation formal manifest must bind 17 targets / 34 conditions")

    checks = (
        ("source_common_path", "source_common_sha256"),
        ("source_formal_manifest_path", "source_formal_manifest_sha256"),
        ("comment_free_target_manifest_path", "comment_free_target_manifest_sha256"),
        ("comment_free_rag_manifest_path", "comment_free_rag_manifest_sha256"),
    )
    for path_key, hash_key in checks:
        path = root / str(manifest[path_key])
        if sha256_file(path) != str(manifest[hash_key]):
            raise RoundtripABError(f"frozen input hash mismatch: {path_key}")

    common_path = root / str(manifest["source_common_path"])
    source_manifest_path = root / str(manifest["source_formal_manifest_path"])
    common = load_common_v2(common_path, root)
    source_manifest = load_formal_manifest(source_manifest_path, root)
    return manifest, common, source_manifest


def _load_comment_free_inputs(
    root: Path,
    config: Mapping[str, Any],
    entry: Mapping[str, Any],
    repository_root: Path,
) -> tuple[TargetInput, ...]:
    original_inputs = load_target_inputs(config, repository_root)
    frozen_units_raw = entry.get("comment_free_target_units")
    if not isinstance(frozen_units_raw, list):
        raise RoundtripABError("frozen comment-free target units missing")
    frozen_units = {
        (str(unit["file_id"]), str(unit["unit_id"])): unit
        for unit in frozen_units_raw
        if isinstance(unit, dict)
    }
    expected_pairs = {(x.file_id, x.unit_id) for x in original_inputs}
    if set(frozen_units) != expected_pairs:
        raise RoundtripABError(
            f"comment-free unit set differs for {config['target_id']}: "
            f"expected={sorted(expected_pairs)}, actual={sorted(frozen_units)}"
        )

    records: list[TargetInput] = []
    for original in original_inputs:
        pair = (original.file_id, original.unit_id)
        frozen = frozen_units[pair]
        if str(frozen["original_path"]) != original.path:
            raise RoundtripABError(f"comment-free original path differs: {config['target_id']} {pair}")
        path = root / str(frozen["output_path"])
        if sha256_file(path) != str(frozen["output_sha256"]):
            raise RoundtripABError(f"comment-free target artifact hash mismatch: {path}")
        derived = _normalized_text(path)
        expected, _, _ = strip_cpp_comments(original.content)
        expected = expected.replace("\r\n", "\n").replace("\r", "\n")
        if derived != expected:
            raise RoundtripABError(
                f"comment-free target is not exactly strip(original): {config['target_id']} {pair}"
            )
        second, line_comments, block_comments = strip_cpp_comments(derived)
        if second != derived or line_comments != 0 or block_comments != 0:
            raise RoundtripABError(f"comments remain in target input: {config['target_id']} {pair}")
        records.append(
            TargetInput(
                file_id=original.file_id,
                unit_id=original.unit_id,
                path=original.path,
                replacement_required=original.replacement_required,
                role=original.role,
                content=derived,
                source_file_sha256=original.source_file_sha256,
                content_sha256=sha256_bytes(derived.encode("utf-8", errors="surrogateescape")),
            )
        )
    return tuple(records)


def _load_comment_free_retrieval(
    root: Path,
    config: Mapping[str, Any],
    common: Mapping[str, Any],
    entry: Mapping[str, Any],
) -> RetrievalBundle:
    target_id = str(config["target_id"])
    frozen = _mapping(entry.get("comment_free_rag"), "comment_free_rag")
    paths = {
        "context": root / str(frozen["context_path"]),
        "selected": root / str(frozen["selected_path"]),
        "query": root / str(frozen["query_path"]),
        "retrieval_manifest": root / str(frozen["retrieval_manifest_path"]),
    }
    hashes = {
        "context": frozen["context_sha256"],
        "selected": frozen["selected_sha256"],
        "query": frozen["query_sha256"],
        "retrieval_manifest": frozen["retrieval_manifest_sha256"],
    }
    for name, path in paths.items():
        if sha256_file(path) != str(hashes[name]):
            raise RoundtripABError(f"comment-free RAG artifact hash mismatch: {target_id} {name}")

    selected = _jsonl(paths["selected"])
    original_selected_path = (
        root
        / "experiments/rag/roundtrip-ab-v1/formal-r2"
        / target_id
        / "condition-b/retrieval/candidates_selected.jsonl"
    )
    original = _jsonl(original_selected_path)
    if len(original) != len(selected):
        raise RoundtripABError(f"RAG dependency count changed: {target_id}")
    for old, new in zip(original, selected):
        if str(old.get("path")) != str(new.get("path")):
            raise RoundtripABError(f"RAG selected path/order changed: {target_id}")
        old_content = str(old.get("content", "")).replace("\r\n", "\n").replace("\r", "\n")
        expected, _, _ = strip_cpp_comments(old_content)
        new_content = str(new.get("content", "")).replace("\r\n", "\n").replace("\r", "\n")
        if new_content != expected:
            raise RoundtripABError(f"RAG dependency is not exactly strip(original): {target_id} {old.get('path')}")
        second, line_comments, block_comments = strip_cpp_comments(new_content)
        if second != new_content or line_comments != 0 or block_comments != 0:
            raise RoundtripABError(f"comments remain in RAG dependency: {target_id} {old.get('path')}")

    rebuilt_context = compose_repository_context(selected)
    actual_context = paths["context"].read_text(encoding="utf-8-sig")
    actual_context = actual_context.replace("\r\n", "\n").replace("\r", "\n")
    if rebuilt_context != actual_context:
        raise RoundtripABError(f"comment-free RAG context does not match selected records: {target_id}")
    if sha256_bytes(actual_context.encode("utf-8")) != str(frozen["context_sha256"]):
        # The stored file is expected to be LF canonical already; keep this
        # explicit semantic-text hash check in addition to file hash.
        raise RoundtripABError(f"comment-free RAG context content hash differs: {target_id}")

    query = _read_json(paths["query"])
    retrieval_manifest = _read_json(paths["retrieval_manifest"])
    knowledge = load_common_knowledge(common, root)
    manifest = {
        "artifact_schema_version": "comment-ablation-retrieval-runtime-v1",
        "condition": "B",
        "target_id": target_id,
        "context_sha256": sha256_bytes(actual_context.encode("utf-8")),
        "dependency_header_count": len(selected),
        "source_selection": "frozen-from-comment-present-formal-r2-condition-b",
        "comments_absent_from_dependency_code": True,
        "source_retrieval_manifest": retrieval_manifest,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "status": "pass",
    }
    return RetrievalBundle(
        context=actual_context,
        query=query,
        fixed_design_knowledge=knowledge["detailed_design_guidance"],
        roundtrip_completeness_knowledge=knowledge["roundtrip_completeness"],
        dependency_records=tuple(dict(x) for x in selected),
        manifest=manifest,
    )


def _entry_map(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return _target_map(manifest)


def preflight(root: Path, manifest_path: Path, auth_path: Path) -> dict[str, Any]:
    manifest, common, source_manifest = _load_frozen(root, manifest_path)
    entries = _entry_map(manifest)
    source_ids = [str(x["target_id"]) for x in source_manifest["targets"]]
    if set(entries) != set(source_ids):
        raise RoundtripABError("comment-ablation manifest target set differs from formal-r2")

    if not auth_path.is_file():
        raise RoundtripABError("authorization artifact is missing")
    auth = _read_json(auth_path)
    if auth.get("artifact_schema_version") != AUTH_SCHEMA:
        raise RoundtripABError("authorization schema differs")
    if auth.get("manifest_sha256") != sha256_file(manifest_path):
        raise RoundtripABError("authorization manifest hash is stale")
    if auth.get("common_config_sha256") != manifest["source_common_sha256"]:
        raise RoundtripABError("authorization common hash is stale")

    target_comments = 0
    rag_comments = 0
    dependencies = 0
    prompts_checked = 0
    unchanged_target_inputs = 0

    for source_item in source_manifest["targets"]:
        target_id = str(source_item["target_id"])
        entry = entries[target_id]
        config_path = root / str(entry["source_target_config_path"])
        if sha256_file(config_path) != str(entry["source_target_config_sha256"]):
            raise RoundtripABError(f"formal-r2 target config hash mismatch: {target_id}")
        config = load_json(config_path)
        validate_target_v2(config, formal=True)
        repository_root = resolve_repository_root(config, root)
        verify_repository(config, repository_root)
        inputs = _load_comment_free_inputs(root, config, entry, repository_root)
        retrieval = _load_comment_free_retrieval(root, config, common, entry)

        a = build_design_request_v2(
            config, common, root, inputs, condition="A", repository_context=None
        )
        b = build_design_request_v2(
            config, common, root, inputs, condition="B", repository_context=retrieval.context
        )
        for key in ("model", "options", "stream"):
            if a.payload[key] != b.payload[key]:
                raise RoundtripABError(f"A/B generation field differs in preflight: {target_id} {key}")
        if a.audit["treatment_knowledge_injected"] is not False:
            raise RoundtripABError(f"Condition A received treatment knowledge: {target_id}")
        if b.audit["treatment_knowledge_injected"] is not True:
            raise RoundtripABError(f"Condition B lacks treatment knowledge: {target_id}")
        if a.audit["repository_context_injected"] is not False:
            raise RoundtripABError(f"Condition A received repository context: {target_id}")
        if b.audit["repository_context_injected"] is not True:
            raise RoundtripABError(f"Condition B lacks repository context: {target_id}")

        for condition in CONDITIONS:
            run_root = root / str(entry["output_root"]) / f"condition-{condition.lower()}"
            if run_root.exists():
                raise RoundtripABError(f"formal comment-ablation output already exists: {run_root}")
        prompts_checked += 2

        for unit in entry["comment_free_target_units"]:
            count = int(unit["line_comments_removed"]) + int(unit["block_comments_removed"])
            target_comments += count
            if str(unit["source_sha256"]) == str(unit["output_sha256"]):
                unchanged_target_inputs += 1
        rag_info = entry["comment_free_rag"]
        rag_comments += int(rag_info["comments_removed"])
        dependencies += int(rag_info["dependency_header_count"])

    return {
        "artifact_schema_version": "comment-ablation-preflight-v1",
        "status": "pass",
        "generation_server_contacted": False,
        "llm_call_count": 0,
        "target_count": 17,
        "condition_count": 34,
        "design_prompts_checked": prompts_checked,
        "target_comments_removed": target_comments,
        "rag_dependency_comments_removed": rag_comments,
        "dependency_headers": dependencies,
        "authorization_currently_enabled": auth.get("authorized") is True,
        "all_output_roots_unused": True,
        "formal_r2_outputs_untouched": True,
        "target_input_freeze_commit": manifest["target_input_freeze_commit"],
    }


def authorize(root: Path, manifest_path: Path, auth_path: Path) -> dict[str, Any]:
    # A full preflight is mandatory immediately before authorization.
    result = preflight(root, manifest_path, auth_path)
    auth = _read_json(auth_path)
    if auth.get("authorized") is True:
        raise RoundtripABError("comment-ablation execution is already authorized")
    canonical_runner = root / "scripts/research/run_comment_ablation_ab.py"
    if not canonical_runner.is_file():
        raise RoundtripABError("runner must be placed at scripts/research/run_comment_ablation_ab.py")
    auth["authorized"] = True
    auth["formal_generation_started"] = False
    auth["runner_sha256"] = sha256_file(canonical_runner)
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


def _verify_authorized(root: Path, manifest_path: Path, auth_path: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest, common, source_manifest = _load_frozen(root, manifest_path)
    auth = _read_json(auth_path)
    if auth.get("artifact_schema_version") != AUTH_SCHEMA or auth.get("authorized") is not True:
        raise RoundtripABError("comment-ablation formal execution is not authorized")
    if auth.get("manifest_sha256") != sha256_file(manifest_path):
        raise RoundtripABError("authorized manifest hash mismatch")
    if auth.get("common_config_sha256") != manifest["source_common_sha256"]:
        raise RoundtripABError("authorized common hash mismatch")
    runner = root / "scripts/research/run_comment_ablation_ab.py"
    if sha256_file(runner) != str(auth.get("runner_sha256", "")):
        raise RoundtripABError("authorized runner hash mismatch")
    return manifest, common, source_manifest


def _copy_retrieval_artifacts(root: Path, run_root: Path, entry: Mapping[str, Any], retrieval: RetrievalBundle) -> None:
    frozen = _mapping(entry["comment_free_rag"], "comment_free_rag")
    dest = run_root / "retrieval"
    _write_exclusive(dest / "query.json", (root / str(frozen["query_path"])).read_bytes())
    _write_exclusive(dest / "candidates_selected.jsonl", (root / str(frozen["selected_path"])).read_bytes())
    _write_exclusive(dest / "actual_rag_context.txt", retrieval.context.encode("utf-8"))
    _write_exclusive(dest / "source_retrieval_manifest.json", (root / str(frozen["retrieval_manifest_path"])).read_bytes())
    _write_exclusive(dest / "runtime_retrieval_manifest.json", canonical_json_bytes(retrieval.manifest))


def _execute_one(
    root: Path,
    manifest: Mapping[str, Any],
    common: Mapping[str, Any],
    entry: Mapping[str, Any],
    condition: str,
) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise RoundtripABError("condition must be A or B")
    target_id = str(entry["target_id"])
    config_path = root / str(entry["source_target_config_path"])
    config = load_json(config_path)
    validate_target_v2(config, formal=True)
    repository_root = resolve_repository_root(config, root)
    repository_state = verify_repository(config, repository_root)
    run_root = root / str(entry["output_root"]) / f"condition-{condition.lower()}"
    if run_root.exists():
        raise RoundtripABError(f"one-shot attempt or result already exists: {run_root}")

    attempt = {
        "artifact_schema_version": "comment-ablation-attempt-v1",
        "target_id": target_id,
        "condition": condition,
        "formal": True,
        "sensitivity_analysis": "comment-ablation-v1",
        "comment_condition": "absent",
        "target_comments_absent": True,
        "rag_dependency_comments_absent": condition == "B",
        "design_generation_count": 1,
        "code_generation_count": 1,
        "retry_allowed": False,
        "automatic_repair": False,
        "manual_patch": False,
        "reserved_at_utc": utc_now(),
    }
    _write_exclusive(run_root / "attempt.json", canonical_json_bytes(attempt))
    _write_exclusive(run_root / "snapshots/source_target_config.json", canonical_json_bytes(config))
    _write_exclusive(run_root / "snapshots/common_config.json", canonical_json_bytes(common))
    _write_exclusive(run_root / "snapshots/comment_ablation_manifest.json", canonical_json_bytes(manifest))

    inputs = _load_comment_free_inputs(root, config, entry, repository_root)
    retrieval = _load_comment_free_retrieval(root, config, common, entry)
    repository_context = retrieval.context if condition == "B" else None
    if condition == "B":
        _copy_retrieval_artifacts(root, run_root, entry, retrieval)
    else:
        _write_exclusive(run_root / "retrieval/actual_rag_context.txt", b"")
        _write_exclusive(
            run_root / "retrieval/retrieval_manifest.json",
            canonical_json_bytes(
                {
                    "artifact_schema_version": "comment-ablation-retrieval-not-applied-v1",
                    "condition": "A",
                    "context_sha256": sha256_bytes(b""),
                    "repository_context_injected": False,
                }
            ),
        )

    design_request = build_design_request_v2(
        config,
        common,
        root,
        inputs,
        condition=condition,
        repository_context=repository_context,
    )
    design_bytes = canonical_json_bytes(design_request.payload)
    _write_exclusive(run_root / "design/prompt.txt", design_request.prompt.encode("utf-8"))
    _write_exclusive(run_root / "design/request.json", design_bytes)
    design_audit = dict(design_request.audit)
    design_audit.update(
        {
            "comment_condition": "absent",
            "comment_free_target_input": True,
            "comment_free_rag_dependency_input": condition == "B",
        }
    )
    _write_exclusive(run_root / "design/request_audit.json", canonical_json_bytes(design_audit))

    generation = _mapping(common.get("generation"), "generation")
    endpoint = str(generation["endpoint"])
    headers = dict(_mapping(generation.get("headers"), "generation.headers"))
    timeout = int(generation["timeout_seconds"])
    execution = _mapping(config.get("execution"), "execution")

    transaction: SourceReplacementTransaction | None = None
    restored: dict[str, str] = {}
    stages: dict[str, Any] = {}
    contacts = 0
    primary_error: Exception | None = None
    restore_error: Exception | None = None

    try:
        _write_exclusive(
            run_root / "design/contact.json",
            canonical_json_bytes(
                {
                    "contact_attempted": True,
                    "request_sha256": sha256_bytes(design_bytes),
                    "retry": False,
                    "started_at_utc": utc_now(),
                }
            ),
        )
        contacts += 1
        design_response = contact_generation_server(endpoint, headers, design_bytes, timeout)
        _write_exclusive(run_root / "design/response.json", design_response)
        design_document = _ollama_text(design_response, "design generation")
        _write_exclusive(run_root / "design/final_design.md", design_document.encode("utf-8"))

        units = config["replacement_units"]
        code_request = build_code_request_v2(
            design_document, common, root, expected_units=units
        )
        code_bytes = canonical_json_bytes(code_request.payload)
        _write_exclusive(run_root / "code/prompt.txt", code_request.prompt.encode("utf-8"))
        _write_exclusive(run_root / "code/request.json", code_bytes)
        _write_exclusive(run_root / "code/request_audit.json", canonical_json_bytes(code_request.audit))
        _write_exclusive(
            run_root / "code/contact.json",
            canonical_json_bytes(
                {
                    "contact_attempted": True,
                    "request_sha256": sha256_bytes(code_bytes),
                    "retry": False,
                    "started_at_utc": utc_now(),
                }
            ),
        )
        contacts += 1
        code_response = contact_generation_server(endpoint, headers, code_bytes, timeout)
        _write_exclusive(run_root / "code/response.json", code_response)
        generated_text = _ollama_text(code_response, "code generation")
        generated = validate_generated_units(generated_text, units)
        _write_exclusive(
            run_root / "code/generated_units.json",
            canonical_json_bytes(
                {
                    "units": [
                        {"file_id": pair[0], "unit_id": pair[1], "content": content}
                        for pair, content in sorted(generated.items())
                    ]
                }
            ),
        )

        transaction = SourceReplacementTransaction(repository_root, units, generated)
        transaction.apply()
        workspace = run_root / "evaluation-workspace"
        workspace.mkdir(parents=True, exist_ok=False)
        commands = _mapping(execution.get("commands"), "execution.commands")
        timeouts = _mapping(execution.get("stage_timeouts_seconds"), "execution.stage_timeouts_seconds")
        stage_order = execution.get("stage_order", ["configure", "build", "direct_test", "full_test"])
        if not isinstance(stage_order, list) or not stage_order:
            raise RoundtripABError("execution.stage_order must be non-empty")
        for stage in stage_order:
            command = commands.get(stage)
            if not isinstance(command, list) or not command:
                raise RoundtripABError(f"execution command is missing: {stage}")
            record = _run_stage(
                str(stage),
                [str(x) for x in command],
                repository_root,
                workspace,
                int(timeouts[stage]),
            )
            stages[str(stage)] = record
            _write_exclusive(run_root / f"evaluation/{stage}.json", canonical_json_bytes(record))
            if record["status"] != "pass":
                break
    except Exception as exc:
        primary_error = exc
    finally:
        if transaction is not None:
            try:
                restored = transaction.restore()
            except Exception as exc:
                restore_error = exc
        repository_clean = git_output(repository_root, "status", "--short") == ""
        restoration = {
            "artifact_schema_version": "comment-ablation-restoration-v1",
            "error": str(restore_error) if restore_error else None,
            "repository_clean": repository_clean,
            "restored_hashes": restored,
            "status": "fail" if restore_error or not repository_clean else "pass",
        }
        _write_exclusive(run_root / "evaluation/source_restoration.json", canonical_json_bytes(restoration))

    stage_order = [str(x) for x in execution.get("stage_order", [])]
    all_stages = bool(stage_order) and list(stages) == stage_order and all(
        x["status"] == "pass" for x in stages.values()
    )
    repository_clean = git_output(repository_root, "status", "--short") == ""
    success = primary_error is None and restore_error is None and all_stages and repository_clean
    result = {
        "artifact_schema_version": "comment-ablation-result-v1",
        "target_id": target_id,
        "condition": condition,
        "formal": True,
        "sensitivity_analysis": "comment-ablation-v1",
        "comment_condition": "absent",
        "error": str(primary_error) if primary_error else (str(restore_error) if restore_error else None),
        "error_type": type(primary_error).__name__ if primary_error else (type(restore_error).__name__ if restore_error else None),
        "generation_server_contact_count": contacts,
        "llm_call_count": contacts,
        "overall_pass": success,
        "repository_clean_after_restoration": repository_clean,
        "repository_commit": repository_state["commit"],
        "retry_performed": False,
        "automatic_repair_performed": False,
        "stages": {stage: record["status"] for stage, record in stages.items()},
        "status": "pass" if success else "fail",
    }
    terminal_name = "result.json" if primary_error is None and restore_error is None else "failure.json"
    _write_exclusive(run_root / terminal_name, canonical_json_bytes(result))
    return result


def execute_batch(root: Path, manifest_path: Path, auth_path: Path, report_root: Path) -> dict[str, Any]:
    # Full no-contact preflight immediately before the first formal call.
    preflight_result = preflight(root, manifest_path, auth_path)
    manifest, common, source_manifest = _verify_authorized(root, manifest_path, auth_path)
    entries = _entry_map(manifest)

    tracked = git_output(root, "status", "--short", "--untracked-files=no")
    if tracked:
        raise RoundtripABError("parent repository has tracked changes before formal execution:\n" + tracked)

    for source_item in source_manifest["targets"]:
        entry = entries[str(source_item["target_id"])]
        for condition in CONDITIONS:
            run_root = root / str(entry["output_root"]) / f"condition-{condition.lower()}"
            if run_root.exists():
                raise RoundtripABError(f"one-shot output already exists before batch start: {run_root}")

    results: list[dict[str, Any]] = []
    for source_item in source_manifest["targets"]:
        target_id = str(source_item["target_id"])
        entry = entries[target_id]
        for condition in CONDITIONS:
            result = _execute_one(root, manifest, common, entry, condition)
            results.append(
                {
                    "target_id": target_id,
                    "condition": condition,
                    "status": result["status"],
                    "overall_pass": result["overall_pass"],
                    "error": result.get("error"),
                }
            )
            print(f"{target_id} {condition}: {result['status']}", flush=True)

    a_pass = sum(1 for x in results if x["condition"] == "A" and x["overall_pass"])
    b_pass = sum(1 for x in results if x["condition"] == "B" and x["overall_pass"])
    summary = {
        "artifact_schema_version": "comment-ablation-batch-execution-v1",
        "status": "complete",
        "sensitivity_analysis": "comment-ablation-v1",
        "comment_condition": "absent",
        "target_count": 17,
        "condition_count": 34,
        "a_pass": a_pass,
        "a_fail": 17 - a_pass,
        "b_pass": b_pass,
        "b_fail": 17 - b_pass,
        "retry_performed": False,
        "automatic_repair_performed": False,
        "preflight": preflight_result,
        "results": results,
    }
    report_path = report_root / "batch_execution.json"
    if report_path.exists():
        raise RoundtripABError(f"refusing to overwrite batch report: {report_path}")
    _write_exclusive(report_path, canonical_json_bytes(summary))
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare, verify, authorize, or execute the 17-target comment-ablation A/B sensitivity experiment."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--authorize", action="store_true")
    mode.add_argument("--execute-batch", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTH)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve()
    manifest_path = _project_path(root, args.manifest)
    auth_path = _project_path(root, args.authorization)
    report_root = _project_path(root, args.report_root)

    if args.prepare:
        result = prepare(root, manifest_path, auth_path)
    elif args.preflight:
        result = preflight(root, manifest_path, auth_path)
    elif args.authorize:
        result = authorize(root, manifest_path, auth_path)
    else:
        result = execute_batch(root, manifest_path, auth_path, report_root)

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
