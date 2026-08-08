from __future__ import annotations

import argparse
import csv
import importlib.util
import json
from pathlib import Path
from typing import Any


V2_BATCH = Path(__file__).resolve().parents[1] / "roundtrip_v2" / "run_formal_batch_v2.py"
spec = importlib.util.spec_from_file_location("roundtrip_v2_batch", V2_BATCH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load v2 batch helpers: {V2_BATCH}")
v2b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2b)

PROTOCOL_ID = "prompt-preserving-detailed-design-rag-v3-formal-001"
CONTROL_CONDITION = "full_source_prompt_preserving_non_rag"
RAG_CONDITION = "full_source_prompt_preserving_detailed_design_rag"


def write_summary(project_root: Path, records: list[dict[str, Any]]) -> list[Path]:
    output_root = project_root / "analysis" / "formal_v3"
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "formal_results.json"
    csv_path = output_root / "formal_results.csv"
    markdown_path = output_root / "summary.md"

    v2b.write_json(
        json_path,
        {
            "schema_version": "1.0",
            "protocol_id": PROTOCOL_ID,
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
        key = "rag" if record["condition"] == RAG_CONDITION else "non_rag"
        by_pair.setdefault(record["pair_id"], {})[key] = record

    transitions = {
        "FAIL->PASS": 0,
        "PASS->FAIL": 0,
        "PASS->PASS": 0,
        "FAIL->FAIL": 0,
    }
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
        "# Prompt-preserving Detailed-design RAG v3 formal results",
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


def commit_pair(
    project_root: Path,
    pair_id: str,
    experiment_roots: list[Path],
    *,
    push: bool,
) -> str | None:
    relative = [p.relative_to(project_root).as_posix() for p in experiment_roots]
    v2b.run_command(["git", "-C", str(project_root), "add", "--", *relative])
    if not v2b.git_output(project_root, "diff", "--cached", "--name-only"):
        return None
    v2b.run_command(
        [
            "git",
            "-C",
            str(project_root),
            "commit",
            "-m",
            f"experiment: record v3 formal pair {pair_id}",
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
        [
            "git",
            "-C",
            str(project_root),
            "commit",
            "-m",
            "analysis: summarize formal v3 results",
        ],
        capture=True,
    )
    commit = v2b.git_output(project_root, "rev-parse", "HEAD")
    if push:
        v2b.run_command(["git", "-C", str(project_root), "push"], capture=True)
    return commit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/roundtrip_v3/formal/generation_manifest.json"),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--push", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise RuntimeError("Formal execution requires explicit --execute")

    project_root = args.project_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else project_root / args.manifest
    manifest = v2b.read_json(manifest_path)
    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise RuntimeError("Unexpected v3 protocol_id")
    if manifest.get("pair_count") != 17 or manifest.get("config_count") != 34:
        raise RuntimeError("Formal manifest is not the frozen 17-pair inventory")

    runner = project_root / "scripts" / "roundtrip_v3" / "run_target_v3.py"
    v2b.verify_runtime_preconditions(project_root, manifest)
    all_records: list[dict[str, Any]] = []

    for target in manifest["targets"]:
        pair_id = target["pair_id"]
        pair_results: list[dict[str, Any]] = []
        stop_after_pair = False
        for condition_key in ("non_rag", "rag"):
            config_path = project_root / target["conditions"][condition_key]["config_path"]
            result = v2b.run_one(project_root, runner, config_path)
            pair_results.append(result)
            all_records.append(v2b.summarize_record(result))
            if result["kind"] == "pipeline_failure" and result["status"] == "executed_once":
                failed_stage = result["artifact"].get("failed_stage")
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
        v2b.parent_tracked_clean(project_root)
        if stop_after_pair:
            paths = write_summary(project_root, all_records)
            commit_summary(project_root, paths, push=args.push)
            return 2

    summary_paths = write_summary(project_root, all_records)
    commit_summary(project_root, summary_paths, push=args.push)
    print(
        json.dumps(
            {"completed_runs": len(all_records), "completed_pairs": 17},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())