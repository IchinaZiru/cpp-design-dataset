from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROUNDTRIP_DIR = Path(__file__).resolve().parents[1] / "roundtrip"
if str(ROUNDTRIP_DIR) not in sys.path:
    sys.path.insert(0, str(ROUNDTRIP_DIR))

from roundtrip_common import (  # noqa: E402
    call_ollama,
    docker_image_id,
    docker_run,
    extract_includes,
    find_matching_brace,
    git_output,
    load_json,
    locate_class_span,
    parse_ctest_counts,
    parse_gtest_counts,
    read_text,
    sha256_bytes,
    sha256_file,
    strip_inline_callable_bodies,
    utc_now,
    write_json,
    write_text,
)
from run_target import normalize_outer_markdown_fence, ollama_options  # noqa: E402


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"stdout", "stderr"}}


def ensure_clean(repository: Path) -> None:
    status = git_output(repository, "status", "--short", "--untracked-files=no")
    if status:
        raise RuntimeError(f"Repository has tracked changes before run:\n{status}")


def locate_function_span(text: str, locator: dict[str, Any]) -> tuple[int, int]:
    signature_regex = locator.get("signature_regex")
    if not isinstance(signature_regex, str) or not signature_regex.strip():
        raise ValueError("Function locator requires a non-empty signature_regex")

    pattern = re.compile(signature_regex, re.MULTILINE)
    matches: list[tuple[re.Match[str], int, int]] = []

    for match in pattern.finditer(text):
        open_brace = text.find("{", match.end())
        if open_brace < 0:
            continue
        semicolon = text.find(";", match.end(), open_brace)
        if semicolon >= 0:
            continue
        try:
            close_brace = find_matching_brace(text, open_brace)
        except ValueError:
            continue
        matches.append((match, open_brace, close_brace))

    if len(matches) != 1:
        symbol = locator.get("symbol", "<unknown>")
        raise ValueError(
            f"Expected one function definition for {symbol}, found {len(matches)}"
        )

    match, _open_brace, close_brace = matches[0]
    return match.start(), close_brace + 1


def locate_target_span(text: str, locator: dict[str, Any]) -> tuple[int, int]:
    kind = locator.get("kind")
    symbol = locator.get("symbol")
    if kind == "class":
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("Class locator requires symbol")
        return locate_class_span(text, symbol)
    if kind == "function":
        return locate_function_span(text, locator)
    raise ValueError(f"Unsupported locator kind: {kind!r}")


def make_target_scaffold(target_text: str, locator: dict[str, Any]) -> str:
    kind = locator.get("kind")
    if kind == "class":
        return strip_inline_callable_bodies(target_text).rstrip() + "\n"
    if kind == "function":
        open_brace = target_text.find("{")
        if open_brace < 0:
            raise ValueError("Opening brace not found in target function")
        return target_text[:open_brace].rstrip() + ";\n"
    raise ValueError(f"Unsupported locator kind: {kind!r}")


def build_observation_bundle(repository: Path, observation_files: list[str]) -> str:
    parts: list[str] = []
    for relative in observation_files:
        path = repository / relative
        if not path.exists():
            raise FileNotFoundError(path)
        text = read_text(path)
        parts.append(f"===== FILE: {relative} =====\n{text.rstrip()}\n")
    return "\n".join(parts)


def build_dependency_context(repository: Path, observation_files: list[str]) -> str:
    includes: list[str] = []
    for relative in observation_files:
        includes.extend(extract_includes(read_text(repository / relative)))
    return "\n".join(dict.fromkeys(includes)) + "\n"


def resolve_experiment_root(config: dict[str, Any], project_root: Path) -> Path:
    return project_root / "experiments" / str(config["experiment_id"])


def resolve_design_knowledge(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> str:
    knowledge = config.get("design_knowledge") or {}
    if not knowledge.get("enabled", False):
        return ""

    context_file = knowledge.get("context_file")
    if not isinstance(context_file, str) or not context_file:
        raise ValueError("Enabled design_knowledge requires context_file")

    source_path = project_root / context_file
    text = read_text(source_path).strip()
    if not text:
        raise ValueError("Design knowledge context is empty")

    retrieval_dir = experiment_root / "retrieval"
    write_text(retrieval_dir / "context.txt", text + "\n")
    write_json(
        retrieval_dir / "retrieval_manifest.json",
        {
            "schema_version": "1.0",
            "condition": config.get("condition"),
            "knowledge_type": "general_detailed_design",
            "retrieval_mode": "fixed_query_fixed_knowledge",
            "query": knowledge.get("query"),
            "context_file": context_file,
            "context_sha256": sha256_bytes((text + "\n").encode("utf-8")),
            "retrieved_at_utc": utc_now(),
            "target_specific_tuning": False,
        },
    )
    return text


def prepare(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> dict[str, Any]:
    repository = project_root / str(config["repository_path"])
    ensure_clean(repository)

    head = git_output(repository, "rev-parse", "HEAD")
    if head != config["repository_commit"]:
        raise RuntimeError(f"Repository commit mismatch: {head}")

    observation_files = [str(item) for item in config["observation_files"]]
    target_source_file = str(config["target_source_file"])
    locator = dict(config["locator"])

    if target_source_file not in observation_files:
        raise ValueError("target_source_file must be included in observation_files")

    input_dir = experiment_root / "input"
    backup_dir = experiment_root / "backup"

    for relative in observation_files:
        source = repository / relative
        backup = backup_dir / "files" / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)

    target_path = repository / target_source_file
    target_source_text = read_text(target_path)
    start, end = locate_target_span(target_source_text, locator)
    original_target = target_source_text[start:end]

    design_input = build_observation_bundle(repository, observation_files)
    scaffold = make_target_scaffold(original_target, locator)
    dependency_context = build_dependency_context(repository, observation_files)

    write_text(input_dir / "design_input.txt", design_input)
    write_text(input_dir / "fixed_scaffold.txt", scaffold)
    write_text(input_dir / "dependency_context.txt", dependency_context)
    write_text(backup_dir / "original_target.cpp", original_target + "\n")

    metadata = {
        "schema_version": "2.0",
        "target_id": config["target_id"],
        "target_name": config["target_name"],
        "condition": config.get("condition"),
        "repository_id": config["repository_id"],
        "repository_commit": head,
        "observation_scope": "full_files",
        "observation_files": observation_files,
        "target_source_file": target_source_file,
        "replacement_scope": "target_span",
        "locator": locator,
        "target_start_offset": start,
        "target_end_offset": end,
        "target_sha256": sha256_bytes(original_target.encode("utf-8")),
        "observation_file_hashes": {
            relative: sha256_file(repository / relative)
            for relative in observation_files
        },
        "prepared_at_utc": utc_now(),
    }
    write_json(input_dir / "source_metadata.json", metadata)
    write_json(experiment_root / "configs" / "target_config.json", config)
    return metadata


def generate_design(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> dict[str, Any]:
    design_input = read_text(experiment_root / "input" / "design_input.txt")
    knowledge_text = resolve_design_knowledge(config, project_root, experiment_root)

    system = (
        "あなたはC++ソフトウェアのリバースエンジニアリング担当者です。"
        "与えられたコードだけを根拠として、再実装に必要な設計文書を日本語で作成してください。"
        "推測で存在しない機能を追加しないでください。"
    )

    knowledge_section = ""
    if knowledge_text:
        knowledge_section = f"""
# 検索コンテキスト
以下は、対象コードに依存しない汎用的な詳細設計知識です。
元コードに存在する事実を優先し、該当しない項目を推測で補完しないでください。

----- BEGIN RETRIEVED CONTEXT -----
{knowledge_text}
----- END RETRIEVED CONTEXT -----
"""

    prompt = f"""# 対象
- target: {config['target_name']}
- granularity: target_span
- target_kind: {config['locator']['kind']}
- target_symbol: {config['locator']['symbol']}

# 対象範囲
元コード全体は対象部分を理解するための文脈として参照してください。
設計文書は target_symbol で指定した対象部分だけについて作成してください。
対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。

# 記載項目
責務、公開インターフェース、入力、出力、状態、処理手順、例外・失敗条件、依存関係、重要な不変条件を記載してください。
{knowledge_section}
# 元コード
{design_input}
"""

    payload = {
        "model": config["model"]["name"],
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": ollama_options(config),
    }

    response, elapsed = call_ollama(payload)
    raw_dir = experiment_root / "raw_output"
    write_json(raw_dir / "design_generation_request.json", payload)
    write_json(raw_dir / "design_generation_response.json", response)

    metadata = {
        "started_at_utc": utc_now(),
        "elapsed_seconds": elapsed,
        "done": response.get("done"),
        "done_reason": response.get("done_reason"),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "eval_count": response.get("eval_count"),
        "retry": False,
        "automatic_repair": False,
    }
    write_json(raw_dir / "design_generation_metadata.json", metadata)

    text = response.get("response")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Design generation returned an empty response")
    write_text(experiment_root / "generated" / "design_document.md", text)
    return metadata


def regenerate(config: dict[str, Any], experiment_root: Path) -> dict[str, Any]:
    design = read_text(experiment_root / "generated" / "design_document.md")
    scaffold = read_text(experiment_root / "input" / "fixed_scaffold.txt")
    dependency = read_text(experiment_root / "input" / "dependency_context.txt")

    kind = config["locator"]["kind"]
    if kind == "class":
        output_instruction = (
            "対象クラスまたは構造体の定義全体だけをC++コードとして返してください。"
            "Markdownコードフェンス、説明文、JSONは出力しないでください。"
        )
    elif kind == "function":
        output_instruction = (
            "対象関数の定義全体だけをC++コードとして返してください。"
            "関数シグネチャを変更しないでください。"
            "Markdownコードフェンス、説明文、JSONは出力しないでください。"
        )
    else:
        raise ValueError(f"Unsupported locator kind: {kind!r}")

    system = (
        "あなたはC++実装担当者です。設計文書と固定インターフェースだけを根拠に実装してください。"
        "元実装は与えられていません。公開インターフェースとファイル構成を変更しないでください。"
    )
    prompt = f"""# 対象
- target: {config['target_name']}
- granularity: target_span
- target_kind: {kind}
- target_symbol: {config['locator']['symbol']}
- source_file: {config['target_source_file']}

# 出力規則
{output_instruction}

# 設計文書
{design}

# 固定インターフェース・スキャフォールド
{scaffold}

# 依存情報
{dependency}
"""

    payload = {
        "model": config["model"]["name"],
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": ollama_options(config),
    }

    response, elapsed = call_ollama(payload)
    raw_dir = experiment_root / "raw_output"
    write_json(raw_dir / "code_regeneration_request.json", payload)
    write_json(raw_dir / "code_regeneration_response.json", response)

    metadata = {
        "started_at_utc": utc_now(),
        "elapsed_seconds": elapsed,
        "done": response.get("done"),
        "done_reason": response.get("done_reason"),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "eval_count": response.get("eval_count"),
        "retry": False,
        "automatic_repair": False,
    }
    write_json(raw_dir / "code_regeneration_metadata.json", metadata)

    text = response.get("response")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Code regeneration returned an empty response")

    normalized, normalization = normalize_outer_markdown_fence(
        text,
        {"", "cpp", "c++", "cc", "cxx"},
    )
    write_json(raw_dir / "code_regeneration_normalization.json", normalization)
    write_text(experiment_root / "generated" / "regenerated_target.cpp", normalized)
    return metadata


def evaluate(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> dict[str, Any]:
    repository = project_root / str(config["repository_path"])
    target_source_file = str(config["target_source_file"])
    source_path = repository / target_source_file
    original_bytes = source_path.read_bytes()
    original_hash = sha256_bytes(original_bytes)

    records: dict[str, Any] = {}
    error: str | None = None
    evaluation_dir = experiment_root / "evaluation"
    log_root = project_root / "logs" / "roundtrip_v2" / str(config["run_id"])

    try:
        source_text = read_text(source_path)
        start, end = locate_target_span(source_text, dict(config["locator"]))
        generated = read_text(
            experiment_root / "generated" / "regenerated_target.cpp"
        ).strip()

        newline = "\r\n" if "\r\n" in source_text else "\n"
        generated = (
            generated.replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\n", newline)
        )
        modified = source_text[:start] + generated + source_text[end:]
        source_path.write_text(modified, encoding="utf-8", newline="")

        evaluation = config["evaluation"]
        stage_timeouts = {
            "configure": 300,
            "build": 600,
            "direct_test": 300,
            "full_test": 600,
        }
        stage_timeouts.update(evaluation.get("stage_timeouts_seconds", {}) or {})

        actual_image_id = docker_image_id(evaluation["docker_image"])
        if actual_image_id != evaluation["docker_image_id"]:
            raise RuntimeError("Docker image ID changed after configuration")

        for stage, command in (
            ("configure", evaluation["configure_command"]),
            ("build", evaluation["build_command"]),
            ("direct_test", evaluation["direct_test_command"]),
            ("full_test", evaluation["full_test_command"]),
        ):
            if stage != "configure" and not all(
                item.get("passed") for item in records.values()
            ):
                records[stage] = {"stage": stage, "passed": False, "skipped": True}
                continue

            record = docker_run(
                project_root=project_root,
                repository_path=str(config["repository_path"]),
                image=evaluation["docker_image"],
                shell_command=command,
                log_root=log_root,
                stage=stage,
                timeout_seconds=int(stage_timeouts[stage]),
            )
            output = record["stdout"] + "\n" + record["stderr"]

            if stage == "direct_test":
                counts = parse_gtest_counts(output)
                record["counts"] = counts
                record["passed"] = (
                    record["exit_code"] == 0
                    and counts["ran"] == evaluation["expected_direct_tests"]
                    and counts["passed"] == evaluation["expected_direct_tests"]
                    and counts["failed"] == 0
                )
            elif stage == "full_test":
                if evaluation["full_test_kind"] == "ctest":
                    counts = parse_ctest_counts(output)
                else:
                    counts = parse_gtest_counts(output)
                record["counts"] = counts
                record["passed"] = (
                    record["exit_code"] == 0
                    and counts["ran"] == evaluation["expected_full_tests"]
                    and counts["passed"] == evaluation["expected_full_tests"]
                    and counts["failed"] == 0
                )

            records[stage] = public_record(record)
            if not records[stage]["passed"]:
                for remaining in ("build", "direct_test", "full_test"):
                    if remaining not in records:
                        records[remaining] = {
                            "stage": remaining,
                            "passed": False,
                            "skipped": True,
                        }
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        source_path.write_bytes(original_bytes)

    restored_hash = sha256_file(source_path)
    restored = restored_hash == original_hash
    tracked_status = git_output(
        repository,
        "status",
        "--short",
        "--untracked-files=no",
    )
    repository_clean = tracked_status == ""

    overall = (
        error is None
        and all(
            records.get(stage, {}).get("passed") is True
            for stage in ("configure", "build", "direct_test", "full_test")
        )
        and restored
        and repository_clean
    )

    result = {
        "schema_version": "2.0",
        "target_id": config["target_id"],
        "run_id": config["run_id"],
        "condition": config.get("condition"),
        "completed_at_utc": utc_now(),
        "overall_pass": overall,
        "error": error,
        "stages": records,
        "restoration": {
            "restored": restored,
            "original_hash": original_hash,
            "restored_hash": restored_hash,
            "repository_clean": repository_clean,
            "tracked_status": tracked_status,
        },
        "code_regeneration_normalization": load_json(
            experiment_root
            / "raw_output"
            / "code_regeneration_normalization.json"
        ),
        "local_raw_log_directory": log_root.relative_to(project_root).as_posix(),
    }
    write_json(evaluation_dir / "evaluation_manifest.json", result)
    return result


def record_pipeline_failure(
    config: dict[str, Any],
    experiment_root: Path,
    stage: str,
    error: Exception,
) -> None:
    write_json(
        experiment_root / "evaluation" / "pipeline_failure.json",
        {
            "schema_version": "2.0",
            "target_id": config.get("target_id"),
            "run_id": config.get("run_id"),
            "condition": config.get("condition"),
            "failed_stage": stage,
            "error_type": type(error).__name__,
            "error": str(error),
            "recorded_at_utc": utc_now(),
            "retry_performed": False,
            "automatic_repair_performed": False,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one full-source observation / target-span round-trip experiment."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_path = (
        args.config if args.config.is_absolute() else project_root / args.config
    )
    config = load_json(config_path)

    if not config.get("enabled", False):
        raise RuntimeError("Target config is disabled")

    experiment_root = resolve_experiment_root(config, project_root)
    if experiment_root.exists():
        raise FileExistsError(
            f"Experiment directory already exists: {experiment_root}. "
            "Use a new experiment_id and run_id; do not overwrite a formal run."
        )

    stage = "prepare"
    try:
        prepare(config, project_root, experiment_root)
        stage = "design_generation"
        generate_design(config, project_root, experiment_root)
        stage = "code_regeneration"
        regenerate(config, experiment_root)
        stage = "evaluation"
        result = evaluate(config, project_root, experiment_root)
    except Exception as exc:
        record_pipeline_failure(config, experiment_root, stage, exc)
        raise

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
