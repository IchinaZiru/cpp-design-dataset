from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


V2_BATCH = Path(__file__).resolve().parents[1] / "roundtrip_v2" / "run_formal_batch_v2.py"
spec = importlib.util.spec_from_file_location("roundtrip_v2_batch", V2_BATCH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load v2 batch helpers: {V2_BATCH}")
v2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2b)

CONTROL_CONFIG = Path(
    "configs/roundtrip_v3/pilot/non-rag/riscv-simulator-session.json"
)
RAG_CONFIG = Path(
    "configs/roundtrip_v3/pilot/rag/riscv-simulator-session.json"
)
PAIR_ID = "riscv-simulator-session-v3-pilot"


def preconditions(project_root: Path) -> None:
    v2b.parent_tracked_clean(project_root)
    v2b.run_command(["ollama", "show", "qwen2.5-coder:32b"], capture=True)
    control = v2b.read_json(project_root / CONTROL_CONFIG)
    repository = project_root / control["repository_path"]
    v2b.repository_tracked_clean(repository)
    head = v2b.git_output(repository, "rev-parse", "HEAD")
    if head != control["repository_commit"]:
        raise RuntimeError(
            f"Repository commit mismatch: {head} != {control['repository_commit']}"
        )
    evaluation = control["evaluation"]
    actual_image = v2b.inspect_docker_image(evaluation["docker_image"])
    if actual_image != evaluation["docker_image_id"]:
        raise RuntimeError(
            f"Docker image mismatch: {actual_image} != {evaluation['docker_image_id']}"
        )


def summarize(result: dict) -> dict:
    artifact = result["artifact"]
    config = result["config"]
    return {
        "condition": config["condition"],
        "status": result["status"],
        "kind": result["kind"],
        "overall_pass": artifact.get("overall_pass"),
        "failed_stage": artifact.get("failed_stage"),
        "experiment_id": config["experiment_id"],
        "run_id": config["run_id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the formal-outside v3 Session pilot pair exactly once per condition."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise RuntimeError("Pilot execution requires explicit --execute")

    project_root = args.project_root.resolve()
    runner = project_root / "scripts" / "roundtrip_v3" / "run_target_v3.py"
    preconditions(project_root)

    results = []
    for config_rel in (CONTROL_CONFIG, RAG_CONFIG):
        config_path = project_root / config_rel
        result = v2b.run_one(project_root, runner, config_path)
        results.append(result)
        if result["kind"] == "pipeline_failure" and result["status"] == "executed_once":
            print(
                json.dumps(
                    {
                        "pair_id": PAIR_ID,
                        "stopped_after_pipeline_failure": True,
                        "results": [summarize(item) for item in results],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2

    v2b.parent_tracked_clean(project_root)
    print(
        json.dumps(
            {
                "pair_id": PAIR_ID,
                "pilot_only": True,
                "formal_result_eligible": False,
                "results": [summarize(item) for item in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())