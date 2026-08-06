from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from scripts.rag.formal_run_policy import (
    FormalRunPolicyError,
    RequestBundle,
    ValidatedFormalTarget,
    build_code_request,
    build_design_request,
    read_json,
    read_text,
    resolve_project_path,
    sha256_bytes,
    sha256_file,
)


class FormalRunExecutionError(RuntimeError):
    """Raised when one formal RAG target cannot safely continue."""


@dataclass(frozen=True)
class PreparedInputs:
    design_input: str
    fixed_scaffold: str
    repository: Path
    source_files: tuple[str, ...]
    original_hashes: dict[str, str]
    nested_repository: Path | None = None


@dataclass(frozen=True)
class RuntimeHooks:
    git_output: Callable[..., str]
    docker_image_id: Callable[[str], str]
    docker_run: Callable[..., dict[str, Any]]
    call_ollama: Callable[..., tuple[dict[str, Any], float]]
    run_command: Callable[..., dict[str, Any]]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    path.write_text(normalized, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _run_process(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def real_git_output(repository: Path, *args: str) -> str:
    result = _run_process(["git", "-C", str(repository), *args])
    if result.returncode != 0:
        raise FormalRunExecutionError(
            "git command failed: "
            + " ".join(args)
            + "\n"
            + result.stdout
            + "\n"
            + result.stderr
        )
    return result.stdout.strip()


def real_docker_image_id(image: str) -> str:
    result = _run_process(
        ["docker", "image", "inspect", "--format={{.Id}}", image]
    )
    if result.returncode != 0:
        raise FormalRunExecutionError(
            f"Docker image is unavailable: {image}\n{result.stderr}"
        )
    return result.stdout.strip()


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def real_docker_run(
    *,
    project_root: Path,
    repository_path: str,
    image: str,
    shell_command: str,
    log_root: Path,
    stage: str,
    timeout_seconds: int | None,
) -> dict[str, Any]:
    container_name = f"cpp-rag-formal-{stage}-{uuid.uuid4().hex[:12]}"
    workdir = "/workspace/" + repository_path.replace("\\", "/")
    command = [
        "docker",
        "run",
        "--name",
        container_name,
        "--rm",
        "--mount",
        f"type=bind,source={project_root},target=/workspace",
        "-w",
        workdir,
        image,
        "bash",
        "-lc",
        shell_command,
    ]
    recorded = command.copy()
    recorded[recorded.index("--name") + 1] = "<CONTAINER_NAME>"
    for index, item in enumerate(recorded):
        if item.startswith("type=bind,source=") and item.endswith(",target=/workspace"):
            recorded[index] = "type=bind,source=<PROJECT_ROOT>,target=/workspace"

    started_at = utc_now()
    started = time.perf_counter()
    timed_out = False
    try:
        result = _run_process(command, timeout=timeout_seconds)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = _timeout_text(error.stdout)
        stderr = _timeout_text(error.stderr)
        exit_code = 124
        cleanup = _run_process(["docker", "rm", "-f", container_name], timeout=30)
        note = f"Process timed out after {timeout_seconds} seconds."
        cleanup_text = (cleanup.stdout + "\n" + cleanup.stderr).strip()
        if cleanup.returncode != 0 and "No such container" not in cleanup_text:
            note += " Docker cleanup failed: " + cleanup_text
        stderr = (stderr.rstrip() + "\n" + note + "\n").lstrip("\n")

    write_text(log_root / f"{stage}.stdout.txt", stdout)
    write_text(log_root / f"{stage}.stderr.txt", stderr)
    return {
        "stage": stage,
        "command": recorded,
        "container_shell_command": shell_command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "elapsed_seconds": time.perf_counter() - started,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "passed": exit_code == 0 and not timed_out,
        "stdout_log": log_root.joinpath(f"{stage}.stdout.txt").relative_to(project_root).as_posix(),
        "stderr_log": log_root.joinpath(f"{stage}.stderr.txt").relative_to(project_root).as_posix(),
        "stdout": stdout,
        "stderr": stderr,
    }


def real_run_command(
    *,
    command: Sequence[str],
    recorded_command: Sequence[str],
    project_root: Path,
    log_root: Path,
    stage: str,
    timeout_seconds: int | None,
) -> dict[str, Any]:
    started_at = utc_now()
    started = time.perf_counter()
    timed_out = False
    try:
        result = _run_process(command, timeout=timeout_seconds)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = _timeout_text(error.stdout)
        stderr = _timeout_text(error.stderr)
        exit_code = 124
        stderr = (
            stderr.rstrip()
            + f"\nProcess timed out after {timeout_seconds} seconds.\n"
        ).lstrip("\n")
    write_text(log_root / f"{stage}.stdout.txt", stdout)
    write_text(log_root / f"{stage}.stderr.txt", stderr)
    return {
        "stage": stage,
        "command": list(recorded_command),
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "elapsed_seconds": time.perf_counter() - started,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "passed": exit_code == 0 and not timed_out,
        "stdout_log": log_root.joinpath(f"{stage}.stdout.txt").relative_to(project_root).as_posix(),
        "stderr_log": log_root.joinpath(f"{stage}.stderr.txt").relative_to(project_root).as_posix(),
        "stdout": stdout,
        "stderr": stderr,
    }


def real_call_ollama(
    *,
    payload: Mapping[str, Any],
    endpoint: str,
    timeout_seconds: int,
) -> tuple[dict[str, Any], float]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as error:
        raise FormalRunExecutionError(f"Ollama request failed: {error}") from error
    value = json.loads(body)
    if not isinstance(value, dict):
        raise FormalRunExecutionError("Ollama response root is not an object")
    return value, time.perf_counter() - started


def default_hooks() -> RuntimeHooks:
    return RuntimeHooks(
        git_output=real_git_output,
        docker_image_id=real_docker_image_id,
        docker_run=real_docker_run,
        call_ollama=real_call_ollama,
        run_command=real_run_command,
    )


def _find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    state = "code"
    index = open_index
    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and nxt == "/":
                state = "line_comment"
                index += 2
                continue
            if char == "/" and nxt == "*":
                state = "block_comment"
                index += 2
                continue
            if char == '"':
                state = "string"
                index += 1
                continue
            if char == "'":
                state = "char"
                index += 1
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
        elif state == "line_comment":
            if char == "\n":
                state = "code"
        elif state == "block_comment":
            if char == "*" and nxt == "/":
                state = "code"
                index += 2
                continue
        elif state == "string":
            if char == "\\":
                index += 2
                continue
            if char == '"':
                state = "code"
        elif state == "char":
            if char == "\\":
                index += 2
                continue
            if char == "'":
                state = "code"
        index += 1
    raise FormalRunExecutionError("Matching closing brace was not found")


def locate_class_span(text: str, symbol: str) -> tuple[int, int]:
    pattern = re.compile(rf"\b(?:class|struct)\s+{re.escape(symbol)}\b")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise FormalRunExecutionError(
            f"Expected one class/struct definition for {symbol}, found {len(matches)}"
        )
    start = matches[0].start()
    open_brace = text.find("{", matches[0].end())
    if open_brace < 0:
        raise FormalRunExecutionError(f"Opening brace not found for {symbol}")
    close_brace = _find_matching_brace(text, open_brace)
    semicolon = text.find(";", close_brace)
    end = semicolon + 1 if semicolon >= 0 else close_brace + 1
    return start, end


def locate_ini_writer_body(text: str) -> tuple[int, int]:
    signature = "inline static void write("
    signature_index = text.find(signature)
    if signature_index < 0:
        raise FormalRunExecutionError("INIWriter::write signature was not found")
    open_brace = text.find("{", signature_index)
    if open_brace < 0:
        raise FormalRunExecutionError("INIWriter::write opening brace was not found")
    return open_brace, _find_matching_brace(text, open_brace)


def strip_inline_callable_bodies(text: str) -> str:
    output: list[str] = []
    cursor = 0
    index = 0
    while index < len(text):
        if text[index] != "{":
            index += 1
            continue
        prefix = text[max(0, index - 240):index]
        stripped = prefix.rstrip()
        looks_callable = bool(
            re.search(
                r"\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:final\s*)?$",
                stripped,
            )
        )
        looks_control = bool(
            re.search(r"\b(?:if|for|while|switch|catch)\s*\([^)]*\)\s*$", stripped)
        )
        if not looks_callable or looks_control:
            index += 1
            continue
        close = _find_matching_brace(text, index)
        output.append(text[cursor:index])
        output.append(";")
        cursor = close + 1
        index = cursor
    output.append(text[cursor:])
    return "".join(output)


def _ensure_clean_repository(
    repository: Path,
    expected_commit: str,
    hooks: RuntimeHooks,
) -> None:
    actual = hooks.git_output(repository, "rev-parse", "HEAD")
    if actual != expected_commit:
        raise FormalRunExecutionError(
            f"Repository commit mismatch: expected={expected_commit}, actual={actual}"
        )
    status = hooks.git_output(
        repository,
        "status",
        "--short",
        "--untracked-files=no",
    )
    if status:
        raise FormalRunExecutionError(
            f"Repository has tracked changes before run:\n{status}"
        )


def _source_files(config: Mapping[str, Any]) -> tuple[str, ...]:
    if config.get("target_kind") == "legacy_function":
        value = config.get("source_file")
        if not isinstance(value, str) or not value:
            raise FormalRunExecutionError("legacy source_file is missing")
        return (value,)
    values = config.get("source_files")
    if not isinstance(values, list) or not values:
        raise FormalRunExecutionError("source_files is missing")
    return tuple(str(item) for item in values)


def _prepare_standard_inputs(
    target: ValidatedFormalTarget,
    project_root: Path,
    repository: Path,
    source_files: tuple[str, ...],
) -> tuple[str, str, dict[str, Any]]:
    design_parts: list[str] = []
    scaffold_parts: list[str] = []
    metadata: dict[str, Any] = {"locator": None}
    if target.config["granularity"] == "module_files":
        for relative in source_files:
            text = read_text(repository / relative)
            design_parts.append(f"===== FILE: {relative} =====\n{text.rstrip()}\n")
            if Path(relative).suffix.lower() in {".h", ".hh", ".hpp", ".hxx"}:
                scaffold = strip_inline_callable_bodies(text)
                scaffold_parts.append(
                    f"===== FILE: {relative} =====\n{scaffold.rstrip()}\n"
                )
        return "\n".join(design_parts), "\n".join(scaffold_parts), metadata

    if target.config["granularity"] == "class_span":
        if len(source_files) != 1:
            raise FormalRunExecutionError("class_span requires one source file")
        symbol = str(target.config["locator"]["symbol"])
        source_text = read_text(repository / source_files[0])
        start, end = locate_class_span(source_text, symbol)
        original_span = source_text[start:end]
        metadata["locator"] = {
            "symbol": symbol,
            "start_offset": start,
            "end_offset": end,
            "original_span_sha256": sha256_bytes(original_span.encode("utf-8")),
        }
        return original_span + "\n", strip_inline_callable_bodies(original_span) + "\n", metadata

    raise FormalRunExecutionError(
        f"Unsupported standard granularity: {target.config['granularity']}"
    )


def _prepare_legacy_inputs(
    target: ValidatedFormalTarget,
    project_root: Path,
) -> tuple[str, str, dict[str, Any]]:
    design_spec = target.config.get("design_input")
    scaffold_spec = target.config.get("regeneration_input")
    if not isinstance(design_spec, Mapping) or not isinstance(scaffold_spec, Mapping):
        raise FormalRunExecutionError("legacy frozen input metadata is missing")
    design_path = resolve_project_path(
        project_root,
        str(design_spec.get("path", "")),
        field="legacy design_input.path",
    )
    scaffold_path = resolve_project_path(
        project_root,
        str(scaffold_spec.get("fixed_scaffold", "")),
        field="legacy regeneration_input.fixed_scaffold",
    )
    if not design_path.is_file() or not scaffold_path.is_file():
        raise FormalRunExecutionError("legacy frozen input file is missing")
    expected_design_sha = str(design_spec.get("sha256", ""))
    actual_design_sha = sha256_file(design_path)
    if actual_design_sha != expected_design_sha:
        raise FormalRunExecutionError(
            "legacy design input SHA-256 mismatch: "
            f"expected={expected_design_sha}, actual={actual_design_sha}"
        )
    return (
        read_text(design_path),
        read_text(scaffold_path),
        {
            "legacy_design_input_path": design_path.relative_to(project_root).as_posix(),
            "legacy_design_input_sha256": actual_design_sha,
            "legacy_fixed_scaffold_path": scaffold_path.relative_to(project_root).as_posix(),
            "legacy_fixed_scaffold_sha256": sha256_file(scaffold_path),
        },
    )


def prepare_inputs(
    target: ValidatedFormalTarget,
    project_root: Path,
    hooks: RuntimeHooks,
) -> PreparedInputs:
    root = project_root.resolve()
    repository = resolve_project_path(
        root,
        str(target.config["repository_path"]),
        field="repository_path",
    )
    _ensure_clean_repository(
        repository,
        str(target.config["repository_commit"]),
        hooks,
    )
    nested_repository: Path | None = None
    if target.target_kind == "legacy_function":
        nested_repository = repository / "googletest"
        if nested_repository.is_dir() and target.config.get("submodule_commit"):
            _ensure_clean_repository(
                nested_repository,
                str(target.config["submodule_commit"]),
                hooks,
            )

    source_files = _source_files(target.config)
    original_hashes: dict[str, str] = {}
    metadata_files: list[dict[str, Any]] = []
    for relative in source_files:
        source = repository / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        data = source.read_bytes()
        original_hashes[relative] = sha256_bytes(data)
        if target.target_kind == "legacy_function":
            readiness = target.config.get("readiness")
            restoration = (
                readiness.get("restoration")
                if isinstance(readiness, Mapping)
                else None
            )
            expected = (
                str(restoration.get("expected_sha256", ""))
                if isinstance(restoration, Mapping)
                else ""
            )
            if expected:
                normalized = sha256_bytes(data.replace(b"\r\n", b"\n"))
                if original_hashes[relative] != expected and normalized != expected:
                    raise FormalRunExecutionError(
                        "legacy source SHA-256 differs from frozen evidence: "
                        f"expected={expected}, actual={original_hashes[relative]}, "
                        f"lf_normalized={normalized}"
                    )
        backup = target.experiment_root / "backup" / "files" / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)
        metadata_files.append(
            {"path": relative, "sha256": original_hashes[relative]}
        )

    if target.target_kind == "legacy_function":
        design_input, fixed_scaffold, extra = _prepare_legacy_inputs(target, root)
    else:
        design_input, fixed_scaffold, extra = _prepare_standard_inputs(
            target,
            root,
            repository,
            source_files,
        )

    write_text(target.experiment_root / "input" / "design_input.txt", design_input)
    write_text(target.experiment_root / "input" / "fixed_scaffold.txt", fixed_scaffold)
    write_json(
        target.experiment_root / "input" / "source_metadata.json",
        {
            "artifact_schema_version": "rag-formal-source-input-v1",
            "target_id": target.target_id,
            "repository_commit": target.config["repository_commit"],
            "source_files": metadata_files,
            "design_input_sha256": sha256_bytes(design_input.encode("utf-8")),
            "fixed_scaffold_sha256": sha256_bytes(fixed_scaffold.encode("utf-8")),
            "context_path": target.context_path.relative_to(root).as_posix(),
            "context_sha256": target.context_sha256,
            **extra,
        },
    )
    write_json(
        target.experiment_root / "configs" / "target_config.json",
        target.config,
    )
    return PreparedInputs(
        design_input=design_input,
        fixed_scaffold=fixed_scaffold,
        repository=repository,
        source_files=source_files,
        original_hashes=original_hashes,
        nested_repository=nested_repository,
    )


def _endpoint_and_timeout(config: Mapping[str, Any]) -> tuple[str, int]:
    endpoint = str(config.get("endpoint", "http://localhost:11434/api/generate"))
    timeout = int(config.get("generation_request_timeout_seconds", 1800))
    return endpoint, timeout


def execute_llm_request(
    *,
    target: ValidatedFormalTarget,
    request: RequestBundle,
    stage: str,
    hooks: RuntimeHooks,
    call_index: int,
) -> tuple[dict[str, Any], str]:
    raw_dir = target.experiment_root / "raw_output"
    write_json(raw_dir / f"{stage}_request.json", request.payload)
    write_json(raw_dir / f"{stage}_request_audit.json", request.audit)
    endpoint, timeout = _endpoint_and_timeout(target.config)
    started_at = utc_now()
    response, elapsed = hooks.call_ollama(
        payload=request.payload,
        endpoint=endpoint,
        timeout_seconds=timeout,
    )
    write_json(raw_dir / f"{stage}_response.json", response)
    text = response.get("response")
    metadata = {
        "artifact_schema_version": "rag-formal-generation-metadata-v1",
        "target_id": target.target_id,
        "stage": stage,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "elapsed_seconds": elapsed,
        "done": response.get("done"),
        "done_reason": response.get("done_reason"),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "eval_count": response.get("eval_count"),
        "llm_call_index": call_index,
        "llm_call_count_for_stage": 1,
        "retry_performed": False,
        "automatic_repair_performed": False,
    }
    write_json(raw_dir / f"{stage}_metadata.json", metadata)
    if not isinstance(text, str) or not text.strip():
        raise FormalRunExecutionError(f"{stage} returned an empty response")
    write_text(raw_dir / f"{stage}_raw.txt", text)
    return metadata, text


def normalize_outer_markdown_fence(
    text: str,
    allowed_languages: set[str],
) -> tuple[str, dict[str, Any]]:
    raw_sha = sha256_bytes(text.encode("utf-8"))
    match = re.fullmatch(
        r"\s*```([A-Za-z0-9_+\-]*)[ \t]*\r?\n(.*)\r?\n```[ \t]*\s*",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        if re.search(r"(?m)^[ \t]*```[A-Za-z0-9_+\-]*[ \t]*$", text):
            raise FormalRunExecutionError(
                "Code regeneration output contains an unmatched or non-outer Markdown fence"
            )
        normalized = text
        applied = False
        language: str | None = None
    else:
        language = match.group(1).lower()
        if language not in allowed_languages:
            raise FormalRunExecutionError(
                f"Unexpected outer Markdown fence language: {language!r}"
            )
        normalized = match.group(2)
        if not normalized.strip():
            raise FormalRunExecutionError("Code regeneration became empty after normalization")
        if re.search(r"(?m)^[ \t]*```[A-Za-z0-9_+\-]*[ \t]*$", normalized):
            raise FormalRunExecutionError(
                "Code regeneration output contains an additional Markdown fence"
            )
        applied = True
    return normalized, {
        "schema_version": "1.0",
        "normalization_applied": applied,
        "normalization_type": "outer_markdown_fence" if applied else "none",
        "fence_language": language,
        "strict_format_pass": not applied,
        "raw_sha256": raw_sha,
        "normalized_sha256": sha256_bytes(normalized.encode("utf-8")),
        "code_body_modified": False,
        "retry_performed": False,
        "automatic_repair_performed": False,
    }


def parse_module_output(text: str, expected_paths: list[str]) -> dict[str, str]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise FormalRunExecutionError(
            f"Code regeneration output is not valid JSON: line={error.lineno}, column={error.colno}"
        ) from error
    if not isinstance(value, dict) or not isinstance(value.get("files"), list):
        raise FormalRunExecutionError("Module output must contain a files array")
    files: dict[str, str] = {}
    for item in value["files"]:
        if not isinstance(item, dict):
            raise FormalRunExecutionError("Each files item must be an object")
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            raise FormalRunExecutionError("Each file requires string path and content")
        if path in files:
            raise FormalRunExecutionError(f"Duplicate generated path: {path}")
        files[path] = content
    if set(files) != set(expected_paths):
        raise FormalRunExecutionError(
            f"Generated file paths mismatch: expected={expected_paths}, actual={sorted(files)}"
        )
    return files


def materialize_code_output(
    target: ValidatedFormalTarget,
    response_text: str,
) -> dict[str, Any]:
    generated = target.experiment_root / "generated"
    raw_dir = target.experiment_root / "raw_output"
    if target.target_kind == "legacy_function":
        normalization = {
            "schema_version": "legacy-exact-output-v1",
            "normalization_applied": False,
            "normalization_type": "none",
            "raw_sha256": sha256_bytes(response_text.encode("utf-8")),
            "normalized_sha256": sha256_bytes(response_text.encode("utf-8")),
            "code_body_modified": False,
            "retry_performed": False,
            "automatic_repair_performed": False,
        }
        write_text(generated / "regenerated_write_body.cpp", response_text.rstrip() + "\n")
    elif target.config["granularity"] == "module_files":
        normalized, normalization = normalize_outer_markdown_fence(response_text, {"", "json"})
        files = parse_module_output(
            normalized,
            [str(item) for item in target.config["source_files"]],
        )
        for relative, content in files.items():
            write_text(generated / "files" / relative, content)
        write_json(generated / "generated_files_manifest.json", {"files": sorted(files)})
    else:
        normalized, normalization = normalize_outer_markdown_fence(
            response_text,
            {"", "cpp", "c++", "cc", "cxx"},
        )
        write_text(generated / "regenerated_target.cpp", normalized)
    write_json(raw_dir / "code_regeneration_normalization.json", normalization)
    return normalization


def parse_gtest_counts(output: str) -> dict[str, int | None]:
    ran = re.findall(r"\[==========\]\s+(\d+)\s+tests?\s+from", output)
    passed = re.findall(r"\[\s*PASSED\s*\]\s+(\d+)\s+tests?", output)
    failed = re.findall(r"\[\s*FAILED\s*\]\s+(\d+)\s+tests?", output)
    return {
        "ran": int(ran[-1]) if ran else None,
        "passed": int(passed[-1]) if passed else None,
        "failed": int(failed[-1]) if failed else 0,
    }


def parse_ctest_counts(output: str) -> dict[str, int | None]:
    match = re.search(
        r"(\d+)%\s+tests\s+passed,\s+(\d+)\s+tests\s+failed\s+out\s+of\s+(\d+)",
        output,
    )
    if match is None:
        return {"ran": None, "passed": None, "failed": None}
    failed = int(match.group(2))
    total = int(match.group(3))
    return {"ran": total, "passed": total - failed, "failed": failed}


def _public_stage(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"stdout", "stderr"} and not key.startswith("_")
    }


def _record_skipped(stage: str) -> dict[str, Any]:
    return {"stage": stage, "passed": False, "skipped": True}


def _standard_generated_source(
    target: ValidatedFormalTarget,
    prepared: PreparedInputs,
) -> dict[str, bytes]:
    replacements: dict[str, bytes] = {}
    if target.config["granularity"] == "module_files":
        for relative in prepared.source_files:
            path = target.experiment_root / "generated" / "files" / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            replacements[relative] = path.read_bytes()
        return replacements

    relative = prepared.source_files[0]
    source_path = prepared.repository / relative
    source_text = read_text(source_path)
    symbol = str(target.config["locator"]["symbol"])
    start, end = locate_class_span(source_text, symbol)
    generated = read_text(
        target.experiment_root / "generated" / "regenerated_target.cpp"
    ).strip()
    newline = "\r\n" if "\r\n" in source_text else "\n"
    generated = generated.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    replacements[relative] = (source_text[:start] + generated + source_text[end:]).encode("utf-8")
    return replacements


def _legacy_generated_source(
    target: ValidatedFormalTarget,
    prepared: PreparedInputs,
) -> dict[str, bytes]:
    relative = prepared.source_files[0]
    source_path = prepared.repository / relative
    original = source_path.read_bytes()
    source_text = original.decode("utf-8")
    newline = "\r\n" if "\r\n" in source_text else "\n"
    open_brace, close_brace = locate_ini_writer_body(source_text)
    body = read_text(
        target.experiment_root / "generated" / "regenerated_write_body.cpp"
    )
    normalized = body.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    indented = newline.join(
        ("        " + line) if line else ""
        for line in normalized.split("\n")
    )
    replacement = newline + indented + newline + "    "
    modified = source_text[: open_brace + 1] + replacement + source_text[close_brace:]
    return {relative: modified.encode("utf-8")}


def _replace_project_root(command: Sequence[str], project_root: Path) -> list[str]:
    return [item.replace("<PROJECT_ROOT>", str(project_root)) for item in command]


def _evaluate_standard(
    target: ValidatedFormalTarget,
    project_root: Path,
    prepared: PreparedInputs,
    hooks: RuntimeHooks,
) -> tuple[dict[str, Any], list[str]]:
    config = target.config
    evaluation = config["evaluation"]
    log_root = project_root / "logs" / "rag" / "formal" / str(config["run_id"])
    replacements = _standard_generated_source(target, prepared)
    originals = {
        relative: (prepared.repository / relative).read_bytes()
        for relative in prepared.source_files
    }
    for relative, data in replacements.items():
        (prepared.repository / relative).write_bytes(data)

    stages: dict[str, Any] = {}
    error: str | None = None
    timeouts = {
        "configure": 300,
        "build": 600,
        "direct_test": 300,
        "full_test": 600,
    }
    timeouts.update(evaluation.get("stage_timeouts_seconds", {}) or {})
    try:
        actual_image_id = hooks.docker_image_id(str(evaluation["docker_image"]))
        if actual_image_id != evaluation["docker_image_id"]:
            raise FormalRunExecutionError("Docker image ID changed after configuration")
        for stage, command in (
            ("configure", evaluation["configure_command"]),
            ("build", evaluation["build_command"]),
            ("direct_test", evaluation["direct_test_command"]),
            ("full_test", evaluation["full_test_command"]),
        ):
            if stage != "configure" and not all(
                stages.get(previous, {}).get("passed") is True
                for previous in ("configure", "build", "direct_test", "full_test")
                if previous in stages
            ):
                stages[stage] = _record_skipped(stage)
                continue
            record = hooks.docker_run(
                project_root=project_root,
                repository_path=str(config["repository_path"]),
                image=str(evaluation["docker_image"]),
                shell_command=str(command),
                log_root=log_root,
                stage=stage,
                timeout_seconds=int(timeouts[stage]),
            )
            output = str(record.get("stdout", "")) + "\n" + str(record.get("stderr", ""))
            if stage == "direct_test":
                counts = parse_gtest_counts(output)
                record["counts"] = counts
                record["passed"] = (
                    record.get("exit_code") == 0
                    and counts["ran"] == evaluation["expected_direct_tests"]
                    and counts["passed"] == evaluation["expected_direct_tests"]
                    and counts["failed"] == 0
                )
            elif stage == "full_test":
                counts = (
                    parse_ctest_counts(output)
                    if evaluation["full_test_kind"] == "ctest"
                    else parse_gtest_counts(output)
                )
                record["counts"] = counts
                record["passed"] = (
                    record.get("exit_code") == 0
                    and counts["ran"] == evaluation["expected_full_tests"]
                    and counts["passed"] == evaluation["expected_full_tests"]
                    and counts["failed"] == 0
                )
            stages[stage] = _public_stage(record)
            if stages[stage].get("passed") is not True:
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        for relative, data in originals.items():
            (prepared.repository / relative).write_bytes(data)

    for stage in ("configure", "build", "direct_test", "full_test"):
        stages.setdefault(stage, _record_skipped(stage))
    restored_hashes = {
        relative: sha256_file(prepared.repository / relative)
        for relative in prepared.source_files
    }
    restored = restored_hashes == prepared.original_hashes
    tracked_status = hooks.git_output(
        prepared.repository,
        "status",
        "--short",
        "--untracked-files=no",
    )
    repository_clean = tracked_status == ""
    overall = (
        error is None
        and all(stages[stage].get("passed") is True for stage in ("configure", "build", "direct_test", "full_test"))
        and restored
        and repository_clean
    )
    return {
        "schema_version": "rag-formal-evaluation-v1",
        "target_id": target.target_id,
        "run_id": config["run_id"],
        "completed_at_utc": utc_now(),
        "overall_pass": overall,
        "error": error,
        "stages": stages,
        "restoration": {
            "restored": restored,
            "original_hashes": prepared.original_hashes,
            "restored_hashes": restored_hashes,
            "repository_clean": repository_clean,
            "tracked_status": tracked_status,
        },
        "local_raw_log_directory": log_root.relative_to(project_root).as_posix(),
    }, ["configure", "build", "direct_test", "full_test"]


def _legacy_stage_pass(
    stage: str,
    record: dict[str, Any],
    evaluation: Mapping[str, Any],
) -> None:
    output = str(record.get("stdout", "")) + "\n" + str(record.get("stderr", ""))
    if stage == "direct_test":
        counts = parse_gtest_counts(output)
        record["counts"] = counts
        record["passed"] = (
            record.get("exit_code") == 0
            and counts["ran"] == evaluation["expected_direct_tests"]
            and counts["passed"] == evaluation["expected_direct_tests"]
            and counts["failed"] == 0
        )
    elif stage == "full_test":
        counts = parse_gtest_counts(output)
        record["counts"] = counts
        record["passed"] = (
            record.get("exit_code") == 0
            and counts["ran"] == evaluation["expected_full_tests"]
            and counts["passed"] == evaluation["expected_full_tests"]
            and counts["failed"] == 0
        )
    elif stage == "ctest":
        record["passed"] = (
            record.get("exit_code") == 0
            and re.search(r"100%\s+tests\s+passed,\s+0\s+tests\s+failed", output) is not None
        )


def _evaluate_legacy(
    target: ValidatedFormalTarget,
    project_root: Path,
    prepared: PreparedInputs,
    hooks: RuntimeHooks,
) -> tuple[dict[str, Any], list[str]]:
    config = target.config
    evaluation = config["evaluation"]
    log_root = project_root / "logs" / "rag" / "formal" / str(config["run_id"])
    replacements = _legacy_generated_source(target, prepared)
    originals = {
        relative: (prepared.repository / relative).read_bytes()
        for relative in prepared.source_files
    }
    for relative, data in replacements.items():
        (prepared.repository / relative).write_bytes(data)

    stage_specs: list[tuple[str, Sequence[str]]] = [
        ("configure", evaluation["configure_command"]),
        ("build", evaluation["build_command"]),
        ("direct_test", evaluation["direct_test_command"]),
        ("full_test", evaluation["full_test_command"]),
        ("ctest", evaluation["ctest_command"]),
    ]
    stages: dict[str, Any] = {}
    error: str | None = None
    try:
        actual_image_id = hooks.docker_image_id(str(evaluation["docker_image"]))
        if actual_image_id != evaluation["docker_image_id"]:
            raise FormalRunExecutionError("Docker image ID changed after configuration")
        for stage, recorded_command in stage_specs:
            if stage == "build" and stages.get("configure", {}).get("passed") is not True:
                stages[stage] = _record_skipped(stage)
                continue
            if stage in {"direct_test", "full_test", "ctest"} and (
                stages.get("build", {}).get("passed") is not True
            ):
                stages[stage] = _record_skipped(stage)
                continue
            actual_command = _replace_project_root(recorded_command, project_root)
            record = hooks.run_command(
                command=actual_command,
                recorded_command=recorded_command,
                project_root=project_root,
                log_root=log_root,
                stage=stage,
                timeout_seconds=None,
            )
            _legacy_stage_pass(stage, record, evaluation)
            stages[stage] = _public_stage(record)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        for relative, data in originals.items():
            (prepared.repository / relative).write_bytes(data)

    stage_names = [item[0] for item in stage_specs]
    for stage in stage_names:
        stages.setdefault(stage, _record_skipped(stage))
    restored_hashes = {
        relative: sha256_file(prepared.repository / relative)
        for relative in prepared.source_files
    }
    restored = restored_hashes == prepared.original_hashes
    tracked_status = hooks.git_output(
        prepared.repository,
        "status",
        "--short",
        "--untracked-files=no",
    )
    nested_status = ""
    if prepared.nested_repository is not None:
        nested_status = hooks.git_output(
            prepared.nested_repository,
            "status",
            "--short",
            "--untracked-files=no",
        )
    repository_clean = tracked_status == "" and nested_status == ""
    overall = (
        error is None
        and all(stages[stage].get("passed") is True for stage in stage_names)
        and restored
        and repository_clean
    )
    return {
        "schema_version": "rag-formal-evaluation-v1",
        "target_id": target.target_id,
        "run_id": config["run_id"],
        "completed_at_utc": utc_now(),
        "overall_pass": overall,
        "error": error,
        "stages": stages,
        "restoration": {
            "restored": restored,
            "original_hashes": prepared.original_hashes,
            "restored_hashes": restored_hashes,
            "repository_clean": repository_clean,
            "tracked_status": tracked_status,
            "nested_status": nested_status,
        },
        "local_raw_log_directory": log_root.relative_to(project_root).as_posix(),
    }, stage_names


def evaluate_generated_code(
    target: ValidatedFormalTarget,
    project_root: Path,
    prepared: PreparedInputs,
    hooks: RuntimeHooks,
) -> dict[str, Any]:
    if target.target_kind == "legacy_function":
        result, _ = _evaluate_legacy(target, project_root, prepared, hooks)
    else:
        result, _ = _evaluate_standard(target, project_root, prepared, hooks)
    normalization_path = (
        target.experiment_root / "raw_output" / "code_regeneration_normalization.json"
    )
    if normalization_path.is_file():
        result["code_regeneration_normalization"] = read_json(normalization_path)
    write_json(target.experiment_root / "evaluation" / "evaluation_manifest.json", result)
    return result


def build_overview_markdown(
    target: ValidatedFormalTarget,
    evaluation: Mapping[str, Any],
) -> str:
    lines = [
        "# Formal repository-context RAG round-trip result",
        "",
        f"- target_id: `{target.target_id}`",
        f"- run_id: `{target.config['run_id']}`",
        f"- condition_id: `{target.config['condition_id']}`",
        f"- context_sha256: `{target.context_sha256}`",
        f"- overall: **{'PASS' if evaluation.get('overall_pass') else 'FAIL'}**",
        "",
        "| stage | result | detail |",
        "|---|---|---|",
    ]
    for stage, record in evaluation.get("stages", {}).items():
        if record.get("skipped"):
            label = "SKIPPED"
            detail = "previous stage failed"
        else:
            label = "PASS" if record.get("passed") else "FAIL"
            counts = record.get("counts")
            detail = (
                f"{counts.get('passed')}/{counts.get('ran')} passed"
                if isinstance(counts, Mapping)
                else f"exit={record.get('exit_code')}"
            )
        lines.append(f"| {stage} | {label} | {detail} |")
    lines.extend(
        [
            "",
            "A PASS indicates correctness only within the behavior observed by the frozen tests.",
            "",
        ]
    )
    return "\n".join(lines)


def write_target_reports(
    target: ValidatedFormalTarget,
    evaluation: Mapping[str, Any],
) -> None:
    write_json(
        target.experiment_root / "report" / "experiment_overview.json",
        dict(evaluation),
    )
    write_text(
        target.experiment_root / "report" / "experiment_overview.md",
        build_overview_markdown(target, evaluation),
    )


def record_pipeline_failure(
    *,
    target: ValidatedFormalTarget,
    project_root: Path,
    stage: str,
    error: Exception,
    llm_calls: Mapping[str, int],
    hooks: RuntimeHooks,
) -> None:
    repository = resolve_project_path(
        project_root,
        str(target.config["repository_path"]),
        field="repository_path",
    )
    tracked_status: str | None = None
    repository_clean: bool | None = None
    try:
        tracked_status = hooks.git_output(
            repository,
            "status",
            "--short",
            "--untracked-files=no",
        )
        repository_clean = tracked_status == ""
    except Exception:
        repository_clean = None
    write_json(
        target.experiment_root / "evaluation" / "pipeline_failure.json",
        {
            "artifact_schema_version": "rag-formal-pipeline-failure-v1",
            "target_id": target.target_id,
            "run_id": target.config["run_id"],
            "failed_stage": stage,
            "error_type": type(error).__name__,
            "error": str(error),
            "recorded_at_utc": utc_now(),
            "llm_calls": dict(llm_calls),
            "retry_performed": False,
            "automatic_repair_performed": False,
            "manual_patch_performed": False,
            "repository_clean": repository_clean,
            "tracked_status": tracked_status,
        },
    )


def terminal_result_path(target: ValidatedFormalTarget) -> Path:
    evaluation = target.experiment_root / "evaluation"
    manifest = evaluation / "evaluation_manifest.json"
    if manifest.is_file():
        return manifest
    failure = evaluation / "pipeline_failure.json"
    if failure.is_file():
        return failure
    raise FormalRunExecutionError(
        f"Terminal target evidence is missing: {target.target_id}"
    )


def result_summary(target: ValidatedFormalTarget) -> dict[str, Any]:
    path = terminal_result_path(target)
    value = read_json(path)
    if path.name == "evaluation_manifest.json":
        status = "passed" if value.get("overall_pass") is True else "failed"
        failure_stage = None
        if status == "failed":
            for stage, record in value.get("stages", {}).items():
                if record.get("passed") is not True and not record.get("skipped"):
                    failure_stage = stage
                    break
    else:
        status = "failed"
        failure_stage = value.get("failed_stage")
    return {
        "target_id": target.target_id,
        "run_id": target.config["run_id"],
        "status": status,
        "failure_stage": failure_stage,
        "result_path": path.relative_to(target.experiment_root.parents[2]).as_posix(),
    }


def write_formal_runs_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "target_id",
        "condition_id",
        "status",
        "failure_stage",
        "result_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
