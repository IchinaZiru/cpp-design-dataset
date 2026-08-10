"""Build/check the deterministic 17-target design-only A/B freeze candidate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.rag.canonical import canonical_json_bytes, sha256_bytes, sha256_file
from scripts.rag.roundtrip_ab_formal import MANIFEST_SCHEMA, TARGET_SCHEMA


TARGET_IDS = (
    "echo-web-server-block-deque",
    "echo-web-server-buffer",
    "echo-web-server-config",
    "echo-web-server-heap-timer",
    "echo-web-server-http",
    "echo-web-server-io",
    "echo-web-server-ip",
    "echo-web-server-log",
    "echo-web-server-thread-pool",
    "echo-web-server-util",
    "ini-cpp-ini-writer",
    "ini-cpp-inireader",
    "riscv-simulator-instruction",
    "riscv-simulator-memory",
    "riscv-simulator-parser",
    "riscv-simulator-register",
    "riscv-simulator-registerfile",
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return value


def _normalized(raw: bytes) -> str:
    return raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def _raw_span(raw: bytes, normalized_span: str) -> tuple[int, int]:
    candidates = [normalized_span.encode("utf-8"), normalized_span.replace("\n", "\r\n").encode("utf-8")]
    matches: list[tuple[int, int]] = []
    for needle in candidates:
        start = raw.find(needle)
        if start >= 0 and raw.find(needle, start + 1) < 0:
            matches.append((start, start + len(needle)))
    if not matches:
        raise RuntimeError("normalized replacement span does not map uniquely to raw bytes")
    return matches[0]


def _ini_writer_span(text: str) -> tuple[int, int]:
    signature = "inline static void write("
    signature_at = text.index(signature)
    start = text.rfind("    /**", 0, signature_at)
    if start < 0:
        start = text.rfind("\n", 0, signature_at) + 1
    open_brace = text.index("{", signature_at)
    depth = 0
    in_string: str | None = None
    escaped = False
    for index in range(open_brace, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == in_string:
                in_string = None
            continue
        if char in {'"', "'"}:
            in_string = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, index + 1
    raise RuntimeError("INIWriter::write closing brace not found")


def _docker_prefix(image: str, *, project_mount: bool = False) -> list[str]:
    command = [
        "docker", "run", "--rm",
        "--mount", "type=bind,source=<REPOSITORY_ROOT>,target=/source,readonly",
        "--mount", "type=bind,source=<EVALUATION_WORKSPACE>,target=/evaluation",
    ]
    if project_mount:
        command.extend(["--mount", "type=bind,source=<PROJECT_ROOT>,target=/project,readonly"])
    command.extend([image, "bash", "-lc"])
    return command


def _commands(legacy: dict[str, Any], repository_id: str) -> dict[str, Any]:
    evaluation = legacy["evaluation"]
    image = str(evaluation["docker_image"])
    if repository_id == "Echo-Web-Server":
        configure = "cmake -S /source -B /evaluation/build -DCMAKE_BUILD_TYPE=Debug -DECHO_WEB_SERVER_BUILD_TESTS=ON -DCMAKE_PROJECT_INCLUDE=/project/configs/roundtrip/cmake/echo_web_server_gtest.cmake"
        build = "cmake --build /evaluation/build --parallel"
        direct = "exe=$(find /evaluation/build -type f -name test-bundle -perm -111 | head -n 1); test -n \"$exe\"; \"$exe\" --gtest_color=no --gtest_filter=" + repr(evaluation["direct_test_filter"])
        full = "ctest --test-dir /evaluation/build --output-on-failure"
        prefix = _docker_prefix(image, project_mount=True)
    elif repository_id == "ini-cpp":
        configure = "cmake -S /source -B /evaluation/build -DCMAKE_BUILD_TYPE=Debug"
        build = "cmake --build /evaluation/build --parallel"
        fixture = "rm -rf /evaluation/build/test/fixtures && cp -a /source/test/fixtures /evaluation/build/test/fixtures"
        direct = fixture + "; cd /evaluation/build/test && ./all_test --gtest_color=no --gtest_filter=" + repr(evaluation["direct_test_filter"])
        full = fixture + "; cd /evaluation/build/test && ./all_test --gtest_color=no"
        prefix = _docker_prefix(image)
    else:
        configure = "cmake -S /source -B /evaluation/build -DCMAKE_BUILD_TYPE=Debug"
        build = "cmake --build /evaluation/build --parallel"
        direct = "/evaluation/build/RISCV_Simulator_Test --gtest_color=no --gtest_filter=" + repr(evaluation["direct_test_filter"])
        full = "/evaluation/build/RISCV_Simulator_Test --gtest_color=no"
        prefix = _docker_prefix(image)
    return {
        "commands": {
            "configure": prefix + [configure],
            "build": prefix + [build],
            "direct_test": prefix + [direct],
            "full_test": prefix + [full],
        },
        "stage_order": ["configure", "build", "direct_test", "full_test"],
        "stage_timeouts_seconds": {"configure": 300, "build": 600, "direct_test": 300, "full_test": 600},
    }


def _repository_id(legacy: dict[str, Any]) -> str:
    value = str(legacy["repository_id"])
    if value.lower() == "ini-cpp":
        return "ini-cpp"
    return value


def _build_target(root: Path, target_id: str) -> dict[str, Any]:
    evidence_path = root / "configs" / "rag" / "targets" / f"{target_id}.json"
    legacy = _json(evidence_path)
    repository_id = _repository_id(legacy)
    repository_path = str(legacy["repository_path"])
    repository_root = root / repository_path
    metadata_path = root / str(legacy["non_rag_evidence"]["source_metadata_path"])
    metadata = _json(metadata_path)
    granularity = "function" if target_id == "ini-cpp-ini-writer" else str(legacy["granularity"])
    if target_id == "ini-cpp-ini-writer":
        source_files = ["ini/ini.h"]
    else:
        source_files = [str(x) for x in metadata["source_files"]]

    inputs: list[dict[str, Any]] = []
    units: list[dict[str, Any]] = []
    for index, relative in enumerate(source_files, 1):
        raw = (repository_root / relative).read_bytes()
        file_hash = sha256_bytes(raw)
        file_id = f"F{index:02d}"
        unit_id = f"U{index:02d}"
        if granularity in {"module_files", "full_file"}:
            normalized_span = _normalized(raw)
            input_record = {
                "content_sha256": sha256_bytes(normalized_span.encode("utf-8")),
                "file_id": file_id,
                "path": relative,
                "replacement_required": True,
                "role": "complete target-owned implementation/declaration file",
                "scope": "full_file",
                "source_file_sha256": file_hash,
                "unit_id": unit_id,
            }
            unit_record = dict(input_record)
            unit_record.pop("replacement_required")
            unit_record.pop("role")
        else:
            text = _normalized(raw)
            if granularity == "function":
                start_char, end_char = _ini_writer_span(text)
                role = "complete INIWriter::write member function definition including signature and body"
            else:
                locator = metadata["locator"]
                start_char, end_char = int(locator["start_offset"]), int(locator["end_offset"])
                role = f"complete {locator['symbol']} class definition span"
            normalized_span = text[start_char:end_char]
            start_byte, end_byte = _raw_span(raw, normalized_span)
            input_record = {
                "content_sha256": sha256_bytes(normalized_span.encode("utf-8")),
                "end_byte": end_byte,
                "file_id": file_id,
                "path": relative,
                "replacement_required": True,
                "role": role,
                "scope": "byte_span",
                "source_file_sha256": file_hash,
                "start_byte": start_byte,
                "unit_id": unit_id,
            }
            unit_record = {
                "content_sha256": sha256_bytes(raw[start_byte:end_byte]),
                "end_byte": end_byte,
                "file_id": file_id,
                "path": relative,
                "scope": "byte_span",
                "source_file_sha256": file_hash,
                "start_byte": start_byte,
                "unit_id": unit_id,
            }
        inputs.append(input_record)
        units.append(unit_record)

    include_roots = {
        "Echo-Web-Server": ["include", "src"],
        "ini-cpp": [".", "ini"],
        "RISCV-Simulator": ["src", "src/Common"],
    }[repository_id]
    execution = _commands(legacy, repository_id)
    execution.update(
        {
            "enabled": True,
            "expected_direct_tests": legacy["evaluation"].get("expected_direct_tests"),
            "expected_full_tests": legacy["evaluation"].get("expected_full_tests"),
            "output_root": f"experiments/rag/roundtrip-ab-v1/formal/{target_id}",
            "plan_root": f"reports/rag/roundtrip-ab-v1/formal/{target_id}/plan",
        }
    )
    return {
        "artifact_schema_version": TARGET_SCHEMA,
        "execution": execution,
        "formal_execution_authorized": False,
        "formal_target_member": True,
        "freeze_evidence": {
            "legacy_formal_config_path": evidence_path.relative_to(root).as_posix(),
            "legacy_formal_config_sha256": sha256_file(evidence_path),
            "source_metadata_path": metadata_path.relative_to(root).as_posix(),
            "source_metadata_sha256": sha256_file(metadata_path),
        },
        "granularity": granularity,
        "one_shot": {
            "automatic_repair": False,
            "code_generation_count": 1,
            "design_generation_count": 1,
            "manual_patch": False,
            "overwrite": False,
            "retry": False,
        },
        "replacement_units": units,
        "repository": {
            "commit": legacy["repository_commit"],
            "external": False,
            "id": repository_id,
            "path": repository_path,
        },
        "retrieval": {
            "dependency_header_mode": "direct-project-local-quoted-include-whole-file-one-hop-v1",
            "dependency_header_normalization": "utf8-bom-aware-newlines-to-lf-v1",
            "expected_evidence": [],
            "include_roots": include_roots,
            "maximum_dependency_headers": 64,
            "source_feature_selection": False,
            "target_specific_manual_query": False,
            "target_specific_override": False,
        },
        "stage": "formal_freeze_candidate_disabled",
        "target_id": target_id,
        "target_owned_inputs": inputs,
    }


def build(root: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    outputs: dict[str, bytes] = {}
    entries: list[dict[str, Any]] = []
    for target_id in TARGET_IDS:
        config = _build_target(root, target_id)
        relative = f"configs/rag/roundtrip_ab_v1/formal/targets/{target_id}.json"
        data = canonical_json_bytes(config)
        outputs[relative] = data
        source_records = [
            {"path": item["path"], "sha256": item["source_file_sha256"]}
            for item in config["target_owned_inputs"]
        ]
        entries.append(
            {
                "build_test_conditions": {
                    "expected_direct_tests": config["execution"]["expected_direct_tests"],
                    "expected_full_tests": config["execution"]["expected_full_tests"],
                    "stage_order": config["execution"]["stage_order"],
                },
                "repository_commit": config["repository"]["commit"],
                "replacement_granularity": config["granularity"],
                "replacement_units": config["replacement_units"],
                "source_files": source_records,
                "target_config_path": relative,
                "target_config_sha256": sha256_bytes(data),
                "target_id": target_id,
            }
        )
    common_path = root / "configs/rag/roundtrip_ab_v1/common.json"
    manifest = {
        "artifact_schema_version": MANIFEST_SCHEMA,
        "common_config_path": "configs/rag/roundtrip_ab_v1/common.json",
        "common_config_sha256": sha256_file(common_path),
        "development_history_is_formal_result": False,
        "formal_completed_target_count": 0,
        "formal_execution_started": False,
        "formal_target_count": 17,
        "instruction_development_results_reused": False,
        "targets": entries,
    }
    manifest_relative = "configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json"
    manifest_bytes = canonical_json_bytes(manifest)
    outputs[manifest_relative] = manifest_bytes
    outputs["configs/rag/roundtrip_ab_v1/formal/execution_authorization.json"] = canonical_json_bytes(
        {
            "artifact_schema_version": "roundtrip-ab-formal-execution-authorization-v1",
            "authorized": False,
            "common_config_sha256": sha256_file(common_path),
            "formal_generation_started": False,
            "manifest_sha256": sha256_bytes(manifest_bytes),
            "note": "Change only authorized/formal_generation_started in a dedicated reviewed commit after GO.",
        }
    )

    instruction = _build_target(root, "riscv-simulator-instruction")
    instruction["formal_target_member"] = False
    instruction["stage"] = "formal_excluded_context-capacity-development"
    instruction["target_id"] = "riscv-simulator-instruction-ab-v1-dev05"
    instruction["execution"]["output_root"] = "experiments/rag/roundtrip-ab-v1/development/riscv-simulator-instruction-dev05"
    instruction["execution"]["plan_root"] = "reports/rag/roundtrip-ab-v1/development/riscv-simulator-instruction-dev05/plan"
    outputs["configs/rag/roundtrip_ab_v1/development/riscv-simulator-instruction-dev05.json"] = canonical_json_bytes(instruction)
    return outputs, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--refresh", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    outputs, manifest = build(root)
    mismatches: list[str] = []
    for relative, expected in outputs.items():
        path = root / relative
        if args.write or args.refresh:
            if path.exists():
                if path.read_bytes() != expected:
                    if args.refresh:
                        path.write_bytes(expected)
                    else:
                        raise RuntimeError(f"refusing to overwrite differing artifact: {relative}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(expected)
        elif not path.is_file() or path.read_bytes() != expected:
            mismatches.append(relative)
    if mismatches:
        raise RuntimeError("freeze candidate differs: " + ", ".join(mismatches))
    status = "refreshed" if args.refresh else ("written" if args.write else "match")
    print(json.dumps({"formal_target_count": len(manifest["targets"]), "status": status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
