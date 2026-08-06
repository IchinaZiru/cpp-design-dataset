from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.rag.formal_run_policy import (
    FORMAL_BATCH_REPORT_ROOT,
    FORMAL_RUN_MANIFEST,
    FormalRunPolicyError,
    build_code_request,
    build_design_request,
    build_formal_batch_plan,
    sha256_file,
    validate_formal_target,
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def make_target(
    root: Path,
    *,
    target_id: str = "sample",
    target_kind: str = "standard",
    granularity: str = "module_files",
    enabled: bool = False,
) -> Path:
    context_path = root / f"rag/retrieval/formal/{target_id}/context.txt"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        "Repository-Context RAG v1\nhelper interface\n",
        encoding="utf-8",
        newline="\n",
    )
    context_sha = sha256_file(context_path)
    write_json(
        context_path.parent / "retrieval_manifest.json",
        {
            "target_id": target_id,
            "status": "pass",
            "deterministic": True,
            "context_sha256": context_sha,
            "llm_calls": {
                "code_regeneration": 0,
                "design_generation": 0,
            },
        },
    )

    config: dict[str, object] = {
        "artifact_schema_version": "rag-formal-target-config-v1",
        "condition_id": "rag-design-context-v1",
        "target_id": target_id,
        "target_name": "sample target",
        "target_kind": target_kind,
        "granularity": granularity,
        "enabled": enabled,
        "context_status": "generated_and_audited",
        "context_path": context_path.relative_to(root).as_posix(),
        "context_sha256": context_sha,
        "run_id": f"rag-v1-formal-{target_id}",
        "formal_run_id": f"rag-v1-formal-{target_id}",
        "experiment_id": f"rag-v1-formal-{target_id}",
        "output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
        "formal_output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
        "source_files": ["include/sample.h", "src/sample.cpp"],
        "model": {
            "name": "qwen2.5-coder:32b",
            "stream": False,
            "temperature": 0,
            "seed": 42,
            "num_ctx": 16384,
            "num_predict": 8192,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "retry": False,
            "automatic_repair": False,
            "generations": 1,
        },
        "one_shot_generation_policy": {
            "design_generation_count": 1,
            "code_generation_count": 1,
            "retry": False,
            "automatic_repair": False,
            "manual_patch": False,
            "overwrite": False,
        },
        "input_isolation": {
            "design_generation_allowed_inputs": [
                "frozen design instruction",
                "frozen target source",
                "frozen context.txt",
            ],
            "code_regeneration_allowed_inputs": [
                "single one-shot generated design document",
                "fixed scaffold equivalent to the corresponding non-RAG target",
            ],
            "code_regeneration_forbidden_inputs": [
                "original target source body",
                "retrieved context",
                "selected chunks",
                "candidates",
                "query artifact",
                "repository source",
                "design-generation request or prompt",
                "design audit findings",
                "previous generated output",
            ],
        },
    }

    if target_kind == "legacy_function":
        config.pop("source_files")
        config["source_file"] = "ini/ini.h"
        config["granularity"] = "function_body"
        config["generation"] = {
            "stream": False,
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_ctx": 8192,
                "num_predict": 2048,
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        }
        config["conditions"] = {
            "generations_per_stage": 1,
            "retry_on_failure": False,
            "automatic_repair": False,
        }

    config_path = root / f"configs/rag/targets/{target_id}.json"
    write_json(config_path, config)
    return config_path


def test_standard_design_request_places_context_before_source(tmp_path: Path) -> None:
    config_path = make_target(tmp_path)
    target = validate_formal_target(config_path, tmp_path)

    request = build_design_request(
        target,
        tmp_path,
        "int target_source();\n",
    )

    prompt = request.payload["prompt"]
    assert prompt.index("BEGIN RETRIEVED CONTEXT") < prompt.index("# 元コード")
    assert "helper interface" in prompt
    assert "int target_source();" in prompt
    assert request.audit["retrieval_section_precedes_target_source"] is True
    assert request.audit["llm_call_count_before_request"] == 0


def test_code_request_uses_only_design_and_scaffold(tmp_path: Path) -> None:
    config_path = make_target(tmp_path)
    target = validate_formal_target(config_path, tmp_path)

    request = build_code_request(
        target,
        "DESIGN-DOCUMENT-ONLY",
        "FIXED-SCAFFOLD-ONLY",
    )

    prompt = request.payload["prompt"]
    assert "DESIGN-DOCUMENT-ONLY" in prompt
    assert "FIXED-SCAFFOLD-ONLY" in prompt
    assert "検索コンテキスト" not in prompt
    assert "依存情報" not in prompt
    assert request.audit["dependency_context_loaded"] is False
    assert request.audit["retrieved_context_directly_injected"] is False
    assert request.audit["target_source_directly_injected"] is False
    assert request.audit["forbidden_inputs_directly_loaded"] == []


def test_context_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    config_path = make_target(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["context_sha256"] = "0" * 64
    write_json(config_path, config)

    with pytest.raises(FormalRunPolicyError, match="context_sha256 differs"):
        validate_formal_target(config_path, tmp_path)


def test_existing_formal_output_is_rejected(tmp_path: Path) -> None:
    config_path = make_target(tmp_path)
    output = tmp_path / "experiments/rag/rag-v1-formal-sample"
    output.mkdir(parents=True)

    with pytest.raises(FormalRunPolicyError, match="formal output already exists"):
        validate_formal_target(config_path, tmp_path)


def test_legacy_design_request_preserves_template_and_inserts_context(
    tmp_path: Path,
) -> None:
    template = tmp_path / (
        "experiments/ini-writer-minimal/prompts/design_generation_prompt.md"
    )
    template.parent.mkdir(parents=True)
    template.write_text(
        "# 役割\nlegacy instruction\n\n"
        "# 対象ソースコード\n\n{{DESIGN_INPUT}}\n",
        encoding="utf-8",
        newline="\n",
    )
    config_path = make_target(
        tmp_path,
        target_id="ini-cpp-ini-writer",
        target_kind="legacy_function",
    )
    target = validate_formal_target(config_path, tmp_path)

    request = build_design_request(
        target,
        tmp_path,
        "inline static void write();\n",
    )

    prompt = request.payload["prompt"]
    assert "legacy instruction" in prompt
    assert prompt.index("BEGIN RETRIEVED CONTEXT") < prompt.index(
        "# 対象ソースコード"
    )
    assert "inline static void write();" in prompt


def test_legacy_code_request_has_no_dependency_section(tmp_path: Path) -> None:
    config_path = make_target(
        tmp_path,
        target_id="ini-cpp-ini-writer",
        target_kind="legacy_function",
    )
    target = validate_formal_target(config_path, tmp_path)

    request = build_code_request(target, "LEGACY DESIGN", "LEGACY SCAFFOLD")

    prompt = request.payload["prompt"]
    assert "LEGACY DESIGN" in prompt
    assert "LEGACY SCAFFOLD" in prompt
    assert "# 依存関係情報" not in prompt
    assert "{{DEPENDENCY_CONTEXT}}" not in prompt
    assert "format" not in request.payload


def test_batch_plan_uses_rag_specific_paths(tmp_path: Path) -> None:
    for index in range(17):
        make_target(tmp_path, target_id=f"target-{index:02d}")

    plan = build_formal_batch_plan(tmp_path)

    assert plan["target_count"] == 17
    assert plan["counts"] == {"disabled": 17}
    assert plan["batch_report_root"] == FORMAL_BATCH_REPORT_ROOT.as_posix()
    assert plan["formal_run_manifest"] == FORMAL_RUN_MANIFEST.as_posix()
    assert plan["shared_non_rag_batch_report_used"] is False
    assert plan["shared_non_rag_run_manifest_used"] is False
    assert plan["force_supported"] is False
    assert plan["reprocess_existing_supported"] is False
