from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable


PROTOCOL_ID = "deterministic-exact-contract-v6-formal-001"
PROMPT_PROFILE = "source-faithful-detailed-design-v6"
BASE_PROMPT_PROFILE = "source-faithful-detailed-design-v4"
CONTROL_CONDITION = "full_source_deterministic_exact_contract_v6_non_rag"
RAG_CONDITION = "full_source_deterministic_exact_contract_v6_rag"
GENERIC_KNOWLEDGE_FILE = "knowledge/detailed-design/general-v4.md"
TOKENIZER_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct"
EXPECTED_TRANSFORMERS_VERSION = "4.57.6"
EXPECTED_MODEL = "qwen2.5-coder:32b"
EXPECTED_NUM_CTX = 32768
EXPECTED_NUM_PREDICT = 16384
EXPECTED_TREE_SITTER = "0.26.0"
EXPECTED_TREE_SITTER_CPP = "0.23.4"
BUDGET_RULE = "assembled_code_regeneration_input_tokens + num_predict <= num_ctx"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve().parent
ROUNDTRIP_ROOT = HERE.parent
V4_RUNNER = ROUNDTRIP_ROOT / "roundtrip_v4" / "run_target_v4.py"
DIRECT_RETRIEVAL = ROUNDTRIP_ROOT / "roundtrip_v5" / "direct_include_retrieval.py"
CONTRACT_EXTRACTOR = HERE / "contract_extractor.py"

v4 = load_module("roundtrip_v4_runner_for_v6", V4_RUNNER)
v2 = v4.v3.v2
retrieval = load_module("direct_include_retrieval_for_v6", DIRECT_RETRIEVAL)
contract_extractor = load_module("contract_extractor_for_v6_runner", CONTRACT_EXTRACTOR)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def runtime_package_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def common_design_context(project_root: Path) -> str:
    path = project_root / GENERIC_KNOWLEDGE_FILE
    if not path.is_file():
        raise FileNotFoundError(path)
    generic = read_text(path).strip()
    if not generic:
        raise ValueError(f"Generic design knowledge is empty: {path}")
    return "# Generic detailed-design guidance\n\n" + generic + "\n"


def _required_bool(value: Any, expected: bool, field: str) -> None:
    if value is not expected:
        raise ValueError(f"{field} must be {str(expected).lower()}")


def validate_v6_config(
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

    if config.get("schema_version") != "6.0-formal":
        raise ValueError("schema_version must be '6.0-formal'")
    _required_bool(config.get("pilot_only"), False, "pilot_only")
    _required_bool(config.get("formal_result_eligible"), True, "formal_result_eligible")

    condition = config.get("condition")
    if condition not in {CONTROL_CONDITION, RAG_CONDITION}:
        raise ValueError(f"Unsupported v6 condition: {condition!r}")

    if config.get("design_prompt_profile") != PROMPT_PROFILE:
        raise ValueError(f"design_prompt_profile must be {PROMPT_PROFILE!r}")

    model = config.get("model") or {}
    if model.get("name") != EXPECTED_MODEL:
        raise ValueError(f"model.name must be {EXPECTED_MODEL!r}")
    if model.get("temperature") != 0:
        raise ValueError("model.temperature must be 0")
    if model.get("seed") != 42:
        raise ValueError("model.seed must be 42")
    if model.get("num_ctx") != EXPECTED_NUM_CTX:
        raise ValueError(f"model.num_ctx must be {EXPECTED_NUM_CTX}")
    if model.get("num_predict") != EXPECTED_NUM_PREDICT:
        raise ValueError(f"model.num_predict must be {EXPECTED_NUM_PREDICT}")
    if model.get("generations", 1) != 1:
        raise ValueError("model.generations must be 1")
    if model.get("retry", False) is not False:
        raise ValueError("model.retry must be false")
    if model.get("automatic_repair", False) is not False:
        raise ValueError("model.automatic_repair must be false")

    knowledge = config.get("design_knowledge") or {}
    if knowledge.get("enabled") is not True:
        raise ValueError("design_knowledge.enabled must be true for both v6 conditions")
    if knowledge.get("context_file") != GENERIC_KNOWLEDGE_FILE:
        raise ValueError(
            f"design_knowledge.context_file must be {GENERIC_KNOWLEDGE_FILE!r}"
        )
    if knowledge.get("instruction_mode") != "required_additional_artifacts":
        raise ValueError(
            "design_knowledge.instruction_mode must be 'required_additional_artifacts'"
        )

    design_context = config.get("design_context") or {}
    if design_context.get("common_context_file") != GENERIC_KNOWLEDGE_FILE:
        raise ValueError("design_context.common_context_file mismatch")
    if design_context.get("common_render_mode") != "v5_generic_guidance_prefix":
        raise ValueError("design_context.common_render_mode mismatch")
    if not isinstance(design_context.get("common_context_sha256"), str):
        raise ValueError("design_context.common_context_sha256 is required")

    repository_retrieval = config.get("repository_retrieval") or {}
    contract_cfg = config.get("deterministic_contract") or {}

    if contract_cfg.get("extractor_version") != contract_extractor.EXTRACTOR_VERSION:
        raise ValueError("deterministic_contract.extractor_version mismatch")
    if contract_cfg.get("source_local_required") is not True:
        raise ValueError("source-local contract must be required")
    if not isinstance(contract_cfg.get("expected_source_contract_sha256"), str):
        raise ValueError("expected source-contract hash is required")
    if not isinstance(contract_cfg.get("expected_combined_contract_sha256"), str):
        raise ValueError("expected combined-contract hash is required")

    if condition == CONTROL_CONDITION:
        if repository_retrieval.get("enabled") is not False:
            raise ValueError("non-RAG repository_retrieval.enabled must be false")
        if repository_retrieval.get("mode") != "none":
            raise ValueError("non-RAG repository_retrieval.mode must be 'none'")
        if contract_cfg.get("mode") != "nonrag":
            raise ValueError("non-RAG deterministic_contract.mode must be 'nonrag'")
        if contract_cfg.get("dependency_api_required") is not False:
            raise ValueError("non-RAG dependency API contract must be disabled")
        if contract_cfg.get("expected_dependency_contract_sha256") is not None:
            raise ValueError("non-RAG dependency contract hash must be null")
    else:
        expected_retrieval_fields = {
            "enabled": True,
            "mode": "direct_include_whole_file_one_hop",
            "quoted_includes_only": True,
            "tracked_files_only": True,
            "whole_file": True,
            "depth": 1,
            "exclude_target_source_files": True,
            "target_specific_tuning": False,
        }
        for key, expected in expected_retrieval_fields.items():
            if repository_retrieval.get(key) != expected:
                raise ValueError(
                    f"repository_retrieval.{key} must be {expected!r}"
                )
        if not isinstance(
            repository_retrieval.get("expected_combined_context_sha256"), str
        ):
            raise ValueError("RAG expected_combined_context_sha256 is required")
        if not isinstance(repository_retrieval.get("expected_selected_paths"), list):
            raise ValueError("RAG expected_selected_paths must be a list")
        if not isinstance(
            repository_retrieval.get("frozen_reference_manifest_sha256"), str
        ):
            raise ValueError("RAG frozen reference manifest hash is required")
        if contract_cfg.get("mode") != "rag":
            raise ValueError("RAG deterministic_contract.mode must be 'rag'")
        if contract_cfg.get("dependency_api_required") is not True:
            raise ValueError("RAG dependency API contract must be required")
        if not isinstance(contract_cfg.get("expected_dependency_contract_sha256"), str):
            raise ValueError("RAG dependency contract hash is required")

    budget = config.get("context_budget") or {}
    if budget.get("rule") != BUDGET_RULE:
        raise ValueError("context budget rule mismatch")
    if budget.get("tokenizer") != TOKENIZER_NAME:
        raise ValueError("context budget tokenizer mismatch")
    if budget.get("transformers_version") != EXPECTED_TRANSFORMERS_VERSION:
        raise ValueError("context budget transformers version mismatch")
    if budget.get("action_on_violation") != "stop_before_code_regeneration_no_retry":
        raise ValueError("context budget violation action mismatch")

    protocol = config.get("protocol") or {}
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise ValueError(f"protocol.protocol_id must be {PROTOCOL_ID!r}")
    if protocol.get("formal_target_set_member") is not True:
        raise ValueError("protocol.formal_target_set_member must be true")
    if protocol.get("result_classification") != "formal_paired_v6":
        raise ValueError("protocol.result_classification mismatch")
    if protocol.get("design_prompt_profile") != PROMPT_PROFILE:
        raise ValueError("protocol.design_prompt_profile mismatch")
    if protocol.get("original_source_in_code_regeneration") is not False:
        raise ValueError("original source must not enter code regeneration")
    if protocol.get("retrieved_context_in_code_regeneration") is not False:
        raise ValueError("retrieved context must not enter code regeneration")
    if protocol.get("retry") is not False:
        raise ValueError("protocol.retry must be false")
    if protocol.get("automatic_repair") is not False:
        raise ValueError("protocol.automatic_repair must be false")
    if protocol.get("generated_code_manual_edit") is not False:
        raise ValueError("protocol.generated_code_manual_edit must be false")
    if protocol.get("generations_per_stage") != 1:
        raise ValueError("protocol.generations_per_stage must be 1")

    if check_files:
        if project_root is None:
            raise ValueError("project_root is required when check_files=True")
        if runtime_package_version("tree-sitter") != EXPECTED_TREE_SITTER:
            raise RuntimeError("tree-sitter version mismatch")
        if runtime_package_version("tree-sitter-cpp") != EXPECTED_TREE_SITTER_CPP:
            raise RuntimeError("tree-sitter-cpp version mismatch")
        actual_common = common_design_context(project_root)
        if sha256_text(actual_common) != design_context["common_context_sha256"]:
            raise RuntimeError("Common design-context hash mismatch")

    return {
        **summary,
        "condition": condition,
        "protocol_id": PROTOCOL_ID,
        "prompt_profile": PROMPT_PROFILE,
        "contract_mode": contract_cfg.get("mode"),
    }


def validate_repository_state(config: dict[str, Any], project_root: Path) -> None:
    repository = project_root / str(config["repository_path"])
    v2.ensure_clean(repository)
    head = v2.git_output(repository, "rev-parse", "HEAD")
    if head != config["repository_commit"]:
        raise RuntimeError(
            f"Repository commit mismatch: {head} != {config['repository_commit']}"
        )


def resolve_design_context_v6(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> str:
    common = common_design_context(project_root)
    expected_common = str(config["design_context"]["common_context_sha256"])
    if sha256_text(common) != expected_common:
        raise RuntimeError("Common design context differs from frozen config")

    if config["condition"] == CONTROL_CONDITION:
        return common.strip()

    repository = project_root / str(config["repository_path"])
    source_files = v2.source_files_for(config)
    bundle = retrieval.build_bundle(
        repository=repository,
        repository_commit=str(config["repository_commit"]),
        source_files=source_files,
        generic_knowledge_path=project_root / GENERIC_KNOWLEDGE_FILE,
        pair_id=str(config["pair_id"]),
    )
    if bundle["unresolved"] or bundle["ambiguous"]:
        raise RuntimeError(
            "Direct-include retrieval is incomplete: "
            f"unresolved={len(bundle['unresolved'])}, "
            f"ambiguous={len(bundle['ambiguous'])}"
        )

    retrieval_cfg = config["repository_retrieval"]
    expected_hash = str(retrieval_cfg["expected_combined_context_sha256"])
    if bundle["combined_context_sha256"] != expected_hash:
        raise RuntimeError(
            "RAG context differs from frozen v6 config: "
            f"{bundle['combined_context_sha256']} != {expected_hash}"
        )
    expected_paths = list(retrieval_cfg["expected_selected_paths"])
    if list(bundle["selected_paths"]) != expected_paths:
        raise RuntimeError(
            "RAG selected paths differ from frozen v6 config: "
            f"{bundle['selected_paths']} != {expected_paths}"
        )

    target_sources = set(v2.source_files_for(config))
    overlap = sorted(target_sources.intersection(bundle["selected_paths"]))
    if overlap:
        raise RuntimeError(f"Target source leaked into RAG dependency paths: {overlap}")

    retrieval.write_artifacts(bundle, experiment_root / "retrieval")
    return str(bundle["combined_context"]).strip()


def generate_design_v6(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> dict[str, Any]:
    design_input = v2.read_text(experiment_root / "input" / "design_input.txt")
    knowledge_text = resolve_design_context_v6(config, project_root, experiment_root)
    system, prompt = v4.v3.build_design_prompt(config, design_input, knowledge_text)

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
        "base_prompt_profile": BASE_PROMPT_PROFILE,
        "num_ctx": config["model"]["num_ctx"],
        "num_predict": config["model"]["num_predict"],
        "retry": False,
        "automatic_repair": False,
        "generation_count": 1,
    }
    v2.write_json(raw_dir / "design_generation_metadata.json", metadata)

    text = response.get("response")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Design generation returned an empty response")

    v2.write_text(experiment_root / "generated" / "design_document_llm.md", text)

    if response.get("done_reason") != "stop":
        raise RuntimeError(
            "Design generation did not terminate normally: "
            f"done_reason={response.get('done_reason')!r}, "
            f"eval_count={response.get('eval_count')!r}"
        )

    validation = v4.validate_generated_design_v4(config, text, experiment_root)
    validation["prompt_profile"] = PROMPT_PROFILE
    validation["base_prompt_profile"] = BASE_PROMPT_PROFILE
    v2.write_json(raw_dir / "design_contract_validation.json", validation)
    return metadata


def append_deterministic_contract_v6(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> dict[str, Any]:
    config_path = experiment_root / "configs" / "target_config.json"
    mode = str(config["deterministic_contract"]["mode"])
    retrieval_manifest_path = None
    if mode == "rag":
        retrieval_manifest_path = experiment_root / "retrieval" / "retrieval_manifest.json"
        if not retrieval_manifest_path.is_file():
            raise FileNotFoundError(retrieval_manifest_path)

    result = contract_extractor.extract_contracts(
        project_root=project_root,
        config_path=config_path,
        mode=mode,
        retrieval_manifest_path=retrieval_manifest_path,
    )

    expected = config["deterministic_contract"]
    manifest = result["manifest"]
    checks = {
        "source_contract_sha256": expected["expected_source_contract_sha256"],
        "dependency_contract_sha256": expected["expected_dependency_contract_sha256"],
        "combined_contract_sha256": expected["expected_combined_contract_sha256"],
    }
    for key, expected_value in checks.items():
        if manifest.get(key) != expected_value:
            raise RuntimeError(
                f"Formal contract differs from pre-formal freeze for {key}: "
                f"{manifest.get(key)!r} != {expected_value!r}"
            )

    if mode == "rag":
        retrieval_cfg = config["repository_retrieval"]
        if manifest.get("retrieval_context_sha256") != retrieval_cfg.get(
            "expected_combined_context_sha256"
        ):
            raise RuntimeError("Contract retrieval-context hash mismatch")
        if list(manifest.get("selected_dependency_paths") or []) != list(
            retrieval_cfg.get("expected_selected_paths") or []
        ):
            raise RuntimeError("Contract selected dependency paths mismatch")

    contract_extractor.write_outputs(result, experiment_root / "contracts")

    llm_design_path = experiment_root / "generated" / "design_document_llm.md"
    llm_design = v2.read_text(llm_design_path)
    combined = str(result["combined_contract"])
    augmented = llm_design.rstrip() + "\n\n" + combined.rstrip() + "\n"
    final_path = experiment_root / "generated" / "design_document.md"
    v2.write_text(final_path, augmented)

    final_manifest = {
        "schema_version": "6.0",
        "construction": "one-shot LLM design + deterministic exact-contract append",
        "llm_design_sha256": sha256_text(llm_design),
        "combined_contract_sha256": manifest["combined_contract_sha256"],
        "augmented_design_sha256": sha256_text(augmented),
        "contract_mode": mode,
        "llm_generation_count": 1,
        "contract_llm_called": False,
        "deterministic_contract": True,
    }
    v2.write_json(
        experiment_root / "generated" / "design_document_manifest.json",
        final_manifest,
    )
    return {"contract_manifest": manifest, "design_manifest": final_manifest}


def count_chat_tokens(tokenizer: Any, system: str, prompt: str) -> int:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
    )
    return len(ids)


def regenerate_v6_with_budget_guard(
    config: dict[str, Any],
    experiment_root: Path,
) -> dict[str, Any]:
    transformers_version = runtime_package_version("transformers")
    if transformers_version != EXPECTED_TRANSFORMERS_VERSION:
        raise RuntimeError(
            "transformers version mismatch: "
            f"{transformers_version!r} != {EXPECTED_TRANSFORMERS_VERSION!r}"
        )

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_NAME,
        trust_remote_code=False,
        local_files_only=True,
    )

    original_call: Callable[..., Any] = v2.call_ollama
    call_count = 0

    def guarded_call(payload: dict[str, Any]):
        nonlocal call_count
        call_count += 1
        if call_count != 1:
            raise RuntimeError("Code regeneration attempted more than one LLM call")

        system = payload.get("system")
        prompt = payload.get("prompt")
        if not isinstance(system, str) or not isinstance(prompt, str):
            raise RuntimeError("Code-regeneration payload is missing system/prompt")
        if payload.get("model") != config["model"]["name"]:
            raise RuntimeError("Code-regeneration model differs from frozen config")

        input_tokens = count_chat_tokens(tokenizer, system, prompt)
        num_ctx = int(config["model"]["num_ctx"])
        num_predict = int(config["model"]["num_predict"])
        total_reserved = input_tokens + num_predict
        passed = total_reserved <= num_ctx

        budget_record = {
            "schema_version": "6.0",
            "rule": BUDGET_RULE,
            "tokenizer": TOKENIZER_NAME,
            "transformers_version": transformers_version,
            "assembled_code_regeneration_input_tokens": input_tokens,
            "num_predict": num_predict,
            "num_ctx": num_ctx,
            "input_plus_reserved_output": total_reserved,
            "headroom_after_reserved_output": num_ctx - total_reserved,
            "passed": passed,
            "system_sha256": sha256_text(system),
            "prompt_sha256": sha256_text(prompt),
            "llm_call_attempted": False,
            "llm_call_returned": False,
            "retry": False,
            "automatic_repair": False,
        }
        raw_dir = experiment_root / "raw_output"
        v2.write_json(raw_dir / "code_regeneration_budget.json", budget_record)
        v2.write_json(
            raw_dir / "code_regeneration_request_budgeted.json",
            payload,
        )

        if not passed:
            raise RuntimeError(
                "Fixed v6 context-budget rule failed before code regeneration: "
                f"{input_tokens} + {num_predict} > {num_ctx}"
            )

        budget_record["llm_call_attempted"] = True
        v2.write_json(raw_dir / "code_regeneration_budget.json", budget_record)
        try:
            result = original_call(payload)
        except Exception as exc:
            budget_record["llm_call_error"] = f"{type(exc).__name__}: {exc}"
            v2.write_json(raw_dir / "code_regeneration_budget.json", budget_record)
            raise
        budget_record["llm_call_returned"] = True
        v2.write_json(raw_dir / "code_regeneration_budget.json", budget_record)
        return result

    v2.call_ollama = guarded_call
    try:
        metadata = v2.regenerate(config, experiment_root)
    finally:
        v2.call_ollama = original_call

    if call_count != 1:
        raise RuntimeError(f"Expected one code-regeneration LLM call, got {call_count}")
    if metadata.get("done_reason") != "stop":
        raise RuntimeError(
            "Code regeneration did not terminate normally: "
            f"done_reason={metadata.get('done_reason')!r}, "
            f"eval_count={metadata.get('eval_count')!r}"
        )
    return metadata


def plan_record(config: dict[str, Any], project_root: Path) -> dict[str, Any]:
    validate_repository_state(config, project_root)
    experiment_root = v2.resolve_experiment_root(config, project_root)
    return {
        "valid": True,
        "enabled": bool(config.get("enabled", False)),
        "pair_id": config.get("pair_id"),
        "condition": config.get("condition"),
        "experiment_id": config.get("experiment_id"),
        "run_id": config.get("run_id"),
        "experiment_root": str(experiment_root),
        "experiment_root_exists": experiment_root.exists(),
        "repository_commit": config.get("repository_commit"),
        "contract_mode": (config.get("deterministic_contract") or {}).get("mode"),
        "context_budget_rule": (config.get("context_budget") or {}).get("rule"),
        "llm_called": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one deterministic exact-contract v6 paired formal target."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--validate-config-only", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    if args.validate_config_only and args.plan_only:
        raise ValueError("Choose only one of --validate-config-only or --plan-only")

    project_root = args.project_root.resolve()
    config_path = args.config if args.config.is_absolute() else project_root / args.config
    config = v2.load_json(config_path)

    validation = validate_v6_config(
        config,
        project_root=project_root,
        check_files=True,
    )

    if args.validate_config_only:
        print(json.dumps({"valid": True, **validation}, ensure_ascii=False, indent=2))
        return 0

    if args.plan_only:
        print(json.dumps(plan_record(config, project_root), ensure_ascii=False, indent=2))
        return 0

    if not config.get("enabled", False):
        raise RuntimeError("Target config is disabled")

    validate_repository_state(config, project_root)
    experiment_root = v2.resolve_experiment_root(config, project_root)
    if experiment_root.exists():
        raise FileExistsError(
            f"Experiment directory already exists: {experiment_root}. "
            "Use the frozen run ID exactly once; do not overwrite a run."
        )

    stage = "prepare"
    try:
        v2.prepare(config, project_root, experiment_root)
        stage = "design_generation"
        generate_design_v6(config, project_root, experiment_root)
        stage = "deterministic_contract_append"
        append_deterministic_contract_v6(config, project_root, experiment_root)
        stage = "code_regeneration"
        regenerate_v6_with_budget_guard(config, experiment_root)
        stage = "evaluation"
        result = v2.evaluate(config, project_root, experiment_root)
    except Exception as exc:
        v2.record_pipeline_failure(config, experiment_root, stage, exc)
        raise

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
