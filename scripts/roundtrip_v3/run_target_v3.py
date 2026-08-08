from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


V2_RUNNER = Path(__file__).resolve().parents[1] / "roundtrip_v2" / "run_target_v2.py"
spec = importlib.util.spec_from_file_location("roundtrip_v2_runner", V2_RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load v2 runner: {V2_RUNNER}")
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)

PROTOCOL_ID = "prompt-preserving-detailed-design-rag-v3-formal-001"
PROMPT_PROFILE = "prompt-preserving-detailed-design-v3"
CONTROL_CONDITION = "full_source_prompt_preserving_non_rag"
RAG_CONDITION = "full_source_prompt_preserving_detailed_design_rag"
KNOWLEDGE_FILE = "knowledge/detailed-design/general-v3.md"
EXPECTED_MODEL = "qwen2.5-coder:32b"
EXPECTED_NUM_CTX = 32768
EXPECTED_NUM_PREDICT = 16384

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
DIAGRAM_REQUIREMENTS = {
    "クラス図": "classDiagram",
    "シーケンス図": "sequenceDiagram",
    "処理フロー図": "flowchart",
}
SYSTEM_PROMPT = (
    "あなたはC++ソフトウェアのリバースエンジニアリング担当者です。"
    "与えられたコードだけを根拠として、再実装に必要な設計文書を日本語で作成してください。"
    "推測で存在しない機能を追加しないでください。"
    "指定された見出し構成を厳密に保持してください。"
)


def validate_v3_config(
    config: dict[str, Any],
    *,
    project_root: Path | None = None,
    check_files: bool = False,
) -> dict[str, Any]:
    summary = v2.validate_config(
        config,
        project_root=project_root,
        check_files=check_files,
    )
    if config.get("design_prompt_profile") != PROMPT_PROFILE:
        raise ValueError(f"design_prompt_profile must be {PROMPT_PROFILE!r}")

    condition = config.get("condition")
    if condition not in {CONTROL_CONDITION, RAG_CONDITION}:
        raise ValueError(f"Unsupported v3 condition: {condition!r}")

    model = config.get("model") or {}
    if model.get("name") != EXPECTED_MODEL:
        raise ValueError(f"model.name must be {EXPECTED_MODEL!r}")
    if model.get("num_ctx") != EXPECTED_NUM_CTX:
        raise ValueError(f"model.num_ctx must be {EXPECTED_NUM_CTX}")
    if model.get("num_predict") != EXPECTED_NUM_PREDICT:
        raise ValueError(f"model.num_predict must be {EXPECTED_NUM_PREDICT}")
    if model.get("temperature") != 0:
        raise ValueError("model.temperature must be 0")
    if model.get("seed") != 42:
        raise ValueError("model.seed must be 42")
    if model.get("generations", 1) != 1:
        raise ValueError("model.generations must be 1")
    if model.get("retry", False) is not False:
        raise ValueError("model.retry must be false")
    if model.get("automatic_repair", False) is not False:
        raise ValueError("model.automatic_repair must be false")

    knowledge = config.get("design_knowledge") or {}
    enabled = bool(knowledge.get("enabled", False))
    if condition == CONTROL_CONDITION:
        if enabled:
            raise ValueError("Control condition must not enable design_knowledge")
    else:
        if not enabled:
            raise ValueError("RAG condition must enable design_knowledge")
        if knowledge.get("context_file") != KNOWLEDGE_FILE:
            raise ValueError(f"RAG condition must use {KNOWLEDGE_FILE}")
        if knowledge.get("instruction_mode") != "required_additional_artifacts":
            raise ValueError(
                "RAG design_knowledge.instruction_mode must be required_additional_artifacts"
            )

    protocol = config.get("protocol") or {}
    protocol_id = protocol.get("protocol_id")
    if protocol_id is not None and protocol_id != PROTOCOL_ID:
        raise ValueError(f"protocol.protocol_id must be {PROTOCOL_ID!r}")
    return summary


def resolve_detailed_design_knowledge(
    config: dict[str, Any], project_root: Path, experiment_root: Path
) -> str:
    knowledge = config.get("design_knowledge") or {}
    if not knowledge.get("enabled", False):
        return ""

    context_file = str(knowledge["context_file"])
    source_path = project_root / context_file
    text = v2.read_text(source_path).strip()
    if not text:
        raise ValueError("Detailed-design knowledge context is empty")

    retrieval_dir = experiment_root / "retrieval"
    v2.write_text(retrieval_dir / "context.txt", text + "\n")
    v2.write_json(
        retrieval_dir / "retrieval_manifest.json",
        {
            "schema_version": "3.0",
            "condition": config.get("condition"),
            "knowledge_type": "generic_detailed_design_bundle",
            "retrieval_mode": "fixed_query_fixed_knowledge",
            "instruction_mode": "required_additional_artifacts",
            "query": knowledge.get("query"),
            "context_file": context_file,
            "context_sha256": v2.sha256_bytes((text + "\n").encode("utf-8")),
            "retrieved_at_utc": v2.utc_now(),
            "target_specific_tuning": False,
            "base_sections_preserved": True,
            "additional_artifacts": DETAIL_SECTIONS,
        },
    )
    return text


def target_and_scope(config: dict[str, Any]) -> tuple[str, str]:
    granularity = v2.normalized_granularity(config)
    if granularity == "module_files":
        source_files = v2.source_files_for(config)
        target_description = (
            f"- target: {config['target_name']}\n"
            "- granularity: module_files\n"
            f"- source_files: {json.dumps(source_files, ensure_ascii=False)}"
        )
        scope_description = (
            "元コードとして示したsource_files全体を1つのモジュールとして扱ってください。\n"
            "設計文書は、各ファイルの責務、ファイル間の関係、公開インターフェース、実装上の処理を含めて作成してください。\n"
            "再実装ではsource_filesにある各ファイル全体を生成するため、ファイルごとの構造と責務を区別してください。"
        )
        return target_description, scope_description

    locator = dict(config["locator"])
    target_description = (
        f"- target: {config['target_name']}\n"
        "- granularity: target_span\n"
        f"- target_kind: {locator['kind']}\n"
        f"- target_symbol: {locator['symbol']}"
    )
    scope_description = (
        "元コード全体は対象部分を理解するための文脈として参照してください。\n"
        "設計文書はtarget_symbolで指定した対象部分だけについて作成してください。\n"
        "対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。"
    )
    return target_description, scope_description


def fixed_output_contract() -> str:
    headings = "\n".join(f"## {name}" for name in BASE_SECTIONS)
    return f"""# 基本設計項目の出力構成（全条件共通・固定）
以下の9個のlevel-2見出しを、この順序・この表記で必ず出力してください。
見出し名の変更、統合、省略、順序変更を禁止します。
各項目は元コードから確認できる事実だけを記述し、同じ事実を複数項目で長文反復しないでください。
非RAG条件では、以下9個以外のlevel-2見出しを追加しないでください。

{headings}
"""


def rag_append_section(knowledge_text: str) -> str:
    if not knowledge_text:
        return ""
    detail_headings = "\n".join(f"### {name}" for name in DETAIL_SECTIONS)
    return f"""# RAGによる追加詳細設計成果物
基本9項目をすべて同じ順序で出力した後に、次のlevel-2見出しを1つだけ追加してください。

## {DETAIL_ROOT_SECTION}

その配下に、以下7個のlevel-3見出しをこの順序・この表記で必ず出力してください。
各成果物は基本9項目の単なる言い換えではなく、構造・関係・順序・制約を具体化してください。
対象に該当しない成果物も見出しを省略せず、「該当なし」と簡潔な根拠を記載してください。
元コードで確認できない内容は推測せず「確認不能」としてください。
図が該当する場合は検索コンテキストで指定されたMermaid形式を使用してください。

{detail_headings}

----- BEGIN RETRIEVED CONTEXT -----
{knowledge_text}
----- END RETRIEVED CONTEXT -----
"""


def build_design_prompt(
    config: dict[str, Any], design_input: str, knowledge_text: str
) -> tuple[str, str]:
    target_description, scope_description = target_and_scope(config)
    prompt = f"""# 対象
{target_description}

# 対象範囲
{scope_description}

{fixed_output_contract()}
{rag_append_section(knowledge_text)}
# 元コード
{design_input}
"""
    return SYSTEM_PROMPT, prompt


def _markdown_outline(text: str) -> tuple[list[str], list[str], dict[str, str]]:
    h2: list[str] = []
    detail_h3: list[str] = []
    detail_contents: dict[str, list[str]] = {}
    current_h2: str | None = None
    current_h3: str | None = None
    in_fence = False

    for line in text.splitlines():
        if re.match(r"^\s*```", line):
            in_fence = not in_fence
            if current_h2 == DETAIL_ROOT_SECTION and current_h3 is not None:
                detail_contents.setdefault(current_h3, []).append(line)
            continue
        if in_fence:
            if current_h2 == DETAIL_ROOT_SECTION and current_h3 is not None:
                detail_contents.setdefault(current_h3, []).append(line)
            continue

        match2 = re.match(r"^##(?!#)\s+(.+?)\s*$", line)
        if match2:
            current_h2 = match2.group(1).strip()
            current_h3 = None
            h2.append(current_h2)
            continue

        match3 = re.match(r"^###(?!#)\s+(.+?)\s*$", line)
        if match3:
            current_h3 = match3.group(1).strip()
            if current_h2 == DETAIL_ROOT_SECTION:
                detail_h3.append(current_h3)
                detail_contents.setdefault(current_h3, [])
            continue

        if current_h2 == DETAIL_ROOT_SECTION and current_h3 is not None:
            detail_contents.setdefault(current_h3, []).append(line)

    return h2, detail_h3, {
        key: "\n".join(lines).strip() for key, lines in detail_contents.items()
    }


def validate_generated_design(
    config: dict[str, Any], text: str, experiment_root: Path
) -> dict[str, Any]:
    condition = config["condition"]
    expected_h2 = list(BASE_SECTIONS)
    if condition == RAG_CONDITION:
        expected_h2.append(DETAIL_ROOT_SECTION)

    actual_h2, actual_detail_h3, detail_contents = _markdown_outline(text)
    errors: list[str] = []
    if actual_h2 != expected_h2:
        errors.append(
            f"level-2 headings differ: expected={expected_h2!r}, actual={actual_h2!r}"
        )

    artifact_checks: dict[str, Any] = {}
    if condition == RAG_CONDITION:
        if actual_detail_h3 != DETAIL_SECTIONS:
            errors.append(
                "detail level-3 headings differ: "
                f"expected={DETAIL_SECTIONS!r}, actual={actual_detail_h3!r}"
            )
        for section in DETAIL_SECTIONS:
            content = detail_contents.get(section, "")
            check: dict[str, Any] = {
                "non_empty": bool(content.strip()),
                "not_applicable": "該当なし" in content,
                "unconfirmed": "確認不能" in content,
            }
            required_diagram = DIAGRAM_REQUIREMENTS.get(section)
            if required_diagram is not None:
                check["required_mermaid_type"] = required_diagram
                check["mermaid_present"] = bool(
                    re.search(
                        rf"```mermaid\s*\n\s*{re.escape(required_diagram)}\b",
                        content,
                        re.IGNORECASE,
                    )
                )
                if not check["mermaid_present"] and not check["not_applicable"]:
                    errors.append(
                        f"{section}: requires Mermaid {required_diagram} or an explicit 該当なし"
                    )
            elif not content.strip():
                errors.append(f"{section}: section is empty")
            artifact_checks[section] = check
    else:
        if DETAIL_ROOT_SECTION in actual_h2:
            errors.append("Control condition must not contain the RAG detail root section")

    result = {
        "schema_version": "2.0",
        "prompt_profile": PROMPT_PROFILE,
        "condition": condition,
        "expected_level2_headings": expected_h2,
        "actual_level2_headings": actual_h2,
        "expected_detail_level3_headings": DETAIL_SECTIONS if condition == RAG_CONDITION else [],
        "actual_detail_level3_headings": actual_detail_h3,
        "artifact_checks": artifact_checks,
        "passed": not errors,
        "errors": errors,
        "validated_at_utc": v2.utc_now(),
    }
    v2.write_json(
        experiment_root / "raw_output" / "design_contract_validation.json",
        result,
    )
    if errors:
        raise RuntimeError("Design output contract violation: " + "; ".join(errors))
    return result


def generate_design_v3(
    config: dict[str, Any], project_root: Path, experiment_root: Path
) -> dict[str, Any]:
    design_input = v2.read_text(experiment_root / "input" / "design_input.txt")
    knowledge_text = resolve_detailed_design_knowledge(
        config, project_root, experiment_root
    )
    system, prompt = build_design_prompt(config, design_input, knowledge_text)
    payload = {
        "model": config["model"]["name"],
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": v2.ollama_options(config),
    }
    response, elapsed = v2.call_ollama(payload)
    raw_dir = experiment_root / "raw_output"
    v2.write_json(raw_dir / "design_generation_request.json", payload)
    v2.write_json(raw_dir / "design_generation_response.json", response)

    metadata = {
        "started_at_utc": v2.utc_now(),
        "elapsed_seconds": elapsed,
        "done": response.get("done"),
        "done_reason": response.get("done_reason"),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "eval_count": response.get("eval_count"),
        "prompt_profile": PROMPT_PROFILE,
        "num_ctx": config["model"]["num_ctx"],
        "num_predict": config["model"]["num_predict"],
        "retry": False,
        "automatic_repair": False,
    }
    v2.write_json(raw_dir / "design_generation_metadata.json", metadata)

    text = response.get("response")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Design generation returned an empty response")
    v2.write_text(experiment_root / "generated" / "design_document.md", text)

    if response.get("done_reason") != "stop":
        raise RuntimeError(
            "Design generation did not terminate normally: "
            f"done_reason={response.get('done_reason')!r}, "
            f"eval_count={response.get('eval_count')!r}"
        )

    validate_generated_design(config, text, experiment_root)
    return metadata


def regenerate_v3(config: dict[str, Any], experiment_root: Path) -> dict[str, Any]:
    metadata = v2.regenerate(config, experiment_root)
    if metadata.get("done_reason") != "stop":
        raise RuntimeError(
            "Code regeneration did not terminate normally: "
            f"done_reason={metadata.get('done_reason')!r}, "
            f"eval_count={metadata.get('eval_count')!r}"
        )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one prompt-preserving detailed-design RAG v3 target."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--validate-config-only", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_path = args.config if args.config.is_absolute() else project_root / args.config
    config = v2.load_json(config_path)

    if args.validate_config_only:
        summary = validate_v3_config(
            config, project_root=project_root, check_files=True
        )
        print(json.dumps({"valid": True, **summary}, ensure_ascii=False, indent=2))
        return 0

    validate_v3_config(config, project_root=project_root, check_files=True)
    if not config.get("enabled", False):
        raise RuntimeError("Target config is disabled")

    experiment_root = v2.resolve_experiment_root(config, project_root)
    if experiment_root.exists():
        raise FileExistsError(
            f"Experiment directory already exists: {experiment_root}. "
            "Use a new experiment_id and run_id; do not overwrite a run."
        )

    stage = "prepare"
    try:
        v2.prepare(config, project_root, experiment_root)
        stage = "design_generation"
        generate_design_v3(config, project_root, experiment_root)
        stage = "code_regeneration"
        regenerate_v3(config, experiment_root)
        stage = "evaluation"
        result = v2.evaluate(config, project_root, experiment_root)
    except Exception as exc:
        v2.record_pipeline_failure(config, experiment_root, stage, exc)
        raise

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())