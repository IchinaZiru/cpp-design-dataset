from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGE_ORDER = [
    "prepare",
    "generate_design",
    "regenerate_code",
    "evaluate",
    "generate_report",
    "register_run",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_target_filter(csv_path: Path | None) -> set[str] | None:
    if csv_path is None:
        return None
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        row["target_id"].strip()
        for row in rows
        if row.get("target_id") and row["target_id"].strip()
    }


def execution_missing(config: dict[str, Any]) -> list[str]:
    missing: list[str] = []

    for key in ("target_id", "repository_id", "target_name", "granularity"):
        if not config.get(key):
            missing.append(key)

    readiness = config.get("readiness", {})
    if isinstance(readiness, dict):
        for item in readiness.get("execution_missing", []):
            if item:
                missing.append(str(item))

    commands = config.get("stage_commands")
    if not isinstance(commands, dict):
        missing.append("stage_commands")
    else:
        for stage in STAGE_ORDER:
            value = commands.get(stage)
            if not isinstance(value, list) or not value:
                missing.append(f"stage_commands.{stage}")

    return sorted(set(missing))


def classify_plan(config: dict[str, Any], path: Path) -> tuple[str, list[str]]:
    if path.name.endswith(".draft.json") or config.get("enabled") is not True:
        readiness = config.get("readiness", {})
        missing = (
            list(readiness.get("execution_missing", []))
            if isinstance(readiness, dict)
            else []
        )
        return "draft", sorted(set(str(item) for item in missing if item))

    missing = execution_missing(config)
    return ("blocked", missing) if missing else ("ready", [])


def run_command(
    command: list[str],
    cwd: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    started_at = utc_now()
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    write_text(stdout_path, result.stdout)
    write_text(stderr_path, result.stderr)
    return {
        "command": command,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "elapsed_seconds": elapsed,
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "stdout_log": stdout_path.as_posix(),
        "stderr_log": stderr_path.as_posix(),
    }


def execute_target(
    project_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    config = read_json(config_path)
    target_id = str(config.get("target_id") or config_path.stem)
    status, missing = classify_plan(config, config_path)

    if status != "ready":
        return {
            "target_id": target_id,
            "config_path": config_path.as_posix(),
            "status": "skipped_" + status,
            "missing": missing,
            "stages": [],
        }

    run_id = f"{target_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    log_root = project_root / "logs" / "roundtrip-batch" / run_id
    stage_results: list[dict[str, Any]] = []

    for stage in STAGE_ORDER:
        command = [str(item) for item in config["stage_commands"][stage]]
        record = run_command(
            command,
            project_root,
            log_root / f"{stage}.stdout.txt",
            log_root / f"{stage}.stderr.txt",
        )
        record["stage"] = stage
        stage_results.append(record)
        if not record["passed"]:
            break

    overall_pass = (
        len(stage_results) == len(STAGE_ORDER)
        and all(stage["passed"] for stage in stage_results)
    )
    return {
        "target_id": target_id,
        "run_id": run_id,
        "config_path": config_path.as_posix(),
        "status": "passed" if overall_pass else "failed",
        "missing": [],
        "stages": stage_results,
    }


def markdown_summary(
    title: str,
    results: list[dict[str, Any]],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Generated at: `{utc_now()}`",
        f"- Targets: **{len(results)}**",
        "",
        "| target | status | completed stages | failed stage |",
        "|---|---|---:|---|",
    ]
    for result in results:
        stages = result.get("stages", [])
        failed = next(
            (
                stage.get("stage")
                for stage in stages
                if stage.get("passed") is False
            ),
            "-",
        )
        lines.append(
            f"| {result.get('target_id')} | {result.get('status')} | "
            f"{sum(1 for stage in stages if stage.get('passed'))}/{len(stages)} | "
            f"{failed} |"
        )
    lines.append("")
    return "\n".join(lines)


def csv_summary(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "target_id",
                "run_id",
                "status",
                "completed_stages",
                "stage_count",
                "failed_stage",
                "missing",
                "config_path",
            ],
        )
        writer.writeheader()
        for result in results:
            stages = result.get("stages", [])
            failed = next(
                (
                    stage.get("stage")
                    for stage in stages
                    if stage.get("passed") is False
                ),
                "",
            )
            writer.writerow(
                {
                    "target_id": result.get("target_id"),
                    "run_id": result.get("run_id", ""),
                    "status": result.get("status"),
                    "completed_stages": sum(
                        1 for stage in stages if stage.get("passed")
                    ),
                    "stage_count": len(stages),
                    "failed_stage": failed,
                    "missing": ";".join(result.get("missing", [])),
                    "config_path": result.get("config_path"),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or execute validated round-trip target configs sequentially. "
            "No retry and no automatic repair."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path("configs/roundtrip/targets"),
    )
    parser.add_argument(
        "--targets",
        type=Path,
        default=None,
        help="Optional CSV containing a target_id column used as a filter.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute only configs classified as ready.",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_dir = (
        args.config_dir
        if args.config_dir.is_absolute()
        else project_root / args.config_dir
    )
    target_filter = load_target_filter(
        args.targets
        if args.targets is None or args.targets.is_absolute()
        else project_root / args.targets
    )

    config_paths = sorted(
        path
        for path in config_dir.glob("*.json")
        if not path.name.endswith(".schema.json")
    )
    if not config_paths:
        raise FileNotFoundError(f"No target JSON configs found in {config_dir}")

    results: list[dict[str, Any]] = []
    for config_path in config_paths:
        config = read_json(config_path)
        target_id = str(config.get("target_id") or config_path.stem)
        if target_filter is not None and target_id not in target_filter:
            continue

        if args.execute:
            result = execute_target(project_root, config_path)
        else:
            status, missing = classify_plan(config, config_path)
            result = {
                "target_id": target_id,
                "status": status,
                "missing": missing,
                "config_path": config_path.as_posix(),
                "stages": [],
            }
        results.append(result)

    report_dir = project_root / "reports" / "batch"
    suffix = "execution" if args.execute else "plan"
    write_json(report_dir / f"batch_{suffix}.json", results)
    write_text(
        report_dir / f"batch_{suffix}.md",
        markdown_summary(
            "Round-trip batch execution" if args.execute else "Round-trip batch plan",
            results,
        ),
    )
    csv_summary(report_dir / f"batch_{suffix}.csv", results)

    counts: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1

    summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    print(f"Summary: {summary or 'no targets'}")
    print(f"Report:  {report_dir / f'batch_{suffix}.md'}")

    if not args.execute:
        return 0
    return 1 if any(result["status"] == "failed" for result in results) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
