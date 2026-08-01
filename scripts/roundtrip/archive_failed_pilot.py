from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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


def git_status(repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "status", "--short", "--untracked-files=no"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout.strip()


def bump_identifier(value: str) -> str:
    match = re.search(r"-(\d{3})$", value)
    if match:
        number = int(match.group(1)) + 1
        return value[: match.start(1)] + f"{number:03d}"
    return value + "-002"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive a failed pilot run and prepare a new immutable run id."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--reason",
        default=(
            "Pilot harness failure: module_files response contained invalid JSON "
            "before source replacement and test execution."
        ),
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_path = args.config if args.config.is_absolute() else project_root / args.config
    config = read_json(config_path)

    repository = project_root / config["repository_path"]
    status = git_status(repository)
    if status:
        raise RuntimeError(f"Repository has tracked changes; archive aborted:\n{status}")

    experiment_root = project_root / "experiments" / config["experiment_id"]
    if not experiment_root.exists():
        raise FileNotFoundError(experiment_root)

    raw_response = experiment_root / "raw_output" / "code_regeneration_response.json"
    evaluation_manifest = experiment_root / "evaluation" / "evaluation_manifest.json"
    if not raw_response.exists():
        raise RuntimeError("No code regeneration response exists; this is not the expected pilot failure.")
    if evaluation_manifest.exists():
        raise RuntimeError("Evaluation already exists; refusing to classify this as a pre-evaluation pilot failure.")

    old_run_id = str(config["run_id"])
    archive_root = (
        project_root
        / "experiments"
        / "pilot-failures"
        / old_run_id
    )
    if archive_root.exists():
        raise FileExistsError(archive_root)
    archive_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(experiment_root), str(archive_root))

    write_json(
        archive_root / "pilot_failure_manifest.json",
        {
            "schema_version": "1.0",
            "target_id": config["target_id"],
            "run_id": old_run_id,
            "classification": "harness_validation_failure",
            "failed_stage": "regenerate_code_output_parse",
            "reason": args.reason,
            "source_replacement_performed": False,
            "test_execution_performed": False,
            "retry_performed": False,
            "automatic_repair_performed": False,
            "repository_clean": True,
            "archived_at_utc": datetime.now(timezone.utc).isoformat(),
            "archive_path": archive_root.relative_to(project_root).as_posix(),
        },
    )

    config["run_id"] = bump_identifier(old_run_id)
    old_experiment_id = str(config["experiment_id"])
    config["experiment_id"] = bump_identifier(old_experiment_id)
    config.setdefault("protocol", {})
    config["protocol"].update(
        {
            "module_output_format": "ollama_json_schema",
            "pilot_failure_excluded": old_run_id,
            "retry": False,
            "automatic_repair": False,
        }
    )
    write_json(config_path, config)

    print(f"Archived pilot: {archive_root}")
    print(f"New run_id:      {config['run_id']}")
    print(f"New experiment:  {config['experiment_id']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
