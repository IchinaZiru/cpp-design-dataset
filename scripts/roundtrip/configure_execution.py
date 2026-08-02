from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from roundtrip_common import (
    docker_image_id,
    docker_run,
    git_output,
    load_json,
    locate_class_span,
    read_text,
    write_json,
    write_text,
)


REPOSITORIES = {
    "Echo-Web-Server": {
        "path": "repos/Echo-Web-Server",
        "image": "cpp-roundtrip-env:echo-web-server-v2",
        "configure": (
            "rm -rf build && "
            "cmake -S . -B build "
            "-DCMAKE_BUILD_TYPE=Debug "
            "-DECHO_WEB_SERVER_BUILD_TESTS=ON "
            "-DCMAKE_PROJECT_INCLUDE="
            "/workspace/configs/roundtrip/cmake/echo_web_server_gtest.cmake"
        ),
        "build": "cmake --build build --parallel",
        "full": "ctest --test-dir build --output-on-failure",
        "full_kind": "ctest",
        "expected_full": 63,
        "direct_template": (
            "exe=$(find build -type f -name test-bundle -perm -111 | head -n 1); "
            "test -n \"$exe\"; \"$exe\" --gtest_color=no --gtest_filter='{filter}'"
        ),
    },
    "ini-cpp": {
        "path": "repos/ini-cpp",
        "image": "cpp-roundtrip-env:ini-cpp-v2",
        "configure": "rm -rf build && cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug",
        "build": "cmake --build build --parallel",
        "full": (
            "rm -rf build/test/fixtures && cp -a test/fixtures build/test/fixtures && "
            "cd build/test && ./all_test --gtest_color=no"
        ),
        "full_kind": "gtest",
        "expected_full": 27,
        "direct_template": (
            "rm -rf build/test/fixtures && cp -a test/fixtures build/test/fixtures && "
            "cd build/test && ./all_test --gtest_color=no --gtest_filter='{filter}'"
        ),
    },
    "RISCV-Simulator": {
        "path": "repos/RISCV-Simulator",
        "image": "cpp-roundtrip-env:ubuntu22.04",
        "configure": "rm -rf build && cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug",
        "build": "cmake --build build --parallel",
        "full": "ctest --test-dir build --output-on-failure",
        "full_kind": "ctest",
        "expected_full": 18,
        "direct_template": (
            "exe=''; while IFS= read -r candidate; do "
            "if \"$candidate\" --gtest_list_tests 2>/dev/null | grep -q '^{suite}\\.'; "
            "then exe=\"$candidate\"; break; fi; done < <(find build -type f -perm -111); "
            "test -n \"$exe\"; \"$exe\" --gtest_color=no --gtest_filter='{filter}'"
        ),
    },
}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def scan_classes(repository: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in repository.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".h", ".hh", ".hpp", ".hxx"}:
            continue
        if any(part in {"build", ".git", "third_party", "vendor"} for part in path.parts):
            continue
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        for match in re.finditer(r"\b(?:class|struct)\s+([A-Za-z_][A-Za-z0-9_]*)\b", text):
            result.setdefault(match.group(1), []).append(path.relative_to(repository).as_posix())
    return result


def scan_gtests(repository: Path) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    pattern = re.compile(
        r"\bTEST(?:_F|_P)?\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
    )
    for path in repository.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".cc", ".cpp", ".cxx"}:
            continue
        if any(part in {"build", ".git"} for part in path.parts):
            continue
        try:
            text = read_text(path)
        except UnicodeDecodeError:
            continue
        for suite, test in pattern.findall(text):
            result.setdefault(suite, []).append(f"{suite}.{test}")
    return result


def infer_symbol(target_name: str, classes: dict[str, list[str]]) -> tuple[str | None, list[str]]:
    wanted = normalize(target_name)
    matches = [name for name in classes if normalize(name) == wanted]
    if len(matches) == 1:
        return matches[0], classes[matches[0]]
    contains = [name for name in classes if wanted in normalize(name) or normalize(name) in wanted]
    if len(contains) == 1:
        return contains[0], classes[contains[0]]
    return None, []


def infer_tests(target_name: str, tests: dict[str, list[str]]) -> tuple[str | None, list[str]]:
    wanted = normalize(target_name)
    suites = [suite for suite in tests if normalize(suite) == wanted]
    if not suites:
        suites = [suite for suite in tests if wanted in normalize(suite) or normalize(suite) in wanted]
    if len(suites) != 1:
        return None, []
    suite = suites[0]
    return suite, tests[suite]


def parse_draft(path: Path) -> dict[str, Any]:
    return load_json(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Finalize execution configs from draft target configs and local repositories."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--probe", action="store_true", help="Run baseline configure/build/full/direct tests before enabling configs.")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Limit configuration/probing to one target_id. Repeat for multiple targets.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing finalized configs.")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    draft_dir = project_root / "configs" / "roundtrip" / "targets"
    report_dir = project_root / "reports" / "batch"
    log_root = project_root / "logs" / "roundtrip-configure"
    rows: list[dict[str, Any]] = []

    repo_cache: dict[str, dict[str, Any]] = {}

    selected_targets = set(args.target)

    for draft_path in sorted(draft_dir.glob("*.draft.json")):
        draft = parse_draft(draft_path)
        repository_id = str(draft["repository_id"])
        repo_cfg = REPOSITORIES.get(repository_id)
        target_id = str(draft["target_id"])
        if selected_targets and target_id not in selected_targets:
            continue
        status = "blocked"
        reasons: list[str] = []

        if repo_cfg is None:
            reasons.append("repository execution template missing")
            rows.append({"target_id": target_id, "status": status, "reasons": reasons})
            continue

        repository = project_root / repo_cfg["path"]
        if not repository.exists():
            reasons.append(f"repository missing: {repo_cfg['path']}")
            rows.append({"target_id": target_id, "status": status, "reasons": reasons})
            continue

        cache = repo_cache.setdefault(repository_id, {})
        if "classes" not in cache:
            cache["classes"] = scan_classes(repository)
            cache["tests"] = scan_gtests(repository)
            cache["head"] = git_output(repository, "rev-parse", "HEAD")
            cache["image_id"] = docker_image_id(repo_cfg["image"])

        granularity = str(draft.get("granularity") or "")
        source_files = [str(item) for item in draft.get("source_files", [])]
        locator: dict[str, Any] = {}

        if granularity == "class_span":
            symbol, discovered_files = infer_symbol(str(draft["target_name"]), cache["classes"])
            if symbol is None:
                reasons.append("class symbol could not be inferred uniquely")
            else:
                locator = {"kind": "class", "symbol": symbol}
                if not source_files:
                    source_files = discovered_files
                definition_files: list[str] = []
                for relative in source_files:
                    path = repository / relative
                    if not path.exists():
                        continue
                    try:
                        locate_class_span(read_text(path), symbol)
                        definition_files.append(relative)
                    except ValueError:
                        pass
                if len(definition_files) != 1:
                    reasons.append(f"expected one class definition file, found {len(definition_files)}")
                else:
                    source_files = definition_files
        elif granularity == "module_files":
            missing_files = [relative for relative in source_files if not (repository / relative).exists()]
            if missing_files:
                reasons.append("missing source files: " + ", ".join(missing_files))
        else:
            reasons.append(f"unsupported granularity: {granularity or 'empty'}")

        direct_names = [str(item) for item in draft.get("evaluation", {}).get("direct_test_names", [])]
        direct_filter = str(draft.get("evaluation", {}).get("direct_test_filter") or "")
        suite = None
        if not direct_names or not direct_filter:
            suite, inferred_names = infer_tests(str(draft["target_name"]), cache["tests"])
            if inferred_names:
                direct_names = inferred_names
                direct_filter = ":".join(inferred_names)
        else:
            suite = direct_names[0].split(".", 1)[0] if direct_names else None

        expected_direct = draft.get("evaluation", {}).get("expected_direct_tests")
        if expected_direct is None:
            expected_direct = len(direct_names) if direct_names else None
        if not direct_filter or expected_direct is None:
            reasons.append("direct tests could not be inferred")

        direct_command = repo_cfg["direct_template"].format(
            filter=direct_filter,
            suite=suite or str(draft["target_name"]),
        )

        stage_timeouts = {
            "configure": 300,
            "build": 600,
            "direct_test": 300,
            "full_test": 600,
        }

        final_config = {
            "schema_version": "3.0",
            "enabled": False,
            "target_id": target_id,
            "experiment_id": f"{target_id}-roundtrip",
            "run_id": f"{target_id}-qwen25coder32b-001",
            "repository_id": repository_id,
            "repository_path": repo_cfg["path"],
            "repository_commit": cache["head"],
            "target_name": draft["target_name"],
            "adoption_status": draft.get("adoption_status"),
            "granularity": granularity,
            "source_files": source_files,
            "locator": locator,
            "test_files": draft.get("test_files", []),
            "model": draft.get("model", {}),
            "evaluation": {
                "docker_image": repo_cfg["image"],
                "docker_image_id": cache["image_id"],
                "configure_command": repo_cfg["configure"],
                "build_command": repo_cfg["build"],
                "direct_test_command": direct_command,
                "full_test_command": repo_cfg["full"],
                "full_test_kind": repo_cfg["full_kind"],
                "direct_test_filter": direct_filter,
                "direct_test_names": direct_names,
                "expected_direct_tests": expected_direct,
                "expected_full_tests": draft.get("evaluation", {}).get("expected_full_tests") or repo_cfg["expected_full"],
                "stage_timeouts_seconds": stage_timeouts,
            },
            "readiness": {
                "configured": not reasons,
                "reasons": reasons,
                "baseline_probed": False,
            },
        }

        final_path = draft_dir / f"{target_id}.json"
        if final_path.exists() and not args.force:
            reasons.append("final config already exists; use --force to replace")
        elif not reasons:
            if args.probe:
                probe_root = log_root / repository_id / target_id
                configure = docker_run(
                    project_root=project_root,
                    repository_path=repo_cfg["path"],
                    image=repo_cfg["image"],
                    shell_command=repo_cfg["configure"],
                    log_root=probe_root,
                    stage="configure",
                    timeout_seconds=stage_timeouts["configure"],
                )
                build = docker_run(
                    project_root=project_root,
                    repository_path=repo_cfg["path"],
                    image=repo_cfg["image"],
                    shell_command=repo_cfg["build"],
                    log_root=probe_root,
                    stage="build",
                    timeout_seconds=stage_timeouts["build"],
                ) if configure["passed"] else {"passed": False}
                full = docker_run(
                    project_root=project_root,
                    repository_path=repo_cfg["path"],
                    image=repo_cfg["image"],
                    shell_command=repo_cfg["full"],
                    log_root=probe_root,
                    stage="full",
                    timeout_seconds=stage_timeouts["full_test"],
                ) if build["passed"] else {"passed": False}
                direct = docker_run(
                    project_root=project_root,
                    repository_path=repo_cfg["path"],
                    image=repo_cfg["image"],
                    shell_command=direct_command,
                    log_root=probe_root,
                    stage="direct",
                    timeout_seconds=stage_timeouts["direct_test"],
                ) if build["passed"] else {"passed": False}
                baseline_ok = all(item.get("passed") is True for item in (configure, build, full, direct))
                final_config["readiness"]["baseline_probed"] = True
                final_config["readiness"]["baseline_passed"] = baseline_ok
                if not baseline_ok:
                    reasons.append("baseline probe failed")
                else:
                    final_config["enabled"] = True
                    final_config["readiness"]["configured"] = True
                    status = "ready"
            else:
                final_config["enabled"] = False
                final_config["readiness"]["configured"] = True
                status = "configured_unprobed"

            if reasons:
                status = "blocked"
            write_json(final_path, final_config)
        rows.append({"target_id": target_id, "repository_id": repository_id, "status": status, "reasons": reasons})

    report_dir.mkdir(parents=True, exist_ok=True)
    csv_path = report_dir / "execution_config_readiness.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["repository_id", "target_id", "status", "reasons"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "reasons": ";".join(row["reasons"])})

    md = [
        "# Execution configuration readiness",
        "",
        "| repository | target | status | reasons |",
        "|---|---|---|---|",
    ]
    for row in rows:
        md.append(
            f"| {row.get('repository_id', '')} | {row['target_id']} | {row['status']} | "
            f"{'<br>'.join(row['reasons']) if row['reasons'] else '-'} |"
        )
    write_text(report_dir / "execution_config_readiness.md", "\n".join(md) + "\n")

    ready = sum(row["status"] == "ready" for row in rows)
    blocked = sum(row["status"] == "blocked" for row in rows)
    print(f"Execution configs: ready={ready}, blocked={blocked}")
    print(f"Report: {report_dir / 'execution_config_readiness.md'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
