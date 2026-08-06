"""Plan or execute the frozen 17-target formal RAG batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.formal_run_policy import (
    FORMAL_BATCH_REPORT_ROOT,
    FORMAL_CONFIG_DIR,
    FORMAL_RUN_MANIFEST,
    FormalRunPolicyError,
    build_formal_batch_plan,
    read_json,
    validate_formal_target,
)
from scripts.rag.formal_run_runtime import (
    FormalRunExecutionError,
    default_hooks,
    result_summary,
    terminal_result_path,
    write_formal_runs_csv,
    write_json,
    write_text,
)
from scripts.rag.run_formal_target import run_formal_target


def _canonical_plan_bytes(plan: dict[str, Any]) -> bytes:
    return (
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Formal repository-context RAG batch plan",
        "",
        f"- condition_id: `{plan['condition_id']}`",
        f"- target_count: `{plan['target_count']}`",
        f"- counts: `{json.dumps(plan['counts'], sort_keys=True)}`",
        "",
        "| target | status | config | context SHA-256 |",
        "|---|---|---|---|",
    ]
    for item in plan["targets"]:
        lines.append(
            f"| {item['target_id']} | {item['status']} | "
            f"`{item['config']}` | `{item['context_sha256']}` |"
        )
    return "\n".join(lines) + "\n"


def write_batch_plan(project_root: Path, plan: dict[str, Any]) -> tuple[Path, Path]:
    report_root = project_root / FORMAL_BATCH_REPORT_ROOT
    if plan.get("counts") == {"disabled": 17}:
        stem = "batch_plan_disabled"
    elif plan.get("counts") == {"ready": 17}:
        stem = "batch_plan"
    else:
        raise FormalRunExecutionError(
            f"Unsupported formal plan state: {plan.get('counts')}"
        )
    json_path = report_root / f"{stem}.json"
    markdown_path = report_root / f"{stem}.md"
    expected_json = _canonical_plan_bytes(plan)
    expected_markdown = _plan_markdown(plan).encode("utf-8")
    for path, expected in (
        (json_path, expected_json),
        (markdown_path, expected_markdown),
    ):
        if path.exists() and path.read_bytes() != expected:
            raise FormalRunExecutionError(
                f"Existing batch plan differs and will not be overwritten: {path}"
            )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_bytes(expected_json)
    markdown_path.write_bytes(expected_markdown)
    return json_path, markdown_path


def _set_disabled(config_path: Path) -> None:
    config = read_json(config_path)
    if config.get("enabled") is not True:
        raise FormalRunExecutionError(
            f"Completed target was not enabled: {config_path}"
        )
    config["enabled"] = False
    compact = json.dumps(
        config,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    config_path.write_text(compact, encoding="utf-8", newline="\n")


def _execution_markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Formal repository-context RAG batch execution",
        "",
        "| target | status | failure stage | result |",
        "|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['target_id']} | {item['status']} | "
            f"{item.get('failure_stage') or ''} | `{item['result_path']}` |"
        )
    return "\n".join(lines) + "\n"


def _persist_execution(
    project_root: Path,
    plan: dict[str, Any],
    results: list[dict[str, Any]],
) -> None:
    report_root = project_root / FORMAL_BATCH_REPORT_ROOT
    payload = {
        "artifact_schema_version": "rag-formal-batch-execution-v1",
        "condition_id": plan["condition_id"],
        "planned_target_count": plan["target_count"],
        "completed_target_count": len(results),
        "results": results,
        "retry_performed": False,
        "automatic_repair_performed": False,
    }
    write_json(report_root / "batch_execution.json", payload)
    write_text(report_root / "batch_execution.md", _execution_markdown(results))
    rows = [
        {
            "run_id": item["run_id"],
            "target_id": item["target_id"],
            "condition_id": plan["condition_id"],
            "status": item["status"],
            "failure_stage": item.get("failure_stage") or "",
            "result_path": item["result_path"],
        }
        for item in results
    ]
    write_formal_runs_csv(project_root / FORMAL_RUN_MANIFEST, rows)


def execute_batch(project_root: Path) -> int:
    root = project_root.resolve()
    plan = build_formal_batch_plan(root)
    if plan["counts"] != {"ready": 17}:
        raise FormalRunExecutionError(
            f"Formal execution requires exactly 17 ready targets: {plan['counts']}"
        )
    plan_json = root / FORMAL_BATCH_REPORT_ROOT / "batch_plan.json"
    if not plan_json.is_file():
        raise FormalRunExecutionError("Committed enabled batch plan is missing")
    if plan_json.read_bytes() != _canonical_plan_bytes(plan):
        raise FormalRunExecutionError("Current enabled set differs from batch plan")

    execution_json = root / FORMAL_BATCH_REPORT_ROOT / "batch_execution.json"
    execution_md = root / FORMAL_BATCH_REPORT_ROOT / "batch_execution.md"
    manifest = root / FORMAL_RUN_MANIFEST
    existing = [path for path in (execution_json, execution_md, manifest) if path.exists()]
    if existing:
        raise FormalRunExecutionError(
            "Formal batch terminal output already exists: "
            + ", ".join(str(path) for path in existing)
        )

    results: list[dict[str, Any]] = []
    hooks = default_hooks()
    root_status = hooks.git_output(
        root,
        "status",
        "--short",
        "--untracked-files=no",
    )
    if root_status:
        raise FormalRunExecutionError(
            "Parent repository has tracked changes before formal execution:\n"
            + root_status
        )
    for item in plan["targets"]:
        config_path = root / item["config"]
        target = validate_formal_target(
            config_path,
            root,
            require_enabled=True,
            require_output_absent=True,
        )
        try:
            exit_code = run_formal_target(config_path, root, hooks=hooks)
        except Exception:
            exit_code = 1
        terminal_result_path(target)
        summary = result_summary(target)
        summary["exit_code"] = exit_code
        results.append(summary)
        _set_disabled(config_path)
        _persist_execution(root, plan, results)
        print(f"{target.target_id}: {summary['status']}")

    return 1 if any(item["status"] == "failed" for item in results) else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or execute the frozen formal RAG batch."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    if args.execute:
        return execute_batch(root)
    plan = build_formal_batch_plan(root)
    write_batch_plan(root, plan)
    print("Summary: " + ", ".join(f"{key}={value}" for key, value in sorted(plan["counts"].items())))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
