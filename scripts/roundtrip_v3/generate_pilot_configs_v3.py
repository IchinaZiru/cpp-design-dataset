from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


PILOT_PROTOCOL_ID = "prompt-preserving-detailed-design-rag-v3-pilot-001"
FORMAL_PROTOCOL_ID = "prompt-preserving-detailed-design-rag-v3-formal-001"
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
SOURCE_CONFIG = Path(
    "configs/roundtrip_v2/pilot/rag/"
    "riscv-simulator-session-module-files-pilot-002.json"
)
PAIR_ID = "riscv-simulator-session-v3-pilot"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(source: dict[str, Any], *, rag: bool) -> dict[str, Any]:
    config = copy.deepcopy(source)
    config["schema_version"] = "5.1-pilot"
    config["enabled"] = False
    config["pilot_only"] = True
    config["formal_result_eligible"] = False
    config["pair_id"] = PAIR_ID
    config["pair_sequence"] = 0
    config["target_id"] = "riscv-simulator-session-v3-mechanics-pilot-001"
    config["design_prompt_profile"] = PROMPT_PROFILE
    config["condition"] = RAG_CONDITION if rag else CONTROL_CONDITION
    config["experiment_id"] = (
        f"v3/pilot/{'rag' if rag else 'non-rag'}/"
        "riscv-simulator-session-001"
    )
    config["run_id"] = (
        "riscv-simulator-session-v3-"
        f"{'detailed-design-rag' if rag else 'non-rag'}-pilot-001"
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

    protocol = copy.deepcopy(config.get("protocol") or {})
    protocol.update(
        {
            "protocol_id": FORMAL_PROTOCOL_ID,
            "pilot_protocol_id": PILOT_PROTOCOL_ID,
            "formal_target_set_member": False,
            "formal_pair_id": None,
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
            "retry": False,
            "automatic_repair": False,
            "generated_code_manual_edit": False,
            "generations_per_stage": 1,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT,
            "weak_test_warning": (
                "Session.Construct only verifies construction and destruction. "
                "This pilot checks v3 prompt/output/pipeline mechanics only and is not formal behavioral-equivalence evidence."
            ),
            "note": (
                "Formal-outside v3 mechanics pilot. Do not reuse pilot artifacts as formal results. "
                "A terminal pilot ID is never rerun; use a new pilot ID after implementation fixes."
            ),
        }
    )
    config["protocol"] = protocol

    provenance = copy.deepcopy(config.get("provenance") or {})
    provenance.update(
        {
            "v3_source_config": SOURCE_CONFIG.as_posix(),
            "v2_pilot_artifact_not_reused": True,
            "v3_pilot_purpose": (
                "Check exact base-heading preservation, seven treatment artifacts, "
                "32K/16K generation settings, source restoration, and round-trip mechanics."
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
    source_path = root / SOURCE_CONFIG
    source = read_json(source_path)

    outputs = []
    for rag in (False, True):
        rel = (
            Path("configs/roundtrip_v3/pilot")
            / ("rag" if rag else "non-rag")
            / "riscv-simulator-session.json"
        )
        path = root / rel
        if path.exists():
            raise FileExistsError(
                f"Refusing to overwrite existing v3 pilot config: {path}"
            )
        write_json(path, build(source, rag=rag))
        outputs.append(rel.as_posix())

    print(
        json.dumps(
            {"created": outputs, "enabled": False, "formal_result_eligible": False},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())