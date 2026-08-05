"""Plan or execute the yaml-cpp YAML::Node external-pilot design call once."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
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


DEFAULT_CONFIG = "configs/rag/pilot/yaml_cpp_yaml_node_design_generation_v1.json"
PROMPT_FILE = "design_prompt.txt"
REQUEST_FILE = "ollama_request.json"
PLAN_FILE = "plan_manifest.json"
RESPONSE_FILE = "design_generation_response.json"
DESIGN_FILE = "design_document.md"
FAILURE_FILE = "design_generation_failure.json"
CONTACT_FILE = "generation_server_contact.json"


class DesignGenerationError(RuntimeError):
    """Raised when frozen inputs or one-shot invariants do not hold."""


@dataclass(frozen=True)
class RepositoryState:
    head: str
    branch: str | None
    clean: bool


@dataclass(frozen=True)
class FrozenInputs:
    target_source: str
    retrieved_context: str
    source_file_sha256: str
    source_range_sha256: str
    context_sha256: str
    selection_sha256: str
    retrieval_manifest_sha256: str
    project_state: RepositoryState
    pilot_state: RepositoryState


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DesignGenerationError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DesignGenerationError(f"JSON root must be an object: {path}")
    return value


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DesignGenerationError(f"{field} must be an object")
    return value


def load_config(path: Path) -> dict[str, Any]:
    config = _load_json_object(path)
    if config.get("artifact_schema_version") != "rag-yaml-cpp-design-generation-config-v1":
        raise DesignGenerationError("unsupported design-generation config schema")
    posix_relative_path(str(config.get("output_path", "")))
    target = _require_mapping(config.get("target"), "target")
    artifacts = _require_mapping(config.get("frozen_artifacts"), "frozen_artifacts")
    for field in ("path",):
        posix_relative_path(str(target.get(field, "")))
    for field in ("selection_path", "retrieval_manifest_path", "context_path"):
        posix_relative_path(str(artifacts.get(field, "")))
    policy = _require_mapping(config.get("one_shot_policy"), "one_shot_policy")
    expected_policy = {
        "design_generation_requests": 1,
        "retry_allowed": False,
        "repair_allowed": False,
        "overwrite_allowed": False,
        "second_call_allowed": False,
    }
    for field, expected in expected_policy.items():
        if policy.get(field) != expected:
            raise DesignGenerationError(f"one-shot policy mismatch for {field}")
    downstream = _require_mapping(
        config.get("downstream_code_regeneration_policy"),
        "downstream_code_regeneration_policy",
    )
    forbidden = set(downstream.get("forbidden_direct_inputs", []))
    required_forbidden = {
        "frozen_target_source",
        "frozen_retrieved_repository_context",
        "design_generation_prompt",
        "design_generation_request",
    }
    if downstream.get("implemented_by_this_runner") is not False:
        raise DesignGenerationError("this design-only runner must not implement regeneration")
    if not required_forbidden.issubset(forbidden):
        raise DesignGenerationError("downstream raw-input exclusion policy is incomplete")
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
        raise DesignGenerationError(
            f"git {' '.join(arguments)} failed for {repository}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def repository_state(repository: Path, *, required_branch: str | None = None) -> RepositoryState:
    head = _git(repository, "rev-parse", "HEAD").stdout.strip().lower()
    branch = _git(repository, "branch", "--show-current").stdout.strip() or None
    status = _git(
        repository,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    ).stdout
    if status:
        raise DesignGenerationError(f"worktree is not clean: {repository}\n{status.rstrip()}")
    if required_branch is not None and branch != required_branch:
        raise DesignGenerationError(
            f"branch mismatch for {repository}: expected {required_branch}, got {branch}"
        )
    return RepositoryState(head=head, branch=branch, clean=True)


def verify_repository_states(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> tuple[RepositoryState, RepositoryState]:
    project_config = _require_mapping(
        config.get("project_repository"), "project_repository"
    )
    pilot_config = _require_mapping(config.get("pilot_repository"), "pilot_repository")
    project = repository_state(
        project_root,
        required_branch=str(project_config["required_branch"]),
    )
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
        raise DesignGenerationError(
            f"required project baseline {baseline} is not an ancestor of {project.head}"
        )
    pilot = repository_state(pilot_root)
    expected_pilot = str(pilot_config["required_commit"]).lower()
    if pilot.head != expected_pilot:
        raise DesignGenerationError(
            f"yaml-cpp commit mismatch: expected {expected_pilot}, got {pilot.head}"
        )
    return project, pilot


def normalize_source_bytes(raw: bytes) -> bytes:
    normalized = raw.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise DesignGenerationError("source contains unsupported lone CR bytes")
    return normalized


def verify_source(config: Mapping[str, Any], pilot_root: Path) -> tuple[str, str, str]:
    target = _require_mapping(config.get("target"), "target")
    source_path = pilot_root / str(target["path"])
    try:
        normalized = normalize_source_bytes(source_path.read_bytes())
    except OSError as exc:
        raise DesignGenerationError(f"cannot read target source {source_path}: {exc}") from exc
    actual_file_hash = sha256_bytes(normalized)
    expected_file_hash = str(target["normalized_source_sha256"]).lower()
    if actual_file_hash != expected_file_hash:
        raise DesignGenerationError(
            f"target source hash mismatch: expected {expected_file_hash}, got {actual_file_hash}"
        )
    start = int(target["start_byte"])
    end = int(target["end_byte"])
    if start < 0 or end <= start or end > len(normalized):
        raise DesignGenerationError(f"invalid frozen source range [{start}, {end})")
    source_range = normalized[start:end]
    actual_range_hash = sha256_bytes(source_range)
    expected_range_hash = str(target["source_range_sha256"]).lower()
    if actual_range_hash != expected_range_hash:
        raise DesignGenerationError(
            f"target source range hash mismatch: expected {expected_range_hash}, "
            f"got {actual_range_hash}"
        )
    actual_start_line = normalized[:start].count(b"\n") + 1
    actual_end_line = normalized[:end].count(b"\n") + (0 if normalized[end - 1:end] == b"\n" else 1)
    if actual_start_line != int(target["start_line"]):
        raise DesignGenerationError("target source start line mismatch")
    if actual_end_line != int(target["end_line"]):
        raise DesignGenerationError("target source end line mismatch")
    try:
        decoded = source_range.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DesignGenerationError("target source range is not UTF-8") from exc
    return decoded, actual_file_hash, actual_range_hash


def _verify_selection(config: Mapping[str, Any], project_root: Path) -> str:
    artifacts = _require_mapping(config.get("frozen_artifacts"), "frozen_artifacts")
    target = _require_mapping(config.get("target"), "target")
    pilot = _require_mapping(config.get("pilot_repository"), "pilot_repository")
    path = project_root / str(artifacts["selection_path"])
    actual_hash = sha256_file(path)
    expected_hash = str(artifacts["selection_sha256"]).lower()
    if actual_hash != expected_hash:
        raise DesignGenerationError(
            f"frozen selection hash mismatch: expected {expected_hash}, got {actual_hash}"
        )
    selection = _load_json_object(path)
    if selection.get("status") != "selected" or selection.get("pilot_ids_frozen") is not True:
        raise DesignGenerationError("selection artifact is not frozen and selected")
    if selection.get("repository_id") != pilot["repository_id"]:
        raise DesignGenerationError("selection repository mismatch")
    if str(selection.get("repository_commit", "")).lower() != str(pilot["required_commit"]).lower():
        raise DesignGenerationError("selection repository commit mismatch")
    candidates = selection.get("selected_candidates")
    if not isinstance(candidates, list):
        raise DesignGenerationError("selection artifact has no selected_candidates array")
    matches = [item for item in candidates if isinstance(item, Mapping) and item.get("pilot_target_id") == target["target_id"]]
    if len(matches) != 1:
        raise DesignGenerationError("frozen target does not occur exactly once in selection")
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
            raise DesignGenerationError(f"frozen selection field mismatch: {field}")
    return actual_hash


def _verify_retrieval_and_context(
    config: Mapping[str, Any], project_root: Path
) -> tuple[str, str, str]:
    artifacts = _require_mapping(config.get("frozen_artifacts"), "frozen_artifacts")
    target = _require_mapping(config.get("target"), "target")
    pilot = _require_mapping(config.get("pilot_repository"), "pilot_repository")
    manifest_path = project_root / str(artifacts["retrieval_manifest_path"])
    actual_manifest_hash = sha256_file(manifest_path)
    expected_manifest_hash = str(artifacts["retrieval_manifest_sha256"]).lower()
    if actual_manifest_hash != expected_manifest_hash:
        raise DesignGenerationError(
            "frozen retrieval manifest hash mismatch: "
            f"expected {expected_manifest_hash}, got {actual_manifest_hash}"
        )
    manifest = _load_json_object(manifest_path)
    if manifest.get("status") != "pass" or manifest.get("deterministic") is not True:
        raise DesignGenerationError("retrieval manifest is not deterministic/pass")
    expected_identity = {
        "target_id": target["target_id"],
        "repository_id": pilot["repository_id"],
        "repository_commit": pilot["required_commit"],
    }
    for field, expected in expected_identity.items():
        if manifest.get(field) != expected:
            raise DesignGenerationError(f"retrieval manifest field mismatch: {field}")
    leakage = _require_mapping(manifest.get("leakage_validation"), "leakage_validation")
    if leakage.get("status") != "pass" or leakage.get("verbatim_target_source_in_context") is not False:
        raise DesignGenerationError("retrieval leakage validation is not pass")
    llm_calls = _require_mapping(manifest.get("llm_calls"), "llm_calls")
    if llm_calls.get("design_generation") != 0 or llm_calls.get("code_regeneration") != 0:
        raise DesignGenerationError("retrieval preparation already records an LLM call")
    source = _require_mapping(manifest.get("target_source"), "target_source")
    expected_source = {
        "path": target["path"],
        "start_byte": target["start_byte"],
        "end_byte": target["end_byte"],
        "source_sha256": target["normalized_source_sha256"],
        "content_sha256": target["source_range_sha256"],
    }
    for field, expected in expected_source.items():
        if source.get(field) != expected:
            raise DesignGenerationError(f"retrieval target source mismatch: {field}")
    context_path = project_root / str(artifacts["context_path"])
    context_bytes = context_path.read_bytes()
    actual_context_hash = sha256_bytes(context_bytes)
    expected_context_hash = str(artifacts["context_sha256"]).lower()
    declared_context_hash = str(manifest.get("context_sha256", "")).lower()
    artifact_hashes = _require_mapping(manifest.get("artifact_hashes"), "artifact_hashes")
    if actual_context_hash != expected_context_hash:
        raise DesignGenerationError(
            f"frozen context hash mismatch: expected {expected_context_hash}, got {actual_context_hash}"
        )
    if declared_context_hash != expected_context_hash or artifact_hashes.get("context.txt") != expected_context_hash:
        raise DesignGenerationError("retrieval manifest context hash mismatch")
    try:
        context = context_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DesignGenerationError("frozen context is not UTF-8") from exc
    return context, actual_context_hash, actual_manifest_hash


def validate_frozen_inputs(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> FrozenInputs:
    project_state, pilot_state = verify_repository_states(config, project_root, pilot_root)
    selection_hash = _verify_selection(config, project_root)
    source, source_file_hash, source_range_hash = verify_source(config, pilot_root)
    context, context_hash, retrieval_hash = _verify_retrieval_and_context(config, project_root)
    return FrozenInputs(
        target_source=source,
        retrieved_context=context,
        source_file_sha256=source_file_hash,
        source_range_sha256=source_range_hash,
        context_sha256=context_hash,
        selection_sha256=selection_hash,
        retrieval_manifest_sha256=retrieval_hash,
        project_state=project_state,
        pilot_state=pilot_state,
    )


def compose_design_prompt(
    config: Mapping[str, Any], target_source: str, retrieved_context: str
) -> str:
    target = _require_mapping(config.get("target"), "target")
    prompt = _require_mapping(config.get("prompt"), "prompt")
    source_heading = str(prompt["target_source_heading"])
    context_heading = str(prompt["retrieved_context_heading"])
    if not source_heading or not context_heading or source_heading == context_heading:
        raise DesignGenerationError("prompt section headings must be distinct")
    return (
        "# Target\n"
        f"- target_id: {target['target_id']}\n"
        f"- target_symbol: {target['target_symbol']}\n"
        f"- granularity: {target['granularity']}\n\n"
        "# Design-document task\n"
        f"{prompt['task_instruction']}\n\n"
        f"# {source_heading}\n"
        f"{target_source.rstrip()}\n"
        f"# END {source_heading}\n\n"
        f"# {context_heading}\n"
        f"{retrieved_context.rstrip()}\n"
        f"# END {context_heading}\n"
    )


def build_request_payload(config: Mapping[str, Any], prompt_text: str) -> dict[str, Any]:
    prompt = _require_mapping(config.get("prompt"), "prompt")
    ollama = _require_mapping(config.get("ollama"), "ollama")
    options = _require_mapping(ollama.get("options"), "ollama.options")
    return {
        "model": ollama["model"],
        "system": prompt["system"],
        "prompt": prompt_text,
        "stream": ollama["stream"],
        "options": dict(options),
    }


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise DesignGenerationError(f"refusing to overwrite existing evidence: {path}") from exc


def _write_exclusive_json(path: Path, value: Any) -> str:
    data = canonical_json_bytes(value)
    _write_exclusive(path, data)
    return sha256_bytes(data)


def output_root(config: Mapping[str, Any], project_root: Path) -> Path:
    return project_root / str(config["output_path"])


def ensure_execution_not_attempted(config: Mapping[str, Any], run_root: Path) -> None:
    policy = _require_mapping(config.get("one_shot_policy"), "one_shot_policy")
    guarded = [
        run_root / str(policy["attempt_marker"]),
        run_root / str(policy["result_marker"]),
        run_root / RESPONSE_FILE,
        run_root / DESIGN_FILE,
        run_root / FAILURE_FILE,
        run_root / CONTACT_FILE,
    ]
    existing = [path for path in guarded if path.exists()]
    if existing:
        names = ", ".join(path.name for path in existing)
        raise DesignGenerationError(
            f"one-shot design generation is already attempted or complete: {names}"
        )


def run_plan_only(
    config: Mapping[str, Any], config_path: Path, project_root: Path, pilot_root: Path
) -> dict[str, Any]:
    frozen = validate_frozen_inputs(config, project_root, pilot_root)
    run_root = output_root(config, project_root)
    ensure_execution_not_attempted(config, run_root)
    plan_root = run_root / "plan"
    prompt_text = compose_design_prompt(
        config, frozen.target_source, frozen.retrieved_context
    )
    prompt_bytes = prompt_text.encode("utf-8")
    payload = build_request_payload(config, prompt_text)
    request_bytes = canonical_json_bytes(payload)
    prompt_hash = sha256_bytes(prompt_bytes)
    request_hash = sha256_bytes(request_bytes)
    target = _require_mapping(config.get("target"), "target")
    artifacts = _require_mapping(config.get("frozen_artifacts"), "frozen_artifacts")
    ollama = _require_mapping(config.get("ollama"), "ollama")
    policy = _require_mapping(config.get("one_shot_policy"), "one_shot_policy")
    manifest = {
        "artifact_schema_version": "rag-yaml-cpp-one-shot-design-plan-v1",
        "condition_id": config["condition_id"],
        "run_id": config["run_id"],
        "status": "ready_to_execute_once",
        "plan_only": True,
        "target": dict(target),
        "repositories": {
            "project": {
                "branch": frozen.project_state.branch,
                "commit": frozen.project_state.head,
                "required_baseline_ancestor": config["project_repository"]["required_baseline_ancestor"],
                "worktree_clean_before_plan": frozen.project_state.clean,
            },
            "yaml_cpp": {
                "commit": frozen.pilot_state.head,
                "worktree_clean_before_plan": frozen.pilot_state.clean,
            },
        },
        "frozen_inputs": {
            "selection_path": artifacts["selection_path"],
            "selection_sha256": frozen.selection_sha256,
            "retrieval_manifest_path": artifacts["retrieval_manifest_path"],
            "retrieval_manifest_sha256": frozen.retrieval_manifest_sha256,
            "source_sha256": frozen.source_file_sha256,
            "source_range_sha256": frozen.source_range_sha256,
            "context_path": artifacts["context_path"],
            "context_sha256": frozen.context_sha256,
        },
        "request": {
            "endpoint": ollama["endpoint"],
            "method": ollama["method"],
            "headers": ollama["headers"],
            "prompt_path": f"plan/{PROMPT_FILE}",
            "prompt_sha256": prompt_hash,
            "payload_path": f"plan/{REQUEST_FILE}",
            "payload_sha256": request_hash,
        },
        "one_shot_policy": dict(policy),
        "downstream_code_regeneration_policy": config["downstream_code_regeneration_policy"],
        "config": {
            "path": config_path.relative_to(project_root).as_posix(),
            "sha256": sha256_file(config_path),
        },
        "llm_called": False,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "design_document_generated": False,
        "code_regeneration_performed": False,
    }
    _write_exclusive(plan_root / PROMPT_FILE, prompt_bytes)
    _write_exclusive(plan_root / REQUEST_FILE, request_bytes)
    _write_exclusive_json(plan_root / PLAN_FILE, manifest)
    return manifest


def _load_and_verify_plan(
    config: Mapping[str, Any], project_root: Path, frozen: FrozenInputs
) -> tuple[dict[str, Any], bytes]:
    run_root = output_root(config, project_root)
    plan_root = run_root / "plan"
    manifest = _load_json_object(plan_root / PLAN_FILE)
    prompt_bytes = (plan_root / PROMPT_FILE).read_bytes()
    request_bytes = (plan_root / REQUEST_FILE).read_bytes()
    expected_prompt = compose_design_prompt(
        config, frozen.target_source, frozen.retrieved_context
    ).encode("utf-8")
    expected_request = canonical_json_bytes(
        build_request_payload(config, expected_prompt.decode("utf-8"))
    )
    if prompt_bytes != expected_prompt:
        raise DesignGenerationError("stored plan prompt is not the exact frozen prompt")
    if request_bytes != expected_request:
        raise DesignGenerationError("stored Ollama request is not the exact frozen request")
    request_record = _require_mapping(manifest.get("request"), "plan.request")
    if sha256_bytes(prompt_bytes) != request_record.get("prompt_sha256"):
        raise DesignGenerationError("stored prompt SHA-256 mismatch")
    if sha256_bytes(request_bytes) != request_record.get("payload_sha256"):
        raise DesignGenerationError("stored request SHA-256 mismatch")
    if manifest.get("llm_called") is not False or manifest.get("generation_server_contacted") is not False:
        raise DesignGenerationError("plan manifest incorrectly records generation contact")
    return manifest, request_bytes


def contact_generation_server(
    *, endpoint: str, headers: Mapping[str, str], request_bytes: bytes, timeout: int
) -> bytes:
    request = urllib.request.Request(
        endpoint,
        data=request_bytes,
        headers=dict(headers),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_execute_once(
    config: Mapping[str, Any], project_root: Path, pilot_root: Path
) -> dict[str, Any]:
    frozen = validate_frozen_inputs(config, project_root, pilot_root)
    run_root = output_root(config, project_root)
    _manifest, request_bytes = _load_and_verify_plan(config, project_root, frozen)
    ensure_execution_not_attempted(config, run_root)
    policy = _require_mapping(config.get("one_shot_policy"), "one_shot_policy")
    ollama = _require_mapping(config.get("ollama"), "ollama")
    attempt_path = run_root / str(policy["attempt_marker"])
    result_path = run_root / str(policy["result_marker"])
    request_hash = sha256_bytes(request_bytes)
    _write_exclusive_json(
        attempt_path,
        {
            "artifact_schema_version": "rag-yaml-cpp-design-attempt-v1",
            "run_id": config["run_id"],
            "target_id": config["target"]["target_id"],
            "status": "one_shot_reserved_before_request",
            "request_sha256": request_hash,
            "design_generation_request_limit": 1,
            "retry_allowed": False,
            "repair_allowed": False,
            "overwrite_allowed": False,
            "reserved_at_utc": _utc_now(),
        },
    )
    contacted = False
    try:
        _write_exclusive_json(
            run_root / CONTACT_FILE,
            {
                "artifact_schema_version": "rag-yaml-cpp-generation-contact-v1",
                "run_id": config["run_id"],
                "request_sha256": request_hash,
                "llm_called": True,
                "llm_call_count": 1,
                "generation_server_contact_attempted": True,
                "retry_performed": False,
                "contact_started_at_utc": _utc_now(),
            },
        )
        contacted = True
        response_bytes = contact_generation_server(
            endpoint=str(ollama["endpoint"]),
            headers=_require_mapping(ollama.get("headers"), "ollama.headers"),
            request_bytes=request_bytes,
            timeout=int(ollama["timeout_seconds"]),
        )
        _write_exclusive(run_root / RESPONSE_FILE, response_bytes)
        response = json.loads(response_bytes.decode("utf-8"))
        if not isinstance(response, dict):
            raise DesignGenerationError("Ollama response root is not an object")
        design = response.get("response")
        if not isinstance(design, str) or not design.strip():
            raise DesignGenerationError("design generation returned an empty response")
        design_bytes = design.encode("utf-8")
        _write_exclusive(run_root / DESIGN_FILE, design_bytes)
        result = {
            "artifact_schema_version": "rag-yaml-cpp-design-result-v1",
            "run_id": config["run_id"],
            "target_id": config["target"]["target_id"],
            "status": "completed",
            "request_sha256": request_hash,
            "response_sha256": sha256_bytes(response_bytes),
            "design_document_sha256": sha256_bytes(design_bytes),
            "llm_called": True,
            "llm_call_count": 1,
            "generation_server_contacted": True,
            "retry_performed": False,
            "repair_performed": False,
            "code_regeneration_performed": False,
            "completed_at_utc": _utc_now(),
        }
        _write_exclusive_json(result_path, result)
        return result
    except Exception as exc:
        failure = {
            "artifact_schema_version": "rag-yaml-cpp-design-failure-v1",
            "run_id": config["run_id"],
            "target_id": config["target"]["target_id"],
            "status": "failed_without_retry",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "request_sha256": request_hash,
            "llm_called": contacted,
            "llm_call_count": 1 if contacted else 0,
            "generation_server_contact_attempted": contacted,
            "retry_performed": False,
            "repair_performed": False,
            "overwrite_performed": False,
            "failed_at_utc": _utc_now(),
        }
        try:
            _write_exclusive_json(run_root / FAILURE_FILE, failure)
        except Exception as evidence_error:
            raise DesignGenerationError(
                f"execution failed ({exc}); failure evidence write also failed ({evidence_error})"
            ) from exc
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or perform the frozen yaml-cpp YAML::Node design request once."
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
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
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
