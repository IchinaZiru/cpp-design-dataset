from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EXPECTED_BRANCH = "experiment/deterministic-exact-contract-v6"
EXPECTED_HEAD = "3c17ad77de563e819208b0f0901cfbd22b91e2fb"
CONFIG_ROOT = Path("configs/roundtrip_v6/formal/non-rag")
DEFAULT_OUT = Path("analysis/v6-baseline-probe")
DEFAULT_LOG_ROOT = Path("logs/v6-baseline-probe")


@dataclass
class GroupRow:
    group_id: str
    repository_id: str
    repository_path: str
    repository_commit: str
    target_count: int
    target_pairs: str
    docker_image: str
    docker_image_id_expected: str
    docker_image_id_actual: str | None
    docker_image_id_match: bool
    configure_pass: bool
    build_pass: bool
    full_test_pass: bool
    full_test_expected: int
    full_test_ran: int | None
    full_test_passed: int | None
    full_test_failed: int | None
    tracked_clean_before: bool
    tracked_clean_after: bool
    source_hashes_unchanged: bool
    overall_pass: bool


@dataclass
class TargetRow:
    pair_id: str
    pair_sequence: int
    repository_id: str
    group_id: str
    expected_direct_tests: int
    direct_test_ran: int | None
    direct_test_passed: int | None
    direct_test_failed: int | None
    direct_test_command_pass: bool
    direct_test_count_match: bool
    direct_test_pass: bool


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"stdout", "stderr"}}


def stable_group_key(config: dict[str, Any]) -> str:
    evaluation = config["evaluation"]
    value = {
        "repository_path": config["repository_path"],
        "repository_commit": config["repository_commit"],
        "docker_image": evaluation["docker_image"],
        "docker_image_id": evaluation["docker_image_id"],
        "configure_command": evaluation["configure_command"],
        "build_command": evaluation["build_command"],
        "full_test_command": evaluation["full_test_command"],
        "full_test_kind": evaluation["full_test_kind"],
        "expected_full_tests": evaluation["expected_full_tests"],
        "stage_timeouts_seconds": evaluation.get("stage_timeouts_seconds") or {},
    }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def load_configs(root: Path) -> list[dict[str, Any]]:
    config_dir = root / CONFIG_ROOT
    if not config_dir.is_dir():
        raise FileNotFoundError(config_dir)
    configs: list[dict[str, Any]] = []
    for path in sorted(config_dir.glob("*.json")):
        config = read_json(path)
        if config.get("enabled") is not False:
            raise RuntimeError(f"Baseline probe requires disabled config: {path}")
        if config.get("formal_result_eligible") is not True:
            raise RuntimeError(f"Expected formal_result_eligible=true: {path}")
        config["_config_path"] = path.relative_to(root).as_posix()
        configs.append(config)
    if len(configs) != 17:
        raise RuntimeError(f"Expected 17 v6 non-RAG configs, found {len(configs)}")
    configs.sort(key=lambda item: int(item.get("pair_sequence", 10**9)))
    pair_ids = [str(item["pair_id"]) for item in configs]
    if len(set(pair_ids)) != 17:
        raise RuntimeError("Duplicate pair_id in v6 non-RAG configs")
    return configs


def repository_source_hashes(root: Path, configs: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    by_repo: dict[str, set[str]] = {}
    for config in configs:
        repo_path = str(config["repository_path"])
        source_files = config.get("source_files") or []
        if not isinstance(source_files, list) or not source_files:
            raise RuntimeError(f"Missing source_files for {config.get('pair_id')}")
        by_repo.setdefault(repo_path, set()).update(str(value) for value in source_files)
    result: dict[str, dict[str, str]] = {}
    for repo_path, files in sorted(by_repo.items()):
        repository = root / repo_path
        result[repo_path] = {}
        for relative in sorted(files):
            path = repository / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            result[repo_path][relative] = sha256_file(path)
    return result


def parse_full_counts(common: Any, kind: str, output: str) -> dict[str, int | None]:
    if kind == "ctest":
        return common.parse_ctest_counts(output)
    if kind == "gtest":
        return common.parse_gtest_counts(output)
    raise ValueError(f"Unsupported full_test_kind: {kind!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description="v6 original-source baseline readiness probe")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    log_root = args.log_root if args.log_root.is_absolute() else root / args.log_root

    common = load_module(
        "v6_baseline_roundtrip_common",
        root / "scripts" / "roundtrip" / "roundtrip_common.py",
    )

    print("=== BASELINE PREFLIGHT ===")
    branch = common.git_output(root, "branch", "--show-current")
    head = common.git_output(root, "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"HEAD   = {head}")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"Wrong branch: {branch} != {EXPECTED_BRANCH}")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"Wrong HEAD: {head} != {EXPECTED_HEAD}")
    if out_dir.exists():
        raise RuntimeError(f"Refusing to overwrite baseline output: {out_dir}")

    configs = load_configs(root)
    source_hashes_before = repository_source_hashes(root, configs)

    repositories: dict[str, dict[str, Any]] = {}
    for config in configs:
        repo_path = str(config["repository_path"])
        repository = root / repo_path
        expected_commit = str(config["repository_commit"])
        actual_commit = common.git_output(repository, "rev-parse", "HEAD")
        tracked_status = common.git_output(repository, "status", "--short", "--untracked-files=no")
        info = repositories.setdefault(
            repo_path,
            {
                "repository_id": str(config["repository_id"]),
                "expected_commit": expected_commit,
                "actual_commit": actual_commit,
                "tracked_status_before": tracked_status,
            },
        )
        if info["expected_commit"] != expected_commit:
            raise RuntimeError(f"Conflicting expected commits for {repo_path}")
        if actual_commit != expected_commit:
            raise RuntimeError(f"Repository commit mismatch: {repo_path}: {actual_commit} != {expected_commit}")
        if tracked_status:
            raise RuntimeError(f"Repository has tracked changes before baseline probe: {repo_path}\n{tracked_status}")

    groups: dict[str, list[dict[str, Any]]] = {}
    for config in configs:
        groups.setdefault(stable_group_key(config), []).append(config)

    print(f"configs = {len(configs)}")
    print(f"evaluation groups = {len(groups)}")

    group_rows: list[GroupRow] = []
    target_rows: list[TargetRow] = []
    group_records: list[dict[str, Any]] = []

    for group_index, (group_hash, members) in enumerate(
        sorted(groups.items(), key=lambda item: min(int(row["pair_sequence"]) for row in item[1])),
        start=1,
    ):
        exemplar = members[0]
        evaluation = exemplar["evaluation"]
        repository = root / str(exemplar["repository_path"])
        group_id = f"g{group_index:02d}-{group_hash}"
        group_log_root = log_root / group_id
        timeouts = {
            "configure": 300,
            "build": 600,
            "direct_test": 300,
            "full_test": 600,
        }
        timeouts.update(evaluation.get("stage_timeouts_seconds") or {})

        print()
        print(f"=== GROUP {group_index}/{len(groups)} {group_id} ===")
        print(f"repository = {exemplar['repository_id']}")
        print(f"targets    = {len(members)}")

        actual_image_id: str | None = None
        image_match = False
        try:
            actual_image_id = common.docker_image_id(str(evaluation["docker_image"]))
            image_match = actual_image_id == str(evaluation["docker_image_id"])
        except Exception as exc:
            print(f"docker image check FAIL: {exc}")

        tracked_before = common.git_output(repository, "status", "--short", "--untracked-files=no") == ""
        configure_record: dict[str, Any]
        build_record: dict[str, Any]
        full_record: dict[str, Any]

        if image_match:
            configure_record = common.docker_run(
                project_root=root,
                repository_path=str(exemplar["repository_path"]),
                image=str(evaluation["docker_image"]),
                shell_command=str(evaluation["configure_command"]),
                log_root=group_log_root,
                stage="configure",
                timeout_seconds=int(timeouts["configure"]),
            )
        else:
            configure_record = {
                "stage": "configure",
                "passed": False,
                "skipped": True,
                "reason": "docker_image_id_mismatch_or_unavailable",
            }

        if configure_record.get("passed"):
            build_record = common.docker_run(
                project_root=root,
                repository_path=str(exemplar["repository_path"]),
                image=str(evaluation["docker_image"]),
                shell_command=str(evaluation["build_command"]),
                log_root=group_log_root,
                stage="build",
                timeout_seconds=int(timeouts["build"]),
            )
        else:
            build_record = {
                "stage": "build",
                "passed": False,
                "skipped": True,
                "reason": "configure_failed",
            }

        for member in sorted(members, key=lambda row: int(row["pair_sequence"])):
            direct_eval = member["evaluation"]
            pair_id = str(member["pair_id"])
            expected_direct = int(direct_eval["expected_direct_tests"])
            if build_record.get("passed"):
                direct_record = common.docker_run(
                    project_root=root,
                    repository_path=str(member["repository_path"]),
                    image=str(direct_eval["docker_image"]),
                    shell_command=str(direct_eval["direct_test_command"]),
                    log_root=group_log_root / "direct",
                    stage=pair_id,
                    timeout_seconds=int((direct_eval.get("stage_timeouts_seconds") or {}).get("direct_test", 300)),
                )
                direct_output = str(direct_record.get("stdout", "")) + "\n" + str(direct_record.get("stderr", ""))
                direct_counts = common.parse_gtest_counts(direct_output)
            else:
                direct_record = {
                    "stage": pair_id,
                    "passed": False,
                    "skipped": True,
                    "reason": "build_failed",
                }
                direct_counts = {"ran": None, "passed": None, "failed": None}

            direct_count_match = (
                direct_counts.get("ran") == expected_direct
                and direct_counts.get("passed") == expected_direct
                and direct_counts.get("failed") == 0
            )
            direct_pass = bool(direct_record.get("passed")) and direct_count_match
            target_rows.append(
                TargetRow(
                    pair_id=pair_id,
                    pair_sequence=int(member["pair_sequence"]),
                    repository_id=str(member["repository_id"]),
                    group_id=group_id,
                    expected_direct_tests=expected_direct,
                    direct_test_ran=direct_counts.get("ran"),
                    direct_test_passed=direct_counts.get("passed"),
                    direct_test_failed=direct_counts.get("failed"),
                    direct_test_command_pass=bool(direct_record.get("passed")),
                    direct_test_count_match=direct_count_match,
                    direct_test_pass=direct_pass,
                )
            )
            print(
                f"direct {pair_id:36s} "
                f"command={'PASS' if direct_record.get('passed') else 'FAIL'} "
                f"count={direct_counts.get('ran')}/{expected_direct} "
                f"verdict={'PASS' if direct_pass else 'FAIL'}"
            )

        if build_record.get("passed"):
            full_record = common.docker_run(
                project_root=root,
                repository_path=str(exemplar["repository_path"]),
                image=str(evaluation["docker_image"]),
                shell_command=str(evaluation["full_test_command"]),
                log_root=group_log_root,
                stage="full_test",
                timeout_seconds=int(timeouts["full_test"]),
            )
            full_output = str(full_record.get("stdout", "")) + "\n" + str(full_record.get("stderr", ""))
            full_counts = parse_full_counts(common, str(evaluation["full_test_kind"]), full_output)
        else:
            full_record = {
                "stage": "full_test",
                "passed": False,
                "skipped": True,
                "reason": "build_failed",
            }
            full_counts = {"ran": None, "passed": None, "failed": None}

        expected_full = int(evaluation["expected_full_tests"])
        full_count_match = (
            full_counts.get("ran") == expected_full
            and full_counts.get("passed") == expected_full
            and full_counts.get("failed") == 0
        )
        full_pass = bool(full_record.get("passed")) and full_count_match

        tracked_after = common.git_output(repository, "status", "--short", "--untracked-files=no") == ""
        current_hashes = {
            relative: sha256_file(repository / relative)
            for relative in source_hashes_before[str(exemplar["repository_path"])]
        }
        source_unchanged = current_hashes == source_hashes_before[str(exemplar["repository_path"])]

        member_direct_pass = all(
            row.direct_test_pass for row in target_rows if row.group_id == group_id
        )
        overall_group = (
            image_match
            and bool(configure_record.get("passed"))
            and bool(build_record.get("passed"))
            and full_pass
            and member_direct_pass
            and tracked_before
            and tracked_after
            and source_unchanged
        )

        group_rows.append(
            GroupRow(
                group_id=group_id,
                repository_id=str(exemplar["repository_id"]),
                repository_path=str(exemplar["repository_path"]),
                repository_commit=str(exemplar["repository_commit"]),
                target_count=len(members),
                target_pairs=",".join(str(row["pair_id"]) for row in sorted(members, key=lambda row: int(row["pair_sequence"]))),
                docker_image=str(evaluation["docker_image"]),
                docker_image_id_expected=str(evaluation["docker_image_id"]),
                docker_image_id_actual=actual_image_id,
                docker_image_id_match=image_match,
                configure_pass=bool(configure_record.get("passed")),
                build_pass=bool(build_record.get("passed")),
                full_test_pass=full_pass,
                full_test_expected=expected_full,
                full_test_ran=full_counts.get("ran"),
                full_test_passed=full_counts.get("passed"),
                full_test_failed=full_counts.get("failed"),
                tracked_clean_before=tracked_before,
                tracked_clean_after=tracked_after,
                source_hashes_unchanged=source_unchanged,
                overall_pass=overall_group,
            )
        )
        group_records.append(
            {
                "group_id": group_id,
                "pairs": [str(row["pair_id"]) for row in sorted(members, key=lambda row: int(row["pair_sequence"]))],
                "configure": public_record(configure_record),
                "build": public_record(build_record),
                "full_test": public_record(full_record),
                "full_test_counts": full_counts,
            }
        )
        print(
            f"full expected={expected_full} ran={full_counts.get('ran')} "
            f"verdict={'PASS' if full_pass else 'FAIL'}"
        )
        print(f"group verdict = {'PASS' if overall_group else 'FAIL'}")

    source_hashes_after = repository_source_hashes(root, configs)
    all_source_hashes_unchanged = source_hashes_after == source_hashes_before
    repository_after: dict[str, Any] = {}
    for repo_path, info in repositories.items():
        repository = root / repo_path
        repository_after[repo_path] = {
            **info,
            "actual_commit_after": common.git_output(repository, "rev-parse", "HEAD"),
            "tracked_status_after": common.git_output(repository, "status", "--short", "--untracked-files=no"),
        }

    all_direct_pass = len(target_rows) == 17 and all(row.direct_test_pass for row in target_rows)
    all_groups_pass = bool(group_rows) and all(row.overall_pass for row in group_rows)
    all_full_pass = bool(group_rows) and all(row.full_test_pass for row in group_rows)
    repositories_clean_after = all(not info["tracked_status_after"] for info in repository_after.values())
    commits_unchanged = all(
        info["actual_commit_after"] == info["expected_commit"] for info in repository_after.values()
    )
    go = (
        all_direct_pass
        and all_groups_pass
        and all_full_pass
        and all_source_hashes_unchanged
        and repositories_clean_after
        and commits_unchanged
    )

    out_dir.mkdir(parents=True)
    with (out_dir / "groups.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(group_rows[0]).keys()))
        writer.writeheader()
        for row in group_rows:
            writer.writerow(asdict(row))
    with (out_dir / "targets.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(target_rows[0]).keys()))
        writer.writeheader()
        for row in sorted(target_rows, key=lambda item: item.pair_sequence):
            writer.writerow(asdict(row))

    summary = {
        "schema_version": "1.0",
        "audit_type": "v6_original_source_baseline_readiness_probe",
        "formal_llm_generation_performed": False,
        "ollama_called": False,
        "docker_called": True,
        "build_and_test_called": True,
        "branch": branch,
        "head": head,
        "config_root": CONFIG_ROOT.as_posix(),
        "target_count": len(target_rows),
        "evaluation_group_count": len(group_rows),
        "all_configs_disabled": all(config.get("enabled") is False for config in configs),
        "all_direct_tests_pass": all_direct_pass,
        "all_full_tests_pass": all_full_pass,
        "all_evaluation_groups_pass": all_groups_pass,
        "all_source_hashes_unchanged": all_source_hashes_unchanged,
        "repositories_tracked_clean_after": repositories_clean_after,
        "repository_commits_unchanged": commits_unchanged,
        "go_for_preparation_commit": go,
        "go_for_formal_enablement": False,
        "repository_state": repository_after,
        "source_hashes_before": source_hashes_before,
        "source_hashes_after": source_hashes_after,
        "groups": [asdict(row) for row in group_rows],
        "targets": [asdict(row) for row in sorted(target_rows, key=lambda item: item.pair_sequence)],
        "stage_records": group_records,
        "log_root": log_root.relative_to(root).as_posix() if log_root.is_relative_to(root) else str(log_root),
    }
    write_json(out_dir / "summary.json", summary)

    print()
    print("=== BASELINE SUMMARY ===")
    print(f"targets                         = {len(target_rows)}/17")
    print(f"evaluation groups               = {len(group_rows)}")
    print(f"all direct tests PASS           = {all_direct_pass}")
    print(f"all full tests PASS             = {all_full_pass}")
    print(f"all evaluation groups PASS      = {all_groups_pass}")
    print(f"source hashes unchanged         = {all_source_hashes_unchanged}")
    print(f"repositories tracked clean      = {repositories_clean_after}")
    print(f"repository commits unchanged    = {commits_unchanged}")
    print(f"go_for_preparation_commit       = {go}")
    print("go_for_formal_enablement        = False")
    print(f"saved = {(out_dir / 'summary.json').relative_to(root)}")
    print(f"saved = {(out_dir / 'groups.csv').relative_to(root)}")
    print(f"saved = {(out_dir / 'targets.csv').relative_to(root)}")
    print("No LLM or Ollama call was made.")

    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())
