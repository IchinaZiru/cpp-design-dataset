from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

import scripts.rag.roundtrip_ab_formal as formal_module
from scripts.rag.canonical import sha256_bytes, sha256_file
from scripts.rag.roundtrip_ab import RoundtripABError, load_json, load_target_inputs, resolve_repository_root
from scripts.rag.roundtrip_ab_formal import (
    build_design_request_v2,
    build_plan_v2,
    build_retrieval_bundle_v2,
    execute_condition_v2_once,
    load_common_v2,
    load_formal_manifest,
    validate_target_v2,
    verify_formal_authorization,
)


ROOT = Path(__file__).resolve().parents[2]
COMMON_PATH = ROOT / "configs/rag/roundtrip_ab_v1/common.json"
MANIFEST_PATH = ROOT / "configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json"
AUTH_PATH = ROOT / "configs/rag/roundtrip_ab_v1/formal/execution_authorization.json"


def test_manifest_freezes_17_new_formal_targets_including_instruction() -> None:
    manifest = load_formal_manifest(MANIFEST_PATH, ROOT)
    ids = [item["target_id"] for item in manifest["targets"]]
    assert len(ids) == len(set(ids)) == 17
    assert "riscv-simulator-instruction" in ids
    assert manifest["formal_completed_target_count"] == 0
    assert manifest["formal_execution_started"] is False
    assert manifest["instruction_development_results_reused"] is False


def test_all_targets_bind_common_knowledge_and_prohibit_target_overrides() -> None:
    common = load_common_v2(COMMON_PATH, ROOT)
    manifest = load_formal_manifest(MANIFEST_PATH, ROOT)
    assert common["common_design_knowledge"]["target_override_allowed"] is False
    prohibited = formal_module.COMMON_KNOWLEDGE_TARGET_KEYS | formal_module.TARGET_TUNING_KEYS
    for entry in manifest["targets"]:
        config = load_json(ROOT / entry["target_config_path"])
        assert not (prohibited & set(config["retrieval"]))
        changed = copy.deepcopy(config)
        changed["retrieval"]["fixed_design_knowledge_path"] = "target-specific.txt"
        with pytest.raises(RoundtripABError, match="target-level"):
            validate_target_v2(changed)


def test_a_is_minimal_and_b_adds_treatment_knowledge_and_repository_context() -> None:
    common = load_common_v2(COMMON_PATH, ROOT)
    config = load_json(ROOT / "configs/rag/roundtrip_ab_v1/formal/targets/riscv-simulator-instruction.json")
    repository = resolve_repository_root(config, ROOT)
    inputs = load_target_inputs(config, repository)
    retrieval = build_retrieval_bundle_v2(config, common, ROOT, repository)
    a = build_design_request_v2(config, common, ROOT, inputs, condition="A", repository_context=None)
    b = build_design_request_v2(config, common, ROOT, inputs, condition="B", repository_context=retrieval.context)
    assert a.payload["model"] == b.payload["model"]
    assert a.payload["options"] == b.payload["options"]
    assert a.audit["base_prompt_sha256"] == b.audit["base_prompt_sha256"]
    assert a.audit["treatment_knowledge_sha256"] == b.audit["treatment_knowledge_sha256"]
    assert a.audit["treatment_knowledge_injected"] is False
    assert b.audit["treatment_knowledge_injected"] is True
    assert "BEGIN TREATMENT DESIGN KNOWLEDGE" not in a.prompt
    assert "V4/V5 DETAILED-DESIGN GUIDANCE" not in a.prompt
    assert "ROUND-TRIP COMPLETENESS KNOWLEDGE" not in a.prompt
    assert "BEGIN TREATMENT DESIGN KNOWLEDGE" in b.prompt
    assert "V4/V5 DETAILED-DESIGN GUIDANCE" in b.prompt
    assert "ROUND-TRIP COMPLETENESS KNOWLEDGE" in b.prompt
    assert "BEGIN RAG_CONTEXT" not in a.prompt
    assert retrieval.context not in a.prompt
    assert retrieval.context in b.prompt
    assert "using Immediate" in b.prompt


def test_generic_knowledge_has_no_instruction_implementation_facts() -> None:
    common = load_common_v2(COMMON_PATH, ROOT)
    paths = [
        ROOT / common["common_design_knowledge"]["detailed_design_guidance"]["path"],
        ROOT / common["common_design_knowledge"]["roundtrip_completeness"]["path"],
    ]
    text = "\n".join(path.read_text(encoding="utf-8-sig") for path in paths)
    for forbidden in ("Instruction.hpp", "using Immediate", "InstructionR", "RISCV_Simulator_Test"):
        assert forbidden not in text


def test_token_preflight_passes_with_native_common_context_and_stage_specific_output_limits() -> None:
    report = load_json(ROOT / "reports/rag/roundtrip-ab-v1/formal-preflight/token-preflight-v1.json")
    assert report["status"] == "pass"
    assert report["risk_target_count"] == 0
    assert report["formal_target_count"] == 17
    settings = report["common_generation"]
    assert settings["design_num_ctx"] == settings["code_num_ctx"] == 32768
    assert settings["design_num_predict"] == 8192
    assert settings["code_num_predict"] == 16384
    assert max(item["condition_b_design_request"]["input_plus_max_output"] for item in report["targets"]) < 32768
    assert report["llm_call_count"] == 0


def test_ini_writer_freezes_complete_class_span_not_legacy_body_only_span() -> None:
    config = load_json(ROOT / "configs/rag/roundtrip_ab_v1/formal/targets/ini-cpp-ini-writer.json")
    repository = resolve_repository_root(config, ROOT)
    inputs = load_target_inputs(config, repository)
    item = inputs[0]
    assert config["granularity"] == "class_span"
    assert item.content.lstrip().startswith("class INIWriter")
    assert "inline static void write(" in item.content
    assert "const bool overwrite = false) {" in item.content
    assert "out << key << \"=\"" in item.content
    assert config["replacement_units"][0]["scope"] == "byte_span"
    assert item.source_file_sha256 == "30dfffabdda27182ddf2351193c9224b533b42349e9186a4cecf40f781b0c7f1"


def test_formal_authorization_is_separate_and_initially_refuses_execution() -> None:
    authorization = load_json(AUTH_PATH)
    assert authorization["authorized"] is False
    with pytest.raises(RoundtripABError, match="not authorized"):
        verify_formal_authorization(AUTH_PATH, MANIFEST_PATH, COMMON_PATH, ROOT)


def _init_repo(path: Path) -> str:
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "formal@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Formal Test"], check=True)
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def _copy_common(tmp_path: Path) -> dict[str, object]:
    source = load_json(COMMON_PATH)
    common = copy.deepcopy(source)
    for section, names in (
        ("prompts", ("design_generation", "code_generation_system", "code_generation_user", "code_generation_schema")),
    ):
        for name in names:
            source_path = ROOT / source[section][name]
            destination = tmp_path / "protocol" / source_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source_path.read_bytes())
            common[section][name] = destination.relative_to(tmp_path).as_posix()
            common[section][f"{name}_sha256"] = sha256_file(destination)
    for name in ("detailed_design_guidance", "roundtrip_completeness"):
        record = common["common_design_knowledge"][name]
        source_path = ROOT / record["path"]
        destination = tmp_path / "knowledge" / source_path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source_path.read_bytes())
        record["path"] = destination.relative_to(tmp_path).as_posix()
        record["file_sha256"] = sha256_file(destination)
    return common


def _mechanics_fixture(tmp_path: Path, granularity: str) -> tuple[dict[str, object], dict[str, object], dict[tuple[str, str], str], dict[str, bytes]]:
    repository = tmp_path / "repo"
    repository.mkdir()
    originals: dict[str, bytes]
    if granularity == "module_files":
        originals = {"one.cpp": b"int one = 1;\n", "two.cpp": b"int two = 2;\n"}
    else:
        originals = {"target.cpp": b"AAA BBB CCC DDD\n"}
    for relative, raw in originals.items():
        (repository / relative).write_bytes(raw)
    commit = _init_repo(repository)
    inputs = []
    units = []
    generated: dict[tuple[str, str], str] = {}
    if granularity in {"full_file", "module_files"}:
        for index, (relative, raw) in enumerate(originals.items(), 1):
            pair = (f"F{index:02d}", f"U{index:02d}")
            record = {"file_id": pair[0], "unit_id": pair[1], "path": relative, "scope": "full_file", "source_file_sha256": sha256_bytes(raw), "content_sha256": sha256_bytes(raw)}
            inputs.append({**record, "replacement_required": True, "role": "complete file"})
            units.append(record)
            generated[pair] = f"int replacement_{index} = {index};\n"
    else:
        raw = originals["target.cpp"]
        spans = [(0, 3)] if granularity != "multiple_units" else [(0, 3), (8, 11)]
        for index, (start, end) in enumerate(spans, 1):
            pair = ("F01", f"U{index:02d}")
            record = {"file_id": pair[0], "unit_id": pair[1], "path": "target.cpp", "scope": "byte_span", "start_byte": start, "end_byte": end, "source_file_sha256": sha256_bytes(raw), "content_sha256": sha256_bytes(raw[start:end])}
            inputs.append({**record, "replacement_required": True, "role": "complete replacement span"})
            units.append(record)
            generated[pair] = "XXX" if index == 1 else "YYY"
    command = ["unused"]
    config: dict[str, object] = {
        "artifact_schema_version": "roundtrip-design-only-ab-target-v2",
        "execution": {"enabled": True, "output_root": f"outputs/{granularity}", "stage_order": ["configure", "build", "direct_test", "full_test"], "commands": {stage: command for stage in ("configure", "build", "direct_test", "full_test")}, "stage_timeouts_seconds": {stage: 5 for stage in ("configure", "build", "direct_test", "full_test")}},
        "formal_execution_authorized": False,
        "formal_target_member": False,
        "granularity": "function" if granularity == "multiple_units" else granularity,
        "one_shot": {"automatic_repair": False, "code_generation_count": 1, "design_generation_count": 1, "manual_patch": False, "overwrite": False, "retry": False},
        "replacement_units": units,
        "repository": {"commit": commit, "external": False, "id": "fixture", "path": "repo"},
        "retrieval": {"dependency_header_mode": formal_module.DEPENDENCY_MODE, "dependency_header_normalization": formal_module.NORMALIZATION_MODE, "expected_evidence": [], "include_roots": [], "maximum_dependency_headers": 8, "source_feature_selection": False, "target_specific_manual_query": False, "target_specific_override": False},
        "stage": "development_test",
        "target_id": f"mechanics-{granularity}",
        "target_owned_inputs": inputs,
    }
    return config, _copy_common(tmp_path), generated, originals


def _responses(generated: dict[tuple[str, str], str]):
    values = iter(
        [
            json.dumps({"response": "complete design", "done": True}).encode(),
            json.dumps({"response": json.dumps({"units": [{"file_id": pair[0], "unit_id": pair[1], "content": content} for pair, content in generated.items()]}), "done": True}).encode(),
        ]
    )
    return lambda *_args: next(values)


@pytest.mark.parametrize("granularity", ["full_file", "module_files", "class_span", "function", "multiple_units"])
def test_mocked_end_to_end_replacement_mechanics_and_restoration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, granularity: str) -> None:
    config, common, generated, originals = _mechanics_fixture(tmp_path, granularity)
    monkeypatch.setattr(formal_module, "_run_stage", lambda stage, *_args: {"stage": stage, "status": "pass", "returncode": 0, "stdout": "", "stderr": "", "timeout": False, "command": []})
    result = execute_condition_v2_once(config, common, tmp_path, "A", formal=False, call_generation=_responses(generated))
    assert result["status"] == "pass"
    for relative, raw in originals.items():
        assert (tmp_path / "repo" / relative).read_bytes() == raw
    run_root = tmp_path / "outputs" / granularity / "condition-a"
    for relative in (
        "snapshots/common_config.json", "snapshots/target_config.json", "design/request.json", "design/response.json",
        "design/final_design.md", "retrieval/actual_rag_context.txt", "code/request.json", "code/response.json",
        "code/generated_units.json", "evaluation/source_restoration.json", "result.json", "aggregate_run_entry.json", "artifact_hashes.json",
    ):
        assert (run_root / relative).is_file()
    with pytest.raises(RoundtripABError, match="one-shot"):
        execute_condition_v2_once(config, common, tmp_path, "A", formal=False, call_generation=_responses(generated))


def test_timeout_is_recorded_and_source_is_restored(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, common, generated, originals = _mechanics_fixture(tmp_path, "function")
    monkeypatch.setattr(formal_module, "_run_stage", lambda stage, *_args: {"stage": stage, "status": "fail", "returncode": None, "stdout": "", "stderr": "timeout", "timeout": True, "command": []})
    result = execute_condition_v2_once(config, common, tmp_path, "A", formal=False, call_generation=_responses(generated))
    assert result["status"] == "fail"
    assert (tmp_path / "outputs/function/condition-a/evaluation/configure.json").is_file()
    assert load_json(tmp_path / "outputs/function/condition-a/evaluation/source_restoration.json")["status"] == "pass"
    assert (tmp_path / "repo/target.cpp").read_bytes() == originals["target.cpp"]


def test_restore_failure_preserves_failure_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config, common, generated, _ = _mechanics_fixture(tmp_path, "function")
    monkeypatch.setattr(formal_module, "_run_stage", lambda stage, *_args: {"stage": stage, "status": "pass", "returncode": 0, "stdout": "", "stderr": "", "timeout": False, "command": []})
    original_restore = formal_module.SourceReplacementTransaction.restore
    def fail_restore(self):
        original_restore(self)
        raise RoundtripABError("simulated restore verification failure")
    monkeypatch.setattr(formal_module.SourceReplacementTransaction, "restore", fail_restore)
    with pytest.raises(RoundtripABError, match="source restoration failed"):
        execute_condition_v2_once(config, common, tmp_path, "A", formal=False, call_generation=_responses(generated))
    run_root = tmp_path / "outputs/function/condition-a"
    assert (run_root / "failure.json").is_file()
    assert (run_root / "artifact_hashes.json").is_file()
    assert load_json(run_root / "evaluation/source_restoration.json")["status"] == "fail"

