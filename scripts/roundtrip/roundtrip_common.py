from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(read_text(path))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_process(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=timeout,
    )


def git_output(repository: Path, *args: str) -> str:
    result = run_process(["git", "-C", str(repository), *args])
    if result.returncode != 0:
        raise RuntimeError(
            f"git command failed: {' '.join(args)}\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


def docker_image_id(image: str) -> str:
    result = run_process(
        ["docker", "image", "inspect", "--format={{.Id}}", image]
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Docker image is unavailable: {image}\n{result.stderr}"
        )
    return result.stdout.strip()


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def docker_run(
    *,
    project_root: Path,
    repository_path: str,
    image: str,
    shell_command: str,
    log_root: Path,
    stage: str,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    container_name = (
        f"cpp-roundtrip-{stage}-{uuid.uuid4().hex[:12]}"
    )

    command = [
        "docker",
        "run",
        "--name",
        container_name,
        "--rm",
        "--mount",
        f"type=bind,source={project_root},target=/workspace",
        "-w",
        f"/workspace/{repository_path.replace('\\\\', '/').replace('\\', '/')}",
        image,
        "bash",
        "-lc",
        shell_command,
    ]

    recorded_command = command.copy()
    recorded_command[recorded_command.index("--name") + 1] = "<CONTAINER_NAME>"

    for index, item in enumerate(recorded_command):
        if (
            item.startswith("type=bind,source=")
            and item.endswith(",target=/workspace")
        ):
            recorded_command[index] = (
                "type=bind,source=<PROJECT_ROOT>,target=/workspace"
            )

    started_at = utc_now()
    started = time.perf_counter()
    timed_out = False

    try:
        result = run_process(command, timeout=timeout_seconds)
        stdout = result.stdout
        stderr = result.stderr
        exit_code = result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = _timeout_output(error.stdout)
        stderr = _timeout_output(error.stderr)
        exit_code = 124

        cleanup_error = ""
        try:
            cleanup = run_process(
                ["docker", "rm", "-f", container_name],
                timeout=30,
            )
            cleanup_output = (
                cleanup.stdout + "\n" + cleanup.stderr
            ).strip()

            if (
                cleanup.returncode != 0
                and "No such container" not in cleanup_output
            ):
                cleanup_error = (
                    "Docker cleanup failed: " + cleanup_output
                )
        except subprocess.TimeoutExpired:
            cleanup_error = (
                "Docker cleanup timed out after 30 seconds."
            )

        timeout_note = (
            f"Process timed out after {timeout_seconds} seconds."
        )

        stderr_parts = [
            part
            for part in (
                stderr.rstrip(),
                timeout_note,
                cleanup_error,
            )
            if part
        ]
        stderr = "\n".join(stderr_parts) + "\n"

    elapsed = time.perf_counter() - started

    stdout_path = log_root / f"{stage}.stdout.txt"
    stderr_path = log_root / f"{stage}.stderr.txt"
    write_text(stdout_path, stdout)
    write_text(stderr_path, stderr)

    return {
        "stage": stage,
        "command": recorded_command,
        "container_shell_command": shell_command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "elapsed_seconds": elapsed,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "passed": exit_code == 0 and not timed_out,
        "stdout_log": stdout_path.relative_to(project_root).as_posix(),
        "stderr_log": stderr_path.relative_to(project_root).as_posix(),
        "stdout": stdout,
        "stderr": stderr,
    }

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
    if not match:
        return {"ran": None, "passed": None, "failed": None}
    failed = int(match.group(2))
    total = int(match.group(3))
    return {"ran": total, "passed": total - failed, "failed": failed}


def call_ollama(payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
    request = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=1800) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as error:
        raise RuntimeError(f"Ollama request failed: {error}") from error
    elapsed = time.perf_counter() - started
    value = json.loads(body)
    if not isinstance(value, dict):
        raise RuntimeError("Ollama response root is not an object")
    return value, elapsed


def find_matching_brace(text: str, open_index: int) -> int:
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
    raise ValueError("Matching closing brace was not found")


def locate_class_span(text: str, symbol: str) -> tuple[int, int]:
    pattern = re.compile(rf"\b(?:class|struct)\s+{re.escape(symbol)}\b")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            f"Expected one class/struct definition for {symbol}, found {len(matches)}"
        )
    start = matches[0].start()
    open_brace = text.find("{", matches[0].end())
    if open_brace < 0:
        raise ValueError(f"Opening brace not found for {symbol}")
    close_brace = find_matching_brace(text, open_brace)
    semicolon = text.find(";", close_brace)
    end = semicolon + 1 if semicolon >= 0 else close_brace + 1
    return start, end


def extract_includes(text: str) -> list[str]:
    return [
        line.rstrip()
        for line in text.splitlines()
        if line.lstrip().startswith("#include")
    ]


def strip_inline_callable_bodies(text: str) -> str:
    """Conservatively replace likely callable bodies with ';'.

    Class/struct/namespace braces are preserved. This is a lexical scaffold,
    not a C++ parser. The generated scaffold is recorded for inspection.
    """
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
            re.search(r"\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?(?:final\s*)?$", stripped)
        )
        looks_control = bool(
            re.search(r"\b(?:if|for|while|switch|catch)\s*\([^)]*\)\s*$", stripped)
        )
        if not looks_callable or looks_control:
            index += 1
            continue
        close = find_matching_brace(text, index)
        output.append(text[cursor:index])
        output.append(";")
        cursor = close + 1
        index = close + 1
    output.append(text[cursor:])
    return "".join(output)


def markdown_details(title: str, content: str, language: str = "text") -> str:
    fence = "```"
    while fence in content:
        fence += "`"
    return (
        "<details>\n"
        f"<summary>{title}</summary>\n\n"
        f"{fence}{language}\n{content.rstrip()}\n{fence}\n\n"
        "</details>"
    )
