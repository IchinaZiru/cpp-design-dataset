from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


V2_BATCH = Path(__file__).resolve().parents[1] / "roundtrip_v2" / "run_formal_batch_v2.py"
spec = importlib.util.spec_from_file_location("roundtrip_v2_batch_for_v4", V2_BATCH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load v2 batch helpers: {V2_BATCH}")
v2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2b)

PROTOCOL_ID = "source-faithful-detailed-design-rag-v4-eval-001"
RAG_CONDITION = "full_source_source_faithful_detailed_design_rag_v4"
V3_CONTROL_CONDITION = "full_source_prompt_preserving_non_rag"


def load_v3_control(project_root: Path) -> dict[str, dict[str, Any]]:
    data = v2b.read_json(project_root / "analysis/formal_v3/formal_results.json")
    records = data.get("records") or []
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("condition") == V3_CONTROL_CONDITION:
            result[str(record["pair_id"])] = record
    if len(result) != 17:
        raise RuntimeError(f"Expected 17 frozen v3 non-RAG control records, got {len(result)}")
    return result


def write_summary(
    project_root: Path,
    records: list[dict[str, Any]],
    controls: dict[str, dict[str, Any]],
) -> list[Path]:
    output_root = project_root / "analysis" / "evaluation_v4"
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "evaluation_results.json"
    csv_path = output_root / "evaluation_results.csv"
    markdown_path = output_root / "summary.md"

    enriched: list[dict[str, Any]] = []
    transitions = {"FAIL->PASS": 0, "PASS->FAIL": 0, "PASS->PASS": 0, "FAIL->FAIL": 0}
    v4_pass = 0
    for record in records:
        pair_id = str(record["pair_id"])
        control = controls[pair_id]
        control_pass = control.get("overall_pass") is True
        treatment_pass = record.get("overall_pass") is True
        transition = f"{'PASS' if control_pass else 'FAIL'}->{'PASS' if treatment_pass else 'FAIL'}"
        transitions[transition] += 1
        v4_pass += int(treatment_pass)
        row = dict(record)
        row["v3_non_rag_overall_pass"] = control_pass
        row["reference_transition"] = transition
        enriched.append(row)

    v2b.write_json(
        json_path,
        {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
            "result_classification": "posthoc_refinement_sensitivity",
            "confirmatory_statistical_claim": False,
            "record_count": len(enriched),
            "v4_pass_count": v4_pass,
            "v4_pass_rate": v4_pass / 17 if len(enriched) == 17 else None,
            "reference_transitions_vs_frozen_v3_non_rag": transitions,
            "records": enriched,
        },
    )

    fieldnames = sorted({key for record in enriched for key in record})
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched)

    lines = [
        "# Source-faithful Detailed-design RAG v4 evaluation results",
        "",
        "This is a post-hoc refinement/sensitivity evaluation informed by v3 formal results.",
        "It is not an independent confirmatory formal experiment.",
        "",
        f"- Terminal runs: {len(enriched)}/17",
        f"- v4 PASS: {v4_pass}/17" if len(enriched) == 17 else f"- v4 PASS so far: {v4_pass}/{len(enriched)}",
        "- Retry: none",
        "- Automatic repair: none",
        "- Design heading validation: advisory/non-blocking",
        "",
        "## Reference transitions vs frozen v3 non-RAG",
        "",
    ]
    for key in ("FAIL->PASS", "PASS->FAIL", "PASS->PASS", "FAIL->FAIL"):
        lines.append(f"- {key}: {transitions[key]}")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return [json_path, csv_path, markdown_path]


def commit_target(
    project_root: Path,
    pair_id: str,
    experiment_root: Path,
    *,
    push: bool,
) -> str | None:
    relative = experiment_root.relative_to(project_root).as_posix()
    v2b.run_command(["git", "-C", str(project_root), "add", "--", relative])
    if not v2b.git_output(project_root, "diff", "--cached", "--name-only"):
        return None
    v2b.run_command(
        [
            "git", "-C", str(project_root), "commit", "-m",
            f"experiment: record v4 evaluation target {pair_id}",
        ],
        capture=True,
    )
    commit = v2b.git_output(project_root, "rev-parse", "HEAD")
    if push:
        v2b.run_command(["git", "-C", str(project_root), "push"], capture=True)
    return commit


def commit_summary(project_root: Path, paths: list[Path], *, push: bool) -> str | None:
    relative = [p.relative_to(project_root).as_posix() for p in paths]
    v2b.run_command(["git", "-C", str(project_root), "add", "--", *relative])
    if not v2b.git_output(project_root, "diff", "--cached", "--name-only"):
        return None
    v2b.run_command(
        ["git", "-C", str(project_root), "commit", "-m", "analysis: summarize v4 evaluation results"],
        capture=True,
    )
    commit = v2b.git_output(project_root, "rev-parse", "HEAD")
    if push:
        v2b.run_command(["git", "-C", str(project_root), "push"], capture=True)
    return commit


def validate_plan(project_root: Path, manifest: dict[str, Any]) -> None:
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise RuntimeError("Unexpected v4 protocol_id")
    if manifest.get("target_count") != 17 or manifest.get("config_count") != 17:
        raise RuntimeError("v4 evaluation manifest must contain exactly 17 configs")
    if manifest.get("all_enabled") is not False:
        raise RuntimeError("v4 generated configs must be disabled before execution")

    seen_run_ids: set[str] = set()
    seen_experiment_ids: set[str] = set()
    for target in manifest["targets"]:
        config_path = project_root / target["config_path"]
        config = v2b.read_json(config_path)
        if config.get("condition") != RAG_CONDITION:
            raise RuntimeError(f"Unexpected condition: {config_path}")
        if config.get("enabled") is not False:
            raise RuntimeError(f"Config must be disabled on disk: {config_path}")
        if (config.get("model") or {}).get("retry") is not False:
            raise RuntimeError(f"retry must be false: {config_path}")
        if (config.get("model") or {}).get("automatic_repair") is not False:
            raise RuntimeError(f"automatic_repair must be false: {config_path}")
        run_id = str(config["run_id"])
        experiment_id = str(config["experiment_id"])
        if run_id in seen_run_ids or experiment_id in seen_experiment_ids:
            raise RuntimeError("Duplicate v4 run_id or experiment_id")
        seen_run_ids.add(run_id)
        seen_experiment_ids.add(experiment_id)
        # Existing terminal artifacts are allowed here so an interrupted batch can
        # be resumed safely. v2b.run_one() verifies the saved config, no-retry
        # policy, source restoration, and terminal artifact before reusing it.
        # A non-terminal/incomplete experiment directory will still fail inside
        # run_one() rather than being overwritten or regenerated.


def verify_runtime_preconditions_v4(project_root: Path, manifest: dict[str, Any]) -> None:
    v2b.parent_tracked_clean(project_root)
    v2b.run_command(["ollama", "show", "qwen2.5-coder:32b"], capture=True)

    checked_repositories: set[tuple[str, str]] = set()
    checked_images: set[tuple[str, str]] = set()
    for target in manifest["targets"]:
        config = v2b.read_json(project_root / target["config_path"])
        repository = project_root / config["repository_path"]
        repo_key = (str(repository), str(config["repository_commit"]))
        if repo_key not in checked_repositories:
            if not repository.is_dir():
                raise FileNotFoundError(repository)
            v2b.repository_tracked_clean(repository)
            head = v2b.git_output(repository, "rev-parse", "HEAD")
            if head != config["repository_commit"]:
                raise RuntimeError(
                    f"Repository commit mismatch: {repository}: {head} != {config['repository_commit']}"
                )
            checked_repositories.add(repo_key)

        evaluation = config["evaluation"]
        image_key = (evaluation["docker_image"], evaluation["docker_image_id"])
        if image_key not in checked_images:
            actual = v2b.inspect_docker_image(evaluation["docker_image"])
            if actual != evaluation["docker_image_id"]:
                raise RuntimeError(
                    f"Docker image mismatch for {evaluation['docker_image']}: "
                    f"{actual} != {evaluation['docker_image_id']}"
                )
            checked_images.add(image_key)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/roundtrip_v4/evaluation/generation_manifest.json"),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else project_root / args.manifest
    manifest = v2b.read_json(manifest_path)
    validate_plan(project_root, manifest)

    if not args.execute:
        print(
            json.dumps(
                {
                    "valid": True,
                    "llm_called": False,
                    "target_count": 17,
                    "condition": RAG_CONDITION,
                    "next": "rerun with --execute after reviewing this plan",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    controls = load_v3_control(project_root)
    runner = project_root / "scripts" / "roundtrip_v4" / "run_target_v4.py"
    verify_runtime_preconditions_v4(project_root, manifest)
    all_records: list[dict[str, Any]] = []

    for target in manifest["targets"]:
        pair_id = str(target["pair_id"])
        config_path = project_root / target["config_path"]
        result = v2b.run_one(project_root, runner, config_path)
        record = v2b.summarize_record(result)
        all_records.append(record)
        commit_target(
            project_root,
            pair_id,
            result["experiment_root"],
            push=args.push,
        )
        v2b.parent_tracked_clean(project_root)
        if result["kind"] == "pipeline_failure":
            failed_stage = result["artifact"].get("failed_stage")
            print(
                f"Pipeline failure preserved for {pair_id} at {failed_stage}; continuing to next target without rerun.",
                flush=True,
            )

    summary_paths = write_summary(project_root, all_records, controls)
    commit_summary(project_root, summary_paths, push=args.push)
    print(json.dumps({"completed_runs": len(all_records), "expected_runs": 17}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
