from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_filter(path: Path | None) -> set[str] | None:
    if path is None:
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            row["target_id"]
            for row in csv.DictReader(handle)
            if row.get("target_id")
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run enabled round-trip configs sequentially.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config-dir", type=Path, default=Path("configs/roundtrip/targets"))
    parser.add_argument("--targets", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_dir = args.config_dir if args.config_dir.is_absolute() else project_root / args.config_dir
    target_filter = load_filter(args.targets if args.targets is None or args.targets.is_absolute() else project_root / args.targets)
    configs = []
    for path in sorted(config_dir.glob("*.json")):
        if path.name.endswith(".draft.json"):
            continue
        config = read_json(path)
        if target_filter is not None and config.get("target_id") not in target_filter:
            continue
        configs.append((path, config))

    results: list[dict[str, Any]] = []
    for path, config in configs:
        status = "ready" if config.get("enabled") is True else "disabled"
        if args.execute and status == "ready":
            command = [
                sys.executable,
                str(project_root / "scripts" / "roundtrip" / "run_target.py"),
                "--config",
                str(path),
                "--project-root",
                str(project_root),
            ]
            if args.force:
                command.append("--force")
            completed = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False)
            status = "passed" if completed.returncode == 0 else "failed"
            results.append({
                "target_id": config.get("target_id"),
                "status": status,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "config": path.relative_to(project_root).as_posix(),
            })
            print(f"{config.get('target_id')}: {status}")
        else:
            results.append({
                "target_id": config.get("target_id"),
                "status": status,
                "config": path.relative_to(project_root).as_posix(),
            })

    report_dir = project_root / "reports" / "batch"
    suffix = "execution" if args.execute else "plan"
    write_json(report_dir / f"batch_{suffix}.json", results)
    lines = [
        f"# Round-trip batch {suffix}",
        "",
        f"- generated_at: `{datetime.now(timezone.utc).isoformat()}`",
        "",
        "| target | status | config |",
        "|---|---|---|",
    ]
    for item in results:
        lines.append(f"| {item['target_id']} | {item['status']} | `{item['config']}` |")
    write_text(report_dir / f"batch_{suffix}.md", "\n".join(lines) + "\n")

    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print("Summary: " + ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
    return 1 if any(item["status"] == "failed" for item in results) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
