from __future__ import annotations

import argparse
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
        raise ValueError(path)
    return value


def normalized_pair_config(config: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(config, ensure_ascii=False))
    for key in ("condition", "experiment_id", "run_id", "design_knowledge"):
        value.pop(key, None)
    return value


def validate_model(config: dict[str, Any], pair_id: str) -> None:
    model = config.get("model") or {}
    expected = {
        "name": MODEL_NAME,
        "temperature": 0,
        "seed": 42,
        "num_ctx": NUM_CTX,
        "num_predict": NUM_PREDICT,
        "generations": 1,
        "retry": False,
        "automatic_repair": False,
    }
    for key, expected_value in expected.items():
        if model.get(key) != expected_value:
            raise RuntimeError(
                f"{pair_id}: model.{key}={model.get(key)!r}, expected={expected_value!r}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/roundtrip_v3/formal/generation_manifest.json"),
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    manifest = read_json(manifest_path)

    if manifest.get("protocol_id") != PROTOCOL_ID:
        raise RuntimeError("Unexpected protocol_id")
    if manifest.get("pair_count") != 17 or manifest.get("config_count") != 34:
        raise RuntimeError("Manifest must contain 17 pairs / 34 configs")
    if manifest.get("design_prompt_profile") != PROMPT_PROFILE:
        raise RuntimeError("Manifest prompt profile mismatch")
    if manifest.get("all_enabled") is not False:
        raise RuntimeError("Formal manifest must remain all-disabled")

    checked = 0
    for target in manifest["targets"]:
        pair_id = target["pair_id"]
        non_path = root / target["conditions"]["non_rag"]["config_path"]
        rag_path = root / target["conditions"]["rag"]["config_path"]
        non = read_json(non_path)
        rag = read_json(rag_path)

        if non["condition"] != CONTROL_CONDITION or rag["condition"] != RAG_CONDITION:
            raise RuntimeError(f"Condition mismatch: {pair_id}")
        if non.get("design_prompt_profile") != PROMPT_PROFILE:
            raise RuntimeError(f"Control prompt profile mismatch: {pair_id}")
        if rag.get("design_prompt_profile") != PROMPT_PROFILE:
            raise RuntimeError(f"RAG prompt profile mismatch: {pair_id}")

        non_knowledge = non.get("design_knowledge") or {}
        rag_knowledge = rag.get("design_knowledge") or {}
        if non_knowledge.get("enabled") is not False:
            raise RuntimeError(f"Control knowledge must be disabled: {pair_id}")
        if rag_knowledge.get("enabled") is not True:
            raise RuntimeError(f"RAG knowledge must be enabled: {pair_id}")
        if rag_knowledge.get("context_file") != KNOWLEDGE_FILE:
            raise RuntimeError(f"RAG knowledge file mismatch: {pair_id}")
        if rag_knowledge.get("instruction_mode") != "required_additional_artifacts":
            raise RuntimeError(f"RAG instruction mode mismatch: {pair_id}")

        if normalized_pair_config(non) != normalized_pair_config(rag):
            raise RuntimeError(f"Pair differs outside allowed treatment fields: {pair_id}")

        for config in (non, rag):
            if config.get("enabled") is not False:
                raise RuntimeError(f"Formal configs must be disabled: {pair_id}")
            if config.get("formal_result_eligible") is not True:
                raise RuntimeError(f"Formal eligibility mismatch: {pair_id}")
            validate_model(config, pair_id)
            protocol = config.get("protocol") or {}
            if protocol.get("protocol_id") != PROTOCOL_ID:
                raise RuntimeError(f"Protocol mismatch: {pair_id}")
            if protocol.get("base_level2_sections") != BASE_SECTIONS:
                raise RuntimeError(f"Base headings mismatch: {pair_id}")
            if protocol.get("treatment_root_level2_section") != DETAIL_ROOT_SECTION:
                raise RuntimeError(f"Detail root mismatch: {pair_id}")
            if protocol.get("treatment_detail_level3_sections") != DETAIL_SECTIONS:
                raise RuntimeError(f"Detail headings mismatch: {pair_id}")
            if protocol.get("allow_other_level2_sections") is not False:
                raise RuntimeError(f"Unexpected level-2 policy: {pair_id}")
            if protocol.get("design_contract_validation_required") is not True:
                raise RuntimeError(f"Design contract validator is not required: {pair_id}")
            if protocol.get("original_source_in_code_regeneration") is not False:
                raise RuntimeError(f"Original source leakage policy mismatch: {pair_id}")
            if protocol.get("retrieved_context_in_code_regeneration") is not False:
                raise RuntimeError(f"Retrieved context leakage policy mismatch: {pair_id}")
            if protocol.get("retry") is not False or protocol.get("automatic_repair") is not False:
                raise RuntimeError(f"Retry/repair policy mismatch: {pair_id}")

        checked += 1

    print(
        json.dumps(
            {"valid": True, "pairs_checked": checked, "configs_checked": checked * 2},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())