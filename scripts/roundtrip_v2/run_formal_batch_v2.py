from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
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


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n"
            f"STDOUT:\n{result.stdout or ''}\nSTDERR:\n{result.stderr or ''}"
        )
    return result


def git_output(repository: Path, *args: str) -> str:
    return run_command(
        ["git", "-C", str(repository), *args],
        capture=True,
    ).stdout.strip()


def parent_tracked_clean(project_root: Path) -> None:
    status = git_output(project_root, "status", "--short", "--untracked-files=no")
    if status:
        raise RuntimeError(f"Parent repository has tracked changes:\n{status}")


def repository_tracked_clean(repository: Path) -> None:
    status = git_output(
        repository,
        "status",
        "--short",
        "--untracked-files=no",
    )
    if status:
        raise RuntimeError(f"Target repository has tracked changes:\n{status}")


def inspect_docker_image(image: str) -> str:
    result = run_command(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        capture=True,
    )
    return result.stdout.strip()


def verify_runtime_preconditions(project_root: Path, manifest: dict[str, Any]) -> None:
    parent_tracked_clean(project_root)
    run_command(["ollama", "show", "qwen2.5-coder:32b"], capture=True)

    checked_repositories: set[tuple[str, str]] = set()
    checked_images: set[tuple[str, str]] = set()
    for target in manifest["targets"]:
        config_path = project_root / target["conditions"]["non_rag"]["config_path"]
        config = read_json(config_path)
        repository = project_root / config["repository_path"]
        key = (str(repository), config["repository_commit"])
        if key not in checked_repositories:
            if not repository.is_dir():
                raise FileNotFoundError(repository)
            repository_tracked_clean(repository)
            head = git_output(repository, "rev-parse", "HEAD")
            if head != config["repository_commit"]:
                raise RuntimeError(
                    f"Repository commit mismatch: {repository}: {head} != "
                    f"{config['repository_commit']}"
                )
            checked_repositories.add(key)

        evaluation = config["evaluation"]
        image_key = (evaluation["docker_image"], evaluation["docker_image_id"])
        if image_key not in checked_images:
            actual = inspect_docker_image(evaluation["docker_image"])
            if actual != evaluation["docker_image_id"]:
                raise RuntimeError(
                    f"Docker image mismatch for {evaluation['docker_image']}: "
                    f"{actual} != {evaluation['docker_image_id']}"
                )
            checked_images.add(image_key)


def enabled_temp_config(config: dict[str, Any]) -> Path:
    value = dict(config)
    value["enabled"] = True
    handle, name = tempfile.mkstemp(prefix="formal-v2-enabled-", suffix=".json")
    os.close(handle)
    path = Path(name)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def experiment_root_for(project_root: Path, config: dict[str, Any]) -> Path:
    return project_root / "experiments" / config["experiment_id"]




def verify_saved_config(
    config: dict[str, Any],
    experiment_root: Path,
    *,
    allow_missing: bool = False,
) -> None:
    saved_path = experiment_root / "configs" / "target_config.json"
    if not saved_path.is_file():
        if allow_missing:
            return
        raise RuntimeError(f"Saved target config is missing: {saved_path}")
    saved = read_json(saved_path)
    saved["enabled"] = False
    expected = dict(config)
    expected["enabled"] = False
    if saved != expected:
        raise RuntimeError(
            f"Saved run config differs from the committed formal config: {experiment_root}"
        )

def result_artifact(experiment_root: Path) -> tuple[str, Path, dict[str, Any]]:
    evaluation = experiment_root / "evaluation" / "evaluation_manifest.json"
    pipeline = experiment_root / "evaluation" / "pipeline_failure.json"
    if evaluation.is_file() and pipeline.is_file():
        raise RuntimeError(f"Both evaluation and pipeline-failure artifacts exist: {experiment_root}")
    if evaluation.is_file():
        return "evaluation", evaluation, read_json(evaluation)
    if pipeline.is_file():
        return "pipeline_failure", pipeline, read_json(pipeline)
    raise RuntimeError(f"No terminal result artifact exists: {experiment_root}")


def verify_no_retry(kind: str, artifact: dict[str, Any], *, pair_id: str) -> None:
    if kind == "evaluation":
        normalization = artifact.get("code_regeneration_normalization") or {}
        if normalization.get("retry_performed") is not False:
            raise RuntimeError(f"{pair_id}: retry flag is not false")
        if normalization.get("automatic_repair_performed") is not False:
            raise RuntimeError(f"{pair_id}: repair flag is not false")
    else:
        if artifact.get("retry_performed") is not False:
            raise RuntimeError(f"{pair_id}: pipeline retry flag is not false")
        if artifact.get("automatic_repair_performed") is not False:
            raise RuntimeError(f"{pair_id}: pipeline repair flag is not false")


def verify_source_restoration(
    project_root: Path,
    config: dict[str, Any],
    experiment_root: Path,
    kind: str,
    artifact: dict[str, Any],
) -> None:
    repository = project_root / config["repository_path"]
    repository_tracked_clean(repository)

    if kind == "evaluation":
        restoration = artifact.get("restoration") or {}
        if restoration.get("restored") is not True:
            raise RuntimeError(f"Source restoration failed: {experiment_root}")
        if restoration.get("repository_clean") is not True:
            raise RuntimeError(f"Evaluation did not report repository_clean: {experiment_root}")

    backup_root = experiment_root / "backup" / "files"
    if not backup_root.is_dir():
        # A prepare-stage failure can occur before backups are created. The
        # tracked-clean check above is the decisive safety condition.
        return
    for relative in config["source_files"]:
        backup = backup_root / relative
        current = repository / relative
        if not backup.is_file() or not current.is_file():
            raise RuntimeError(f"Missing restoration file for {relative}: {experiment_root}")
        if sha256_file(backup) != sha256_file(current):
            raise RuntimeError(f"Restored source differs from backup: {relative}")


def cleanup_build(repository: Path) -> None:
    build = repository / "build"
    if build.exists():
        shutil.rmtree(build)


def run_one(
    project_root: Path,
    runner: Path,
    config_path: Path,
) -> dict[str, Any]:
    config = read_json(config_path)
    experiment_root = experiment_root_for(project_root, config)

    if experiment_root.exists():
        kind, artifact_path, artifact = result_artifact(experiment_root)
        verify_saved_config(
            config,
            experiment_root,
            allow_missing=(
                kind == "pipeline_failure"
                and artifact.get("failed_stage") == "prepare"
            ),
        )
        verify_no_retry(kind, artifact, pair_id=config["pair_id"])
        verify_source_restoration(
            project_root, config, experiment_root, kind, artifact
        )
        return {
            "status": "existing_terminal_artifact",
            "kind": kind,
            "artifact_path": artifact_path.relative_to(project_root).as_posix(),
            "artifact": artifact,
            "experiment_root": experiment_root,
            "config": config,
        }

    temporary = enabled_temp_config(config)
    try:
        print(
            f"\n=== FORMAL RUN: {config['pair_id']} / {config['condition']} ===",
            flush=True,
        )
        result = run_command(
            [
                sys.executable,
                str(runner),
                "--config",
                str(temporary),
                "--project-root",
                str(project_root),
            ],
            capture=False,
            check=False,
        )
    finally:
        temporary.unlink(missing_ok=True)

    if not experiment_root.exists():
        raise RuntimeError(
            f"Runner exited {result.returncode} without creating experiment directory: "
            f"{experiment_root}"
        )

    kind, artifact_path, artifact = result_artifact(experiment_root)
    verify_saved_config(
        config,
        experiment_root,
        allow_missing=(
            kind == "pipeline_failure" and artifact.get("failed_stage") == "prepare"
        ),
    )
    verify_no_retry(kind, artifact, pair_id=config["pair_id"])
    verify_source_restoration(project_root, config, experiment_root, kind, artifact)
    cleanup_build(project_root / config["repository_path"])
    repository_tracked_clean(project_root / config["repository_path"])

    expected_codes = {0, 1} if kind == "evaluation" else set(range(1, 256))
    if result.returncode not in expected_codes:
        raise RuntimeError(
            f"Unexpected runner exit code {result.returncode} for {experiment_root}"
        )

    return {
        "status": "executed_once",
        "kind": kind,
        "artifact_path": artifact_path.relative_to(project_root).as_posix(),
        "artifact": artifact,
        "experiment_root": experiment_root,
        "config": config,
        "runner_exit_code": result.returncode,
    }


def commit_pair(
    project_root: Path,
    pair_id: str,
    experiment_roots: list[Path],
    *,
    push: bool,
) -> str | None:
    relative_paths = [path.relative_to(project_root).as_posix() for path in experiment_roots]
    run_command(["git", "-C", str(project_root), "add", "--", *relative_paths])
    staged = git_output(project_root, "diff", "--cached", "--name-only")
    if not staged:
        return None
    result = run_command(
        [
            "git",
            "-C",
            str(project_root),
            "commit",
            "-m",
            f"experiment: record formal pair {pair_id}",
        ],
        capture=True,
    )
    print(result.stdout, end="")
    commit = git_output(project_root, "rev-parse", "HEAD")
    if push:
        push_result = run_command(
            ["git", "-C", str(project_root), "push"], capture=True
        )
        print(push_result.stdout, end="")
        if push_result.stderr:
            print(push_result.stderr, end="")
    return commit


def summarize_record(result: dict[str, Any]) -> dict[str, Any]:
    config = result["config"]
    artifact = result["artifact"]
    kind = result["kind"]
    record: dict[str, Any] = {
        "pair_id": config["pair_id"],
        "condition": config["condition"],
        "target_id": config["target_id"],
        "run_id": config["run_id"],
        "experiment_id": config["experiment_id"],
        "granularity": config["granularity"],
        "terminal_artifact_kind": kind,
        "artifact_path": result["artifact_path"],
        "batch_status": result["status"],
        "overall_pass": None,
        "failed_stage": None,
        "error": artifact.get("error"),
    }
    if kind == "evaluation":
        record["overall_pass"] = bool(artifact.get("overall_pass"))
        stages = artifact.get("stages") or {}
        for stage in ("configure", "build", "direct_test", "full_test"):
            record[f"{stage}_passed"] = stages.get(stage, {}).get("passed")
        record["restored"] = (artifact.get("restoration") or {}).get("restored")
    else:
        record["failed_stage"] = artifact.get("failed_stage")
        record["restored"] = True
    return record


def write_summary(project_root: Path, records: list[dict[str, Any]]) -> list[Path]:
    output_root = project_root / "analysis" / "formal_v2"
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "formal_results.json"
    csv_path = output_root / "formal_results.csv"
    markdown_path = output_root / "summary.md"

    write_json(
        json_path,
        {
            "schema_version": "1.0",
            "protocol_id": "full-source-design-knowledge-rag-v2-formal-001",
            "record_count": len(records),
            "records": records,
        },
    )

    fieldnames = sorted({key for record in records for key in record})
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        condition = "rag" if "design_knowledge_rag" in record["condition"] else "non_rag"
        by_pair.setdefault(record["pair_id"], {})[condition] = record

    transitions = {"FAIL->PASS": 0, "PASS->FAIL": 0, "PASS->PASS": 0, "FAIL->FAIL": 0}
    complete_pairs = 0
    for pair in by_pair.values():
        if set(pair) != {"non_rag", "rag"}:
            continue
        complete_pairs += 1
        non_pass = pair["non_rag"].get("overall_pass") is True
        rag_pass = pair["rag"].get("overall_pass") is True
        key = f"{'PASS' if non_pass else 'FAIL'}->{'PASS' if rag_pass else 'FAIL'}"
        transitions[key] += 1

    lines = [
        "# Full-source design RAG v2 formal results",
        "",
        f"- Terminal runs: {len(records)}/34",
        f"- Complete pairs: {complete_pairs}/17",
        "- Retry: none",
        "- Automatic repair: none",
        "",
        "## Pair transitions",
        "",
    ]
    for key in ("FAIL->PASS", "PASS->FAIL", "PASS->PASS", "FAIL->FAIL"):
        lines.append(f"- {key}: {transitions[key]}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return [json_path, csv_path, markdown_path]


def commit_summary(project_root: Path, paths: list[Path], *, push: bool) -> str | None:
    relative = [path.relative_to(project_root).as_posix() for path in paths]
    run_command(["git", "-C", str(project_root), "add", "--", *relative])
    if not git_output(project_root, "diff", "--cached", "--name-only"):
        return None
    run_command(
        [
            "git",
            "-C",
            str(project_root),
            "commit",
            "-m",
            "analysis: summarize formal v2 results",
        ],
        capture=True,
    )
    commit = git_output(project_root, "rev-parse", "HEAD")
    if push:
        run_command(["git", "-C", str(project_root), "push"], capture=True)
    return commit


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the 17 paired v2 formal experiments exactly once. Existing "
            "terminal artifacts are validated and skipped; incomplete directories "
            "are never rerun."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/roundtrip_v2/formal/generation_manifest.json"),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    if not args.execute:
        raise RuntimeError("Formal execution requires the explicit --execute flag")

    project_root = args.project_root.resolve()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = project_root / manifest_path
    manifest = read_json(manifest_path)
    if manifest.get("pair_count") != 17 or manifest.get("config_count") != 34:
        raise RuntimeError("Formal manifest is not the frozen 17-pair inventory")

    runner = project_root / "scripts" / "roundtrip_v2" / "run_target_v2.py"
    verify_runtime_preconditions(project_root, manifest)

    all_records: list[dict[str, Any]] = []
    for target in manifest["targets"]:
        pair_id = target["pair_id"]
        pair_results: list[dict[str, Any]] = []
        stop_after_pair = False

        for condition_key in ("non_rag", "rag"):
            config_path = project_root / target["conditions"][condition_key]["config_path"]
            result = run_one(project_root, runner, config_path)
            pair_results.append(result)
            all_records.append(summarize_record(result))

            if (
                result["kind"] == "pipeline_failure"
                and result["status"] == "executed_once"
            ):
                failed_stage = result["artifact"].get("failed_stage")
                # Preserve the one-shot failure. Prepare failures usually signal
                # a shared environment problem, so stop after freezing the pair's
                # available artifacts. Later-stage failures are valid formal
                # failures, but stopping avoids mass repetition of a shared issue.
                stop_after_pair = True
                print(
                    f"Pipeline failure preserved for {pair_id} at {failed_stage}; "
                    "the same experiment ID will not be rerun.",
                    flush=True,
                )
                break

        commit_pair(
            project_root,
            pair_id,
            [result["experiment_root"] for result in pair_results],
            push=args.push,
        )
        parent_tracked_clean(project_root)

        if stop_after_pair:
            paths = write_summary(project_root, all_records)
            commit_summary(project_root, paths, push=args.push)
            return 2

    summary_paths = write_summary(project_root, all_records)
    commit_summary(project_root, summary_paths, push=args.push)
    print(json.dumps({"completed_runs": len(all_records), "completed_pairs": 17}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
