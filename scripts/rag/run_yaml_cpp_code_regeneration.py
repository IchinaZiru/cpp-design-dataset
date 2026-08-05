"""Plan or execute the yaml-cpp YAML::Node code-regeneration pilot once."""

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
from scripts.rag.run_yaml_cpp_design_generation import contact_generation_server
from scripts.roundtrip.roundtrip_common import (
    find_matching_brace,
    strip_inline_callable_bodies,
)


DEFAULT_CONFIG = "configs/rag/pilot/yaml_cpp_yaml_node_code_regeneration_v1.json"
SCAFFOLD_FILE = "fixed_scaffold.txt"
PROMPT_FILE = "code_regeneration_prompt.txt"
REQUEST_FILE = "ollama_request.json"
EVALUATION_PLAN_FILE = "evaluation_plan.json"
PLAN_FILE = "plan_manifest.json"
CONTACT_FILE = "generation_server_contact.json"
RESPONSE_FILE = "code_regeneration_response.json"
GENERATED_FILE = "regenerated_class_span.cpp"
ORIGINAL_FILE = "original_source.bin"


class CodeRegenerationError(RuntimeError):
    """Raised when frozen code-regeneration or evaluation invariants fail."""


@dataclass(frozen=True)
class RepositoryState:
    head: str
    branch: str | None
    clean: bool


@dataclass(frozen=True)
class FrozenInputs:
    design_document: str
    design_document_sha256: str
    original_source_bytes: bytes
    original_source_sha256: str
    normalized_source_sha256: str
    target_source: str
    target_source_sha256: str
    project_state: RepositoryState
    pilot_state: RepositoryState


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CodeRegenerationError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CodeRegenerationError(f"JSON root must be an object: {path}")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CodeRegenerationError(f"{field} must be an object")
    return value


def load_config(path: Path) -> dict[str, Any]:
    config = _load_json_object(path)
    if config.get("artifact_schema_version") != "rag-yaml-cpp-code-regeneration-config-v1":
        raise CodeRegenerationError("unsupported code-regeneration config schema")
    posix_relative_path(str(config.get("output_path", "")))
    target = _mapping(config.get("target"), "target")
    posix_relative_path(str(target.get("path", "")))
    selection = _mapping(config.get("frozen_selection"), "frozen_selection")
    posix_relative_path(str(selection.get("path", "")))
    design = _mapping(config.get("design_evidence"), "design_evidence")
    for field in (
        "root_path",
        "design_document_path",
        "design_request_path",
        "design_result_path",
        "design_attempt_path",
        "design_contact_path",
    ):
        posix_relative_path(str(design.get(field, "")))
    policy = _mapping(config.get("one_shot_policy"), "one_shot_policy")
    required_policy = {
        "code_regeneration_requests": 1,
        "retry_allowed": False,
        "repair_allowed": False,
        "overwrite_allowed": False,
        "manual_patch_allowed": False,
        "second_call_allowed": False,
    }
    for field, expected in required_policy.items():
        if policy.get(field) != expected:
            raise CodeRegenerationError(f"one-shot policy mismatch: {field}")
    input_policy = _mapping(config.get("prompt_input_policy"), "prompt_input_policy")
    if input_policy.get("allowed_verbatim_inputs") != [
        "design_document.md",
        "fixed_scaffold.txt",
    ]:
        raise CodeRegenerationError("prompt allowed-input list is not frozen")
    required_forbidden = {
        "original_target_source_body",
        "frozen_rag_context",
        "selected_retrieval_chunks",
        "design_generation_prompt",
        "design_generation_request",
        "design_document_audit_findings",
        "yaml_cpp_implementation_files_including_node_impl_h",
    }
    if set(input_policy.get("forbidden_inputs", [])) != required_forbidden:
        raise CodeRegenerationError("prompt forbidden-input list is not frozen")
    normalization = _mapping(config.get("normalization"), "normalization")
    if normalization.get("policy") != "existing-roundtrip-outer-markdown-fence-only-v1":
        raise CodeRegenerationError("normalization policy mismatch")
    if normalization.get("automatic_repair_allowed") is not False:
        raise CodeRegenerationError("automatic repair must remain disabled")
    if normalization.get("manual_patch_allowed") is not False:
        raise CodeRegenerationError("manual patching must remain disabled")
    replacement = _mapping(
        config.get("replacement_and_restoration"),
        "replacement_and_restoration",
    )
    if int(replacement.get("replace_only_start_byte", -1)) != int(target["start_byte"]):
        raise CodeRegenerationError("replacement start does not match frozen target")
    if int(replacement.get("replace_only_end_byte", -1)) != int(target["end_byte"]):
        raise CodeRegenerationError("replacement end does not match frozen target")
    if replacement.get("restore_in_finally") is not True:
        raise CodeRegenerationError("source restoration must run in finally")
    if replacement.get("manual_patch_allowed") is not False:
        raise CodeRegenerationError("manual source patching must remain disabled")
    return config


def _git(repository: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise CodeRegenerationError(
            f"git {' '.join(arguments)} failed for {repository}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def repository_state(repository: Path, required_branch: str | None = None) -> RepositoryState:
    head = _git(repository, "rev-parse", "HEAD").stdout.strip().lower()
    branch = _git(repository, "branch", "--show-current").stdout.strip() or None
    status = _git(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).stdout
    if status:
        raise CodeRegenerationError(f"worktree is not clean: {repository}\n{status.rstrip()}")
    if required_branch is not None and branch != required_branch:
        raise CodeRegenerationError(
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
        project_root,
        "merge-base",
        "--is-ancestor",
        baseline,
        project.head,
        check=False,
    )
    if ancestor.returncode != 0:
        raise CodeRegenerationError(
            f"required project baseline {baseline} is not an ancestor of {project.head}"
        )
    pilot = repository_state(pilot_root)
    expected_pilot = str(pilot_config["required_commit"]).lower()
    if pilot.head != expected_pilot:
        raise CodeRegenerationError(
            f"yaml-cpp commit mismatch: expected {expected_pilot}, got {pilot.head}"
        )
    return project, pilot


def normalize_source_bytes(raw: bytes) -> bytes:
    normalized = raw.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise CodeRegenerationError("source contains unsupported lone CR bytes")
    return normalized


def verify_target_source(
    config: Mapping[str, Any], pilot_root: Path
) -> tuple[bytes, str, str, str]:
    target = _mapping(config.get("target"), "target")
    source_path = pilot_root / str(target["path"])
    raw = source_path.read_bytes()
    raw_hash = sha256_bytes(raw)
    if raw_hash != str(target["raw_source_sha256"]).lower():
        raise CodeRegenerationError("original target source raw SHA-256 mismatch")
    normalized = normalize_source_bytes(raw)
    normalized_hash = sha256_bytes(normalized)
    if normalized_hash != str(target["normalized_source_sha256"]).lower():
        raise CodeRegenerationError("normalized target source SHA-256 mismatch")
    start = int(target["start_byte"])
    end = int(target["end_byte"])
    if start < 0 or end <= start or end > len(normalized):
        raise CodeRegenerationError(f"invalid frozen target range [{start}, {end})")
    source_range = normalized[start:end]
    range_hash = sha256_bytes(source_range)
    if range_hash != str(target["source_range_sha256"]).lower():
        raise CodeRegenerationError("frozen target range SHA-256 mismatch")
    start_line = normalized[:start].count(b"\n") + 1
    end_line = normalized[:end].count(b"\n") + (0 if normalized[end - 1:end] == b"\n" else 1)
    if start_line != int(target["start_line"]) or end_line != int(target["end_line"]):
        raise CodeRegenerationError("frozen target line range mismatch")
    text = source_range.decode("utf-8")
    if not text.startswith(str(target["class_declaration"])):
        raise CodeRegenerationError("frozen range does not start with the target class")
    if not text.rstrip().endswith("}") or text.rstrip().endswith("};"):
        raise CodeRegenerationError("frozen range must end at the class closing brace")
    return raw, raw_hash, normalized_hash, text


def _verify_file_hash(project_root: Path, relative: str, expected: str, label: str) -> Path:
    path = project_root / relative
    actual = sha256_file(path)
    if actual != expected.lower():
        raise CodeRegenerationError(
            f"{label} SHA-256 mismatch: expected {expected.lower()}, got {actual}"
        )
    return path


def verify_design_evidence(config: Mapping[str, Any], project_root: Path) -> tuple[str, str]:
    evidence = _mapping(config.get("design_evidence"), "design_evidence")
    target = _mapping(config.get("target"), "target")
    design_path = _verify_file_hash(
        project_root,
        str(evidence["design_document_path"]),
        str(evidence["design_document_sha256"]),
        "design document",
    )
    _verify_file_hash(
        project_root,
        str(evidence["design_request_path"]),
        str(evidence["design_request_sha256"]),
        "design-generation request",
    )
    result_path = _verify_file_hash(
        project_root,
        str(evidence["design_result_path"]),
        str(evidence["design_result_sha256"]),
        "design-generation result",
    )
    attempt_path = _verify_file_hash(
        project_root,
        str(evidence["design_attempt_path"]),
        str(evidence["design_attempt_sha256"]),
        "design-generation attempt",
    )
    contact_path = _verify_file_hash(
        project_root,
        str(evidence["design_contact_path"]),
        str(evidence["design_contact_sha256"]),
        "design-generation contact",
    )
    result = _load_json_object(result_path)
    expected_result = {
        "run_id": evidence["run_id"],
        "target_id": target["target_id"],
        "status": "completed",
        "request_sha256": evidence["design_request_sha256"],
        "design_document_sha256": evidence["design_document_sha256"],
        "llm_called": True,
        "llm_call_count": evidence["expected_llm_call_count"],
        "generation_server_contacted": True,
        "retry_performed": evidence["expected_retry_performed"],
        "repair_performed": evidence["expected_repair_performed"],
        "code_regeneration_performed": False,
    }
    for field, expected in expected_result.items():
        if result.get(field) != expected:
            raise CodeRegenerationError(f"design-generation result mismatch: {field}")
    attempt = _load_json_object(attempt_path)
    if attempt.get("run_id") != evidence["run_id"]:
        raise CodeRegenerationError("design attempt run ID mismatch")
    if attempt.get("design_generation_request_limit") != 1:
        raise CodeRegenerationError("design attempt did not reserve exactly one request")
    for field in ("retry_allowed", "repair_allowed", "overwrite_allowed"):
        if attempt.get(field) is not False:
            raise CodeRegenerationError(f"design attempt policy mismatch: {field}")
    contact = _load_json_object(contact_path)
    if contact.get("llm_called") is not True or contact.get("llm_call_count") != 1:
        raise CodeRegenerationError("design contact does not record exactly one LLM call")
    if contact.get("retry_performed") is not False:
        raise CodeRegenerationError("design contact records a retry")
    plan_path = project_root / str(evidence["root_path"]) / "plan" / "plan_manifest.json"
    design_plan = _load_json_object(plan_path)
    plan_target = _mapping(design_plan.get("target"), "design plan target")
    for field in (
        "target_id",
        "target_symbol",
        "granularity",
        "path",
        "selection_rank",
        "start_byte",
        "end_byte",
        "start_line",
        "end_line",
        "normalized_source_sha256",
        "source_range_sha256",
    ):
        if plan_target.get(field) != target.get(field):
            raise CodeRegenerationError(f"design plan target locator mismatch: {field}")
    design_bytes = design_path.read_bytes()
    try:
        design_text = design_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CodeRegenerationError("design document is not UTF-8") from exc
    return design_text, sha256_bytes(design_bytes)


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
        raise CodeRegenerationError("frozen selection has no selected candidates")
    matches = [
        item
        for item in candidates
        if isinstance(item, Mapping)
        and item.get("pilot_target_id") == target["target_id"]
    ]
    if len(matches) != 1:
        raise CodeRegenerationError("target does not occur exactly once in frozen selection")
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
            raise CodeRegenerationError(f"frozen selection target mismatch: {field}")
    evidence = candidate.get("static_test_evidence")
    if not isinstance(evidence, list):
        raise CodeRegenerationError("frozen target has no static test evidence")
    recorded_paths = sorted(
        str(item.get("path")) for item in evidence if isinstance(item, Mapping)
    )
    configured_paths = sorted(str(item) for item in evaluation["direct_test_evidence_paths"])
    if recorded_paths != configured_paths:
        raise CodeRegenerationError("direct test paths differ from frozen target evidence")
    pattern = re.compile(
        r"\b(?:TEST|TEST_F|TEST_P)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,"
    )
    suites: set[str] = set()
    for relative in configured_paths:
        text = (pilot_root / relative).read_text(encoding="utf-8")
        suites.update(pattern.findall(text))
    configured_suites = [str(item) for item in evaluation["direct_test_suites"]]
    if sorted(suites) != configured_suites:
        raise CodeRegenerationError("direct test suites do not match recorded evidence files")
    expected_filter = ":".join(f"{name}.*" for name in configured_suites)
    if evaluation.get("direct_test_filter") != expected_filter:
        raise CodeRegenerationError("direct GTest filter is not derived from recorded suites")
    direct_command = evaluation.get("commands", {}).get("direct_test", [])
    if f"--gtest_filter={expected_filter}" not in direct_command:
        raise CodeRegenerationError("direct command does not use the frozen GTest filter")
    return sha256_file(selection_path)


def validate_frozen_inputs(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> FrozenInputs:
    project_state, pilot_state = verify_repository_states(config, project_root, pilot_root)
    design, design_hash = verify_design_evidence(config, project_root)
    verify_frozen_selection_and_direct_tests(config, project_root, pilot_root)
    raw, raw_hash, normalized_hash, target_source = verify_target_source(config, pilot_root)
    return FrozenInputs(
        design_document=design,
        design_document_sha256=design_hash,
        original_source_bytes=raw,
        original_source_sha256=raw_hash,
        normalized_source_sha256=normalized_hash,
        target_source=target_source,
        target_source_sha256=sha256_bytes(target_source.encode("utf-8")),
        project_state=project_state,
        pilot_state=pilot_state,
    )


def build_fixed_scaffold(
    config: Mapping[str, Any], project_root: Path, target_source: str
) -> str:
    scaffold_config = _mapping(config.get("scaffold"), "scaffold")
    implementation_path = project_root / str(scaffold_config["implementation_path"])
    actual_implementation_hash = sha256_file(implementation_path)
    if actual_implementation_hash != str(scaffold_config["implementation_sha256"]).lower():
        raise CodeRegenerationError("scaffold implementation SHA-256 mismatch")
    scaffold = strip_inline_callable_bodies(target_source).rstrip() + "\n"
    scaffold_hash = sha256_bytes(scaffold.encode("utf-8"))
    if scaffold_hash != str(scaffold_config["expected_sha256"]).lower():
        raise CodeRegenerationError(
            f"fixed scaffold SHA-256 mismatch: {scaffold_hash}"
        )
    return scaffold


def _verbatim_section(heading: str, content: str) -> str:
    suffix = "" if content.endswith("\n") else "\n"
    return f"# {heading}\n{content}{suffix}# END {heading}\n"


def compose_code_regeneration_prompt(
    config: Mapping[str, Any], design_document: str, fixed_scaffold: str
) -> str:
    target = _mapping(config.get("target"), "target")
    prompt = _mapping(config.get("prompt"), "prompt")
    return (
        "# Target\n"
        f"- target_id: {target['target_id']}\n"
        f"- target_symbol: {target['target_symbol']}\n"
        f"- granularity: {target['granularity']}\n\n"
        "# Output requirements\n"
        f"{prompt['output_instruction']}\n\n"
        "# Input isolation\n"
        f"{prompt['isolation_instruction']}\n\n"
        + _verbatim_section(str(prompt["design_heading"]), design_document)
        + "\n"
        + _verbatim_section(str(prompt["scaffold_heading"]), fixed_scaffold)
    )


def extract_verbatim_section(prompt_text: str, heading: str) -> str:
    start_marker = f"# {heading}\n"
    end_marker = f"# END {heading}\n"
    if prompt_text.count(start_marker) != 1 or prompt_text.count(end_marker) != 1:
        raise CodeRegenerationError(f"prompt section is not unique: {heading}")
    start = prompt_text.index(start_marker) + len(start_marker)
    end = prompt_text.index(end_marker, start)
    return prompt_text[start:end]


def verify_prompt_isolation(
    config: Mapping[str, Any], prompt_text: str, design_document: str,
    fixed_scaffold: str, original_target_source: str
) -> None:
    prompt_config = _mapping(config.get("prompt"), "prompt")
    design_section = extract_verbatim_section(
        prompt_text, str(prompt_config["design_heading"])
    )
    scaffold_section = extract_verbatim_section(
        prompt_text, str(prompt_config["scaffold_heading"])
    )
    expected_design = design_document + ("" if design_document.endswith("\n") else "\n")
    expected_scaffold = fixed_scaffold + ("" if fixed_scaffold.endswith("\n") else "\n")
    if design_section != expected_design:
        raise CodeRegenerationError("prompt does not contain the verbatim design document")
    if scaffold_section != expected_scaffold:
        raise CodeRegenerationError("prompt does not contain the exact fixed scaffold")
    if original_target_source in prompt_text:
        raise CodeRegenerationError("prompt contains the original target source body")
    recomposed = compose_code_regeneration_prompt(
        config, design_document, fixed_scaffold
    )
    if recomposed != prompt_text:
        raise CodeRegenerationError("prompt contains material outside the frozen template")


def build_request_payload(config: Mapping[str, Any], prompt_text: str) -> dict[str, Any]:
    prompt = _mapping(config.get("prompt"), "prompt")
    ollama = _mapping(config.get("ollama"), "ollama")
    options = _mapping(ollama.get("options"), "ollama.options")
    return {
        "model": ollama["model"],
        "system": prompt["system"],
        "prompt": prompt_text,
        "stream": ollama["stream"],
        "options": dict(options),
    }


def build_evaluation_plan(config: Mapping[str, Any]) -> dict[str, Any]:
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    target = _mapping(config.get("target"), "target")
    replacement = _mapping(
        config.get("replacement_and_restoration"),
        "replacement_and_restoration",
    )
    commands = _mapping(evaluation.get("commands"), "evaluation.commands")
    timeouts = _mapping(
        evaluation.get("stage_timeouts_seconds"),
        "evaluation.stage_timeouts_seconds",
    )
    stages = [
        {
            "stage": "code_regeneration",
            "command": [
                str(config["ollama"]["method"]),
                "<OLLAMA_ENDPOINT>",
                "exact bytes from plan/ollama_request.json",
            ],
            "timeout_seconds": int(config["ollama"]["timeout_seconds"]),
            "preserve": ["stdout", "stderr", "exit_code", "timeout", "stage_status"],
        },
        {
            "stage": "normalization",
            "command": ["existing-roundtrip-outer-markdown-fence-only-v1"],
            "timeout_seconds": None,
            "preserve": ["stdout", "stderr", "exit_code", "timeout", "stage_status"],
        },
    ]
    for name in ("configure", "build", "direct_test", "full_test"):
        command = commands.get(name)
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise CodeRegenerationError(f"evaluation command is not a string array: {name}")
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
                "restore exact original_source.bin bytes",
                "verify raw source SHA-256",
                "verify clean yaml-cpp worktree",
            ],
            "timeout_seconds": int(timeouts["restoration"]),
            "preserve": ["stdout", "stderr", "exit_code", "timeout", "stage_status"],
        }
    )
    return {
        "artifact_schema_version": "rag-yaml-cpp-code-evaluation-plan-v1",
        "run_id": config["run_id"],
        "target_id": target["target_id"],
        "baseline": {
            "report_path": evaluation["baseline_report_path"],
            "report_sha256": evaluation["baseline_report_sha256"],
            "docker_image": evaluation["docker_image"],
            "docker_image_id": evaluation["docker_image_id"],
            "source_mount": evaluation["source_mount"],
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
        "source_procedure": {
            "original_raw_sha256": target["raw_source_sha256"],
            "normalized_source_sha256": target["normalized_source_sha256"],
            "frozen_range_sha256": target["source_range_sha256"],
            "frozen_half_open_range": [target["start_byte"], target["end_byte"]],
            "backup_original_bytes_before_replacement": replacement[
                "backup_original_bytes_before_replacement"
            ],
            "replace_only_frozen_span": True,
            "restore_in_finally": replacement["restore_in_finally"],
            "verify_restored_raw_sha256": replacement[
                "verify_restored_raw_sha256"
            ],
            "verify_clean_yaml_cpp_worktree": replacement[
                "verify_clean_yaml_cpp_worktree"
            ],
        },
        "ordered_stages": [
            "code_regeneration",
            "normalization",
            "configure",
            "build",
            "direct_test",
            "full_test",
            "restoration",
        ],
        "stages": stages,
        "failure_policy": {
            "skip_dependent_later_test_stages": True,
            "restoration_always_runs_after_replacement": True,
            "retry": False,
            "repair": False,
            "overwrite": False,
            "manual_patch": False,
        },
    }


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise CodeRegenerationError(f"refusing to overwrite existing evidence: {path}") from exc


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
        run_root / CONTACT_FILE,
        run_root / RESPONSE_FILE,
        run_root / GENERATED_FILE,
        run_root / "evidence" / ORIGINAL_FILE,
    ]
    existing = [path for path in guarded if path.exists()]
    if existing:
        raise CodeRegenerationError(
            "one-shot code regeneration is already attempted, failed, or complete: "
            + ", ".join(path.name for path in existing)
        )


def _verify_baseline(config: Mapping[str, Any], project_root: Path) -> str:
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    path = _verify_file_hash(
        project_root,
        str(evaluation["baseline_report_path"]),
        str(evaluation["baseline_report_sha256"]),
        "yaml-cpp baseline report",
    )
    baseline = _load_json_object(path)
    record = _mapping(baseline.get("baseline"), "baseline")
    environment = _mapping(baseline.get("environment"), "baseline.environment")
    if record.get("baseline_passed") is not True:
        raise CodeRegenerationError("recorded yaml-cpp baseline did not pass")
    if record.get("configure_options") != evaluation["configure_options"]:
        raise CodeRegenerationError("configure options differ from recorded baseline")
    if baseline.get("pilot_repository", {}).get("commit") != config["pilot_repository"]["required_commit"]:
        raise CodeRegenerationError("baseline yaml-cpp commit mismatch")
    if environment.get("image") != evaluation["docker_image"]:
        raise CodeRegenerationError("baseline Docker image mismatch")
    if environment.get("image_id") != evaluation["docker_image_id"]:
        raise CodeRegenerationError("baseline Docker image ID mismatch")
    if record.get("test_names") != evaluation["full_test_names"]:
        raise CodeRegenerationError("full test list differs from recorded baseline")
    return sha256_file(path)


def run_plan_only(
    config: Mapping[str, Any], config_path: Path, project_root: Path, pilot_root: Path
) -> dict[str, Any]:
    run_root = output_root(config, project_root)
    ensure_execution_not_attempted(config, run_root)
    frozen = validate_frozen_inputs(config, project_root, pilot_root)
    baseline_hash = _verify_baseline(config, project_root)
    scaffold = build_fixed_scaffold(config, project_root, frozen.target_source)
    prompt = compose_code_regeneration_prompt(
        config, frozen.design_document, scaffold
    )
    verify_prompt_isolation(
        config, prompt, frozen.design_document, scaffold, frozen.target_source
    )
    request = build_request_payload(config, prompt)
    evaluation_plan = build_evaluation_plan(config)
    plan_root = run_root / "plan"
    scaffold_bytes = scaffold.encode("utf-8")
    prompt_bytes = prompt.encode("utf-8")
    request_bytes = canonical_json_bytes(request)
    evaluation_bytes = canonical_json_bytes(evaluation_plan)
    hashes = {
        SCAFFOLD_FILE: sha256_bytes(scaffold_bytes),
        PROMPT_FILE: sha256_bytes(prompt_bytes),
        REQUEST_FILE: sha256_bytes(request_bytes),
        EVALUATION_PLAN_FILE: sha256_bytes(evaluation_bytes),
    }
    manifest = {
        "artifact_schema_version": "rag-yaml-cpp-one-shot-code-plan-v1",
        "condition_id": config["condition_id"],
        "run_id": config["run_id"],
        "status": "ready_to_execute_code_once",
        "plan_only": True,
        "target": dict(_mapping(config.get("target"), "target")),
        "design_evidence": {
            "run_id": config["design_evidence"]["run_id"],
            "design_document_path": config["design_evidence"]["design_document_path"],
            "design_document_sha256": frozen.design_document_sha256,
            "design_request_sha256": config["design_evidence"]["design_request_sha256"],
            "design_llm_call_count": 1,
            "design_retry_performed": False,
            "design_repair_performed": False,
        },
        "repositories": {
            "project": {
                "branch": frozen.project_state.branch,
                "commit": frozen.project_state.head,
                "required_baseline_ancestor": config["project_repository"][
                    "required_baseline_ancestor"
                ],
                "worktree_clean_before_plan": frozen.project_state.clean,
            },
            "yaml_cpp": {
                "commit": frozen.pilot_state.head,
                "worktree_clean_before_plan": frozen.pilot_state.clean,
            },
        },
        "frozen_inputs": {
            "original_source_sha256": frozen.original_source_sha256,
            "normalized_source_sha256": frozen.normalized_source_sha256,
            "target_source_range_sha256": frozen.target_source_sha256,
            "fixed_scaffold_sha256": hashes[SCAFFOLD_FILE],
            "baseline_report_sha256": baseline_hash,
            "selection_sha256": config["frozen_selection"]["sha256"],
        },
        "plan_artifacts": {
            "fixed_scaffold": {
                "path": f"plan/{SCAFFOLD_FILE}",
                "sha256": hashes[SCAFFOLD_FILE],
            },
            "prompt": {
                "path": f"plan/{PROMPT_FILE}",
                "sha256": hashes[PROMPT_FILE],
            },
            "request": {
                "path": f"plan/{REQUEST_FILE}",
                "sha256": hashes[REQUEST_FILE],
                "endpoint": config["ollama"]["endpoint"],
                "method": config["ollama"]["method"],
                "headers": config["ollama"]["headers"],
            },
            "evaluation_plan": {
                "path": f"plan/{EVALUATION_PLAN_FILE}",
                "sha256": hashes[EVALUATION_PLAN_FILE],
            },
        },
        "prompt_input_policy": config["prompt_input_policy"],
        "normalization": config["normalization"],
        "one_shot_policy": config["one_shot_policy"],
        "config": {
            "path": config_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(config_path),
        },
        "llm_called": False,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "source_replaced": False,
        "build_started": False,
        "tests_started": False,
        "code_regenerated": False,
    }
    _write_exclusive(plan_root / SCAFFOLD_FILE, scaffold_bytes)
    _write_exclusive(plan_root / PROMPT_FILE, prompt_bytes)
    _write_exclusive(plan_root / REQUEST_FILE, request_bytes)
    _write_exclusive(plan_root / EVALUATION_PLAN_FILE, evaluation_bytes)
    _write_exclusive_json(plan_root / PLAN_FILE, manifest)
    return manifest


def _load_and_verify_plan(
    config: Mapping[str, Any], project_root: Path, frozen: FrozenInputs
) -> tuple[dict[str, Any], bytes]:
    plan_root = output_root(config, project_root) / "plan"
    manifest = _load_json_object(plan_root / PLAN_FILE)
    scaffold = build_fixed_scaffold(config, project_root, frozen.target_source)
    prompt = compose_code_regeneration_prompt(
        config, frozen.design_document, scaffold
    )
    verify_prompt_isolation(
        config, prompt, frozen.design_document, scaffold, frozen.target_source
    )
    expected = {
        SCAFFOLD_FILE: scaffold.encode("utf-8"),
        PROMPT_FILE: prompt.encode("utf-8"),
        REQUEST_FILE: canonical_json_bytes(build_request_payload(config, prompt)),
        EVALUATION_PLAN_FILE: canonical_json_bytes(build_evaluation_plan(config)),
    }
    plan_artifacts = _mapping(manifest.get("plan_artifacts"), "plan_artifacts")
    manifest_keys = {
        SCAFFOLD_FILE: "fixed_scaffold",
        PROMPT_FILE: "prompt",
        REQUEST_FILE: "request",
        EVALUATION_PLAN_FILE: "evaluation_plan",
    }
    for filename, expected_bytes in expected.items():
        actual = (plan_root / filename).read_bytes()
        if actual != expected_bytes:
            raise CodeRegenerationError(f"stored plan artifact changed: {filename}")
        record = _mapping(plan_artifacts.get(manifest_keys[filename]), filename)
        if sha256_bytes(actual) != record.get("sha256"):
            raise CodeRegenerationError(f"stored plan artifact SHA-256 mismatch: {filename}")
    if manifest.get("llm_called") is not False:
        raise CodeRegenerationError("plan manifest incorrectly records an LLM call")
    if manifest.get("generation_server_contacted") is not False:
        raise CodeRegenerationError("plan manifest incorrectly records server contact")
    return manifest, expected[REQUEST_FILE]


def normalize_outer_markdown_fence(
    text: str, allowed_languages: set[str]
) -> tuple[str, dict[str, Any]]:
    """Apply the existing round-trip outer-fence-only normalization policy."""
    raw_sha256 = sha256_bytes(text.encode("utf-8"))
    match = re.fullmatch(
        r"\s*```([A-Za-z0-9_+\-]*)[ \t]*\r?\n"
        r"(.*)"
        r"\r?\n```[ \t]*\s*",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        bare_fence = re.search(
            r"(?m)^[ \t]*```[A-Za-z0-9_+\-]*[ \t]*$",
            text,
        )
        if bare_fence is not None:
            raise CodeRegenerationError(
                "code regeneration contains an unmatched or non-outer Markdown fence"
            )
        normalized = text
        applied = False
        language: str | None = None
    else:
        language = match.group(1).lower()
        if language not in allowed_languages:
            raise CodeRegenerationError(
                f"unexpected outer Markdown fence language: {language!r}"
            )
        normalized = match.group(2)
        if not normalized.strip():
            raise CodeRegenerationError("code regeneration is empty after fence normalization")
        if re.search(r"(?m)^[ \t]*```[A-Za-z0-9_+\-]*[ \t]*$", normalized):
            raise CodeRegenerationError("code regeneration contains an additional Markdown fence")
        applied = True
    metadata = {
        "policy": "existing-roundtrip-outer-markdown-fence-only-v1",
        "normalization_applied": applied,
        "normalization_type": "outer_markdown_fence" if applied else "none",
        "fence_language": language,
        "strict_format_pass": not applied,
        "raw_sha256": raw_sha256,
        "normalized_sha256": sha256_bytes(normalized.encode("utf-8")),
        "code_body_modified": False,
        "retry_performed": False,
        "automatic_repair_performed": False,
        "manual_patch_performed": False,
    }
    return normalized, metadata


def validate_generated_class_span(config: Mapping[str, Any], text: str) -> bytes:
    target = _mapping(config.get("target"), "target")
    declaration = str(target["class_declaration"])
    pattern = re.compile(rf"\b{re.escape(declaration)}\b")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise CodeRegenerationError(
            f"expected one generated target class declaration, found {len(matches)}"
        )
    match = matches[0]
    if text[:match.start()].strip():
        raise CodeRegenerationError("generated output has content before the target class")
    open_brace = text.find("{", match.end())
    if open_brace < 0:
        raise CodeRegenerationError("generated target class has no opening brace")
    close_brace = find_matching_brace(text, open_brace)
    suffix = text[close_brace + 1:]
    if suffix.strip():
        if suffix.lstrip().startswith(";"):
            raise CodeRegenerationError("generated frozen class span must exclude the semicolon")
        raise CodeRegenerationError("generated output has content after the target class")
    return text.encode("utf-8")


def raw_offsets_for_normalized_range(raw: bytes, start: int, end: int) -> tuple[int, int]:
    if start < 0 or end <= start:
        raise CodeRegenerationError("invalid normalized replacement range")
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
        if raw[raw_position:raw_position + 2] == b"\r\n":
            raw_position += 2
        elif raw[raw_position:raw_position + 1] == b"\r":
            raise CodeRegenerationError("source contains unsupported lone CR bytes")
        else:
            raw_position += 1
        normalized_position += 1
    if raw_start is None or raw_end is None:
        raise CodeRegenerationError("normalized replacement range exceeds source bytes")
    if normalize_source_bytes(raw[raw_start:raw_end]) != normalize_source_bytes(raw)[start:end]:
        raise CodeRegenerationError("raw and normalized replacement ranges disagree")
    return raw_start, raw_end


class SourceReplacementTransaction:
    """Replace one normalized byte range and restore exact original bytes on exit."""

    def __init__(
        self, source_path: Path, original_bytes: bytes, start: int, end: int,
        replacement_bytes: bytes, expected_original_sha256: str
    ) -> None:
        self.source_path = source_path
        self.original_bytes = original_bytes
        self.start = start
        self.end = end
        self.replacement_bytes = replacement_bytes
        self.expected_original_sha256 = expected_original_sha256
        self.replaced = False
        self.restored = False
        self.restored_sha256: str | None = None
        self.restoration_error: str | None = None

    def __enter__(self) -> "SourceReplacementTransaction":
        current = self.source_path.read_bytes()
        if current != self.original_bytes:
            raise CodeRegenerationError("target source changed before replacement")
        raw_start, raw_end = raw_offsets_for_normalized_range(
            current, self.start, self.end
        )
        replaced = current[:raw_start] + self.replacement_bytes + current[raw_end:]
        self.source_path.write_bytes(replaced)
        self.replaced = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self.replaced:
            try:
                self.source_path.write_bytes(self.original_bytes)
                restored = self.source_path.read_bytes()
                self.restored_sha256 = sha256_bytes(restored)
                if restored != self.original_bytes:
                    raise CodeRegenerationError("restored source bytes differ from original")
                if self.restored_sha256 != self.expected_original_sha256:
                    raise CodeRegenerationError("restored source SHA-256 mismatch")
                self.restored = True
            except Exception as restoration_error:
                self.restoration_error = str(restoration_error)
                raise
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
    run_root: Path, stage: str, stdout: str, stderr: str, record: Mapping[str, Any]
) -> dict[str, Any]:
    stdout_path, stderr_path, record_path = _stage_paths(run_root, stage)
    _write_exclusive(stdout_path, stdout.encode("utf-8"))
    _write_exclusive(stderr_path, stderr.encode("utf-8"))
    value = dict(record)
    value["stdout_path"] = stdout_path.relative_to(run_root).as_posix()
    value["stderr_path"] = stderr_path.relative_to(run_root).as_posix()
    value["stdout_sha256"] = sha256_bytes(stdout.encode("utf-8"))
    value["stderr_sha256"] = sha256_bytes(stderr.encode("utf-8"))
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
    run_root: Path, stage: str, command_template: list[str], command: list[str],
    timeout_seconds: int
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
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr = stderr.rstrip() + f"\nProcess timed out after {timeout_seconds} seconds.\n"
        exit_code = 124
    elapsed = time.perf_counter() - started
    return _record_stage(
        run_root,
        stage,
        stdout,
        stderr,
        {
            "stage": stage,
            "status": "pass" if exit_code == 0 and not timed_out else "fail",
            "command": command_template,
            "started": True,
            "started_at_utc": started_at,
            "completed_at_utc": _utc_now(),
            "elapsed_seconds": elapsed,
            "timeout_seconds": timeout_seconds,
            "timed_out": timed_out,
            "exit_code": exit_code,
        },
    )


def _verify_docker_image(config: Mapping[str, Any]) -> None:
    evaluation = _mapping(config.get("evaluation"), "evaluation")
    result = subprocess.run(
        ["docker", "image", "inspect", "--format={{.Id}}", str(evaluation["docker_image"])],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise CodeRegenerationError(f"baseline Docker image unavailable: {result.stderr.strip()}")
    if result.stdout.strip() != evaluation["docker_image_id"]:
        raise CodeRegenerationError("baseline Docker image ID mismatch")


def _record_missing_stages(
    run_root: Path, records: dict[str, Any], reason: str
) -> None:
    for stage in (
        "code_regeneration",
        "normalization",
        "configure",
        "build",
        "direct_test",
        "full_test",
        "restoration",
    ):
        if stage not in records:
            records[stage] = _record_skipped_stage(run_root, stage, reason)


def run_execute_once(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> dict[str, Any]:
    run_root = output_root(config, project_root)
    ensure_execution_not_attempted(config, run_root)
    frozen = validate_frozen_inputs(config, project_root, pilot_root)
    _verify_baseline(config, project_root)
    _plan, request_bytes = _load_and_verify_plan(config, project_root, frozen)
    ensure_execution_not_attempted(config, run_root)
    _verify_docker_image(config)
    policy = _mapping(config.get("one_shot_policy"), "one_shot_policy")
    ollama = _mapping(config.get("ollama"), "ollama")
    request_hash = sha256_bytes(request_bytes)
    _write_exclusive_json(
        run_root / str(policy["attempt_marker"]),
        {
            "artifact_schema_version": "rag-yaml-cpp-code-attempt-v1",
            "run_id": config["run_id"],
            "target_id": config["target"]["target_id"],
            "status": "one_shot_reserved_before_request",
            "request_sha256": request_hash,
            "code_regeneration_request_limit": 1,
            "retry_allowed": False,
            "repair_allowed": False,
            "overwrite_allowed": False,
            "manual_patch_allowed": False,
            "reserved_at_utc": _utc_now(),
        },
    )
    records: dict[str, Any] = {}
    llm_called = False
    source_replaced = False
    source_restored = False
    transaction: SourceReplacementTransaction | None = None
    try:
        _write_exclusive_json(
            run_root / CONTACT_FILE,
            {
                "artifact_schema_version": "rag-yaml-cpp-code-contact-v1",
                "run_id": config["run_id"],
                "request_sha256": request_hash,
                "llm_called": True,
                "llm_call_count": 1,
                "generation_server_contact_attempted": True,
                "retry_performed": False,
                "contact_started_at_utc": _utc_now(),
            },
        )
        llm_called = True
        code_started = time.perf_counter()
        code_started_at = _utc_now()
        try:
            response_bytes = contact_generation_server(
                endpoint=str(ollama["endpoint"]),
                headers=_mapping(ollama.get("headers"), "ollama.headers"),
                request_bytes=request_bytes,
                timeout=int(ollama["timeout_seconds"]),
            )
        except Exception as exc:
            records["code_regeneration"] = _record_stage(
                run_root,
                "code_regeneration",
                "",
                str(exc) + "\n",
                {
                    "stage": "code_regeneration",
                    "status": "fail",
                    "started": True,
                    "started_at_utc": code_started_at,
                    "completed_at_utc": _utc_now(),
                    "elapsed_seconds": time.perf_counter() - code_started,
                    "timeout_seconds": int(ollama["timeout_seconds"]),
                    "timed_out": isinstance(exc, TimeoutError),
                    "exit_code": None,
                    "llm_call_count": 1,
                    "retry_performed": False,
                },
            )
            raise
        _write_exclusive(run_root / RESPONSE_FILE, response_bytes)
        records["code_regeneration"] = _record_stage(
            run_root,
            "code_regeneration",
            response_bytes.decode("utf-8", errors="replace"),
            "",
            {
                "stage": "code_regeneration",
                "status": "pass",
                "started": True,
                "started_at_utc": code_started_at,
                "completed_at_utc": _utc_now(),
                "elapsed_seconds": time.perf_counter() - code_started,
                "timeout_seconds": int(ollama["timeout_seconds"]),
                "timed_out": False,
                "exit_code": 0,
                "llm_call_count": 1,
                "retry_performed": False,
                "response_sha256": sha256_bytes(response_bytes),
            },
        )
        response = json.loads(response_bytes.decode("utf-8"))
        if not isinstance(response, dict):
            raise CodeRegenerationError("Ollama response root is not an object")
        raw_text = response.get("response")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise CodeRegenerationError("code regeneration returned an empty response")
        normalization_started = time.perf_counter()
        normalization_started_at = _utc_now()
        try:
            allowed = set(config["normalization"]["allowed_outer_fence_languages"])
            normalized, normalization = normalize_outer_markdown_fence(raw_text, allowed)
            replacement_bytes = validate_generated_class_span(config, normalized)
            _write_exclusive(run_root / GENERATED_FILE, replacement_bytes)
            records["normalization"] = _record_stage(
                run_root,
                "normalization",
                normalized,
                "",
                {
                    "stage": "normalization",
                    "status": "pass",
                    "started": True,
                    "started_at_utc": normalization_started_at,
                    "completed_at_utc": _utc_now(),
                    "elapsed_seconds": time.perf_counter() - normalization_started,
                    "timeout_seconds": None,
                    "timed_out": False,
                    "exit_code": 0,
                    "normalization": normalization,
                },
            )
        except Exception as exc:
            records["normalization"] = _record_stage(
                run_root,
                "normalization",
                "",
                str(exc) + "\n",
                {
                    "stage": "normalization",
                    "status": "fail",
                    "started": True,
                    "started_at_utc": normalization_started_at,
                    "completed_at_utc": _utc_now(),
                    "elapsed_seconds": time.perf_counter() - normalization_started,
                    "timeout_seconds": None,
                    "timed_out": False,
                    "exit_code": 1,
                    "retry_performed": False,
                    "repair_performed": False,
                    "manual_patch_performed": False,
                },
            )
            raise
        _write_exclusive(run_root / "evidence" / ORIGINAL_FILE, frozen.original_source_bytes)
        target = _mapping(config.get("target"), "target")
        source_path = pilot_root / str(target["path"])
        transaction = SourceReplacementTransaction(
            source_path=source_path,
            original_bytes=frozen.original_source_bytes,
            start=int(target["start_byte"]),
            end=int(target["end_byte"]),
            replacement_bytes=replacement_bytes,
            expected_original_sha256=frozen.original_source_sha256,
        )
        evaluation = _mapping(config.get("evaluation"), "evaluation")
        command_templates = _mapping(evaluation.get("commands"), "evaluation.commands")
        timeouts = _mapping(
            evaluation.get("stage_timeouts_seconds"),
            "evaluation.stage_timeouts_seconds",
        )
        workspace = run_root / "evaluation_workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        try:
            with transaction:
                source_replaced = True
                previous_pass = True
                for stage in ("configure", "build", "direct_test", "full_test"):
                    if not previous_pass:
                        records[stage] = _record_skipped_stage(
                            run_root, stage, "previous evaluation stage failed"
                        )
                        continue
                    template = list(command_templates[stage])
                    command = _render_command(template, pilot_root, workspace)
                    records[stage] = _run_process_stage(
                        run_root,
                        stage,
                        template,
                        command,
                        int(timeouts[stage]),
                    )
                    previous_pass = records[stage]["status"] == "pass"
        finally:
            source_restored = transaction.restored
            restoration_error = transaction.restoration_error or ""
            clean_status = _git(
                pilot_root,
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                check=False,
            ).stdout
            restoration_pass = (
                transaction.restored
                and transaction.restored_sha256 == frozen.original_source_sha256
                and not clean_status
            )
            records["restoration"] = _record_stage(
                run_root,
                "restoration",
                (
                    f"restored_sha256={transaction.restored_sha256}\n"
                    f"yaml_cpp_worktree_clean={not bool(clean_status)}\n"
                ),
                restoration_error + ("\n" if restoration_error else ""),
                {
                    "stage": "restoration",
                    "status": "pass" if restoration_pass else "fail",
                    "started": transaction.replaced,
                    "exit_code": 0 if restoration_pass else 1,
                    "timed_out": False,
                    "timeout_seconds": int(timeouts["restoration"]),
                    "original_source_sha256": frozen.original_source_sha256,
                    "restored_source_sha256": transaction.restored_sha256,
                    "yaml_cpp_worktree_clean": not bool(clean_status),
                },
            )
        overall_pass = all(
            records[name]["status"] == "pass"
            for name in (
                "code_regeneration",
                "normalization",
                "configure",
                "build",
                "direct_test",
                "full_test",
                "restoration",
            )
        )
        result = {
            "artifact_schema_version": "rag-yaml-cpp-code-result-v1",
            "run_id": config["run_id"],
            "target_id": target["target_id"],
            "status": "pass" if overall_pass else "evaluation_failed",
            "overall_pass": overall_pass,
            "request_sha256": request_hash,
            "generated_class_span_sha256": sha256_bytes(replacement_bytes),
            "llm_called": True,
            "llm_call_count": 1,
            "generation_server_contacted": True,
            "retry_performed": False,
            "repair_performed": False,
            "manual_patch_performed": False,
            "source_replaced": source_replaced,
            "source_restored": source_restored,
            "restored_source_sha256": transaction.restored_sha256,
            "stages": records,
            "completed_at_utc": _utc_now(),
        }
        _write_exclusive_json(run_root / str(policy["result_marker"]), result)
        return result
    except Exception as exc:
        _record_missing_stages(run_root, records, "pipeline stopped after failure")
        failure = {
            "artifact_schema_version": "rag-yaml-cpp-code-failure-v1",
            "run_id": config["run_id"],
            "target_id": config["target"]["target_id"],
            "status": "failed_without_retry_or_repair",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "request_sha256": request_hash,
            "llm_called": llm_called,
            "llm_call_count": 1 if llm_called else 0,
            "generation_server_contacted": llm_called,
            "retry_performed": False,
            "repair_performed": False,
            "overwrite_performed": False,
            "manual_patch_performed": False,
            "source_replaced": source_replaced,
            "source_restored": source_restored,
            "stages": records,
            "failed_at_utc": _utc_now(),
        }
        _write_exclusive_json(run_root / str(policy["failure_marker"]), failure)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or perform the frozen yaml-cpp YAML::Node code-regeneration "
            "and evaluation request once."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--yaml-cpp-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_root = args.project_root.resolve()
    pilot_root = args.yaml_cpp_root.resolve()
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path
    config = load_config(config_path)
    if args.plan_only:
        result = run_plan_only(config, config_path, project_root, pilot_root)
    else:
        result = run_execute_once(config, project_root, pilot_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
