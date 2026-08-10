from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.rag.roundtrip_ab as roundtrip_ab_module

from scripts.rag.canonical import sha256_bytes
from scripts.rag.roundtrip_ab import (
    RoundtripABError,
    SourceReplacementTransaction,
    TargetInput,
    build_code_request,
    build_design_request,
    build_plan,
    build_retrieval_bundle,
    compose_design_prompt,
    execute_condition_once,
    load_common_config,
    load_json,
    resolve_repository_root,
    retrieve_dependency_headers,
    validate_generated_units,
    write_retrieval_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
COMMON_PATH = PROJECT_ROOT / "configs/rag/roundtrip_ab_v1/common.json"


def _target_input(content: str = "int target(int value);\n") -> TargetInput:
    digest = sha256_bytes(content.encode("utf-8"))
    return TargetInput(
        file_id="F01",
        unit_id="U01",
        path="src/target.cpp",
        replacement_required=True,
        role="target implementation",
        content=content,
        source_file_sha256=digest,
        content_sha256=digest,
    )


def _minimal_config(repository_path: str = "repo") -> dict[str, object]:
    return {
        "artifact_schema_version": "roundtrip-design-only-ab-target-v1",
        "formal_execution_authorized": False,
        "formal_target_member": False,
        "target_id": "sample",
        "stage": "test",
        "repository": {
            "path": repository_path,
            "commit": "unused",
            "external": False,
        },
        "target_owned_inputs": [
            {
                "file_id": "F01",
                "unit_id": "U01",
                "path": "src/target.cpp",
                "role": "target implementation",
                "scope": "full_file",
            }
        ],
        "retrieval": {
            "dependency_header_mode": (
                "direct-project-local-quoted-include-whole-file-one-hop-v1"
            ),
            "dependency_header_normalization": (
                "utf8-bom-aware-newlines-to-lf-v1"
            ),
            "include_roots": ["include", "src"],
            "design_knowledge_mode": "fixed-v4-v5-verbatim-all-targets-v1",
            "fixed_design_knowledge_path": (
                "configs/rag/roundtrip_ab_v1/prompts/"
                "fixed_v4_v5_design_knowledge.txt"
            ),
            "maximum_dependency_headers": 8,
            "expected_evidence": [],
            "source_feature_selection": False,
            "target_specific_manual_query": False,
        },
        "one_shot": {
            "design_generation_count": 1,
            "code_generation_count": 1,
            "retry": False,
            "automatic_repair": False,
            "manual_patch": False,
            "overwrite": False,
        },
    }


def _init_git_repository(path: Path) -> str:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(path), "add", "src", "include"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_execution_fixture(tmp_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    repository = tmp_path / "repo"
    (repository / "src").mkdir(parents=True)
    (repository / "include").mkdir(parents=True)
    original = '#include "dep.h"\nint target() { return 1; }\n'
    (repository / "src/target.cpp").write_bytes(original.encode("utf-8"))
    (repository / "include/dep.h").write_bytes(b"using Value = int;\n")
    commit = _init_git_repository(repository)

    source_common = load_json(COMMON_PATH)
    common = dict(source_common)
    common["prompts"] = dict(source_common["prompts"])
    prompt_dir = tmp_path / "protocol"
    prompt_dir.mkdir()
    for name in (
        "design_generation",
        "code_generation_system",
        "code_generation_user",
        "code_generation_schema",
    ):
        source = PROJECT_ROOT / source_common["prompts"][name]
        destination = prompt_dir / source.name
        destination.write_bytes(source.read_bytes())
        common["prompts"][name] = destination.relative_to(tmp_path).as_posix()
        common["prompts"][f"{name}_sha256"] = sha256_bytes(
            destination.read_bytes()
        )
    common_path = tmp_path / "common.json"
    common_path.write_text(json.dumps(common), encoding="utf-8")

    knowledge_source = (
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/prompts/"
        "fixed_v4_v5_design_knowledge.txt"
    )
    knowledge_path = tmp_path / "fixed_design_knowledge.txt"
    knowledge_path.write_bytes(knowledge_source.read_bytes())
    knowledge_text = knowledge_path.read_text(encoding="utf-8").replace(
        "\r\n", "\n"
    ).rstrip("\n")
    original_bytes = original.encode("utf-8")
    command = [sys.executable, "-c", "raise SystemExit(0)"]
    config = _minimal_config()
    config["repository"]["commit"] = commit
    config["target_owned_inputs"][0]["source_file_sha256"] = sha256_bytes(
        original_bytes
    )
    config["target_owned_inputs"][0]["replacement_required"] = True
    config["retrieval"]["fixed_design_knowledge_path"] = (
        "fixed_design_knowledge.txt"
    )
    config["retrieval"]["fixed_design_knowledge_sha256"] = sha256_bytes(
        knowledge_path.read_bytes()
    )
    config["retrieval"]["fixed_design_knowledge_content_sha256"] = sha256_bytes(
        knowledge_text.encode("utf-8")
    )
    config["replacement_units"] = [
        {
            "file_id": "F01",
            "unit_id": "U01",
            "path": "src/target.cpp",
            "scope": "full_file",
            "source_file_sha256": sha256_bytes(original_bytes),
            "content_sha256": sha256_bytes(original_bytes),
        }
    ]
    config["execution"] = {
        "enabled": True,
        "output_root": "experiments/pilot",
        "plan_root": "reports/pilot/plan",
        "commands": {
            "configure": command,
            "build": command,
            "direct_test": command,
            "full_test": command,
        },
        "stage_timeouts_seconds": {
            "configure": 10,
            "build": 10,
            "direct_test": 10,
            "full_test": 10,
        },
    }
    loaded_common = load_common_config(common_path, tmp_path)
    return config, loaded_common


def test_a_and_b_use_same_base_prompt_and_b_only_adds_rag_context() -> None:
    base = "COMMON MINIMAL PROMPT"
    inputs = (_target_input(),)

    prompt_a = compose_design_prompt(
        base, inputs, condition="A", rag_context=None
    )
    prompt_b = compose_design_prompt(
        base, inputs, condition="B", rag_context="retrieved evidence\n"
    )

    assert prompt_a.startswith(base)
    assert prompt_b.startswith(base)
    assert "RAG_CONTEXT" not in prompt_a
    assert "retrieved evidence" not in prompt_a
    assert "===== BEGIN RAG_CONTEXT =====" in prompt_b
    assert prompt_a.split("TARGET-OWNED INPUTS", 1)[0] == prompt_b.split(
        "TARGET-OWNED INPUTS", 1
    )[0]


def test_canonical_minimal_prompt_matches_new_protocol_text() -> None:
    prompt = (
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/prompts/design_generation.txt"
    ).read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")

    assert prompt == (
        "与えられたC++ソースコードを解析し、このソースコードを参照できない別のLLMが"
        "再実装できるように、詳細な設計仕様書を作成してください。\n\n"
        "入力から確認できない情報は推測しないでください。"
    )


def test_fixed_v4_v5_design_knowledge_is_verbatim_and_not_ranked() -> None:
    path = (
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/prompts/"
        "fixed_v4_v5_design_knowledge.txt"
    )
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")

    assert sha256_bytes(text.encode("utf-8")) == (
        "13ffffe8c5c76b6493f36be79c56332ee2cd8ccfcf9b38685edfd6ab4137636f"
    )
    assert text.startswith("# RAGによる追加詳細設計（内容必須・Markdown階層は柔軟）")
    assert "# 汎用詳細設計知識 v4" in text
    assert "- クラス図" in text
    assert "- データ変換・制約" in text
    assert not (
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/design_knowledge_index_v1.json"
    ).exists()


def test_all_targets_use_same_fixed_knowledge_without_source_feature_top_k() -> None:
    bundles = []
    for relative in (
        "configs/rag/roundtrip_ab_v1/retrieval_pilots/"
        "riscv-simulator-instruction.json",
        "configs/rag/roundtrip_ab_v1/retrieval_pilots/echo-web-server-io.json",
    ):
        config = load_json(PROJECT_ROOT / relative)
        retrieval = config["retrieval"]
        assert retrieval["source_feature_selection"] is False
        assert "knowledge_index_path" not in retrieval
        assert "knowledge_index_sha256" not in retrieval
        assert "knowledge_top_k" not in retrieval
        repository = resolve_repository_root(config, PROJECT_ROOT)
        bundles.append(build_retrieval_bundle(config, PROJECT_ROOT, repository))

    assert bundles[0].fixed_design_knowledge == bundles[1].fixed_design_knowledge
    for bundle in bundles:
        assert bundle.query["source_feature_selection_used"] is False
        assert bundle.query["knowledge_top_k_used"] is False
        assert bundle.manifest["source_feature_selection_used"] is False
        assert bundle.manifest["knowledge_top_k_used"] is False


def test_retrieval_rejects_fixed_knowledge_hash_mismatch() -> None:
    config = load_json(
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/retrieval_pilots/"
        "riscv-simulator-instruction.json"
    )
    config["retrieval"]["fixed_design_knowledge_sha256"] = "0" * 64
    repository = resolve_repository_root(config, PROJECT_ROOT)

    with pytest.raises(RoundtripABError, match="file SHA-256 mismatch"):
        build_retrieval_bundle(config, PROJECT_ROOT, repository)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_feature_selection", True),
        ("knowledge_top_k", 5),
        ("knowledge_index_path", "prohibited.json"),
    ],
)
def test_retrieval_rejects_feature_or_top_k_knowledge_selection(
    field: str, value: object
) -> None:
    config = load_json(
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/retrieval_pilots/"
        "echo-web-server-io.json"
    )
    config["retrieval"][field] = value
    repository = resolve_repository_root(config, PROJECT_ROOT)

    with pytest.raises(RoundtripABError):
        build_retrieval_bundle(config, PROJECT_ROOT, repository)


def test_condition_a_rejects_rag_context() -> None:
    with pytest.raises(RoundtripABError, match="Condition A"):
        compose_design_prompt(
            "base", (_target_input(),), condition="A", rag_context="forbidden"
        )


def test_code_request_accepts_design_only_and_uses_common_protocol() -> None:
    common = load_common_config(COMMON_PATH, PROJECT_ROOT)

    request = build_code_request("UNIQUE FINAL DESIGN", common, PROJECT_ROOT)

    assert "UNIQUE FINAL DESIGN" in request.prompt
    assert "RAG_CONTEXT" not in request.prompt
    assert "fixed scaffold" not in request.prompt.lower()
    assert "src/target.cpp" not in request.prompt
    assert request.audit["allowed_semantic_inputs"] == [
        "final design specification"
    ]
    assert request.audit["original_target_source_loaded"] is False
    assert request.audit["dependency_header_loaded"] is False
    assert request.audit["repository_access_used"] is False


def test_common_prompt_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    common = load_json(COMMON_PATH)
    common["prompts"]["design_generation"] = "changed.txt"
    common["prompts"]["design_generation_sha256"] = "0" * 64
    (tmp_path / "changed.txt").write_text("changed", encoding="utf-8")
    for name in (
        "code_generation_system",
        "code_generation_user",
        "code_generation_schema",
    ):
        original = PROJECT_ROOT / common["prompts"][name]
        copied = tmp_path / original.name
        copied.write_bytes(original.read_bytes())
        common["prompts"][name] = copied.name
    path = tmp_path / "common.json"
    path.write_text(json.dumps(common), encoding="utf-8")

    with pytest.raises(RoundtripABError, match="hash mismatch"):
        load_common_config(path, tmp_path)


def test_dependency_retrieval_is_direct_generic_and_excludes_target_owned(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    (repository / "src").mkdir(parents=True)
    (repository / "include").mkdir(parents=True)
    (repository / "src/target.cpp").write_text(
        '#include "target.h"\n#include "dep.h"\n#include <vector>\n'
        "int target() { return Alias{}; }\n",
        encoding="utf-8",
    )
    (repository / "include/target.h").write_text(
        "int target();\n", encoding="utf-8"
    )
    (repository / "include/dep.h").write_text(
        "// dependency comment\n"
        '#include "nested.h"\n'
        "#include <concepts>\n"
        "using Alias = unsigned int;\n"
        "template <typename T>\n"
        "concept Addable = requires(T a, T b) { a + b; };\n"
        "inline int helper() { return 1; }\n",
        encoding="utf-8",
    )
    (repository / "include/nested.h").write_text(
        "using Nested = int;\n", encoding="utf-8"
    )
    config = _minimal_config()
    config["target_owned_inputs"].append(
        {
            "file_id": "F02",
            "unit_id": "U02",
            "path": "include/target.h",
            "role": "target-owned declaration",
            "scope": "full_file",
        }
    )
    inputs = (
        _target_input(
            '#include "target.h"\n#include "dep.h"\n#include <vector>\n'
            "int target() { return Alias{}; }\n"
        ),
        TargetInput(
            file_id="F02",
            unit_id="U02",
            path="include/target.h",
            replacement_required=False,
            role="target-owned declaration",
            content="int target();\n",
            source_file_sha256="",
            content_sha256="",
        ),
    )

    records = retrieve_dependency_headers(config, repository, inputs)
    expected = (repository / "include/dep.h").read_text(encoding="utf-8")

    assert [record["path"] for record in records] == ["include/dep.h"]
    assert records[0]["content"] == expected
    assert records[0]["content_sha256"] == sha256_bytes(expected.encode("utf-8"))
    assert "// dependency comment" in records[0]["content"]
    assert '#include "nested.h"' in records[0]["content"]
    assert "#include <concepts>" in records[0]["content"]
    assert "concept Addable = requires" in records[0]["content"]
    assert "return 1" in records[0]["content"]


def test_echo_io_util_header_is_injected_whole_with_concept_unchanged() -> None:
    config = load_json(
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/retrieval_pilots/echo-web-server-io.json"
    )
    repository = resolve_repository_root(config, PROJECT_ROOT)
    bundle = build_retrieval_bundle(config, PROJECT_ROOT, repository)
    record = next(
        item
        for item in bundle.dependency_records
        if item["path"] == "include/util.h"
    )
    raw = (repository / "include/util.h").read_bytes()
    normalized = raw.decode("utf-8-sig").replace("\r\n", "\n").replace(
        "\r", "\n"
    )
    expected_bytes = normalized.encode("utf-8")
    marker = (
        "----- BEGIN DEPENDENCY HEADER CONTENT: include/util.h -----\n"
    ).encode("utf-8")
    context_bytes = bundle.context.encode("utf-8")
    start = context_bytes.index(marker) + len(marker)
    injected = context_bytes[start : start + record["content_bytes"]]

    assert record["source_sha256"] == sha256_bytes(raw)
    assert record["content"] == normalized
    assert record["content_bytes"] == len(expected_bytes)
    assert record["content_sha256"] == sha256_bytes(expected_bytes)
    assert injected == expected_bytes
    assert (
        "template <typename T, typename U, typename Ret = T>\n"
        "concept Addable = requires(T t, U u) {\n"
        "    { t + u } -> std::convertible_to<Ret>;\n"
        "};"
    ) in record["content"]
    assert "@example tests/util_test.cpp" in record["content"]
    assert "#include <concepts>" in record["content"]


@pytest.mark.parametrize(
    ("relative_config", "expected_path", "expected_symbol"),
    [
        (
            "configs/rag/roundtrip_ab_v1/retrieval_pilots/"
            "riscv-simulator-instruction.json",
            "src/Common/Common.h",
            "using Immediate",
        ),
        (
            "configs/rag/roundtrip_ab_v1/retrieval_pilots/"
            "echo-web-server-io.json",
            "include/containers/buffer.h",
            "class Buffer",
        ),
    ],
)
def test_real_retrieval_only_gate_finds_required_dependency(
    relative_config: str, expected_path: str, expected_symbol: str
) -> None:
    config = load_json(PROJECT_ROOT / relative_config)
    repository = resolve_repository_root(config, PROJECT_ROOT)

    first = build_retrieval_bundle(config, PROJECT_ROOT, repository)
    second = build_retrieval_bundle(config, PROJECT_ROOT, repository)

    assert first.manifest["status"] == "pass"
    assert first.manifest["llm_call_count"] == 0
    assert first.manifest["generation_server_contacted"] is False
    assert first.context == second.context
    assert first.query == second.query
    assert first.fixed_design_knowledge == second.fixed_design_knowledge
    assert first.dependency_records == second.dependency_records
    assert first.manifest == second.manifest
    assert first.manifest["context_sha256"] == second.manifest["context_sha256"]
    match = next(
        item for item in first.dependency_records if item["path"] == expected_path
    )
    assert expected_symbol in match["content"]


def test_plan_records_zero_calls_and_identical_base_prompt() -> None:
    config = load_json(
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/mechanics_pilot/"
        "yaml-cpp-decode-base64.json"
    )
    common = load_common_config(COMMON_PATH, PROJECT_ROOT)

    plan = build_plan(config, common, PROJECT_ROOT)

    assert plan["llm_call_count"] == 0
    assert plan["generation_server_contacted"] is False
    assert plan["conditions"]["A"]["rag_context_injected"] is False
    assert plan["conditions"]["B"]["rag_context_injected"] is True
    assert plan["code_generation_semantic_input"] == (
        "final_design_specification_only"
    )


def test_retrieval_artifacts_refuse_overwrite(tmp_path: Path) -> None:
    config = load_json(
        PROJECT_ROOT
        / "configs/rag/roundtrip_ab_v1/retrieval_pilots/"
        "riscv-simulator-instruction.json"
    )
    repository = resolve_repository_root(config, PROJECT_ROOT)
    bundle = build_retrieval_bundle(config, PROJECT_ROOT, repository)
    output = tmp_path / "retrieval"

    write_retrieval_bundle(output, bundle)

    with pytest.raises(RoundtripABError, match="already exists"):
        write_retrieval_bundle(output, bundle)


def test_strict_json_validation_accepts_exact_units() -> None:
    expected = [{"file_id": "F01", "unit_id": "U01"}]
    parsed = validate_generated_units(
        '{"units":[{"file_id":"F01","unit_id":"U01","content":"int f(){}"}]}',
        expected,
    )

    assert parsed == {("F01", "U01"): "int f(){}"}


@pytest.mark.parametrize(
    "response",
    [
        '{"units":[{"file_id":"F01","unit_id":"U01","content":"&lt;x&gt;"}]}',
        '{"units":[{"file_id":"F02","unit_id":"U02","content":"x"}]}',
        "```json\n{}\n```",
    ],
)
def test_strict_json_validation_rejects_invalid_output(response: str) -> None:
    with pytest.raises(RoundtripABError):
        validate_generated_units(
            response, [{"file_id": "F01", "unit_id": "U01"}]
        )


def test_span_replacement_restores_exact_original_bytes(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    source = repository / "source.cpp"
    original = b"before\r\nint old() { return 1; }\r\nafter\r\n"
    source.write_bytes(original)
    start = original.index(b"int old")
    end = original.index(b"\r\nafter")
    units = [
        {
            "file_id": "F01",
            "unit_id": "U01",
            "path": "source.cpp",
            "scope": "byte_span",
            "start_byte": start,
            "end_byte": end,
            "source_file_sha256": sha256_bytes(original),
            "content_sha256": sha256_bytes(original[start:end]),
        }
    ]
    transaction = SourceReplacementTransaction(
        repository,
        units,
        {("F01", "U01"): "int old() { return 2; }"},
    )

    transaction.apply()
    assert b"return 2" in source.read_bytes()
    restored = transaction.restore()

    assert source.read_bytes() == original
    assert restored["source.cpp"] == sha256_bytes(original)


def test_mocked_mechanics_pipeline_is_design_only_and_restores_source(
    tmp_path: Path,
) -> None:
    config, common = _make_execution_fixture(tmp_path)
    source = tmp_path / "repo/src/target.cpp"
    original = source.read_bytes()
    requests: list[dict[str, object]] = []

    def fake_generation(
        _endpoint: str, _headers: object, request_bytes: bytes, _timeout: int
    ) -> bytes:
        request = json.loads(request_bytes)
        requests.append(request)
        if len(requests) == 1:
            return json.dumps(
                {
                    "done_reason": "stop",
                    "response": "F01/U01 is the complete replacement unit.",
                }
            ).encode()
        generated = json.dumps(
            {
                "units": [
                    {
                        "file_id": "F01",
                        "unit_id": "U01",
                        "content": "int target() { return 2; }\n",
                    }
                ]
            }
        )
        return json.dumps({"done_reason": "stop", "response": generated}).encode()

    result = execute_condition_once(
        config,
        common,
        tmp_path,
        "B",
        call_generation=fake_generation,
    )

    assert result["status"] == "pass"
    assert result["llm_call_count"] == 2
    assert source.read_bytes() == original
    assert len(requests) == 2
    code_request = requests[1]
    assert "target() { return 1; }" not in code_request["prompt"]
    assert "RAG_CONTEXT" not in code_request["prompt"]
    audit = json.loads(
        (
            tmp_path
            / "experiments/pilot/condition-b/code/request_audit.json"
        ).read_text(encoding="utf-8")
    )
    assert audit["allowed_semantic_inputs"] == ["final design specification"]
    assert audit["fixed_scaffold_loaded"] is False


def test_failed_one_shot_cannot_be_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, common = _make_execution_fixture(tmp_path)
    monkeypatch.setattr(
        roundtrip_ab_module,
        "build_retrieval_bundle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Condition A must not execute retrieval")
        ),
    )

    def invalid_generation(
        _endpoint: str, _headers: object, _request: bytes, _timeout: int
    ) -> bytes:
        return json.dumps(
            {"done_reason": "stop", "response": "not valid code JSON"}
        ).encode()

    with pytest.raises(RoundtripABError, match="not valid JSON"):
        execute_condition_once(
            config,
            common,
            tmp_path,
            "A",
            call_generation=invalid_generation,
        )

    failure = tmp_path / "experiments/pilot/condition-a/failure.json"
    assert failure.is_file()
    assert json.loads(failure.read_text(encoding="utf-8"))["retry_performed"] is False
    with pytest.raises(RoundtripABError, match="already exists"):
        execute_condition_once(
            config,
            common,
            tmp_path,
            "A",
            call_generation=invalid_generation,
        )
