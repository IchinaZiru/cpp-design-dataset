from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


PROTOCOL_ID = "deterministic-exact-contract-v6-formal-001"
PROMPT_PROFILE = "source-faithful-detailed-design-v6"
CONTROL_CONDITION = "full_source_deterministic_exact_contract_v6_non_rag"
RAG_CONDITION = "full_source_deterministic_exact_contract_v6_rag"
GENERIC_KNOWLEDGE_FILE = "knowledge/detailed-design/general-v4.md"
TOKENIZER_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct"
TRANSFORMERS_VERSION = "4.57.6"
BUDGET_RULE = "assembled_code_regeneration_input_tokens + num_predict <= num_ctx"
V5_MANIFEST = Path("configs/roundtrip_v5/evaluation/generation_manifest.json")
V5_RUN_ROOT = Path("experiments/v5/evaluation/rag")
BUDGET_AUDIT = Path("analysis/v6-preformal-budget-audit/summary.json")
OUTPUT_ROOT = Path("configs/roundtrip_v6/formal")


DIRECT_TEST_METADATA_CORRECTIONS = {
    "echo-web-server-http": {
        "source_test_file": "tests/http_test.cpp",
        "names": [
            "HTTPTest.StatusCodeEnumConversion",
            "HTTPTest.MethodEnumConversion",
            "HTTPTest.ContentType",
            "HTTPTest.URLEncoding",
            "HTTPTest.HTMLPlaceholder",
            "HTTPTest.PutParameterIntoHTML",
        ],
    },
    "echo-web-server-log": {
        "source_test_file": "tests/log_test.cpp",
        "names": [
            "LoggerTest.SynchronousLog",
            "LoggerTest.AsynchronousLog",
            "LogManagementTest.LoggerManager",
            "LogManagementTest.LevelEnumConversion",
            "LogManagementTest.AppenderTypeEnumConversion",
            "LogFormatterTest.Construction",
            "LogFormatterTest.Format",
        ],
    },
}


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def common_design_context(root: Path) -> str:
    path = root / GENERIC_KNOWLEDGE_FILE
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError(f"Generic design knowledge is empty: {path}")
    return "# Generic detailed-design guidance\n\n" + text + "\n"


def build_base_config(source: dict[str, Any], *, pair_id: str, sequence: int) -> dict[str, Any]:
    config = copy.deepcopy(source)
    config["schema_version"] = "6.0-formal"
    config["enabled"] = False
    config["pilot_only"] = False
    config["formal_result_eligible"] = True
    config.pop("posthoc_refinement", None)
    config.pop("sensitivity_only", None)
    config["pair_id"] = pair_id
    config["pair_sequence"] = sequence
    config["design_prompt_profile"] = PROMPT_PROFILE

    knowledge = copy.deepcopy(config.get("design_knowledge") or {})
    knowledge.update(
        {
            "enabled": True,
            "context_file": GENERIC_KNOWLEDGE_FILE,
            "instruction_mode": "required_additional_artifacts",
        }
    )
    config["design_knowledge"] = knowledge

    protocol = copy.deepcopy(config.get("protocol") or {})
    for stale_key in (
        "repository_retrieval_mode",
        "repository_retrieval_depth",
        "repository_retrieval_whole_file",
        "repository_retrieval_target_specific_tuning",
        "retrieval_preflight_required",
        "v4_reference_config",
        "v4_reference_experiment_id",
    ):
        protocol.pop(stale_key, None)
    protocol.update(
        {
            "protocol_id": PROTOCOL_ID,
            "result_classification": "formal_paired_v6",
            "formal_target_set_member": True,
            "formal_pair_id": pair_id,
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
            "code_regeneration_inputs": [
                "augmented_design_document",
                "fixed_interface_scaffold",
                "dependency_include_context",
            ],
            "contract_extractor_version": "v6-ast-contract-1",
            "source_local_contract_common_to_both_conditions": True,
            "context_budget_rule": BUDGET_RULE,
            "context_budget_tokenizer": TOKENIZER_NAME,
            "formal_enablement_state": "disabled_preparation",
        }
    )
    config["protocol"] = protocol

    provenance = copy.deepcopy(config.get("provenance") or {})
    provenance.update(
        {
            "v6_source_config": None,
            "v6_method": "deterministic exact-contract paired formal",
            "v6_preformal_budget_audit": BUDGET_AUDIT.as_posix(),
            "v6_formal_results_not_started": True,
            "v6_treatment_difference": (
                "repository direct-include retrieval during design generation plus "
                "the deterministic dependency API contract derived from that selected context"
            ),
        }
    )
    config["provenance"] = provenance
    return config



def apply_preformal_test_metadata_correction(
    config: dict[str, Any], *, pair_id: str
) -> None:
    correction = DIRECT_TEST_METADATA_CORRECTIONS.get(pair_id)
    if correction is None:
        return

    evaluation = copy.deepcopy(config.get("evaluation") or {})
    old_names = [str(value) for value in evaluation.get("direct_test_names") or []]
    old_filter = str(evaluation.get("direct_test_filter") or "")
    old_command = str(evaluation.get("direct_test_command") or "")
    old_expected = int(evaluation.get("expected_direct_tests", -1))
    names = [str(value) for value in correction["names"]]
    new_filter = ":".join(names)

    if not old_names or not old_filter or not old_command or old_expected < 0:
        raise RuntimeError(f"Incomplete inherited direct-test metadata for {pair_id}")
    if old_filter not in old_command:
        raise RuntimeError(f"Inherited direct-test filter is not present in command for {pair_id}")
    if not set(names).issubset(set(old_names)):
        raise RuntimeError(f"Corrected direct-test set is not a subset of inherited names for {pair_id}")

    removed = [value for value in old_names if value not in names]
    evaluation["direct_test_names"] = names
    evaluation["direct_test_filter"] = new_filter
    evaluation["expected_direct_tests"] = len(names)
    evaluation["direct_test_command"] = old_command.replace(old_filter, new_filter, 1)
    config["evaluation"] = evaluation

    provenance = copy.deepcopy(config.get("provenance") or {})
    provenance["v6_preformal_direct_test_metadata_correction"] = {
        "reason": (
            "Original-source baseline probe found stale inherited direct-test names "
            "that are absent at the fixed repository commit."
        ),
        "source_test_file": correction["source_test_file"],
        "old_expected_direct_tests": old_expected,
        "new_expected_direct_tests": len(names),
        "removed_stale_test_names": removed,
        "correction_phase": "preformal_before_enablement_before_any_v6_llm_call",
    }
    config["provenance"] = provenance

def build_condition_config(
    base: dict[str, Any],
    *,
    condition_name: str,
    pair_id: str,
    common_hash: str,
    retrieval_reference: dict[str, Any] | None,
    retrieval_manifest_rel: str | None,
    retrieval_manifest_sha: str | None,
) -> dict[str, Any]:
    config = copy.deepcopy(base)
    is_rag = condition_name == "rag"

    if is_rag:
        config["condition"] = RAG_CONDITION
        config["target_id"] = f"{pair_id}-v6-formal-rag"
        config["experiment_id"] = f"v6/formal/rag/{pair_id}-001"
        config["run_id"] = f"{pair_id}-deterministic-exact-contract-v6-rag-formal-001"
    else:
        config["condition"] = CONTROL_CONDITION
        config["target_id"] = f"{pair_id}-v6-formal-non-rag"
        config["experiment_id"] = f"v6/formal/non-rag/{pair_id}-001"
        config["run_id"] = f"{pair_id}-deterministic-exact-contract-v6-non-rag-formal-001"

    config["design_context"] = {
        "common_context_file": GENERIC_KNOWLEDGE_FILE,
        "common_render_mode": "v5_generic_guidance_prefix",
        "common_context_sha256": common_hash,
        "repository_context_enabled": is_rag,
    }

    if is_rag:
        assert retrieval_reference is not None
        assert retrieval_manifest_rel is not None
        assert retrieval_manifest_sha is not None
        config["repository_retrieval"] = {
            "enabled": True,
            "mode": "direct_include_whole_file_one_hop",
            "quoted_includes_only": True,
            "tracked_files_only": True,
            "whole_file": True,
            "depth": 1,
            "exclude_target_source_files": True,
            "target_specific_tuning": False,
            "expected_combined_context_sha256": retrieval_reference[
                "combined_context_sha256"
            ],
            "expected_selected_paths": list(retrieval_reference["selected_paths"]),
            "frozen_reference_manifest": retrieval_manifest_rel,
            "frozen_reference_manifest_sha256": retrieval_manifest_sha,
        }
    else:
        config["repository_retrieval"] = {
            "enabled": False,
            "mode": "none",
            "target_specific_tuning": False,
        }

    config["deterministic_contract"] = {
        "mode": "rag" if is_rag else "nonrag",
        "extractor_version": "v6-ast-contract-1",
        "source_local_required": True,
        "dependency_api_required": is_rag,
        "expected_source_contract_sha256": None,
        "expected_dependency_contract_sha256": None,
        "expected_combined_contract_sha256": None,
        "expected_selected_dependency_paths": (
            list(retrieval_reference["selected_paths"])
            if is_rag and retrieval_reference is not None
            else []
        ),
    }

    config["context_budget"] = {
        "rule": BUDGET_RULE,
        "tokenizer": TOKENIZER_NAME,
        "transformers_version": TRANSFORMERS_VERSION,
        "preformal_audit": BUDGET_AUDIT.as_posix(),
        "action_on_violation": "stop_before_code_regeneration_no_retry",
    }

    protocol = copy.deepcopy(config["protocol"])
    protocol["dependency_api_contract_required"] = is_rag
    protocol["repository_retrieval_during_design_generation"] = is_rag
    config["protocol"] = protocol

    provenance = copy.deepcopy(config["provenance"])
    provenance["v6_condition"] = condition_name
    provenance["v5_retrieval_reference"] = retrieval_manifest_rel if is_rag else None
    config["provenance"] = provenance
    return config


def temp_config(root: Path, config: dict[str, Any]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="v6-config-",
        dir=root,
        encoding="utf-8",
        newline="\n",
        delete=False,
    )
    try:
        json.dump(config, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        return Path(handle.name)
    finally:
        handle.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate all-disabled paired v6 formal configs deterministically."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    output_root = root / OUTPUT_ROOT
    if output_root.exists():
        raise FileExistsError(f"Refusing to overwrite existing v6 formal configs: {output_root}")

    budget = read_json(root / BUDGET_AUDIT)
    if budget.get("proxy_go_for_preformal_config_preparation") is not True:
        raise RuntimeError("Frozen v6 budget audit does not permit config preparation")
    if int(budget.get("target_count", -1)) != 17:
        raise RuntimeError("Frozen v6 budget audit target_count is not 17")
    if int((budget.get("tokenizer_validation") or {}).get("max_abs_delta", -1)) != 0:
        raise RuntimeError("Frozen tokenizer validation is not exact")

    v5_manifest = read_json(root / V5_MANIFEST)
    targets = v5_manifest.get("targets") or []
    if len(targets) != 17:
        raise RuntimeError(f"Expected 17 v5 targets, got {len(targets)}")

    common = common_design_context(root)
    common_hash = sha256_text(common)

    contract_path = root / "scripts" / "roundtrip_v6" / "contract_extractor.py"
    retrieval_path = root / "scripts" / "roundtrip_v5" / "direct_include_retrieval.py"
    contract = load_module("contract_extractor_for_v6_config_generation", contract_path)
    retrieval = load_module("direct_include_retrieval_for_v6_config_generation", retrieval_path)

    prepared: list[dict[str, Any]] = []
    seen_pairs: set[str] = set()

    for target in sorted(targets, key=lambda row: int(row["pair_sequence"])):
        pair_id = str(target["pair_id"])
        sequence = int(target["pair_sequence"])
        if pair_id in seen_pairs:
            raise RuntimeError(f"Duplicate pair_id: {pair_id}")
        seen_pairs.add(pair_id)

        v5_config_rel = str(target["config_path"])
        v5_config = read_json(root / v5_config_rel)
        if str(v5_config.get("pair_id")) != pair_id:
            raise RuntimeError(f"v5 pair mismatch for {pair_id}")

        run_dir = root / V5_RUN_ROOT / f"{pair_id}-001"
        retrieval_manifest_path = run_dir / "retrieval" / "retrieval_manifest.json"
        if not retrieval_manifest_path.is_file():
            raise FileNotFoundError(retrieval_manifest_path)
        retrieval_manifest = read_json(retrieval_manifest_path)
        retrieval_manifest_rel = retrieval_manifest_path.relative_to(root).as_posix()
        retrieval_manifest_sha = sha256_file(retrieval_manifest_path)

        repository = root / str(v5_config["repository_path"])
        if v5_config.get("granularity") == "module_files":
            source_files = list(v5_config.get("source_files") or [])
        else:
            target_source_file = v5_config.get("target_source_file")
            source_files = (
                [str(target_source_file)]
                if isinstance(target_source_file, str) and target_source_file
                else list(v5_config.get("source_files") or [])
            )
        if not source_files:
            raise RuntimeError(f"No source files resolved for {pair_id}")
        rebuilt = retrieval.build_bundle(
            repository=repository,
            repository_commit=str(v5_config["repository_commit"]),
            source_files=source_files,
            generic_knowledge_path=root / GENERIC_KNOWLEDGE_FILE,
            pair_id=pair_id,
        )
        if rebuilt["unresolved"] or rebuilt["ambiguous"]:
            raise RuntimeError(
                f"Retrieval rebuild incomplete for {pair_id}: "
                f"unresolved={len(rebuilt['unresolved'])}, ambiguous={len(rebuilt['ambiguous'])}"
            )
        if rebuilt["combined_context_sha256"] != retrieval_manifest.get(
            "combined_context_sha256"
        ):
            raise RuntimeError(f"Frozen RAG context hash mismatch for {pair_id}")
        if list(rebuilt["selected_paths"]) != list(
            retrieval_manifest.get("selected_paths") or []
        ):
            raise RuntimeError(f"Frozen selected paths mismatch for {pair_id}")

        target_sources = set(source_files)
        overlap = sorted(target_sources.intersection(rebuilt["selected_paths"]))
        if overlap:
            raise RuntimeError(f"Target-source overlap for {pair_id}: {overlap}")

        base = build_base_config(v5_config, pair_id=pair_id, sequence=sequence)
        apply_preformal_test_metadata_correction(base, pair_id=pair_id)
        base["provenance"]["v6_source_config"] = v5_config_rel

        nonrag = build_condition_config(
            base,
            condition_name="non_rag",
            pair_id=pair_id,
            common_hash=common_hash,
            retrieval_reference=None,
            retrieval_manifest_rel=None,
            retrieval_manifest_sha=None,
        )
        rag = build_condition_config(
            base,
            condition_name="rag",
            pair_id=pair_id,
            common_hash=common_hash,
            retrieval_reference=retrieval_manifest,
            retrieval_manifest_rel=retrieval_manifest_rel,
            retrieval_manifest_sha=retrieval_manifest_sha,
        )

        temp_non = temp_config(root, nonrag)
        temp_rag = temp_config(root, rag)
        try:
            non_result = contract.extract_contracts(
                project_root=root,
                config_path=temp_non,
                mode="nonrag",
                retrieval_manifest_path=None,
            )
            rag_result = contract.extract_contracts(
                project_root=root,
                config_path=temp_rag,
                mode="rag",
                retrieval_manifest_path=retrieval_manifest_path,
            )
        finally:
            temp_non.unlink(missing_ok=True)
            temp_rag.unlink(missing_ok=True)

        non_manifest = non_result["manifest"]
        rag_manifest = rag_result["manifest"]
        if non_manifest["source_contract_sha256"] != rag_manifest["source_contract_sha256"]:
            raise RuntimeError(f"Source-local contract differs across conditions for {pair_id}")
        if rag_manifest["retrieval_context_sha256"] != retrieval_manifest.get(
            "combined_context_sha256"
        ):
            raise RuntimeError(f"RAG contract context hash mismatch for {pair_id}")
        if list(rag_manifest["selected_dependency_paths"]) != list(
            retrieval_manifest.get("selected_paths") or []
        ):
            raise RuntimeError(f"RAG contract selected paths mismatch for {pair_id}")

        nonrag["deterministic_contract"].update(
            {
                "expected_source_contract_sha256": non_manifest[
                    "source_contract_sha256"
                ],
                "expected_dependency_contract_sha256": None,
                "expected_combined_contract_sha256": non_manifest[
                    "combined_contract_sha256"
                ],
            }
        )
        rag["deterministic_contract"].update(
            {
                "expected_source_contract_sha256": rag_manifest[
                    "source_contract_sha256"
                ],
                "expected_dependency_contract_sha256": rag_manifest[
                    "dependency_contract_sha256"
                ],
                "expected_combined_contract_sha256": rag_manifest[
                    "combined_contract_sha256"
                ],
                "expected_dependency_symbol_match_count": rag_manifest[
                    "dependency_symbol_match_count"
                ],
                "expected_overload_sets": rag_manifest["overload_sets"],
            }
        )

        prepared.append(
            {
                "pair_id": pair_id,
                "pair_sequence": sequence,
                "granularity": v5_config["granularity"],
                "v5_source_config": v5_config_rel,
                "v5_retrieval_manifest": retrieval_manifest_rel,
                "v5_retrieval_manifest_sha256": retrieval_manifest_sha,
                "expected_rag_context_sha256": retrieval_manifest[
                    "combined_context_sha256"
                ],
                "selected_paths": list(retrieval_manifest.get("selected_paths") or []),
                "non_rag_config": nonrag,
                "rag_config": rag,
            }
        )

    if len(prepared) != 17:
        raise RuntimeError(f"Expected 17 prepared pairs, got {len(prepared)}")

    staging_parent = root / "configs" / "roundtrip_v6"
    staging_parent.mkdir(parents=True, exist_ok=True)
    temp_root = staging_parent / ".formal-preparation-tmp"
    if temp_root.exists():
        raise FileExistsError(f"Temporary preparation path already exists: {temp_root}")

    manifest_targets: list[dict[str, Any]] = []
    generated_files: list[str] = []

    try:
        for row in prepared:
            pair_id = row["pair_id"]
            conditions: dict[str, Any] = {}
            for condition_key, subdir, config_key in (
                ("non_rag", "non-rag", "non_rag_config"),
                ("rag", "rag", "rag_config"),
            ):
                rel = Path("configs/roundtrip_v6/formal") / subdir / f"{pair_id}.json"
                temp_path = temp_root / subdir / f"{pair_id}.json"
                write_json(temp_path, row[config_key])
                config_sha = sha256_file(temp_path)
                generated_files.append(rel.as_posix())
                conditions[condition_key] = {
                    "config_path": rel.as_posix(),
                    "experiment_id": row[config_key]["experiment_id"],
                    "run_id": row[config_key]["run_id"],
                    "config_sha256": config_sha,
                    "contract_mode": row[config_key]["deterministic_contract"]["mode"],
                    "expected_source_contract_sha256": row[config_key][
                        "deterministic_contract"
                    ]["expected_source_contract_sha256"],
                    "expected_dependency_contract_sha256": row[config_key][
                        "deterministic_contract"
                    ]["expected_dependency_contract_sha256"],
                    "expected_combined_contract_sha256": row[config_key][
                        "deterministic_contract"
                    ]["expected_combined_contract_sha256"],
                }

            manifest_targets.append(
                {
                    "pair_id": pair_id,
                    "pair_sequence": row["pair_sequence"],
                    "granularity": row["granularity"],
                    "v5_source_config": row["v5_source_config"],
                    "v5_retrieval_manifest": row["v5_retrieval_manifest"],
                    "v5_retrieval_manifest_sha256": row[
                        "v5_retrieval_manifest_sha256"
                    ],
                    "expected_rag_context_sha256": row[
                        "expected_rag_context_sha256"
                    ],
                    "selected_paths": row["selected_paths"],
                    "conditions": conditions,
                }
            )

        manifest = {
            "schema_version": "6.0",
            "protocol_id": PROTOCOL_ID,
            "result_classification": "formal_paired_v6",
            "expected_pair_count": 17,
            "pair_count": 17,
            "config_count": 34,
            "all_enabled": False,
            "formal_result_eligible": True,
            "design_prompt_profile": PROMPT_PROFILE,
            "common_design_context_sha256": common_hash,
            "budget_rule": BUDGET_RULE,
            "tokenizer": TOKENIZER_NAME,
            "transformers_version": TRANSFORMERS_VERSION,
            "preformal_budget_audit": BUDGET_AUDIT.as_posix(),
            "generated_files": generated_files,
            "targets": manifest_targets,
        }
        write_json(temp_root / "generation_manifest.json", manifest)

        output_root.parent.mkdir(parents=True, exist_ok=True)
        if output_root.exists():
            raise FileExistsError(output_root)
        temp_root.replace(output_root)
    except Exception:
        if temp_root.exists():
            shutil.rmtree(temp_root)
        raise

    print(
        json.dumps(
            {
                "pair_count": 17,
                "config_count": 34,
                "all_enabled": False,
                "manifest": (OUTPUT_ROOT / "generation_manifest.json").as_posix(),
                "common_design_context_sha256": common_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
