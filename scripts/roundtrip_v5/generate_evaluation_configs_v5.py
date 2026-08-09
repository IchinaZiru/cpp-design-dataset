from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_ID = "source-faithful-detailed-design-direct-include-rag-v5-eval-001"
PROMPT_PROFILE = "source-faithful-detailed-design-direct-include-v5"
RAG_CONDITION = "full_source_source_faithful_direct_include_rag_v5"
PREFLIGHT_SUMMARY = "analysis/retrieval_v5/preflight_summary.json"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_v5_config(source: dict[str, Any], *, source_config_path: str) -> dict[str, Any]:
    config = copy.deepcopy(source)
    pair_id = str(config["pair_id"])
    config["schema_version"] = "5.3-v5-evaluation"
    config["enabled"] = False
    config["pilot_only"] = False
    config["formal_result_eligible"] = False
    config["posthoc_refinement"] = True
    config["sensitivity_only"] = True
    config["target_id"] = f"{pair_id}-v5-eval"
    config["condition"] = RAG_CONDITION
    config["experiment_id"] = f"v5/evaluation/rag/{pair_id}-001"
    config["run_id"] = f"{pair_id}-source-faithful-direct-include-rag-v5-eval-001"
    config["design_prompt_profile"] = PROMPT_PROFILE
    config["repository_retrieval"] = {
        "mode": "direct_include_whole_file_one_hop",
        "quoted_includes_only": True,
        "tracked_files_only": True,
        "whole_file": True,
        "depth": 1,
        "exclude_target_source_files": True,
        "target_specific_tuning": False,
        "preflight_summary": PREFLIGHT_SUMMARY,
    }

    protocol = copy.deepcopy(config.get("protocol") or {})
    protocol.update(
        {
            "protocol_id": PROTOCOL_ID,
            "result_classification": "posthoc_refinement_sensitivity",
            "formal_target_set_member": False,
            "design_prompt_profile": PROMPT_PROFILE,
            "original_source_in_code_regeneration": False,
            "retrieved_context_in_code_regeneration": False,
            "retry": False,
            "automatic_repair": False,
            "generated_code_manual_edit": False,
            "generations_per_stage": 1,
            "repository_retrieval_mode": "direct_include_whole_file_one_hop",
            "repository_retrieval_depth": 1,
            "repository_retrieval_whole_file": True,
            "repository_retrieval_target_specific_tuning": False,
            "retrieval_preflight_required": True,
            "v4_reference_config": source_config_path,
            "v4_reference_experiment_id": source["experiment_id"],
        }
    )
    config["protocol"] = protocol

    provenance = copy.deepcopy(config.get("provenance") or {})
    provenance.update(
        {
            "v5_source_config": source_config_path,
            "v5_refinement_is_posthoc": True,
            "v4_results_are_immutable": True,
            "v5_change_scope": (
                "Keep the v4 source-faithful prompt and generation/evaluation mechanics unchanged; "
                "add only whole-file repository-local headers directly included with quoted includes "
                "from target source_files, one hop, excluding target source_files themselves."
            ),
            "v5_control_reference": "frozen v4 evaluation result for the same pair_id",
            "confirmatory_statistical_claim": False,
        }
    )
    config["provenance"] = provenance
    return config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    v4_manifest_path = root / "configs/roundtrip_v4/evaluation/generation_manifest.json"
    v4_manifest = read_json(v4_manifest_path)
    targets = v4_manifest.get("targets") or []
    if len(targets) != 17:
        raise RuntimeError(f"Expected 17 v4 targets, got {len(targets)}")

    output_root = root / "configs/roundtrip_v5/evaluation"
    generated_files: list[str] = []
    manifest_targets: list[dict[str, Any]] = []

    for target in targets:
        pair_id = str(target["pair_id"])
        sequence = int(target["pair_sequence"])
        v4_rel = str(target["config_path"])
        v4_config = read_json(root / v4_rel)
        config = build_v5_config(v4_config, source_config_path=v4_rel)

        rel = Path("configs/roundtrip_v5/evaluation/rag") / f"{pair_id}.json"
        path = root / rel
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing v5 config: {path}")
        write_json(path, config)
        generated_files.append(rel.as_posix())
        manifest_targets.append(
            {
                "pair_id": pair_id,
                "pair_sequence": sequence,
                "granularity": config["granularity"],
                "config_path": rel.as_posix(),
                "experiment_id": config["experiment_id"],
                "run_id": config["run_id"],
                "config_sha256": sha256_file(path),
                "v4_reference_config": v4_rel,
                "v4_reference_experiment_id": v4_config["experiment_id"],
            }
        )

    manifest = {
        "schema_version": "5.0",
        "protocol_id": PROTOCOL_ID,
        "result_classification": "posthoc_refinement_sensitivity",
        "expected_target_count": 17,
        "target_count": 17,
        "config_count": 17,
        "all_enabled": False,
        "design_prompt_profile": PROMPT_PROFILE,
        "condition": RAG_CONDITION,
        "control_reference": "analysis/evaluation_v4/evaluation_results.json",
        "retrieval_preflight": PREFLIGHT_SUMMARY,
        "generated_files": generated_files,
        "targets": manifest_targets,
    }
    manifest_path = output_root / "generation_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing v5 manifest: {manifest_path}")
    write_json(manifest_path, manifest)
    print(json.dumps({"target_count": 17, "config_count": 17, "manifest": str(manifest_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
