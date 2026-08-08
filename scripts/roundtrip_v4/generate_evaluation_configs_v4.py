from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_ID = "source-faithful-detailed-design-rag-v4-eval-001"
PROMPT_PROFILE = "source-faithful-detailed-design-v4"
RAG_CONDITION = "full_source_source_faithful_detailed_design_rag_v4"
KNOWLEDGE_FILE = "knowledge/detailed-design/general-v4.md"
MODEL_NAME = "qwen2.5-coder:32b"
NUM_CTX = 32768
NUM_PREDICT = 16384


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


def build_v4_config(
    source: dict[str, Any],
    *,
    pair_id: str,
    sequence: int,
    v3_control_config_path: str,
    v3_control_experiment_id: str,
) -> dict[str, Any]:
    config = copy.deepcopy(source)
    config["schema_version"] = "5.2-v4-evaluation"
    config["enabled"] = False
    config["pilot_only"] = False
    config["formal_result_eligible"] = False
    config["posthoc_refinement"] = True
    config["sensitivity_only"] = True
    config["pair_id"] = pair_id
    config["pair_sequence"] = sequence
    config["target_id"] = f"{pair_id}-v4-eval"
    config["design_prompt_profile"] = PROMPT_PROFILE
    config["condition"] = RAG_CONDITION
    config["experiment_id"] = f"v4/evaluation/rag/{pair_id}-001"
    config["run_id"] = f"{pair_id}-source-faithful-detailed-design-rag-v4-eval-001"
    config["design_knowledge"] = {
        "enabled": True,
        "context_file": KNOWLEDGE_FILE,
        "instruction_mode": "required_additional_artifacts",
        "query": (
            "再実装に必要な型定義、直接依存API、利用方法、条件・具体値、使用/更新データ、"
            "状態・副作用・不変条件を、ソース全文コピーではなく正確な詳細設計情報として保持する"
        ),
    }

    model = copy.deepcopy(config.get("model") or {})
    model.update(
        {
            "name": MODEL_NAME,
            "temperature": 0,
            "seed": 42,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "stream": False,
            "generations": 1,
            "retry": False,
            "automatic_repair": False,
        }
    )
    config["model"] = model

    protocol = copy.deepcopy(config.get("protocol") or {})
    protocol.update(
        {
            "protocol_id": PROTOCOL_ID,
            "result_classification": "posthoc_refinement_sensitivity",
            "formal_target_set_member": False,
            "observation_scope": "full_source_files",
            "design_prompt_profile": PROMPT_PROFILE,
            "design_contract_validation_mode": "advisory_non_blocking",
            "design_contract_violation_is_terminal": False,
            "allow_heading_level_variation": True,
            "allow_heading_order_variation": True,
            "allow_additional_headings": True,
            "generated_design_automatic_normalization": False,
            "design_done_reason_required": "stop",
            "code_regeneration_done_reason_required": "stop",
            "original_source_in_code_regeneration": False,
            "retrieved_context_in_code_regeneration": False,
            "retry": False,
            "automatic_repair": False,
            "generated_code_manual_edit": False,
            "generations_per_stage": 1,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "v3_control_reference_config": v3_control_config_path,
            "v3_control_reference_experiment_id": v3_control_experiment_id,
        }
    )
    config["protocol"] = protocol

    provenance = copy.deepcopy(config.get("provenance") or {})
    provenance.update(
        {
            "v4_source_config": v3_control_config_path,
            "v4_refinement_is_posthoc": True,
            "v3_formal_results_are_immutable": True,
            "v4_change_scope": (
                "Preserve source-level facts needed for regeneration and make Markdown heading validation advisory."
            ),
            "v4_control_reference": "frozen v3 non-RAG result for the same pair_id",
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

    v3_manifest_path = root / "configs/roundtrip_v3/formal/generation_manifest.json"
    v3_manifest = read_json(v3_manifest_path)
    targets = v3_manifest.get("targets") or []
    if len(targets) != 17:
        raise RuntimeError(f"Expected 17 v3 pairs, got {len(targets)}")

    knowledge_path = root / KNOWLEDGE_FILE
    if not knowledge_path.is_file():
        raise FileNotFoundError(f"Missing v4 knowledge file: {knowledge_path}")

    output_root = root / "configs/roundtrip_v4/evaluation"
    generated_files: list[str] = []
    manifest_targets: list[dict[str, Any]] = []

    for target in targets:
        pair_id = str(target["pair_id"])
        sequence = int(target["pair_sequence"])
        control_info = target["conditions"]["non_rag"]
        control_rel = str(control_info["config_path"])
        control = read_json(root / control_rel)

        config = build_v4_config(
            control,
            pair_id=pair_id,
            sequence=sequence,
            v3_control_config_path=control_rel,
            v3_control_experiment_id=str(control_info["experiment_id"]),
        )
        rel = Path("configs/roundtrip_v4/evaluation/rag") / f"{pair_id}.json"
        path = root / rel
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing v4 config: {path}")
        write_json(path, config)
        generated_files.append(rel.as_posix())
        manifest_targets.append(
            {
                "pair_id": pair_id,
                "pair_sequence": sequence,
                "granularity": control["granularity"],
                "config_path": rel.as_posix(),
                "experiment_id": config["experiment_id"],
                "run_id": config["run_id"],
                "config_sha256": sha256_file(path),
                "v3_control_config_path": control_rel,
                "v3_control_experiment_id": control_info["experiment_id"],
            }
        )

    manifest = {
        "schema_version": "4.0",
        "protocol_id": PROTOCOL_ID,
        "result_classification": "posthoc_refinement_sensitivity",
        "expected_target_count": 17,
        "target_count": 17,
        "config_count": 17,
        "all_enabled": False,
        "design_prompt_profile": PROMPT_PROFILE,
        "condition": RAG_CONDITION,
        "model": {
            "name": MODEL_NAME,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
        "control_reference": "analysis/formal_v3/formal_results.json",
        "generated_files": generated_files,
        "targets": manifest_targets,
    }
    manifest_path = output_root / "generation_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing v4 manifest: {manifest_path}")
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {"target_count": 17, "config_count": 17, "manifest": str(manifest_path)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
