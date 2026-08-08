from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_ID = "prompt-preserving-detailed-design-rag-v3-formal-001"
PROMPT_PROFILE = "prompt-preserving-detailed-design-v3"
CONTROL_CONDITION = "full_source_prompt_preserving_non_rag"
RAG_CONDITION = "full_source_prompt_preserving_detailed_design_rag"
KNOWLEDGE_FILE = "knowledge/detailed-design/general-v3.md"
MODEL_NAME = "qwen2.5-coder:32b"
NUM_CTX = 32768
NUM_PREDICT = 16384
BASE_SECTIONS = [
    "責務",
    "公開インターフェース",
    "入力",
    "出力",
    "状態",
    "処理手順",
    "例外・失敗条件",
    "依存関係",
    "重要な不変条件",
]
DETAIL_ROOT_SECTION = "追加詳細設計情報"
DETAIL_SECTIONS = [
    "クラス図",
    "クラス・メソッド・インターフェース詳細",
    "シーケンス図",
    "メソッド仕様書",
    "処理フロー図",
    "状態遷移・副作用",
    "データ変換・制約",
]


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


def build_config(
    source: dict[str, Any],
    *,
    pair_id: str,
    sequence: int,
    rag: bool,
    source_path: str,
) -> dict[str, Any]:
    config = copy.deepcopy(source)
    config["schema_version"] = "5.1-formal"
    config["enabled"] = False
    config["pilot_only"] = False
    config["formal_result_eligible"] = True
    config["pair_id"] = pair_id
    config["pair_sequence"] = sequence
    config["target_id"] = f"{pair_id}-v3-formal"
    config["design_prompt_profile"] = PROMPT_PROFILE
    config["condition"] = RAG_CONDITION if rag else CONTROL_CONDITION
    config["experiment_id"] = (
        f"v3/formal/{'rag' if rag else 'non-rag'}/{pair_id}-001"
    )
    config["run_id"] = (
        f"{pair_id}-prompt-preserving-"
        f"{'detailed-design-rag' if rag else 'non-rag'}-formal-001"
    )
    config["design_knowledge"] = (
        {
            "enabled": True,
            "context_file": KNOWLEDGE_FILE,
            "instruction_mode": "required_additional_artifacts",
            "query": (
                "対象コードの基本9項目を保持したまま、クラス図、クラス・メソッド・"
                "インターフェース詳細、シーケンス図、メソッド仕様書、処理フロー図、"
                "状態遷移・副作用、データ変換・制約を追加するための汎用詳細設計知識を取得する"
            ),
        }
        if rag
        else {"enabled": False}
    )

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

    old_protocol = copy.deepcopy(config.get("protocol") or {})
    old_protocol.update(
        {
            "protocol_id": PROTOCOL_ID,
            "formal_target_set_member": True,
            "formal_pair_id": pair_id,
            "observation_scope": "full_source_files",
            "design_prompt_profile": PROMPT_PROFILE,
            "base_level2_sections": BASE_SECTIONS,
            "treatment_root_level2_section": DETAIL_ROOT_SECTION,
            "treatment_detail_level3_sections": DETAIL_SECTIONS,
            "allow_other_level2_sections": False,
            "design_contract_validation_required": True,
            "design_done_reason_required": "stop",
            "code_regeneration_done_reason_required": "stop",
            "original_source_in_code_regeneration": False,
            "retrieved_context_in_code_regeneration": False,
            "module_output_format": old_protocol.get(
                "module_output_format", "ollama_json_schema"
            ),
            "retry": False,
            "automatic_repair": False,
            "generated_code_manual_edit": False,
            "generations_per_stage": 1,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        }
    )
    config["protocol"] = old_protocol

    provenance = copy.deepcopy(config.get("provenance") or {})
    provenance.update(
        {
            "v3_source_config": source_path,
            "v2_results_are_not_v3_results": True,
            "v3_change_scope": (
                "Both conditions preserve the same nine base headings. "
                "The treatment additionally externalizes seven generic detailed-design artifacts."
            ),
            "context_preflight": "analysis/v3/context-preflight-final-prompt/v3_context_preflight.json",
            "context_policy": (
                "Use num_ctx=32768 and num_predict=16384 in both conditions; "
                "re-run the exact-prompt preflight after implementation before any LLM pilot."
            ),
        }
    )
    config["provenance"] = provenance
    return config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    v2_manifest_path = root / "configs/roundtrip_v2/formal/generation_manifest.json"
    v2_manifest = read_json(v2_manifest_path)
    targets = v2_manifest.get("targets") or []
    if len(targets) != 17:
        raise RuntimeError(f"Expected 17 v2 target pairs, got {len(targets)}")

    output_root = root / "configs/roundtrip_v3/formal"
    generated_files: list[str] = []
    manifest_targets: list[dict[str, Any]] = []

    for target in targets:
        pair_id = str(target["pair_id"])
        sequence = int(target["pair_sequence"])
        v2_control_rel = target["conditions"]["non_rag"]["config_path"]
        v2_control = read_json(root / v2_control_rel)
        conditions: dict[str, Any] = {}

        for key, rag in (("non_rag", False), ("rag", True)):
            config = build_config(
                v2_control,
                pair_id=pair_id,
                sequence=sequence,
                rag=rag,
                source_path=v2_control_rel,
            )
            rel = (
                Path("configs/roundtrip_v3/formal")
                / ("rag" if rag else "non-rag")
                / f"{pair_id}.json"
            )
            path = root / rel
            if path.exists():
                raise FileExistsError(
                    f"Refusing to overwrite existing v3 config: {path}"
                )
            write_json(path, config)
            generated_files.append(rel.as_posix())
            conditions[key] = {
                "config_path": rel.as_posix(),
                "experiment_id": config["experiment_id"],
                "run_id": config["run_id"],
                "config_sha256": sha256_file(path),
            }

        manifest_targets.append(
            {
                "pair_id": pair_id,
                "pair_sequence": sequence,
                "granularity": v2_control["granularity"],
                "conditions": conditions,
            }
        )

    manifest = {
        "schema_version": "3.1",
        "protocol_id": PROTOCOL_ID,
        "expected_pair_count": 17,
        "expected_config_count": 34,
        "pair_count": 17,
        "config_count": 34,
        "all_enabled": False,
        "design_prompt_profile": PROMPT_PROFILE,
        "model": {
            "name": MODEL_NAME,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
        },
        "formal_target_ids": [target["pair_id"] for target in manifest_targets],
        "condition_order": ["non_rag", "rag"],
        "generated_files": generated_files,
        "targets": manifest_targets,
    }
    manifest_path = output_root / "generation_manifest.json"
    if manifest_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing v3 manifest: {manifest_path}"
        )
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "pair_count": 17,
                "config_count": 34,
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())