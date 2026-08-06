from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FORMAL_TARGETS: tuple[tuple[str, str], ...] = (
    ("echo-web-server-block-deque", "module_files"),
    ("echo-web-server-buffer", "module_files"),
    ("echo-web-server-config", "module_files"),
    ("echo-web-server-heap-timer", "module_files"),
    ("echo-web-server-http", "module_files"),
    ("echo-web-server-io", "module_files"),
    ("echo-web-server-ip", "module_files"),
    ("echo-web-server-log", "module_files"),
    ("echo-web-server-thread-pool", "module_files"),
    ("echo-web-server-util", "module_files"),
    ("ini-cpp-inireader", "class_span"),
    ("ini-cpp-iniwriter", "function"),
    ("riscv-simulator-instruction", "module_files"),
    ("riscv-simulator-memory", "class_span"),
    ("riscv-simulator-parser", "class_span"),
    ("riscv-simulator-register", "class_span"),
    ("riscv-simulator-registerfile", "class_span"),
)

FORMAL_TARGET_IDS = tuple(item[0] for item in FORMAL_TARGETS)
CONDITION_DIRECTORY = {"non_rag": "non-rag", "rag": "rag"}
CONDITION_VALUE = {
    "non_rag": "full_source_non_rag",
    "rag": "full_source_design_knowledge_rag_required_artifacts",
}

# Keep the v2 formal comparison on the same inference settings used by the
# successful v2 mechanics pilots. Both conditions receive exactly these values.
V2_MODEL_OVERRIDES = {
    "num_ctx": 16384,
    "num_predict": 8192,
}

INIWRITER_SIGNATURE_REGEX = (
    r"inline\s+static\s+void\s+write\s*\(\s*"
    r"const\s+std::string\s*&\s*filepath\s*,\s*"
    r"const\s+INIReader\s*&\s*reader\s*,\s*"
    r"const\s+bool\s+overwrite\s*=\s*false\s*\)"
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
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


def canonical_config_path(project_root: Path, target_id: str) -> Path:
    return project_root / "configs" / "roundtrip" / "targets" / f"{target_id}.json"


def require_legacy_fields(config: dict[str, Any], *, target_id: str) -> None:
    required = {
        "target_id",
        "repository_id",
        "repository_path",
        "repository_commit",
        "target_name",
        "source_files",
        "model",
        "evaluation",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"{target_id}: canonical config is missing fields: {missing}")
    if config["target_id"] != target_id:
        raise ValueError(
            f"{target_id}: canonical target_id mismatch: {config['target_id']!r}"
        )


def make_iniwriter_legacy(project_root: Path) -> dict[str, Any]:
    """Construct the formal function target from the verified ini-cpp setup.

    The old INIWriter experiment predates the canonical target-config schema.
    The repository/model/build/full-test values are inherited from the
    canonical INIReader config for the same repository and commit. Only the
    target locator and direct-test filter are changed.
    """
    base_path = canonical_config_path(project_root, "ini-cpp-inireader")
    base = read_json(base_path)
    require_legacy_fields(base, target_id="ini-cpp-inireader")

    config = copy.deepcopy(base)
    config.update(
        {
            "target_id": "ini-cpp-iniwriter",
            "target_name": "INIWriter::write",
            "adoption_status": "採用",
            "granularity": "function",
            "source_files": ["ini/ini.h"],
            "locator": {
                "kind": "function",
                "symbol": "INIWriter::write",
                "signature_regex": INIWRITER_SIGNATURE_REGEX,
            },
        }
    )
    evaluation = copy.deepcopy(config["evaluation"])
    evaluation.update(
        {
            "direct_test_command": (
                "rm -rf build/test/fixtures && cp -a test/fixtures "
                "build/test/fixtures && cd build/test && ./all_test "
                "--gtest_color=no --gtest_filter='INIWriter.*'"
            ),
            "direct_test_filter": "INIWriter.*",
            "direct_test_names": [],
            "expected_direct_tests": 3,
        }
    )
    config["evaluation"] = evaluation
    config["_formal_source_config"] = base_path.relative_to(project_root).as_posix()
    config["_formal_source_note"] = (
        "INIWriter::write uses the verified ini-cpp repository, model, Docker, "
        "build and full-test setup from ini-cpp-inireader; the function locator "
        "and INIWriter.* direct-test filter are formal-v2 additions."
    )
    return config


def load_legacy(project_root: Path, target_id: str) -> dict[str, Any]:
    if target_id == "ini-cpp-iniwriter":
        return make_iniwriter_legacy(project_root)

    path = canonical_config_path(project_root, target_id)
    if not path.is_file():
        raise FileNotFoundError(path)
    config = read_json(path)
    require_legacy_fields(config, target_id=target_id)
    config["_formal_source_config"] = path.relative_to(project_root).as_posix()
    return config


def normalize_model(model: Any, *, target_id: str) -> dict[str, Any]:
    if not isinstance(model, dict):
        raise ValueError(f"{target_id}: model must be an object")
    result = copy.deepcopy(model)
    result.update(V2_MODEL_OVERRIDES)
    result["generations"] = 1
    result["retry"] = False
    result["automatic_repair"] = False
    result["stream"] = False
    return result


def normalize_evaluation(evaluation: Any, *, target_id: str) -> dict[str, Any]:
    if not isinstance(evaluation, dict):
        raise ValueError(f"{target_id}: evaluation must be an object")
    result = copy.deepcopy(evaluation)
    required = {
        "docker_image",
        "docker_image_id",
        "configure_command",
        "build_command",
        "direct_test_command",
        "full_test_command",
        "full_test_kind",
        "expected_direct_tests",
        "expected_full_tests",
    }
    missing = sorted(required - set(result))
    if missing:
        raise ValueError(f"{target_id}: evaluation is missing fields: {missing}")
    result.setdefault(
        "stage_timeouts_seconds",
        {
            "configure": 300,
            "build": 600,
            "direct_test": 300,
            "full_test": 600,
        },
    )
    return result


def target_locator(
    legacy: dict[str, Any],
    *,
    target_id: str,
    granularity: str,
) -> dict[str, Any]:
    if granularity == "module_files":
        return {}

    locator = legacy.get("locator")
    if not isinstance(locator, dict):
        raise ValueError(f"{target_id}: target-span target requires locator")
    expected_kind = "function" if granularity == "function" else "class"
    if locator.get("kind") != expected_kind:
        raise ValueError(
            f"{target_id}: expected locator.kind={expected_kind!r}, "
            f"found {locator.get('kind')!r}"
        )
    if not isinstance(locator.get("symbol"), str) or not locator["symbol"]:
        raise ValueError(f"{target_id}: locator.symbol is required")
    if expected_kind == "function":
        regex = locator.get("signature_regex")
        if not isinstance(regex, str) or not regex:
            raise ValueError(f"{target_id}: function locator requires signature_regex")
        re.compile(regex, re.MULTILINE)
    return copy.deepcopy(locator)


def make_condition_config(
    legacy: dict[str, Any],
    *,
    target_id: str,
    granularity: str,
    condition_key: str,
    sequence: int,
) -> dict[str, Any]:
    rag = condition_key == "rag"
    condition_dir = CONDITION_DIRECTORY[condition_key]
    source_files = [str(value) for value in legacy["source_files"]]
    if not source_files:
        raise ValueError(f"{target_id}: source_files must not be empty")

    locator = target_locator(
        legacy,
        target_id=target_id,
        granularity=granularity,
    )

    config: dict[str, Any] = {
        "schema_version": "4.4-formal",
        "enabled": False,
        "pilot_only": False,
        "formal_result_eligible": True,
        "condition": CONDITION_VALUE[condition_key],
        "target_id": f"{target_id}-v2-formal",
        "pair_id": target_id,
        "pair_sequence": sequence,
        "experiment_id": f"v2/formal/{condition_dir}/{target_id}-001",
        "run_id": f"{target_id}-full-source-{condition_dir}-formal-001",
        "repository_id": legacy["repository_id"],
        "repository_path": legacy["repository_path"],
        "repository_commit": legacy["repository_commit"],
        "target_name": legacy["target_name"],
        "adoption_status": legacy.get("adoption_status", "採用"),
        "granularity": granularity,
        "observation_files": source_files,
        "source_files": source_files,
        "locator": locator,
        "design_knowledge": (
            {
                "enabled": True,
                "context_file": "knowledge/detailed-design/general-v2.md",
                "instruction_mode": "required_additional_artifacts",
                "query": (
                    "対象コードを再実装可能な詳細設計文書に必要な必須成果物、"
                    "完全な関数名とシグネチャ、構造図、処理フロー図、"
                    "仕様項目、状態遷移、記述規則を取得する"
                ),
            }
            if rag
            else {"enabled": False}
        ),
        "model": normalize_model(legacy["model"], target_id=target_id),
        "evaluation": normalize_evaluation(
            legacy["evaluation"], target_id=target_id
        ),
        "protocol": {
            "protocol_id": "full-source-design-knowledge-rag-v2-formal-001",
            "formal_target_set_member": True,
            "formal_pair_id": target_id,
            "observation_scope": "full_source_files",
            "replacement_scope": (
                "module_files" if granularity == "module_files" else "target_span"
            ),
            "code_regeneration_inputs": [
                "generated_design_document",
                "fixed_interface_scaffold",
                "dependency_include_context",
            ],
            "original_source_in_code_regeneration": False,
            "retrieved_context_in_code_regeneration": False,
            "module_output_format": (
                "ollama_json_schema" if granularity == "module_files" else None
            ),
            "retry": False,
            "automatic_repair": False,
            "generated_code_manual_edit": False,
            "generations_per_stage": 1,
        },
        "provenance": {
            "legacy_target_id": target_id,
            "legacy_run_id": legacy.get("run_id"),
            "legacy_experiment_id": legacy.get("experiment_id"),
            "source_config": legacy.get("_formal_source_config"),
            "source_note": legacy.get("_formal_source_note"),
            "legacy_results_are_not_direct_comparator": True,
            "model_setting_policy": (
                "Use v2 mechanics-pilot num_ctx=16384 and num_predict=8192 "
                "for both formal conditions; retain the canonical target's "
                "remaining model options."
            ),
        },
    }

    if granularity != "module_files":
        if len(source_files) != 1:
            raise ValueError(
                f"{target_id}: target-span formal target requires one source file"
            )
        config["target_source_file"] = source_files[0]

    return config


def ensure_output_root(output_root: Path, overwrite: bool) -> None:
    if not output_root.exists():
        return
    existing = [path for path in output_root.rglob("*") if path.is_file()]
    if existing and not overwrite:
        shown = ", ".join(str(path) for path in existing[:5])
        raise FileExistsError(
            f"Formal config output already contains files: {shown}. "
            "Refuse to overwrite without --overwrite-configs."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the 17 paired disabled full-source v2 formal configs. "
            "This command does not call an LLM, Docker, build, or tests."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("configs/roundtrip_v2/formal"),
    )
    parser.add_argument("--overwrite-configs", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = project_root / output_root
    ensure_output_root(output_root, args.overwrite_configs)

    generated_files: list[str] = []
    target_records: list[dict[str, Any]] = []

    for sequence, (target_id, granularity) in enumerate(FORMAL_TARGETS, start=1):
        legacy = load_legacy(project_root, target_id)
        record: dict[str, Any] = {
            "pair_id": target_id,
            "pair_sequence": sequence,
            "granularity": granularity,
            "conditions": {},
        }
        for condition_key in ("non_rag", "rag"):
            config = make_condition_config(
                legacy,
                target_id=target_id,
                granularity=granularity,
                condition_key=condition_key,
                sequence=sequence,
            )
            condition_dir = CONDITION_DIRECTORY[condition_key]
            relative_path = (
                Path("configs")
                / "roundtrip_v2"
                / "formal"
                / condition_dir
                / f"{target_id}.json"
            )
            path = project_root / relative_path
            write_json(path, config)
            generated_files.append(relative_path.as_posix())
            record["conditions"][condition_key] = {
                "config_path": relative_path.as_posix(),
                "experiment_id": config["experiment_id"],
                "run_id": config["run_id"],
                "config_sha256": sha256_file(path),
            }
        target_records.append(record)

    manifest = {
        "schema_version": "2.0",
        "protocol_id": "full-source-design-knowledge-rag-v2-formal-001",
        "expected_pair_count": 17,
        "expected_config_count": 34,
        "pair_count": len(target_records),
        "config_count": len(generated_files),
        "all_enabled": False,
        "formal_target_ids": list(FORMAL_TARGET_IDS),
        "condition_order": ["non_rag", "rag"],
        "generated_files": generated_files,
        "targets": target_records,
        "model_overrides": V2_MODEL_OVERRIDES,
        "legacy_frozen_results_modified": False,
        "formal_experiments_executed": False,
    }
    manifest_path = output_root / "generation_manifest.json"
    write_json(manifest_path, manifest)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest["pair_count"] != 17 or manifest["config_count"] != 34:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
