"""Plan or execute the mechanics-only yaml-cpp YAML::Node replacement pilot."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import (
    canonical_json_bytes,
    posix_relative_path,
    sha256_bytes,
    sha256_file,
)
from scripts.roundtrip.roundtrip_common import find_matching_brace


DEFAULT_CONFIG = "configs/rag/pilot/yaml_cpp_yaml_node_mechanics_v1.json"
FIXTURE_FILE = "fixture_class_span.cpp"
EVALUATION_PLAN_FILE = "mechanics_evaluation_plan.json"
PLAN_MANIFEST_FILE = "mechanics_plan_manifest.json"
ORIGINAL_SOURCE_FILE = "original_source.bin"


class MechanicsError(RuntimeError):
    """Raised when a frozen mechanics invariant fails."""


@dataclass(frozen=True)
class RepositoryState:
    head: str
    branch: str | None
    clean: bool


@dataclass(frozen=True)
class FrozenInputs:
    original_source_bytes: bytes
    original_source_sha256: str
    normalized_source_sha256: str
    target_source: str
    target_source_sha256: str
    fixture_source: str
    fixture_source_sha256: str
    selection_sha256: str
    baseline_report_sha256: str
    project_state: RepositoryState
    pilot_state: RepositoryState


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MechanicsError(f"{field} must be an object")
    return value


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MechanicsError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MechanicsError(f"JSON root must be an object: {path}")
    return value


def load_config(path: Path) -> dict[str, Any]:
    config = _load_json_object(path)
    if config.get("artifact_schema_version") != "rag-yaml-cpp-mechanics-config-v1":
        raise MechanicsError("unsupported mechanics config schema")
    posix_relative_path(str(config.get("output_path", "")))
    target = _mapping(config.get("target"), "target")
    posix_relative_path(str(target.get("path", "")))
    selection = _mapping(config.get("frozen_selection"), "frozen_selection")
    posix_relative_path(str(selection.get("path", "")))
    for path in config.get("protected_immutable_run_paths", []):
        posix_relative_path(str(path))

    expected_classification = {
        "rag_treatment_run": False,
        "code_regeneration_run": False,
        "retry_of_yaml_node_run01": False,
        "formal_experimental_result": False,
        "evidence_of_rag_improvement": False,
    }
    if _mapping(config.get("classification"), "classification") != expected_classification:
        raise MechanicsError("mechanics-only classification is not frozen")
    expected_llm = {
        "llm_allowed": False,
        "generation_server_contact_allowed": False,
        "llm_called": False,
        "llm_call_count": 0,
        "generation_server_contacted": False,
    }
    if _mapping(config.get("llm_policy"), "llm_policy") != expected_llm:
        raise MechanicsError("zero-call LLM policy is not frozen")
    policy = _mapping(config.get("one_shot_policy"), "one_shot_policy")
    required_policy = {
        "execution_count": 1,
        "retry_allowed": False,
        "repair_allowed": False,
        "overwrite_allowed": False,
        "manual_runtime_patch_allowed": False,
        "second_execution_allowed": False,
    }
    for field, expected in required_policy.items():
        if policy.get(field) != expected:
            raise MechanicsError(f"one-shot policy mismatch: {field}")
    for field in ("attempt_marker", "failure_marker", "result_marker"):
        if not isinstance(policy.get(field), str) or "/" in str(policy[field]):
            raise MechanicsError(f"invalid one-shot marker: {field}")

    fixture = _mapping(config.get("fixture"), "fixture")
    if fixture.get("algorithm") != "insert-one-fixed-comment-after-class-opening-brace-v1":
        raise MechanicsError("fixture algorithm mismatch")
    for field in (
        "preserve_complete_original_class_span",
        "interface_changes",
        "declaration_changes",
        "type_changes",
        "behavior_changes",
    ):
        expected = field == "preserve_complete_original_class_span"
        if fixture.get(field) is not expected:
            raise MechanicsError(f"fixture invariant mismatch: {field}")
    replacement = _mapping(
        config.get("replacement_and_restoration"),
        "replacement_and_restoration",
    )
    if int(replacement.get("replace_only_start_byte", -1)) != int(target["start_byte"]):
        raise MechanicsError("replacement start does not match frozen target")
    if int(replacement.get("replace_only_end_byte", -1)) != int(target["end_byte"]):
        raise MechanicsError("replacement end does not match frozen target")
    for field in (
        "backup_original_complete_source_bytes",
        "verify_source_bytes_differ_after_replacement",
        "restore_in_finally",
        "verify_restored_bytes_equal_original",
        "verify_clean_yaml_cpp_worktree",
    ):
        if replacement.get(field) is not True:
            raise MechanicsError(f"restoration invariant mismatch: {field}")
    if replacement.get("manual_runtime_patch_allowed") is not False:
        raise MechanicsError("manual runtime patching must remain disabled")
    return config


def _git(
    repository: Path, *arguments: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise MechanicsError(
            f"git {' '.join(arguments)} failed for {repository}: {detail}"
        )
    return result


def repository_state(
    repository: Path, required_branch: str | None = None
) -> RepositoryState:
    head = _git(repository, "rev-parse", "HEAD").stdout.strip().lower()
    branch = _git(repository, "branch", "--show-current").stdout.strip() or None
    status = _git(
        repository, "status", "--porcelain=v1", "--untracked-files=all"
    ).stdout
    if status:
        raise MechanicsError(f"worktree is not clean: {repository}\n{status.rstrip()}")
    if required_branch is not None and branch != required_branch:
        raise MechanicsError(
            f"branch mismatch for {repository}: expected {required_branch}, got {branch}"
        )
    return RepositoryState(head=head, branch=branch, clean=True)


def verify_repository_states(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> tuple[RepositoryState, RepositoryState]:
    project_config = _mapping(config.get("project_repository"), "project_repository")
    pilot_config = _mapping(config.get("pilot_repository"), "pilot_repository")
    project = repository_state(project_root, str(project_config["required_branch"]))
    baseline = str(project_config["required_baseline_ancestor"]).lower()
    ancestor = _git(
        project_root, "merge-base", "--is-ancestor", baseline, project.head, check=False
    )
    if ancestor.returncode != 0:
        raise MechanicsError(
            f"required project baseline {baseline} is not an ancestor of {project.head}"
        )
    for relative in config.get("protected_immutable_run_paths", []):
        changed = _git(
            project_root,
            "diff",
            "--quiet",
            baseline,
            project.head,
            "--",
            str(relative),
            check=False,
        )
        if changed.returncode != 0:
            raise MechanicsError(f"protected immutable run changed: {relative}")

    pilot = repository_state(pilot_root)
    expected_pilot = str(pilot_config["required_commit"]).lower()
    if pilot.head != expected_pilot:
        raise MechanicsError(
            f"yaml-cpp commit mismatch: expected {expected_pilot}, got {pilot.head}"
        )
    return project, pilot


def normalize_source_bytes(raw: bytes) -> bytes:
    normalized = raw.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise MechanicsError("source contains unsupported lone CR bytes")
    return normalized


def raw_offsets_for_normalized_range(
    raw: bytes, start: int, end: int
) -> tuple[int, int]:
    if start < 0 or end <= start:
        raise MechanicsError("invalid normalized replacement range")
    normalized_position = 0
    raw_position = 0
    raw_start: int | None = None
    raw_end: int | None = None
    while raw_position <= len(raw):
        if normalized_position == start and raw_start is None:
            raw_start = raw_position
        if normalized_position == end:
            raw_end = raw_position
            break
        if raw_position >= len(raw):
            break
        if raw[raw_position : raw_position + 2] == b"\r\n":
            raw_position += 2
        elif raw[raw_position : raw_position + 1] == b"\r":
            raise MechanicsError("source contains unsupported lone CR bytes")
        else:
            raw_position += 1
        normalized_position += 1
    if raw_start is None or raw_end is None:
        raise MechanicsError("normalized replacement range exceeds source bytes")
    if normalize_source_bytes(raw[raw_start:raw_end]) != normalize_source_bytes(raw)[start:end]:
        raise MechanicsError("raw and normalized replacement ranges disagree")
    return raw_start, raw_end


def _verify_class_span(text: str, declaration: str) -> None:
    if not text.startswith(declaration):
        raise MechanicsError("class span does not start with the target declaration")
    open_brace = text.find("{", len(declaration))
    if open_brace < 0:
        raise MechanicsError("target class has no opening brace")
    try:
        close_brace = find_matching_brace(text, open_brace)
    except ValueError as exc:
        raise MechanicsError(f"target class braces are invalid: {exc}") from exc
    if text[close_brace + 1 :].strip():
        raise MechanicsError("class span contains material after the closing brace")
    if text.rstrip().endswith("};"):
        raise MechanicsError("frozen class span must exclude the semicolon")


def build_fixture_class_span(config: Mapping[str, Any], target_source: str) -> str:
    fixture = _mapping(config.get("fixture"), "fixture")
    anchor = str(fixture["insertion_anchor"])
    comment = str(fixture["comment"])
    if target_source.count(anchor) != 1:
        raise MechanicsError("fixture insertion anchor is not unique")
    if comment in target_source:
        raise MechanicsError("fixture comment already occurs in frozen source")
    result = target_source.replace(anchor, anchor + comment, 1)
    if result.replace(comment, "", 1) != target_source:
        raise MechanicsError("fixture does not preserve the complete original class span")
    validate_fixture_class_span(config, target_source, result)
    return result


def validate_fixture_class_span(
    config: Mapping[str, Any], target_source: str, fixture_source: str
) -> None:
    target = _mapping(config.get("target"), "target")
    fixture = _mapping(config.get("fixture"), "fixture")
    comment = str(fixture["comment"])
    if fixture_source == target_source:
        raise MechanicsError("fixture must differ from frozen source")
    if fixture_source.count(comment) != 1:
        raise MechanicsError("fixture must contain exactly one fixed comment")
    if fixture_source.replace(comment, "", 1) != target_source:
        raise MechanicsError("fixture changes material other than the fixed comment")
    _verify_class_span(target_source, str(target["class_declaration"]))
    _verify_class_span(fixture_source, str(target["class_declaration"]))
    actual_hash = sha256_bytes(fixture_source.encode("utf-8"))
    if actual_hash != str(fixture["expected_sha256"]).lower():
        raise MechanicsError(
            f"fixture SHA-256 mismatch: expected {fixture['expected_sha256']}, got {actual_hash}"
        )


def _verify_file_hash(
    project_root: Path, relative: str, expected: str, label: str
) -> Path:
    path = project_root / relative
    actual = sha256_file(path)
    if actual != expected.lower():
        raise MechanicsError(
            f"{label} SHA-256 mismatch: expected {expected.lower()}, got {actual}"
        )
    return path


def verify_target_source(
    config: Mapping[str, Any], pilot_root: Path
) -> tuple[bytes, str, str, str]:
    target = _mapping(config.get("target"), "target")
    source_path = pilot_root / str(target["path"])
    raw = source_path.read_bytes()
    raw_hash = sha256_bytes(raw)
    if raw_hash != str(target["raw_source_sha256"]).lower():
        raise MechanicsError("original target source raw SHA-256 mismatch")
    normalized = normalize_source_bytes(raw)
    normalized_hash = sha256_bytes(normalized)
    if normalized_hash != str(target["normalized_source_sha256"]).lower():
        raise MechanicsError("normalized target source SHA-256 mismatch")
    start = int(target["start_byte"])
    end = int(target["end_byte"])
    if start < 0 or end <= start or end > len(normalized):
        raise MechanicsError(f"invalid frozen target range [{start}, {end})")
    source_range = normalized[start:end]
    range_hash = sha256_bytes(source_range)
    if range_hash != str(target["source_range_sha256"]).lower():
        raise MechanicsError("frozen target range SHA-256 mismatch")
    start_line = normalized[:start].count(b"\n") + 1
    end_line = normalized[:end].count(b"\n") + (
        0 if normalized[end - 1 : end] == b"\n" else 1
    )
    if start_line != int(target["start_line"]) or end_line != int(target["end_line"]):
        raise MechanicsError("frozen target line range mismatch")
    try:
        text = source_range.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MechanicsError("frozen target source is not UTF-8") from exc
    _verify_class_span(text, str(target["class_declaration"]))
    return raw, raw_hash, normalized_hash, text


def verify_frozen_selection_and_direct_tests(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> str:
    selection_config = _mapping(config.get("frozen_selection"), "frozen_selection")
    target = _mapping(config.get("target"), "target")
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    selection_path = _verify_file_hash(
        project_root,
        str(selection_config["path"]),
        str(selection_config["sha256"]),
        "frozen selection",
    )
    selection = _load_json_object(selection_path)
    candidates = selection.get("selected_candidates")
    if not isinstance(candidates, list):
        raise MechanicsError("frozen selection has no selected candidates")
    matches = [
        item
        for item in candidates
        if isinstance(item, Mapping) and item.get("pilot_target_id") == target["target_id"]
    ]
    if len(matches) != 1:
        raise MechanicsError("target does not occur exactly once in frozen selection")
    candidate = matches[0]
    expected_fields = {
        "target_symbol": target["target_symbol"],
        "granularity": target["granularity"],
        "path": target["path"],
        "selection_rank": target["selection_rank"],
        "candidate_id": target["candidate_id"],
        "chunk_id": target["chunk_id"],
        "start_byte": target["start_byte"],
        "end_byte": target["end_byte"],
        "start_line": target["start_line"],
        "end_line": target["end_line"],
    }
    for field, expected in expected_fields.items():
        if candidate.get(field) != expected:
            raise MechanicsError(f"frozen selection target mismatch: {field}")
    evidence = candidate.get("static_test_evidence")
    if not isinstance(evidence, list):
        raise MechanicsError("frozen target has no static test evidence")
    recorded_paths = sorted(
        str(item.get("path")) for item in evidence if isinstance(item, Mapping)
    )
    configured_paths = sorted(str(item) for item in evaluation["direct_test_evidence_paths"])
    if recorded_paths != configured_paths:
        raise MechanicsError("direct test paths differ from frozen target evidence")
    pattern = re.compile(
        r"\b(?:TEST|TEST_F|TEST_P)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,"
    )
    suites: set[str] = set()
    for relative in configured_paths:
        suites.update(pattern.findall((pilot_root / relative).read_text(encoding="utf-8")))
    configured_suites = [str(item) for item in evaluation["direct_test_suites"]]
    if sorted(suites) != configured_suites:
        raise MechanicsError("direct test suites do not match recorded evidence files")
    expected_filter = ":".join(f"{name}.*" for name in configured_suites)
    if evaluation.get("direct_test_filter") != expected_filter:
        raise MechanicsError("direct GTest filter is not derived from recorded suites")
    direct_command = _mapping(evaluation.get("commands"), "evaluation.commands").get(
        "direct_test", []
    )
    if f"--gtest_filter={expected_filter}" not in direct_command:
        raise MechanicsError("direct command does not use the frozen GTest filter")
    return sha256_file(selection_path)


def verify_baseline(config: Mapping[str, Any], project_root: Path) -> str:
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    path = _verify_file_hash(
        project_root,
        str(evaluation["baseline_report_path"]),
        str(evaluation["baseline_report_sha256"]),
        "baseline report",
    )
    baseline = _load_json_object(path)
    baseline_data = _mapping(baseline.get("baseline"), "baseline report baseline")
    environment = _mapping(baseline.get("environment"), "baseline report environment")
    expected = {
        "baseline_passed": True,
        "build_passed": True,
        "configure_passed": True,
        "build_type": evaluation["build_type"],
        "configure_options": evaluation["configure_options"],
        "test_count": evaluation["expected_full_test_count"],
        "test_names": evaluation["full_test_names"],
    }
    for field, value in expected.items():
        if baseline_data.get(field) != value:
            raise MechanicsError(f"baseline report mismatch: {field}")
    if environment.get("image") != evaluation["docker_image"]:
        raise MechanicsError("baseline Docker image mismatch")
    if environment.get("image_id") != evaluation["docker_image_id"]:
        raise MechanicsError("baseline Docker image ID mismatch")
    if environment.get("source_mount") != evaluation["source_mount"]:
        raise MechanicsError("baseline source mount mismatch")
    return sha256_file(path)


def validate_frozen_inputs(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> FrozenInputs:
    project_state, pilot_state = verify_repository_states(config, project_root, pilot_root)
    selection_hash = verify_frozen_selection_and_direct_tests(
        config, project_root, pilot_root
    )
    baseline_hash = verify_baseline(config, project_root)
    raw, raw_hash, normalized_hash, target_source = verify_target_source(
        config, pilot_root
    )
    fixture_source = build_fixture_class_span(config, target_source)
    return FrozenInputs(
        original_source_bytes=raw,
        original_source_sha256=raw_hash,
        normalized_source_sha256=normalized_hash,
        target_source=target_source,
        target_source_sha256=sha256_bytes(target_source.encode("utf-8")),
        fixture_source=fixture_source,
        fixture_source_sha256=sha256_bytes(fixture_source.encode("utf-8")),
        selection_sha256=selection_hash,
        baseline_report_sha256=baseline_hash,
        project_state=project_state,
        pilot_state=pilot_state,
    )


def build_evaluation_plan(config: Mapping[str, Any]) -> dict[str, Any]:
    target = _mapping(config.get("target"), "target")
    fixture = _mapping(config.get("fixture"), "fixture")
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    replacement = _mapping(
        config.get("replacement_and_restoration"),
        "replacement_and_restoration",
    )
    commands = _mapping(evaluation.get("commands"), "evaluation.commands")
    timeouts = _mapping(
        evaluation.get("stage_timeouts_seconds"), "evaluation.stage_timeouts_seconds"
    )
    stages: list[dict[str, Any]] = []
    local_descriptions = {
        "fixture_validation": [
            "verify deterministic fixture SHA-256",
            "verify exact one-comment-only difference",
            "verify complete structurally valid class span",
        ],
        "source_backup": ["preserve complete original raw node.h bytes"],
        "source_replacement": [
            "replace only the normalized frozen half-open byte range",
            "verify resulting source differs from original bytes",
        ],
    }
    for name, command in local_descriptions.items():
        stages.append(
            {
                "stage": name,
                "command": command,
                "timeout_seconds": None,
                "preserve": ["stdout", "stderr", "exit_code", "timeout", "stage_status"],
            }
        )
    for name in ("configure", "build", "direct_test", "full_test"):
        command = commands.get(name)
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise MechanicsError(f"evaluation command is not a string array: {name}")
        stages.append(
            {
                "stage": name,
                "command": command,
                "timeout_seconds": int(timeouts[name]),
                "preserve": ["stdout", "stderr", "exit_code", "timeout", "stage_status"],
            }
        )
    stages.append(
        {
            "stage": "restoration",
            "command": [
                "restore exact original_source.bin bytes in finally",
                "verify exact bytes and raw SHA-256",
                "verify clean yaml-cpp worktree",
            ],
            "timeout_seconds": int(timeouts["restoration"]),
            "preserve": ["stdout", "stderr", "exit_code", "timeout", "stage_status"],
        }
    )
    return {
        "artifact_schema_version": "rag-yaml-cpp-mechanics-evaluation-plan-v1",
        "run_id": config["run_id"],
        "condition_id": config["condition_id"],
        "classification": config["classification"],
        "target": {
            "target_id": target["target_id"],
            "target_symbol": target["target_symbol"],
            "path": target["path"],
            "normalized_half_open_range": [target["start_byte"], target["end_byte"]],
            "original_raw_sha256": target["raw_source_sha256"],
            "original_normalized_sha256": target["normalized_source_sha256"],
            "original_range_sha256": target["source_range_sha256"],
            "fixture_sha256": fixture["expected_sha256"],
        },
        "fixture": {
            "algorithm": fixture["algorithm"],
            "comment": fixture["comment"],
            "only_change": "one harmless fixed comment immediately after opening brace",
            "interface_changes": False,
            "behavior_changes": False,
        },
        "baseline": {
            "report_path": evaluation["baseline_report_path"],
            "report_sha256": evaluation["baseline_report_sha256"],
            "docker_image": evaluation["docker_image"],
            "docker_image_id": evaluation["docker_image_id"],
            "source_mount": evaluation["source_mount"],
            "build_type": evaluation["build_type"],
            "configure_options": evaluation["configure_options"],
        },
        "direct_tests": {
            "recorded_evidence_paths": evaluation["direct_test_evidence_paths"],
            "suites": evaluation["direct_test_suites"],
            "gtest_filter": evaluation["direct_test_filter"],
        },
        "full_tests": {
            "names": evaluation["full_test_names"],
            "expected_count": evaluation["expected_full_test_count"],
        },
        "ordered_stages": list(config["required_stage_records"]),
        "stages": stages,
        "replacement_and_restoration": dict(replacement),
        "one_shot_policy": config["one_shot_policy"],
        "zero_generation_policy": config["llm_policy"],
        "failure_policy": {
            "skip_dependent_later_stages": True,
            "restore_in_finally_after_replacement": True,
            "preserve_partial_evidence": True,
            "retry": False,
            "repair": False,
            "overwrite": False,
            "manual_runtime_patch": False,
        },
    }


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise MechanicsError(f"refusing to overwrite existing evidence: {path}") from exc


def _write_exclusive_json(path: Path, value: Any) -> str:
    data = canonical_json_bytes(value)
    _write_exclusive(path, data)
    return sha256_bytes(data)


def output_root(config: Mapping[str, Any], project_root: Path) -> Path:
    return project_root / str(config["output_path"])


def ensure_execution_not_attempted(config: Mapping[str, Any], run_root: Path) -> None:
    policy = _mapping(config.get("one_shot_policy"), "one_shot_policy")
    guarded = [
        run_root / str(policy["attempt_marker"]),
        run_root / str(policy["failure_marker"]),
        run_root / str(policy["result_marker"]),
    ]
    existing = [path for path in guarded if path.exists()]
    if existing:
        raise MechanicsError(
            "one-shot mechanics execution is already attempted, failed, or complete: "
            + ", ".join(str(path) for path in existing)
        )


def run_plan_only(
    config: Mapping[str, Any],
    config_path: Path,
    project_root: Path,
    pilot_root: Path,
) -> dict[str, Any]:
    run_root = output_root(config, project_root)
    ensure_execution_not_attempted(config, run_root)
    frozen = validate_frozen_inputs(config, project_root, pilot_root)
    fixture_bytes = frozen.fixture_source.encode("utf-8")
    evaluation_bytes = canonical_json_bytes(build_evaluation_plan(config))
    manifest = {
        "artifact_schema_version": "rag-yaml-cpp-mechanics-plan-manifest-v1",
        "status": "ready_to_execute_once",
        "mode": "plan-only",
        "run_id": config["run_id"],
        "condition_id": config["condition_id"],
        "classification": config["classification"],
        "target": dict(config["target"]),
        "repositories": {
            "project": {
                "head": frozen.project_state.head,
                "branch": frozen.project_state.branch,
                "clean": frozen.project_state.clean,
            },
            "yaml_cpp": {
                "head": frozen.pilot_state.head,
                "branch": frozen.pilot_state.branch,
                "clean": frozen.pilot_state.clean,
            },
        },
        "frozen_inputs": {
            "original_raw_source_sha256": frozen.original_source_sha256,
            "original_normalized_source_sha256": frozen.normalized_source_sha256,
            "original_class_span_sha256": frozen.target_source_sha256,
            "fixture_class_span_sha256": frozen.fixture_source_sha256,
            "selection_sha256": frozen.selection_sha256,
            "baseline_report_sha256": frozen.baseline_report_sha256,
        },
        "plan_artifacts": {
            "fixture": {
                "path": f"plan/{FIXTURE_FILE}",
                "sha256": sha256_bytes(fixture_bytes),
            },
            "evaluation_plan": {
                "path": f"plan/{EVALUATION_PLAN_FILE}",
                "sha256": sha256_bytes(evaluation_bytes),
            },
        },
        "config": {
            "path": config_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(config_path),
        },
        "one_shot_policy": config["one_shot_policy"],
        "llm_called": False,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "fixture_frozen": True,
        "source_replaced": False,
        "docker_called": False,
        "configure_started": False,
        "build_started": False,
        "tests_started": False,
    }
    plan_root = run_root / "plan"
    _write_exclusive(plan_root / FIXTURE_FILE, fixture_bytes)
    _write_exclusive(plan_root / EVALUATION_PLAN_FILE, evaluation_bytes)
    _write_exclusive_json(plan_root / PLAN_MANIFEST_FILE, manifest)
    return manifest


def _load_and_verify_plan(
    config: Mapping[str, Any], project_root: Path, frozen: FrozenInputs
) -> dict[str, Any]:
    plan_root = output_root(config, project_root) / "plan"
    manifest = _load_json_object(plan_root / PLAN_MANIFEST_FILE)
    expected = {
        FIXTURE_FILE: frozen.fixture_source.encode("utf-8"),
        EVALUATION_PLAN_FILE: canonical_json_bytes(build_evaluation_plan(config)),
    }
    records = _mapping(manifest.get("plan_artifacts"), "plan_artifacts")
    record_names = {FIXTURE_FILE: "fixture", EVALUATION_PLAN_FILE: "evaluation_plan"}
    for filename, expected_bytes in expected.items():
        actual = (plan_root / filename).read_bytes()
        if actual != expected_bytes:
            raise MechanicsError(f"stored plan artifact changed: {filename}")
        record = _mapping(records.get(record_names[filename]), filename)
        if record.get("sha256") != sha256_bytes(actual):
            raise MechanicsError(f"stored plan artifact SHA-256 mismatch: {filename}")
    required_false = (
        "llm_called",
        "generation_server_contacted",
        "source_replaced",
        "docker_called",
        "configure_started",
        "build_started",
        "tests_started",
    )
    for field in required_false:
        if manifest.get(field) is not False:
            raise MechanicsError(f"plan manifest mutation flag mismatch: {field}")
    if manifest.get("llm_call_count") != 0:
        raise MechanicsError("plan manifest must record zero LLM calls")
    return manifest


class SourceReplacementTransaction:
    """Replace one normalized range and restore exact original raw bytes on exit."""

    def __init__(
        self,
        source_path: Path,
        original_bytes: bytes,
        start: int,
        end: int,
        replacement_bytes: bytes,
        expected_original_sha256: str,
    ) -> None:
        self.source_path = source_path
        self.original_bytes = original_bytes
        self.start = start
        self.end = end
        self.replacement_bytes = replacement_bytes
        self.expected_original_sha256 = expected_original_sha256
        self.replaced = False
        self.replaced_sha256: str | None = None
        self.restored = False
        self.restored_sha256: str | None = None
        self.restoration_error: str | None = None

    def __enter__(self) -> "SourceReplacementTransaction":
        current = self.source_path.read_bytes()
        if current != self.original_bytes:
            raise MechanicsError("target source changed before replacement")
        raw_start, raw_end = raw_offsets_for_normalized_range(
            current, self.start, self.end
        )
        replaced = current[:raw_start] + self.replacement_bytes + current[raw_end:]
        if replaced == current:
            raise MechanicsError("replacement did not change target source bytes")
        self.replaced = True
        try:
            self.source_path.write_bytes(replaced)
            actual = self.source_path.read_bytes()
            if actual != replaced:
                raise MechanicsError("target source replacement bytes were not preserved")
            self.replaced_sha256 = sha256_bytes(actual)
        except Exception:
            self._restore_once()
            raise
        return self

    def _restore_once(self) -> None:
        try:
            self.source_path.write_bytes(self.original_bytes)
            restored = self.source_path.read_bytes()
            self.restored_sha256 = sha256_bytes(restored)
            if restored != self.original_bytes:
                raise MechanicsError("restored source bytes differ from original")
            if self.restored_sha256 != self.expected_original_sha256:
                raise MechanicsError("restored source SHA-256 mismatch")
            self.restored = True
        except Exception as restoration_error:
            self.restoration_error = str(restoration_error)
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self.replaced and not self.restored:
            self._restore_once()
        return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stage_paths(run_root: Path, stage: str) -> tuple[Path, Path, Path]:
    root = run_root / "stages"
    return (
        root / f"{stage}.stdout.txt",
        root / f"{stage}.stderr.txt",
        root / f"{stage}.json",
    )


def _record_stage(
    run_root: Path,
    stage: str,
    stdout: str,
    stderr: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    stdout_path, stderr_path, record_path = _stage_paths(run_root, stage)
    stdout_bytes = stdout.encode("utf-8")
    stderr_bytes = stderr.encode("utf-8")
    _write_exclusive(stdout_path, stdout_bytes)
    _write_exclusive(stderr_path, stderr_bytes)
    value = dict(record)
    value["stdout_path"] = stdout_path.relative_to(run_root).as_posix()
    value["stderr_path"] = stderr_path.relative_to(run_root).as_posix()
    value["stdout_sha256"] = sha256_bytes(stdout_bytes)
    value["stderr_sha256"] = sha256_bytes(stderr_bytes)
    _write_exclusive_json(record_path, value)
    return value


def _record_skipped_stage(run_root: Path, stage: str, reason: str) -> dict[str, Any]:
    return _record_stage(
        run_root,
        stage,
        "",
        "",
        {
            "stage": stage,
            "status": "skipped",
            "reason": reason,
            "exit_code": None,
            "timed_out": False,
            "timeout_seconds": None,
            "started": False,
        },
    )


def _render_command(template: list[str], pilot_root: Path, workspace: Path) -> list[str]:
    return [
        item.replace("<YAML_CPP_ROOT>", str(pilot_root)).replace(
            "<EVALUATION_WORKSPACE>", str(workspace)
        )
        for item in template
    ]


def _run_process_stage(
    run_root: Path,
    stage: str,
    command_template: list[str],
    command: list[str],
    timeout_seconds: int,
) -> dict[str, Any]:
    started_at = _utc_now()
    started = time.perf_counter()
    timed_out = False
    try:
        result = subprocess.run(
            command,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        exit_code = 124
    duration = time.perf_counter() - started
    return _record_stage(
        run_root,
        stage,
        stdout,
        stderr,
        {
            "stage": stage,
            "status": "pass" if exit_code == 0 and not timed_out else "fail",
            "command": command_template,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "timeout_seconds": timeout_seconds,
            "started": True,
            "started_at": started_at,
            "duration_seconds": duration,
        },
    )


def _verify_docker_image(config: Mapping[str, Any]) -> str:
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    image = str(evaluation["docker_image"])
    result = subprocess.run(
        ["docker", "image", "inspect", "--format={{.Id}}", image],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise MechanicsError(
            f"Docker image is unavailable: {image}: {result.stderr.strip()}"
        )
    actual = result.stdout.strip()
    if actual != evaluation["docker_image_id"]:
        raise MechanicsError(
            f"Docker image ID mismatch: expected {evaluation['docker_image_id']}, got {actual}"
        )
    return actual


def run_execution(
    config: Mapping[str, Any],
    project_root: Path,
    pilot_root: Path,
) -> dict[str, Any]:
    """Execute the frozen replacement pipeline once; this function never contacts an LLM."""
    run_root = output_root(config, project_root)
    ensure_execution_not_attempted(config, run_root)
    frozen = validate_frozen_inputs(config, project_root, pilot_root)
    _load_and_verify_plan(config, project_root, frozen)
    ensure_execution_not_attempted(config, run_root)
    policy = _mapping(config.get("one_shot_policy"), "one_shot_policy")
    target = _mapping(config.get("target"), "target")
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    commands = _mapping(evaluation.get("commands"), "evaluation.commands")
    timeouts = _mapping(
        evaluation.get("stage_timeouts_seconds"), "evaluation.stage_timeouts_seconds"
    )
    attempt = {
        "artifact_schema_version": "rag-yaml-cpp-mechanics-attempt-v1",
        "run_id": config["run_id"],
        "started_at": _utc_now(),
        "execution_limit": 1,
        "retry_allowed": False,
        "repair_allowed": False,
        "overwrite_allowed": False,
        "manual_runtime_patch_allowed": False,
        "llm_called": False,
        "llm_call_count": 0,
        "generation_server_contacted": False,
    }
    _write_exclusive_json(run_root / str(policy["attempt_marker"]), attempt)

    records: dict[str, dict[str, Any]] = {}
    transaction: SourceReplacementTransaction | None = None
    source_path = pilot_root / str(target["path"])
    failure: str | None = None
    try:
        _verify_docker_image(config)
        records["fixture_validation"] = _record_stage(
            run_root,
            "fixture_validation",
            f"fixture_sha256={frozen.fixture_source_sha256}\n",
            "",
            {
                "stage": "fixture_validation",
                "status": "pass",
                "exit_code": 0,
                "timed_out": False,
                "timeout_seconds": None,
                "started": True,
                "fixture_sha256": frozen.fixture_source_sha256,
                "exact_one_comment_only_difference": True,
                "structurally_valid_class_span": True,
            },
        )
        backup_path = run_root / "evidence" / ORIGINAL_SOURCE_FILE
        _write_exclusive(backup_path, frozen.original_source_bytes)
        records["source_backup"] = _record_stage(
            run_root,
            "source_backup",
            f"original_raw_sha256={frozen.original_source_sha256}\n",
            "",
            {
                "stage": "source_backup",
                "status": "pass",
                "exit_code": 0,
                "timed_out": False,
                "timeout_seconds": None,
                "started": True,
                "backup_path": backup_path.relative_to(run_root).as_posix(),
                "backup_sha256": sha256_file(backup_path),
            },
        )
        transaction = SourceReplacementTransaction(
            source_path=source_path,
            original_bytes=frozen.original_source_bytes,
            start=int(target["start_byte"]),
            end=int(target["end_byte"]),
            replacement_bytes=frozen.fixture_source.encode("utf-8"),
            expected_original_sha256=frozen.original_source_sha256,
        )
        with transaction:
            normalized = normalize_source_bytes(source_path.read_bytes())
            start = int(target["start_byte"])
            end = int(target["end_byte"])
            fixture_bytes = frozen.fixture_source.encode("utf-8")
            original_normalized = normalize_source_bytes(frozen.original_source_bytes)
            expected_normalized = (
                original_normalized[:start] + fixture_bytes + original_normalized[end:]
            )
            if normalized != expected_normalized:
                raise MechanicsError(
                    "replacement changed bytes outside the frozen normalized range"
                )
            records["source_replacement"] = _record_stage(
                run_root,
                "source_replacement",
                f"replaced_source_sha256={transaction.replaced_sha256}\n",
                "",
                {
                    "stage": "source_replacement",
                    "status": "pass",
                    "exit_code": 0,
                    "timed_out": False,
                    "timeout_seconds": None,
                    "started": True,
                    "normalized_original_range": [target["start_byte"], target["end_byte"]],
                    "fixture_sha256": frozen.fixture_source_sha256,
                    "replaced_source_sha256": transaction.replaced_sha256,
                    "source_bytes_differ": True,
                },
            )
            workspace = run_root / "evaluation"
            workspace.mkdir(parents=True, exist_ok=True)
            previous_passed = True
            for stage in ("configure", "build", "direct_test", "full_test"):
                if not previous_passed:
                    records[stage] = _record_skipped_stage(
                        run_root, stage, "dependent earlier stage failed"
                    )
                    continue
                template = [str(item) for item in commands[stage]]
                command = _render_command(template, pilot_root.resolve(), workspace.resolve())
                records[stage] = _run_process_stage(
                    run_root, stage, template, command, int(timeouts[stage])
                )
                previous_passed = records[stage]["status"] == "pass"
            if not previous_passed:
                raise MechanicsError("one or more evaluation stages failed")
    except Exception as exc:
        failure = str(exc)
    finally:
        if transaction is not None and transaction.replaced:
            if not transaction.restored and transaction.restoration_error is None:
                # Normal context-manager exit restores before control reaches here.
                failure = failure or "source restoration did not complete"
            clean = _git(
                pilot_root, "status", "--porcelain=v1", "--untracked-files=all"
            ).stdout == ""
            restoration_pass = (
                transaction.restored
                and transaction.restored_sha256 == frozen.original_source_sha256
                and source_path.read_bytes() == frozen.original_source_bytes
                and clean
            )
            records["restoration"] = _record_stage(
                run_root,
                "restoration",
                f"restored_source_sha256={transaction.restored_sha256}\nrepository_clean={clean}\n",
                (transaction.restoration_error or "") + ("\n" if transaction.restoration_error else ""),
                {
                    "stage": "restoration",
                    "status": "pass" if restoration_pass else "fail",
                    "exit_code": 0 if restoration_pass else 1,
                    "timed_out": False,
                    "timeout_seconds": int(timeouts["restoration"]),
                    "started": True,
                    "restored_source_sha256": transaction.restored_sha256,
                    "restored_bytes_equal_original": source_path.read_bytes()
                    == frozen.original_source_bytes,
                    "repository_clean": clean,
                },
            )
            if not restoration_pass:
                failure = failure or "source restoration verification failed"
        else:
            if "restoration" not in records:
                records["restoration"] = _record_skipped_stage(
                    run_root, "restoration", "source was not replaced"
                )
        for stage in config["required_stage_records"]:
            if stage not in records:
                records[stage] = _record_skipped_stage(
                    run_root, str(stage), "execution stopped before this stage"
                )

    common = {
        "run_id": config["run_id"],
        "condition_id": config["condition_id"],
        "target_id": target["target_id"],
        "stage_statuses": {name: records[name]["status"] for name in config["required_stage_records"]},
        "llm_called": False,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "retry_performed": False,
        "repair_performed": False,
        "manual_runtime_patch_performed": False,
        "source_restored": bool(transaction and transaction.restored),
    }
    if failure is not None:
        marker = {
            "artifact_schema_version": "rag-yaml-cpp-mechanics-failure-v1",
            **common,
            "status": "failed",
            "failure": failure,
            "finished_at": _utc_now(),
        }
        _write_exclusive_json(run_root / str(policy["failure_marker"]), marker)
        raise MechanicsError(f"mechanics execution failed without retry: {failure}")
    result = {
        "artifact_schema_version": "rag-yaml-cpp-mechanics-result-v1",
        **common,
        "status": "completed",
        "formal_experimental_result": False,
        "evidence_of_rag_improvement": False,
        "finished_at": _utc_now(),
    }
    _write_exclusive_json(run_root / str(policy["result_marker"]), result)
    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--yaml-cpp-root", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(__file__).resolve().parents[2]
    config_path = (project_root / args.config).resolve()
    pilot_root = Path(args.yaml_cpp_root).resolve()
    try:
        config = load_config(config_path)
        if args.plan_only:
            manifest = run_plan_only(config, config_path, project_root, pilot_root)
            print(
                json.dumps(
                    {
                        "status": manifest["status"],
                        "run_id": manifest["run_id"],
                        "output_path": config["output_path"],
                        "llm_call_count": manifest["llm_call_count"],
                        "generation_server_contacted": manifest[
                            "generation_server_contacted"
                        ],
                        "source_replaced": manifest["source_replaced"],
                        "docker_called": manifest["docker_called"],
                    },
                    sort_keys=True,
                )
            )
        else:
            result = run_execution(config, project_root, pilot_root)
            print(json.dumps(result, sort_keys=True))
    except (MechanicsError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
