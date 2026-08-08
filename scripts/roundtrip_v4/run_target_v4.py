from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any


V3_RUNNER = Path(__file__).resolve().parents[1] / "roundtrip_v3" / "run_target_v3.py"
spec = importlib.util.spec_from_file_location("roundtrip_v3_runner_for_v4", V3_RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load v3 runner: {V3_RUNNER}")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)

PROTOCOL_ID = "source-faithful-detailed-design-rag-v4-eval-001"
PROMPT_PROFILE = "source-faithful-detailed-design-v4"
RAG_CONDITION = "full_source_source_faithful_detailed_design_rag_v4"
KNOWLEDGE_FILE = "knowledge/detailed-design/general-v4.md"

# Patch only the v4 treatment constants. The v3 runner mechanics remain the source of truth.
v3.PROTOCOL_ID = PROTOCOL_ID
v3.PROMPT_PROFILE = PROMPT_PROFILE
v3.RAG_CONDITION = RAG_CONDITION
v3.KNOWLEDGE_FILE = KNOWLEDGE_FILE
v3.SYSTEM_PROMPT = (
    "あなたはC++ソフトウェアのリバースエンジニアリング担当者です。"
    "与えられたコードと設計知識だけを根拠として、再実装に必要な設計文書を日本語で作成してください。"
    "推測で存在しない機能・型・API・状態を追加しないでください。"
    "指定された設計項目の内容を含めてください。Markdown見出しのlevelや順序の厳密一致より、"
    "再実装に必要な事実の正確な保持を優先してください。"
)


def flexible_output_contract() -> str:
    names = "\n".join(f"- {name}" for name in v3.BASE_SECTIONS)
    return f"""# 基本設計項目（内容必須・Markdown階層は柔軟）
以下の9項目の内容を設計文書に含めてください。
Markdownの見出しlevel、項目の順序、補助見出しの追加は問いません。
ただし、項目自体を意図的に省略せず、元コードから確認できる事実を記述してください。
同じ事実の長文反復より、再実装に必要な型・条件・データ・依存関係・状態の正確さを優先してください。

{names}
"""


def flexible_rag_append_section(knowledge_text: str) -> str:
    if not knowledge_text:
        return ""
    names = "\n".join(f"- {name}" for name in v3.DETAIL_SECTIONS)
    return f"""# RAGによる追加詳細設計（内容必須・Markdown階層は柔軟）
基本9項目に加えて、以下7項目の内容を設計文書に含めてください。
`追加詳細設計情報`というまとめ見出しを使用しても構いませんが、見出しlevel、順序、追加見出しは固定しません。
各成果物は基本9項目の言い換えだけで終わらせず、構造・関係・順序・制約・再実装に必要な具体的事実を記述してください。
該当しない場合は「該当なし」、確認できない場合は「確認不能」としてください。
図はMermaidを推奨しますが、形式より内容の正確性を優先してください。

{names}

----- BEGIN RETRIEVED CONTEXT -----
{knowledge_text}
----- END RETRIEVED CONTEXT -----
"""


def headings_any_level(text: str) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    in_fence = False
    for line in text.splitlines():
        if re.match(r"^\s*```", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if match:
            headings.append(
                {"level": len(match.group(1)), "name": match.group(2).strip()}
            )
    return headings


def validate_generated_design_v4(
    config: dict[str, Any], text: str, experiment_root: Path
) -> dict[str, Any]:
    headings = headings_any_level(text)
    names = [item["name"] for item in headings]
    warnings: list[str] = []

    for section in v3.BASE_SECTIONS:
        if section not in names:
            warnings.append(f"base section name not found as Markdown heading: {section}")
    for section in v3.DETAIL_SECTIONS:
        if section not in names:
            warnings.append(f"detail section name not found as Markdown heading: {section}")

    diagram_checks = {
        section: bool(re.search(rf"```mermaid\s*\n\s*{kind}\b", text, re.IGNORECASE))
        for section, kind in v3.DIAGRAM_REQUIREMENTS.items()
    }
    for section, present in diagram_checks.items():
        if not present:
            warnings.append(
                f"{section}: expected Mermaid type not detected; advisory only"
            )

    result = {
        "schema_version": "4.0",
        "prompt_profile": PROMPT_PROFILE,
        "condition": config.get("condition"),
        "validation_mode": "advisory_non_blocking",
        "generated_design_unchanged": True,
        "blocking_passed": True,
        "advisory_passed": not warnings,
        "headings": headings,
        "diagram_checks": diagram_checks,
        "warnings": warnings,
        "validated_at_utc": v3.v2.utc_now(),
    }
    v3.v2.write_json(
        experiment_root / "raw_output" / "design_contract_validation.json",
        result,
    )
    return result


# Replace only prompt-format and validator behavior. Generation/evaluation mechanics stay v3/v2.
v3.fixed_output_contract = flexible_output_contract
v3.rag_append_section = flexible_rag_append_section
v3.validate_generated_design = validate_generated_design_v4


def main() -> int:
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
