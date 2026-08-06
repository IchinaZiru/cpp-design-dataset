from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_TARGET_IDS = (
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
    "ini-cpp-inireader",
    "ini-cpp-iniwriter",
    "riscv-simulator-instruction",
    "riscv-simulator-memory",
    "riscv-simulator-parser",
    "riscv-simulator-register",
    "riscv-simulator-registerfile",
)

PAIR_DIFFERENCE_FIELDS = {
    "condition",
    "experiment_id",
    "run_id",
    "design_knowledge",
}


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


def git_output(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def normalized_pair(config: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(config)
    for key in PAIR_DIFFERENCE_FIELDS:
        value.pop(key, None)
    provenance = value.get("provenance")
    if isinstance(provenance, dict):
        # Provenance is shared in current configs. This removal makes the
        # validator tolerant of condition-specific audit notes only.
        provenance.pop("condition_note", None)
    return value


def validate_knowledge(non_rag: dict[str, Any], rag: dict[str, Any]) -> None:
    non_knowledge = non_rag.get("design_knowledge")
    if non_knowledge != {"enabled": False}:
        raise ValueError(
            f"{non_rag['pair_id']}: non-RAG design_knowledge must be disabled"
        )

    rag_knowledge = rag.get("design_knowledge")
    if not isinstance(rag_knowledge, dict) or rag_knowledge.get("enabled") is not True:
        raise ValueError(f"{rag['pair_id']}: RAG design_knowledge must be enabled")
    if rag_knowledge.get("context_file") != "knowledge/detailed-design/general-v2.md":
        raise ValueError(f"{rag['pair_id']}: unexpected RAG context file")
    if rag_knowledge.get("instruction_mode") != "required_additional_artifacts":
        raise ValueError(f"{rag['pair_id']}: RAG instruction mode is not required")


def validate_model(config: dict[str, Any]) -> None:
    model = config.get("model")
    if not isinstance(model, dict):
        raise ValueError(f"{config['pair_id']}: model must be an object")
    required = {
        "name": "qwen2.5-coder:32b",
        "num_ctx": 16384,
        "num_predict": 8192,
        "generations": 1,
        "retry": False,
        "automatic_repair": False,
    }
    for key, expected in required.items():
        if model.get(key) != expected:
            raise ValueError(
                f"{config['pair_id']}: model.{key}={model.get(key)!r}, "
                f"expected {expected!r}"
            )


def validate_runtime_repository(project_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    repository = project_root / str(config["repository_path"])
    if not repository.is_dir():
        raise FileNotFoundError(repository)
    head = git_output(repository, "rev-parse", "HEAD")
    if head != config["repository_commit"]:
        raise ValueError(
            f"{config['pair_id']}: repository commit mismatch: {head} != "
            f"{config['repository_commit']}"
        )
    tracked_status = git_output(
        repository, "status", "--short", "--untracked-files=no"
    )
    if tracked_status:
        raise ValueError(
            f"{config['pair_id']}: repository has tracked changes:\n{tracked_status}"
        )
    observation_chars = 0
    for relative in config["observation_files"]:
        path = repository / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        observation_chars += len(path.read_text(encoding="utf-8", errors="replace"))
    return {
        "repository_path": config["repository_path"],
        "repository_commit": head,
        "observation_character_count": observation_chars,
    }


def run_runner_validation(
    project_root: Path,
    runner: Path,
    config_path: Path,
) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--config",
            str(config_path),
            "--project-root",
            str(project_root),
            "--validate-config-only",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Runner config validation failed for {config_path}:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    value = json.loads(result.stdout)
    if value.get("valid") is not True:
        raise RuntimeError(f"Runner did not report valid=true for {config_path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the 17 paired disabled formal configs, source files, "
            "repository commits, and pairwise fairness."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/roundtrip_v2/formal/generation_manifest.json"),
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = project_root / manifest_path
    manifest = read_json(manifest_path)

    if tuple(manifest.get("formal_target_ids", [])) != EXPECTED_TARGET_IDS:
        raise ValueError("Formal target inventory does not match the frozen 17 targets")
    if manifest.get("pair_count") != 17 or manifest.get("config_count") != 34:
        raise ValueError("Formal manifest must contain 17 pairs and 34 configs")
    if manifest.get("all_enabled") is not False:
        raise ValueError("Generated formal configs must remain disabled")

    runner = project_root / "scripts" / "roundtrip_v2" / "run_target_v2.py"
    if not runner.is_file():
        raise FileNotFoundError(runner)

    rag_context = project_root / "knowledge" / "detailed-design" / "general-v2.md"
    if not rag_context.is_file():
        raise FileNotFoundError(rag_context)
    rag_context_chars = len(rag_context.read_text(encoding="utf-8"))

    records: list[dict[str, Any]] = []
    for expected_sequence, target in enumerate(manifest["targets"], start=1):
        pair_id = target["pair_id"]
        if pair_id != EXPECTED_TARGET_IDS[expected_sequence - 1]:
            raise ValueError(f"Unexpected pair order at {expected_sequence}: {pair_id}")
        if target.get("pair_sequence") != expected_sequence:
            raise ValueError(f"{pair_id}: pair_sequence mismatch")

        non_path = project_root / target["conditions"]["non_rag"]["config_path"]
        rag_path = project_root / target["conditions"]["rag"]["config_path"]
        non_rag = read_json(non_path)
        rag = read_json(rag_path)

        for config, path in ((non_rag, non_path), (rag, rag_path)):
            if config.get("enabled") is not False:
                raise ValueError(f"Formal config must be disabled: {path}")
            if config.get("pilot_only") is not False:
                raise ValueError(f"Formal config marked as pilot: {path}")
            if config.get("formal_result_eligible") is not True:
                raise ValueError(f"Formal config not eligible: {path}")
            if config.get("pair_id") != pair_id:
                raise ValueError(f"Pair ID mismatch: {path}")
            validate_model(config)

            experiment_root = project_root / "experiments" / config["experiment_id"]
            if experiment_root.exists():
                raise FileExistsError(
                    f"Formal experiment directory already exists before execution: "
                    f"{experiment_root}"
                )

        if normalized_pair(non_rag) != normalized_pair(rag):
            raise ValueError(
                f"{pair_id}: pair differs outside condition IDs and design_knowledge"
            )
        validate_knowledge(non_rag, rag)

        non_summary = run_runner_validation(project_root, runner, non_path)
        rag_summary = run_runner_validation(project_root, runner, rag_path)
        if non_summary["source_files"] != rag_summary["source_files"]:
            raise ValueError(f"{pair_id}: source-file mismatch between conditions")

        runtime = validate_runtime_repository(project_root, non_rag)
        records.append(
            {
                "pair_id": pair_id,
                "pair_sequence": expected_sequence,
                "granularity": non_summary["granularity"],
                "non_rag_config": non_path.relative_to(project_root).as_posix(),
                "rag_config": rag_path.relative_to(project_root).as_posix(),
                "non_rag_sha256": sha256_file(non_path),
                "rag_sha256": sha256_file(rag_path),
                "source_files": non_summary["source_files"],
                "observation_files": non_summary["observation_files"],
                **runtime,
            }
        )

    result = {
        "schema_version": "2.0",
        "protocol_id": manifest["protocol_id"],
        "valid": True,
        "pair_count": len(records),
        "config_count": len(records) * 2,
        "rag_context_file": rag_context.relative_to(project_root).as_posix(),
        "rag_context_sha256": sha256_file(rag_context),
        "rag_context_character_count": rag_context_chars,
        "records": records,
        "formal_experiments_executed": False,
    }
    output_path = manifest_path.parent / "validation_manifest.json"
    write_json(output_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
