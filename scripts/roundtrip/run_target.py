from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from roundtrip_common import (
    call_ollama,
    docker_image_id,
    docker_run,
    extract_includes,
    git_output,
    load_json,
    locate_class_span,
    markdown_details,
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


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"stdout", "stderr"}}


def ensure_clean(repository: Path) -> None:
    status = git_output(repository, "status", "--short", "--untracked-files=no")
    if status:
        raise RuntimeError(f"Repository has tracked changes before run:\n{status}")


def build_design_bundle(repository: Path, source_files: list[str]) -> tuple[str, str, str]:
    design_parts: list[str] = []
    scaffold_parts: list[str] = []
    includes: list[str] = []
    for relative in source_files:
        path = repository / relative
        text = read_text(path)
        design_parts.append(f"===== FILE: {relative} =====\n{text.rstrip()}\n")
        if path.suffix.lower() in {".h", ".hh", ".hpp", ".hxx"}:
            scaffold = strip_inline_callable_bodies(text)
            scaffold_parts.append(f"===== FILE: {relative} =====\n{scaffold.rstrip()}\n")
        includes.extend(extract_includes(text))
    dependency = "\n".join(dict.fromkeys(includes)) + "\n"
    return "\n".join(design_parts), "\n".join(scaffold_parts), dependency


def prepare(config: dict[str, Any], project_root: Path, experiment_root: Path) -> dict[str, Any]:
    repository = project_root / config["repository_path"]
    ensure_clean(repository)
    head = git_output(repository, "rev-parse", "HEAD")
    if head != config["repository_commit"]:
        raise RuntimeError(f"Repository commit mismatch: {head}")

    input_dir = experiment_root / "input"
    backup_dir = experiment_root / "backup"
    source_files = [str(item) for item in config["source_files"]]
    metadata: dict[str, Any] = {
        "target_id": config["target_id"],
        "target_name": config["target_name"],
        "repository_id": config["repository_id"],
        "repository_commit": head,
        "granularity": config["granularity"],
        "source_files": source_files,
        "prepared_at_utc": utc_now(),
        "original_files": [],
    }

    for relative in source_files:
        source = repository / relative
        if not source.exists():
            raise FileNotFoundError(source)
        backup = backup_dir / "files" / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)
        metadata["original_files"].append(
            {"path": relative, "sha256": sha256_file(source)}
        )

    if config["granularity"] == "module_files":
        design, scaffold, dependency = build_design_bundle(repository, source_files)
        write_text(input_dir / "design_input.txt", design)
        write_text(input_dir / "fixed_scaffold.txt", scaffold)
        write_text(input_dir / "dependency_context.txt", dependency)
    elif config["granularity"] == "class_span":
        symbol = config["locator"]["symbol"]
        if len(source_files) != 1:
            raise RuntimeError("class_span requires exactly one source file")
        source_text = read_text(repository / source_files[0])
        start, end = locate_class_span(source_text, symbol)
        original_span = source_text[start:end]
        write_text(backup_dir / "original_target.cpp", original_span)
        write_text(input_dir / "design_input.txt", original_span + "\n")
        write_text(
            input_dir / "fixed_scaffold.txt",
            strip_inline_callable_bodies(original_span) + "\n",
        )
        write_text(
            input_dir / "dependency_context.txt",
            "\n".join(extract_includes(source_text)) + "\n",
        )
        metadata["locator"] = {
            "symbol": symbol,
            "start_offset": start,
            "end_offset": end,
            "original_span_sha256": sha256_bytes(original_span.encode("utf-8")),
        }
    else:
        raise RuntimeError(f"Unsupported granularity: {config['granularity']}")

    write_json(input_dir / "source_metadata.json", metadata)
    write_json(experiment_root / "configs" / "target_config.json", config)
    return metadata


def ollama_options(config: dict[str, Any]) -> dict[str, Any]:
    model = config["model"]
    return {
        "temperature": model.get("temperature", 0),
        "seed": model.get("seed", 42),
        "num_ctx": model.get("num_ctx", 8192),
        "num_predict": model.get("num_predict", 2048),
        "top_k": model.get("top_k", 40),
        "top_p": model.get("top_p", 0.9),
        "repeat_penalty": model.get("repeat_penalty", 1.1),
    }


def generate_design(config: dict[str, Any], experiment_root: Path) -> dict[str, Any]:
    design_input = read_text(experiment_root / "input" / "design_input.txt")
    system = (
        "あなたはC++ソフトウェアのリバースエンジニアリング担当者です。"
        "与えられたコードだけを根拠として、再実装に必要な設計文書を日本語で作成してください。"
        "推測で存在しない機能を追加しないでください。"
    )
    prompt = f"""# 対象
- target: {config['target_name']}
- granularity: {config['granularity']}

# 記載項目
責務、公開インターフェース、入力、出力、状態、処理手順、例外・失敗条件、依存関係、重要な不変条件を記載してください。

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


def module_output_schema(expected_paths: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "files": {
                "type": "array",
                "minItems": len(expected_paths),
                "maxItems": len(expected_paths),
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "enum": expected_paths},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["files"],
        "additionalProperties": False,
    }


def parse_module_output(text: str, expected_paths: list[str]) -> dict[str, str]:
    if "```" in text:
        raise RuntimeError("Code regeneration output contains Markdown fences")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        start = max(0, error.pos - 80)
        end = min(len(text), error.pos + 80)
        context = repr(text[start:end])
        raise RuntimeError(
            "Code regeneration output is not valid JSON: "
            f"line={error.lineno}, column={error.colno}, context={context}"
        ) from error
    if not isinstance(value, dict) or not isinstance(value.get("files"), list):
        raise RuntimeError("Module output must be an object containing a files array")
    files: dict[str, str] = {}
    for item in value["files"]:
        if not isinstance(item, dict):
            raise RuntimeError("Each files item must be an object")
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            raise RuntimeError("Each file requires string path and content")
        files[path] = content
    if set(files) != set(expected_paths):
        raise RuntimeError(
            f"Generated file paths mismatch. expected={expected_paths}, actual={sorted(files)}"
        )
    return files


def regenerate(config: dict[str, Any], experiment_root: Path) -> dict[str, Any]:
    design = read_text(experiment_root / "generated" / "design_document.md")
    scaffold = read_text(experiment_root / "input" / "fixed_scaffold.txt")
    dependency = read_text(experiment_root / "input" / "dependency_context.txt")

    output_schema: dict[str, Any] | None = None
    if config["granularity"] == "module_files":
        expected_paths = [str(item) for item in config["source_files"]]
        output_schema = module_output_schema(expected_paths)
        output_instruction = (
            "出力は指定されたJSON Schemaに一致するJSONのみとし、"
            "Markdownコードフェンスを使用しないでください。"
            "source_filesにある各ファイルを完全な内容として1回ずつ返してください。"
            "C++コード中の改行や引用符はJSON文字列として正しくエスケープしてください。"
        )
    else:
        output_instruction = (
            "対象クラス定義全体だけをC++コードとして返してください。"
            "Markdownコードフェンス、説明文、JSONは出力しないでください。"
        )

    system = (
        "あなたはC++実装担当者です。設計文書と固定インターフェースだけを根拠に実装してください。"
        "元実装は与えられていません。公開インターフェースとファイル構成を変更しないでください。"
    )
    prompt = f"""# 対象
- target: {config['target_name']}
- granularity: {config['granularity']}
- source_files: {json.dumps(config['source_files'], ensure_ascii=False)}

# 出力規則
{output_instruction}

# JSON Schema
{json.dumps(output_schema, ensure_ascii=False, indent=2) if output_schema else "N/A"}

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
    if output_schema is not None:
        payload["format"] = output_schema
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

    generated_dir = experiment_root / "generated"
    if config["granularity"] == "module_files":
        files = parse_module_output(text, [str(item) for item in config["source_files"]])
        for relative, content in files.items():
            write_text(generated_dir / "files" / relative, content)
        write_json(generated_dir / "generated_files_manifest.json", {"files": sorted(files)})
    else:
        if "```" in text:
            raise RuntimeError("Class regeneration output contains Markdown fences")
        write_text(generated_dir / "regenerated_target.cpp", text)
    return metadata


def evaluate(config: dict[str, Any], project_root: Path, experiment_root: Path) -> dict[str, Any]:
    repository = project_root / config["repository_path"]
    evaluation_dir = experiment_root / "evaluation"
    log_root = project_root / "logs" / "roundtrip" / config["run_id"]
    originals = {relative: (repository / relative).read_bytes() for relative in config["source_files"]}
    original_hashes = {relative: sha256_bytes(data) for relative, data in originals.items()}
    records: dict[str, Any] = {}
    error: str | None = None

    try:
        if config["granularity"] == "module_files":
            for relative in config["source_files"]:
                generated = experiment_root / "generated" / "files" / relative
                if not generated.exists():
                    raise FileNotFoundError(generated)
                (repository / relative).write_bytes(generated.read_bytes())
        else:
            relative = config["source_files"][0]
            source_path = repository / relative
            source_text = read_text(source_path)
            start, end = locate_class_span(source_text, config["locator"]["symbol"])
            generated = read_text(experiment_root / "generated" / "regenerated_target.cpp").strip()
            newline = "\r\n" if "\r\n" in source_text else "\n"
            generated = generated.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
            modified = source_text[:start] + generated + source_text[end:]
            source_path.write_text(modified, encoding="utf-8", newline="")

        evaluation = config["evaluation"]
        actual_image_id = docker_image_id(evaluation["docker_image"])
        if actual_image_id != evaluation["docker_image_id"]:
            raise RuntimeError("Docker image ID changed after configuration")

        for stage, command in (
            ("configure", evaluation["configure_command"]),
            ("build", evaluation["build_command"]),
            ("direct_test", evaluation["direct_test_command"]),
            ("full_test", evaluation["full_test_command"]),
        ):
            if stage != "configure" and not all(item.get("passed") for item in records.values()):
                records[stage] = {"stage": stage, "passed": False, "skipped": True}
                continue
            record = docker_run(
                project_root=project_root,
                repository_path=config["repository_path"],
                image=evaluation["docker_image"],
                shell_command=command,
                log_root=log_root,
                stage=stage,
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
                counts = (
                    parse_ctest_counts(output)
                    if evaluation["full_test_kind"] == "ctest"
                    else parse_gtest_counts(output)
                )
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
                        records[remaining] = {"stage": remaining, "passed": False, "skipped": True}
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        for relative, data in originals.items():
            (repository / relative).write_bytes(data)

    restored_hashes = {relative: sha256_file(repository / relative) for relative in config["source_files"]}
    restored = restored_hashes == original_hashes
    tracked_status = git_output(repository, "status", "--short", "--untracked-files=no")
    repository_clean = tracked_status == ""
    overall = (
        error is None
        and all(records.get(stage, {}).get("passed") is True for stage in ("configure", "build", "direct_test", "full_test"))
        and restored
        and repository_clean
    )
    result = {
        "schema_version": "1.0",
        "target_id": config["target_id"],
        "run_id": config["run_id"],
        "completed_at_utc": utc_now(),
        "overall_pass": overall,
        "error": error,
        "stages": records,
        "restoration": {
            "restored": restored,
            "original_hashes": original_hashes,
            "restored_hashes": restored_hashes,
            "repository_clean": repository_clean,
            "tracked_status": tracked_status,
        },
        "local_raw_log_directory": log_root.relative_to(project_root).as_posix(),
    }
    write_json(evaluation_dir / "evaluation_manifest.json", result)
    return result


def build_report(config: dict[str, Any], experiment_root: Path, evaluation: dict[str, Any]) -> str:
    design_input = read_text(experiment_root / "input" / "design_input.txt")
    scaffold = read_text(experiment_root / "input" / "fixed_scaffold.txt")
    design = read_text(experiment_root / "generated" / "design_document.md")
    design_request = read_text(experiment_root / "raw_output" / "design_generation_request.json")
    design_response = read_text(experiment_root / "raw_output" / "design_generation_response.json")
    code_request = read_text(experiment_root / "raw_output" / "code_regeneration_request.json")
    code_response = read_text(experiment_root / "raw_output" / "code_regeneration_response.json")

    lines = [
        "# ラウンドトリップ実験 総合レポート",
        "",
        f"- target: `{config['target_name']}`",
        f"- target_id: `{config['target_id']}`",
        f"- run_id: `{config['run_id']}`",
        f"- repository: `{config['repository_id']}`",
        f"- granularity: `{config['granularity']}`",
        f"- model: `{config['model']['name']}`",
        f"- overall: **{'PASS' if evaluation['overall_pass'] else 'FAIL'}**",
        "",
        "## 評価",
        "",
        "| stage | result | detail |",
        "|---|---|---|",
    ]
    for stage in ("configure", "build", "direct_test", "full_test"):
        record = evaluation["stages"].get(stage, {})
        counts = record.get("counts")
        detail = (
            f"{counts.get('passed')}/{counts.get('ran')} passed"
            if isinstance(counts, dict)
            else f"exit={record.get('exit_code', 'N/A')}"
        )
        lines.append(f"| {stage} | {'PASS' if record.get('passed') else 'FAIL'} | {detail} |")
    lines.extend(
        [
            "",
            markdown_details("設計書生成へ与えたコード", design_input, "cpp"),
            "",
            markdown_details("コード再生成時の固定スキャフォールド", scaffold, "cpp"),
            "",
            markdown_details("生成された設計文書", design, "markdown"),
            "",
            markdown_details("設計書生成request JSON", design_request, "json"),
            "",
            markdown_details("設計書生成response JSON", design_response, "json"),
            "",
            markdown_details("コード再生成request JSON", code_request, "json"),
            "",
            markdown_details("コード再生成response JSON", code_response, "json"),
            "",
            "テスト通過は既存テストが観測する範囲での正当性を示すものであり，完全な意味的等価性を保証しない．",
            "",
        ]
    )
    return "\n".join(lines)


def register(config: dict[str, Any], project_root: Path, evaluation: dict[str, Any], experiment_root: Path) -> None:
    runs_path = project_root / "manifests" / "runs.csv"
    targets_path = project_root / "manifests" / "targets.csv"

    with runs_path.open("r", encoding="utf-8-sig", newline="") as handle:
        runs = list(csv.DictReader(handle))
    record = {
        "run_id": config["run_id"],
        "repository_id": config["repository_id"],
        "target_id": config["target_id"],
        "model_id": config["model"]["name"],
        "status": "passed" if evaluation["overall_pass"] else "failed",
        "started_at_utc": load_json(experiment_root / "raw_output" / "design_generation_metadata.json")["started_at_utc"],
        "completed_at_utc": evaluation["completed_at_utc"],
        "result_path": (experiment_root / "evaluation" / "evaluation_manifest.json").relative_to(project_root).as_posix(),
    }
    runs = [item for item in runs if item.get("run_id") != config["run_id"]]
    runs.append(record)
    with runs_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(record))
        writer.writeheader()
        writer.writerows(runs)

    with targets_path.open("r", encoding="utf-8-sig", newline="") as handle:
        targets = list(csv.DictReader(handle))
    if not any(item.get("target_id") == config["target_id"] for item in targets):
        targets.append(
            {
                "repository_id": config["repository_id"],
                "target_id": config["target_id"],
                "target_name": config["target_name"],
                "target_granularity": config["granularity"],
                "source_file": ";".join(config["source_files"]),
                "status": config.get("adoption_status") or "adopted",
                "notes": "Registered by generic round-trip harness.",
            }
        )
        with targets_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["repository_id", "target_id", "target_name", "target_granularity", "source_file", "status", "notes"])
            writer.writeheader()
            writer.writerows(targets)



def record_pipeline_failure(
    *,
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
    stage: str,
    error: Exception,
) -> None:
    repository = project_root / config.get("repository_path", "")
    repository_clean: bool | None = None
    tracked_status: str | None = None
    try:
        if repository.exists():
            tracked_status = git_output(
                repository, "status", "--short", "--untracked-files=no"
            )
            repository_clean = tracked_status == ""
    except Exception:
        repository_clean = None

    write_json(
        experiment_root / "evaluation" / "pipeline_failure.json",
        {
            "schema_version": "1.0",
            "target_id": config.get("target_id"),
            "run_id": config.get("run_id"),
            "failed_stage": stage,
            "error_type": type(error).__name__,
            "error": str(error),
            "recorded_at_utc": utc_now(),
            "retry_performed": False,
            "automatic_repair_performed": False,
            "repository_clean": repository_clean,
            "tracked_status": tracked_status,
        },
    )

def main() -> int:
    parser = argparse.ArgumentParser(description="Run one configured round-trip target end to end.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_path = args.config if args.config.is_absolute() else project_root / args.config
    config = load_json(config_path)
    if config.get("enabled") is not True:
        raise RuntimeError("Target config is not enabled")
    experiment_root = project_root / "experiments" / config["experiment_id"]
    if experiment_root.exists() and any(experiment_root.iterdir()):
        if not args.force:
            raise FileExistsError(f"Experiment output already exists: {experiment_root}")
        shutil.rmtree(experiment_root)

    stage = "prepare"
    try:
        prepare(config, project_root, experiment_root)
        stage = "generate_design"
        generate_design(config, experiment_root)
        stage = "regenerate_code"
        regenerate(config, experiment_root)
        stage = "evaluate"
        evaluation = evaluate(config, project_root, experiment_root)
        stage = "generate_report"
        report = build_report(config, experiment_root, evaluation)
        write_text(experiment_root / "report" / "experiment_overview.md", report)
        write_json(experiment_root / "report" / "experiment_overview.json", evaluation)
        stage = "register_run"
        register(config, project_root, evaluation, experiment_root)
    except Exception as error:
        record_pipeline_failure(
            config=config,
            project_root=project_root,
            experiment_root=experiment_root,
            stage=stage,
            error=error,
        )
        raise

    print(f"Target:  {config['target_id']}")
    print(f"Result:  {'PASS' if evaluation['overall_pass'] else 'FAIL'}")
    print(f"Report:  {experiment_root / 'report' / 'experiment_overview.md'}")
    return 0 if evaluation["overall_pass"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
