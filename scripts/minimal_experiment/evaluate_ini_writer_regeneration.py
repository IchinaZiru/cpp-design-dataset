from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "ini-writer-minimal"
RUN_ID = "qwen25coder32b-run-001"
IMAGE = "cpp-roundtrip-env:ini-cpp-v2"
EXPECTED_IMAGE_ID = (
    "sha256:68500729fc7fc0ba42377dc0737dea8bc2930d2be6e0d20b307490713c97c802"
)
EXPECTED_REPOSITORY_COMMIT = "e1779b837274de8be2051bef579c3b9ec3483522"
EXPECTED_GOOGLETEST_COMMIT = "391ce627def20c1e8a54d10b12949b15086473dd"
EXPECTED_DIRECT_TESTS = 3
EXPECTED_FULL_TESTS = 27


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run_process(
    command: list[str],
    *,
    cwd: Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def git_output(repository: Path, *args: str) -> str:
    result = run_process(["git", "-C", str(repository), *args], check=True)
    return result.stdout.strip()


def assert_equal(label: str, actual: str, expected: str) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{label} mismatch.\nExpected: {expected}\nActual:   {actual}"
        )


def locate_write_body(source: str) -> tuple[int, int]:
    signature = "inline static void write("
    signature_index = source.find(signature)
    if signature_index < 0:
        raise RuntimeError("INIWriter::write signature was not found.")

    open_brace = source.find("{", signature_index)
    if open_brace < 0:
        raise RuntimeError("Opening brace for INIWriter::write was not found.")

    depth = 0
    state = "code"
    index = open_brace
    while index < len(source):
        char = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""

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
                    return open_brace, index
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

    raise RuntimeError("Closing brace for INIWriter::write was not found.")


def indent_generated_body(body: str, indent: str, newline: str) -> str:
    normalized = body.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    lines = normalized.split("\n")
    return newline.join((indent + line) if line else "" for line in lines)


def parse_gtest(output: str) -> dict[str, int | None]:
    ran_matches = re.findall(
        r"\[==========\]\s+(\d+)\s+tests?\s+from", output
    )
    passed_matches = re.findall(
        r"\[\s*PASSED\s*\]\s+(\d+)\s+tests?", output
    )
    failed_matches = re.findall(
        r"\[\s*FAILED\s*\]\s+(\d+)\s+tests?", output
    )
    return {
        "tests_ran": int(ran_matches[-1]) if ran_matches else None,
        "tests_passed": int(passed_matches[-1]) if passed_matches else None,
        "tests_failed": int(failed_matches[-1]) if failed_matches else 0,
    }


def run_docker_stage(
    *,
    project_root: Path,
    shell_command: str,
    name: str,
    raw_log_root: Path,
) -> dict[str, Any]:
    command = [
        "docker",
        "run",
        "--rm",
        "--mount",
        f"type=bind,source={project_root},target=/workspace",
        "-w",
        "/workspace/repos/ini-cpp",
        IMAGE,
        "bash",
        "-lc",
        shell_command,
    ]
    recorded_command = [
        "docker",
        "run",
        "--rm",
        "--mount",
        "type=bind,source=<PROJECT_ROOT>,target=/workspace",
        "-w",
        "/workspace/repos/ini-cpp",
        IMAGE,
        "bash",
        "-lc",
        shell_command,
    ]

    started_at = utc_now()
    started = time.perf_counter()
    result = run_process(command)
    elapsed = time.perf_counter() - started
    completed_at = utc_now()

    stdout_path = raw_log_root / f"{name}.stdout.txt"
    stderr_path = raw_log_root / f"{name}.stderr.txt"
    write_text(stdout_path, result.stdout)
    write_text(stderr_path, result.stderr)

    return {
        "stage": name,
        "command": recorded_command,
        "container_shell_command": shell_command,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "elapsed_seconds": elapsed,
        "exit_code": result.returncode,
        "stdout_log": stdout_path.relative_to(project_root).as_posix(),
        "stderr_log": stderr_path.relative_to(project_root).as_posix(),
        "_stdout": result.stdout,
        "_stderr": result.stderr,
    }


def public_stage_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if not key.startswith("_")}


def ensure_outputs_absent(paths: list[Path], force: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not force:
        raise FileExistsError(
            "Evaluation outputs already exist and were not overwritten.\n"
            "Use --force only when intentionally replacing this run.\n"
            + "\n".join(existing)
        )


def build_summary(
    *,
    source_info: dict[str, Any],
    configure_result: dict[str, Any],
    build_result: dict[str, Any],
    direct_result: dict[str, Any],
    full_result: dict[str, Any],
    ctest_result: dict[str, Any],
    overall_pass: bool,
    restoration: dict[str, Any],
) -> str:
    def mark(value: bool) -> str:
        return "PASS" if value else "FAIL"

    direct_counts = direct_result.get("gtest", {})
    full_counts = full_result.get("gtest", {})

    return f"""# INIWriter最小実験 評価結果

## 実験条件

- 実験ID: `{EXPERIMENT_ID}`
- 実行ID: `{RUN_ID}`
- 対象: `INIWriter::write`
- Repository commit: `{EXPECTED_REPOSITORY_COMMIT}`
- GoogleTest commit: `{EXPECTED_GOOGLETEST_COMMIT}`
- Docker image: `{IMAGE}`
- Docker image ID: `{EXPECTED_IMAGE_ID}`
- 生成コードSHA-256: `{source_info["generated_body_sha256"]}`
- 置換後`ini/ini.h` SHA-256: `{source_info["modified_source_sha256"]}`

## 評価結果

| 項目 | 結果 | 詳細 |
|---|---|---|
| clean configure | {mark(configure_result["passed"])} | exit code `{configure_result["exit_code"]}` |
| full build | {mark(build_result["passed"])} | exit code `{build_result["exit_code"]}` |
| `INIWriter.*` | {mark(direct_result["passed"])} | {direct_counts.get("tests_passed")}/{EXPECTED_DIRECT_TESTS} passed |
| 全GoogleTest | {mark(full_result["passed"])} | {full_counts.get("tests_passed")}/{EXPECTED_FULL_TESTS} passed |
| CTest | {mark(ctest_result["passed"])} | exit code `{ctest_result["exit_code"]}` |
| 元コード復元 | {mark(restoration["restored"])} | restored SHA-256 `{restoration["restored_sha256"]}` |
| submodule clean | {mark(restoration["submodule_clean"])} | tracked diff/statusの有無を確認 |

## 総合判定

**{mark(overall_pass)}**

PASSは，固定環境においてビルド，`INIWriter.*` 3件，全GoogleTest 27件，
CTestおよび元コード復元がすべて成功したことを示す．

この判定は既存テストスイートが観測する範囲での正当性を示すものであり，
未検証機能を含む完全な意味的等価性を保証しない．

## 生ログ

詳細な標準出力・標準エラーはGit管理対象外の
`logs/ini-writer-minimal/{RUN_ID}/`に保存した．
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Temporarily replace INIWriter::write with the generated body, "
            "evaluate it in the fixed Docker environment, and restore the source."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite evaluation outputs for this fixed run.",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    experiment_root = project_root / "experiments" / EXPERIMENT_ID
    evaluation_root = experiment_root / "evaluation"
    raw_log_root = project_root / "logs" / EXPERIMENT_ID / RUN_ID
    repository = project_root / "repos" / "ini-cpp"
    googletest = repository / "googletest"
    source_path = repository / "ini" / "ini.h"
    generated_body_path = experiment_root / "generated" / "regenerated_write_body.cpp"
    expected_hash_path = experiment_root / "backup" / "original_sha256.txt"

    output_paths = [
        evaluation_root / "replacement_diff.patch",
        evaluation_root / "source_replacement.json",
        evaluation_root / "build_result.json",
        evaluation_root / "direct_test_result.json",
        evaluation_root / "full_test_result.json",
        evaluation_root / "ctest_result.json",
        evaluation_root / "evaluation_summary.md",
        evaluation_root / "evaluation_manifest.json",
        evaluation_root / "evaluation_error.json",
    ]
    ensure_outputs_absent(output_paths, args.force)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    raw_log_root.mkdir(parents=True, exist_ok=True)

    if not generated_body_path.exists():
        raise FileNotFoundError(f"Generated body not found: {generated_body_path}")
    if not expected_hash_path.exists():
        raise FileNotFoundError(f"Original SHA-256 record not found: {expected_hash_path}")

    repository_head = git_output(repository, "rev-parse", "HEAD")
    googletest_head = git_output(googletest, "rev-parse", "HEAD")
    assert_equal("ini-cpp commit", repository_head, EXPECTED_REPOSITORY_COMMIT)
    assert_equal(
        "googletest commit",
        googletest_head,
        EXPECTED_GOOGLETEST_COMMIT,
    )

    tracked_status_before = git_output(
        repository, "status", "--short", "--untracked-files=no"
    )
    googletest_status_before = git_output(
        googletest, "status", "--short", "--untracked-files=no"
    )
    if tracked_status_before:
        raise RuntimeError(
            "ini-cpp has tracked changes before evaluation:\n"
            + tracked_status_before
        )
    if googletest_status_before:
        raise RuntimeError(
            "googletest has tracked changes before evaluation:\n"
            + googletest_status_before
        )

    inspect = run_process(
        ["docker", "image", "inspect", "--format={{.Id}}", IMAGE],
        check=True,
    )
    image_id = inspect.stdout.strip()
    assert_equal("Docker image ID", image_id, EXPECTED_IMAGE_ID)

    original_bytes = source_path.read_bytes()
    original_sha256 = sha256_bytes(original_bytes)
    normalized_original_bytes = original_bytes.replace(b"\r\n", b"\n")
    normalized_original_sha256 = sha256_bytes(normalized_original_bytes)
    expected_source_sha256 = read_text(expected_hash_path).strip().split()[0].lower()

    # Windows Git may check out the tracked file with CRLF even though the
    # repository blob and the original experiment record use LF. Accept only
    # this line-ending-only difference. The exact working-tree bytes are still
    # preserved and restored in the finally block.
    if (
        original_sha256.lower() != expected_source_sha256
        and normalized_original_sha256.lower() != expected_source_sha256
    ):
        raise RuntimeError(
            "Original ini.h SHA-256 mismatch even after CRLF-to-LF "
            "normalization.\n"
            f"Expected:          {expected_source_sha256}\n"
            f"Working tree:      {original_sha256.lower()}\n"
            f"LF-normalized:     {normalized_original_sha256.lower()}"
        )

    source_text = original_bytes.decode("utf-8")
    newline = "\r\n" if "\r\n" in source_text else "\n"
    open_brace, close_brace = locate_write_body(source_text)

    generated_body = read_text(generated_body_path)
    generated_body_sha256 = sha256_file(generated_body_path)
    replacement_body = indent_generated_body(generated_body, "        ", newline)
    replacement = newline + replacement_body + newline + "    "
    modified_text = (
        source_text[: open_brace + 1]
        + replacement
        + source_text[close_brace:]
    )
    modified_bytes = modified_text.encode("utf-8")
    modified_sha256 = sha256_bytes(modified_bytes)

    source_info = {
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "source_path": "repos/ini-cpp/ini/ini.h",
        "original_source_sha256": original_sha256,
        "lf_normalized_original_source_sha256": normalized_original_sha256,
        "expected_original_source_sha256": expected_source_sha256,
        "source_hash_match_mode": (
            "exact"
            if original_sha256.lower() == expected_source_sha256
            else "crlf_to_lf_normalized"
        ),
        "generated_body_path": (
            "experiments/ini-writer-minimal/generated/"
            "regenerated_write_body.cpp"
        ),
        "generated_body_sha256": generated_body_sha256,
        "write_open_brace_offset": open_brace,
        "write_close_brace_offset": close_brace,
        "modified_source_sha256": modified_sha256,
        "replacement_policy": (
            "Only the text between the outer braces of INIWriter::write "
            "was replaced. No generated-code repair was performed."
        ),
    }

    configure_record: dict[str, Any] = {
        "stage": "configure",
        "exit_code": None,
        "passed": False,
        "skipped": True,
    }
    build_record: dict[str, Any] = {
        "stage": "build",
        "exit_code": None,
        "passed": False,
        "skipped": True,
    }
    direct_record: dict[str, Any] = {
        "stage": "direct_test",
        "exit_code": None,
        "passed": False,
        "skipped": True,
        "gtest": {},
    }
    full_record: dict[str, Any] = {
        "stage": "full_test",
        "exit_code": None,
        "passed": False,
        "skipped": True,
        "gtest": {},
    }
    ctest_record: dict[str, Any] = {
        "stage": "ctest",
        "exit_code": None,
        "passed": False,
        "skipped": True,
    }
    restoration = {
        "restored": False,
        "restored_sha256": None,
        "submodule_clean": False,
        "tracked_status_after": None,
        "googletest_status_after": None,
    }
    evaluation_error: dict[str, Any] | None = None

    try:
        source_path.write_bytes(modified_bytes)

        diff = git_output(repository, "diff", "--", "ini/ini.h")
        write_text(evaluation_root / "replacement_diff.patch", diff + "\n")
        write_json(evaluation_root / "source_replacement.json", source_info)

        configure_raw = run_docker_stage(
            project_root=project_root,
            shell_command=(
                "rm -rf build && "
                "cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug"
            ),
            name="configure",
            raw_log_root=raw_log_root,
        )
        configure_record = public_stage_record(configure_raw)
        configure_record["passed"] = configure_raw["exit_code"] == 0
        configure_record["skipped"] = False
        write_json(evaluation_root / "build_result.json", {
            "configure": configure_record,
            "build": build_record,
        })

        if configure_record["passed"]:
            build_raw = run_docker_stage(
                project_root=project_root,
                shell_command="cmake --build build --parallel",
                name="build",
                raw_log_root=raw_log_root,
            )
            build_record = public_stage_record(build_raw)
            build_record["passed"] = build_raw["exit_code"] == 0
            build_record["skipped"] = False
            write_json(evaluation_root / "build_result.json", {
                "configure": configure_record,
                "build": build_record,
            })

        if build_record["passed"]:
            direct_raw = run_docker_stage(
                project_root=project_root,
                shell_command=(
                    "rm -rf build/test/fixtures && "
                    "cp -a test/fixtures build/test/fixtures && "
                    "cd build/test && "
                    "./all_test --gtest_color=no "
                    "--gtest_filter='INIWriter.*'"
                ),
                name="direct_test",
                raw_log_root=raw_log_root,
            )
            direct_counts = parse_gtest(
                direct_raw["_stdout"] + "\n" + direct_raw["_stderr"]
            )
            direct_record = public_stage_record(direct_raw)
            direct_record["gtest"] = direct_counts
            direct_record["expected_tests"] = EXPECTED_DIRECT_TESTS
            direct_record["passed"] = (
                direct_raw["exit_code"] == 0
                and direct_counts["tests_ran"] == EXPECTED_DIRECT_TESTS
                and direct_counts["tests_passed"] == EXPECTED_DIRECT_TESTS
                and direct_counts["tests_failed"] == 0
            )
            direct_record["skipped"] = False
            write_json(
                evaluation_root / "direct_test_result.json",
                direct_record,
            )

            full_raw = run_docker_stage(
                project_root=project_root,
                shell_command=(
                    "rm -rf build/test/fixtures && "
                    "cp -a test/fixtures build/test/fixtures && "
                    "cd build/test && "
                    "./all_test --gtest_color=no"
                ),
                name="full_test",
                raw_log_root=raw_log_root,
            )
            full_counts = parse_gtest(
                full_raw["_stdout"] + "\n" + full_raw["_stderr"]
            )
            full_record = public_stage_record(full_raw)
            full_record["gtest"] = full_counts
            full_record["expected_tests"] = EXPECTED_FULL_TESTS
            full_record["passed"] = (
                full_raw["exit_code"] == 0
                and full_counts["tests_ran"] == EXPECTED_FULL_TESTS
                and full_counts["tests_passed"] == EXPECTED_FULL_TESTS
                and full_counts["tests_failed"] == 0
            )
            full_record["skipped"] = False
            write_json(
                evaluation_root / "full_test_result.json",
                full_record,
            )

            ctest_raw = run_docker_stage(
                project_root=project_root,
                shell_command=(
                    "rm -rf build/test/fixtures && "
                    "cp -a test/fixtures build/test/fixtures && "
                    "ctest --test-dir build/test --output-on-failure"
                ),
                name="ctest",
                raw_log_root=raw_log_root,
            )
            ctest_output = ctest_raw["_stdout"] + "\n" + ctest_raw["_stderr"]
            ctest_record = public_stage_record(ctest_raw)
            ctest_record["passed"] = (
                ctest_raw["exit_code"] == 0
                and re.search(
                    r"100%\s+tests\s+passed,\s+0\s+tests\s+failed",
                    ctest_output,
                )
                is not None
            )
            ctest_record["skipped"] = False
            write_json(evaluation_root / "ctest_result.json", ctest_record)

    except Exception as error:
        evaluation_error = {
            "occurred_at_utc": utc_now(),
            "error_type": type(error).__name__,
            "error": str(error),
        }
        write_json(evaluation_root / "evaluation_error.json", evaluation_error)
    finally:
        source_path.write_bytes(original_bytes)
        restored_sha256 = sha256_file(source_path)
        tracked_status_after = git_output(
            repository, "status", "--short", "--untracked-files=no"
        )
        googletest_status_after = git_output(
            googletest, "status", "--short", "--untracked-files=no"
        )
        restoration = {
            "restored": restored_sha256 == original_sha256,
            "restored_sha256": restored_sha256,
            "expected_sha256": original_sha256,
            "submodule_clean": (
                tracked_status_after == "" and googletest_status_after == ""
            ),
            "tracked_status_after": tracked_status_after,
            "googletest_status_after": googletest_status_after,
        }

    # Persist all stage records, including skipped stages, so that a failed
    # build still leaves a complete and auditable evaluation record.
    write_json(evaluation_root / "build_result.json", {
        "configure": configure_record,
        "build": build_record,
    })
    write_json(evaluation_root / "direct_test_result.json", direct_record)
    write_json(evaluation_root / "full_test_result.json", full_record)
    write_json(evaluation_root / "ctest_result.json", ctest_record)

    overall_pass = (
        evaluation_error is None
        and configure_record.get("passed", False)
        and build_record.get("passed", False)
        and direct_record.get("passed", False)
        and full_record.get("passed", False)
        and ctest_record.get("passed", False)
        and restoration["restored"]
        and restoration["submodule_clean"]
    )

    manifest = {
        "schema_version": "1.0",
        "experiment_id": EXPERIMENT_ID,
        "run_id": RUN_ID,
        "completed_at_utc": utc_now(),
        "repository_commit": EXPECTED_REPOSITORY_COMMIT,
        "googletest_commit": EXPECTED_GOOGLETEST_COMMIT,
        "docker_image": IMAGE,
        "docker_image_id": image_id,
        "expected_direct_tests": EXPECTED_DIRECT_TESTS,
        "expected_full_tests": EXPECTED_FULL_TESTS,
        "overall_pass": overall_pass,
        "evaluation_error": evaluation_error,
        "restoration": restoration,
        "git_managed_outputs": [
            "experiments/ini-writer-minimal/evaluation/replacement_diff.patch",
            "experiments/ini-writer-minimal/evaluation/source_replacement.json",
            "experiments/ini-writer-minimal/evaluation/build_result.json",
            "experiments/ini-writer-minimal/evaluation/direct_test_result.json",
            "experiments/ini-writer-minimal/evaluation/full_test_result.json",
            "experiments/ini-writer-minimal/evaluation/ctest_result.json",
            "experiments/ini-writer-minimal/evaluation/evaluation_summary.md",
            "experiments/ini-writer-minimal/evaluation/evaluation_manifest.json",
        ],
        "local_raw_log_directory": (
            f"logs/ini-writer-minimal/{RUN_ID}/"
        ),
    }
    write_json(evaluation_root / "evaluation_manifest.json", manifest)

    summary = build_summary(
        source_info=source_info,
        configure_result=configure_record,
        build_result=build_record,
        direct_result=direct_record,
        full_result=full_record,
        ctest_result=ctest_record,
        overall_pass=overall_pass,
        restoration=restoration,
    )
    write_text(evaluation_root / "evaluation_summary.md", summary)

    print(summary)
    print(f"Evaluation outputs: {evaluation_root}")
    print(f"Local raw logs:     {raw_log_root}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
