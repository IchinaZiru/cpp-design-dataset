from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_EXPERIMENT_ID = "ini-writer-minimal"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(read_text(path))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def line_count(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    text = read_text(path)
    return len(text.splitlines())


def file_info(path: Path, project_root: Path, role: str) -> dict[str, Any]:
    exists = path.exists() and path.is_file()
    return {
        "role": role,
        "path": relative_path(path, project_root),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else None,
        "line_count": line_count(path) if exists else None,
        "sha256": sha256_file(path) if exists else None,
    }


def relative_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def bool_label(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "N/A"


def yes_no(value: Any) -> str:
    if value is True:
        return "はい"
    if value is False:
        return "いいえ"
    return "不明"


def format_number(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def format_duration(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "N/A"
    if seconds < 60:
        return f"{seconds:.2f}秒"
    minutes, remain = divmod(seconds, 60)
    return f"{int(minutes)}分{remain:.2f}秒"


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        cells = []
        for value in row:
            text = str(value).replace("\n", "<br>").replace("|", "\\|")
            cells.append(text)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def fenced_block(content: str, language: str = "text") -> str:
    fence = "```"
    while fence in content:
        fence += "`"
    return f"{fence}{language}\n{content.rstrip()}\n{fence}"


def collapsible(title: str, content: str, language: str = "text") -> str:
    return (
        "<details>\n"
        f"<summary>{title}</summary>\n\n"
        f"{fenced_block(content, language)}\n\n"
        "</details>"
    )


def parse_model(run_config: dict[str, Any]) -> dict[str, Any]:
    model = nested(run_config, "model", default={})
    options = nested(run_config, "generation", "options", default={})
    return {
        "provider": run_config.get("provider"),
        "name": model.get("name"),
        "local_id": model.get("local_id"),
        "architecture": model.get("architecture"),
        "parameters": model.get("parameters"),
        "quantization": model.get("quantization"),
        "ollama_version": model.get("ollama_version"),
        "temperature": options.get("temperature"),
        "seed": options.get("seed"),
        "num_ctx": options.get("num_ctx"),
        "num_predict": options.get("num_predict"),
        "top_k": options.get("top_k"),
        "top_p": options.get("top_p"),
        "repeat_penalty": options.get("repeat_penalty"),
    }


def stage_record(
    name: str,
    passed: Any,
    detail: str,
    elapsed_seconds: Any = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "status": bool_label(passed),
        "detail": detail,
        "elapsed_seconds": elapsed_seconds,
    }


def get_gtest_counts(result: dict[str, Any]) -> tuple[Any, Any, Any]:
    gtest = result.get("gtest", {})
    if not isinstance(gtest, dict):
        return None, None, None
    return (
        gtest.get("tests_ran"),
        gtest.get("tests_passed"),
        gtest.get("tests_failed"),
    )


def normalized_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def compare_code(original_path: Path, regenerated_path: Path) -> dict[str, Any]:
    if not original_path.exists() or not regenerated_path.exists():
        return {
            "available": False,
            "exact_match": None,
            "whitespace_insensitive_match": None,
            "similarity_ratio": None,
            "original_lines": None,
            "regenerated_lines": None,
        }

    original = normalized_text(read_text(original_path))
    regenerated = normalized_text(read_text(regenerated_path))
    original_compact = "".join(original.split())
    regenerated_compact = "".join(regenerated.split())

    return {
        "available": True,
        "exact_match": original == regenerated,
        "whitespace_insensitive_match": original_compact == regenerated_compact,
        "similarity_ratio": difflib.SequenceMatcher(
            None, original, regenerated
        ).ratio(),
        "original_lines": len(original.splitlines()),
        "regenerated_lines": len(regenerated.splitlines()),
        "original_sha256": sha256_file(original_path),
        "regenerated_sha256": sha256_file(regenerated_path),
    }


def build_report(
    *,
    project_root: Path,
    experiment_root: Path,
    include_content: bool,
) -> tuple[str, dict[str, Any]]:
    input_dir = experiment_root / "input"
    config_dir = experiment_root / "configs"
    prompt_dir = experiment_root / "prompts"
    generated_dir = experiment_root / "generated"
    raw_dir = experiment_root / "raw_output"
    evaluation_dir = experiment_root / "evaluation"
    backup_dir = experiment_root / "backup"

    source_metadata = load_json(input_dir / "source_metadata.json")
    run_config = load_json(config_dir / "run_config.json")
    design_metadata = load_json(raw_dir / "design_generation_metadata.json")
    code_metadata = load_json(raw_dir / "code_regeneration_metadata.json")
    evaluation_manifest = load_json(evaluation_dir / "evaluation_manifest.json")
    source_replacement = load_json(evaluation_dir / "source_replacement.json")
    build_result = load_json(evaluation_dir / "build_result.json")
    direct_result = load_json(evaluation_dir / "direct_test_result.json")
    full_result = load_json(evaluation_dir / "full_test_result.json")
    ctest_result = load_json(evaluation_dir / "ctest_result.json")

    model = parse_model(run_config)
    code_comparison = compare_code(
        backup_dir / "original_write_body.cpp",
        generated_dir / "regenerated_write_body.cpp",
    )

    inputs = [
        file_info(
            input_dir / "design_input.cpp",
            project_root,
            "設計書生成へ与えた元コード",
        ),
        file_info(
            input_dir / "fixed_scaffold.cpp",
            project_root,
            "コード再生成時の固定スキャフォールド",
        ),
        file_info(
            input_dir / "dependency_context.txt",
            project_root,
            "コード再生成時の依存関係情報",
        ),
        file_info(
            prompt_dir / "design_generation_prompt.md",
            project_root,
            "設計書生成プロンプト",
        ),
        file_info(
            prompt_dir / "code_regeneration_prompt.md",
            project_root,
            "コード再生成プロンプト",
        ),
        file_info(
            config_dir / "run_config.json",
            project_root,
            "モデル・生成パラメータ",
        ),
    ]

    outputs = [
        file_info(
            generated_dir / "design_document.md",
            project_root,
            "LLMが生成した設計文書",
        ),
        file_info(
            generated_dir / "regenerated_write_body.cpp",
            project_root,
            "設計文書から再生成した関数本体",
        ),
        file_info(
            raw_dir / "design_generation_request.json",
            project_root,
            "設計書生成APIリクエスト",
        ),
        file_info(
            raw_dir / "design_generation_response.json",
            project_root,
            "設計書生成API応答",
        ),
        file_info(
            raw_dir / "code_regeneration_request.json",
            project_root,
            "コード再生成APIリクエスト",
        ),
        file_info(
            raw_dir / "code_regeneration_response.json",
            project_root,
            "コード再生成API応答",
        ),
        file_info(
            evaluation_dir / "evaluation_manifest.json",
            project_root,
            "評価結果の機械可読マニフェスト",
        ),
        file_info(
            evaluation_dir / "evaluation_summary.md",
            project_root,
            "評価結果の要約",
        ),
        file_info(
            evaluation_dir / "replacement_diff.patch",
            project_root,
            "一時置換した差分",
        ),
    ]

    configure = build_result.get("configure", {})
    build = build_result.get("build", {})
    direct_ran, direct_passed, direct_failed = get_gtest_counts(direct_result)
    full_ran, full_passed, full_failed = get_gtest_counts(full_result)
    restoration = evaluation_manifest.get("restoration", {})
    if not isinstance(restoration, dict):
        restoration = {}

    stages = [
        stage_record(
            "設計書生成",
            design_metadata.get("done") is True,
            (
                f"入力{design_metadata.get('prompt_eval_count', 'N/A')} tokens，"
                f"出力{design_metadata.get('eval_count', 'N/A')} tokens"
            ),
            design_metadata.get("elapsed_seconds"),
        ),
        stage_record(
            "コード再生成",
            code_metadata.get("done") is True,
            (
                f"入力{code_metadata.get('prompt_eval_count', 'N/A')} tokens，"
                f"出力{code_metadata.get('eval_count', 'N/A')} tokens"
            ),
            code_metadata.get("elapsed_seconds"),
        ),
        stage_record(
            "clean configure",
            configure.get("passed"),
            f"exit code {configure.get('exit_code', 'N/A')}",
            configure.get("elapsed_seconds"),
        ),
        stage_record(
            "full build",
            build.get("passed"),
            f"exit code {build.get('exit_code', 'N/A')}",
            build.get("elapsed_seconds"),
        ),
        stage_record(
            "直接テスト",
            direct_result.get("passed"),
            f"{direct_passed}/{direct_result.get('expected_tests', direct_ran)} passed",
            direct_result.get("elapsed_seconds"),
        ),
        stage_record(
            "全GoogleTest",
            full_result.get("passed"),
            f"{full_passed}/{full_result.get('expected_tests', full_ran)} passed",
            full_result.get("elapsed_seconds"),
        ),
        stage_record(
            "CTest",
            ctest_result.get("passed"),
            f"exit code {ctest_result.get('exit_code', 'N/A')}",
            ctest_result.get("elapsed_seconds"),
        ),
        stage_record(
            "元コード復元",
            restoration.get("restored"),
            f"SHA-256 {restoration.get('restored_sha256', 'N/A')}",
        ),
        stage_record(
            "submodule clean",
            restoration.get("submodule_clean"),
            "追跡対象の差分・変更がないことを確認",
        ),
    ]

    known_stage_results = [
        stage["passed"] for stage in stages if isinstance(stage["passed"], bool)
    ]
    passed_stage_count = sum(1 for value in known_stage_results if value)
    stage_count = len(known_stage_results)

    design_seconds = design_metadata.get("elapsed_seconds")
    code_seconds = code_metadata.get("elapsed_seconds")
    generation_total_seconds = sum(
        value
        for value in (design_seconds, code_seconds)
        if isinstance(value, (int, float))
    )

    evaluation_seconds = sum(
        value
        for value in (
            configure.get("elapsed_seconds"),
            build.get("elapsed_seconds"),
            direct_result.get("elapsed_seconds"),
            full_result.get("elapsed_seconds"),
            ctest_result.get("elapsed_seconds"),
        )
        if isinstance(value, (int, float))
    )

    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_id": (
            evaluation_manifest.get("experiment_id")
            or run_config.get("experiment_id")
            or experiment_root.name
        ),
        "run_id": (
            evaluation_manifest.get("run_id")
            or run_config.get("run_id")
        ),
        "repository": source_metadata.get("repository"),
        "repository_commit": source_metadata.get("repository_commit"),
        "submodule_commit": source_metadata.get("submodule_commit"),
        "target_name": source_metadata.get("target_function"),
        "target_granularity": source_metadata.get("target_granularity"),
        "source_file": source_metadata.get("source_file"),
        "model": model,
        "overall_pass": evaluation_manifest.get("overall_pass"),
        "stage_passed": passed_stage_count,
        "stage_total": stage_count,
        "direct_tests": {
            "ran": direct_ran,
            "passed": direct_passed,
            "failed": direct_failed,
            "expected": direct_result.get("expected_tests"),
        },
        "full_tests": {
            "ran": full_ran,
            "passed": full_passed,
            "failed": full_failed,
            "expected": full_result.get("expected_tests"),
        },
        "generation_total_seconds": generation_total_seconds,
        "evaluation_total_seconds": evaluation_seconds,
        "inputs": inputs,
        "outputs": outputs,
        "stages": stages,
        "code_comparison": code_comparison,
        "source_replacement": source_replacement,
    }

    overall = bool_label(summary["overall_pass"])
    direct_ratio = (
        f"{direct_passed}/{direct_result.get('expected_tests', direct_ran)}"
        if direct_passed is not None
        else "N/A"
    )
    full_ratio = (
        f"{full_passed}/{full_result.get('expected_tests', full_ran)}"
        if full_passed is not None
        else "N/A"
    )

    lines: list[str] = []
    lines.append("# ラウンドトリップ実験 総合レポート")
    lines.append("")
    lines.append("> このファイルは実験成果物から自動生成した閲覧用レポートである．")
    lines.append("> 元データは変更せず，入力・出力・評価結果を一つに集約する．")
    lines.append("")

    lines.append("## 1. 一目で分かる結果")
    lines.append("")
    lines.append(
        markdown_table(
            ["項目", "値"],
            [
                ["実験ID", f"`{summary['experiment_id']}`"],
                ["実行ID", f"`{summary['run_id']}`"],
                ["対象", f"`{summary['target_name']}`"],
                ["粒度", f"`{summary['target_granularity']}`"],
                ["モデル", f"`{model.get('name')}`"],
                ["総合判定", f"**{overall}**"],
                ["評価工程", f"{passed_stage_count}/{stage_count} PASS"],
                ["直接テスト", f"{direct_ratio} PASS"],
                ["全GoogleTest", f"{full_ratio} PASS"],
                ["生成処理時間", format_duration(generation_total_seconds)],
                ["評価処理時間", format_duration(evaluation_seconds)],
            ],
        )
    )
    lines.append("")

    lines.append("## 2. 実験のデータフロー")
    lines.append("")
    lines.append(
        markdown_table(
            ["段階", "主な入力", "主な出力", "結果"],
            [
                [
                    "元コード → 設計文書",
                    "`design_input.cpp`＋設計書生成プロンプト",
                    "`design_document.md`",
                    bool_label(design_metadata.get("done") is True),
                ],
                [
                    "設計文書 → コード",
                    (
                        "`design_document.md`＋`fixed_scaffold.cpp`＋"
                        "`dependency_context.txt`"
                    ),
                    "`regenerated_write_body.cpp`",
                    bool_label(code_metadata.get("done") is True),
                ],
                [
                    "再生成コード → 評価",
                    (
                        "再生成コード＋固定commit＋Docker環境＋既存テスト"
                    ),
                    "評価JSON・要約・置換差分",
                    overall,
                ],
            ],
        )
    )
    lines.append("")

    lines.append("## 3. 対象と入力条件")
    lines.append("")
    lines.append(
        markdown_table(
            ["項目", "値"],
            [
                ["Repository", source_metadata.get("repository", "N/A")],
                [
                    "Repository commit",
                    f"`{source_metadata.get('repository_commit', 'N/A')}`",
                ],
                [
                    "GoogleTest commit",
                    f"`{source_metadata.get('submodule_commit', 'N/A')}`",
                ],
                ["対象クラス", source_metadata.get("target_class", "N/A")],
                ["対象関数", source_metadata.get("target_function", "N/A")],
                ["置換粒度", source_metadata.get("target_granularity", "N/A")],
                ["ソース", f"`{source_metadata.get('source_file', 'N/A')}`"],
                [
                    "設計生成時に元関数本体を含む",
                    yes_no(
                        source_metadata.get(
                            "original_function_body_included_for_design_generation"
                        )
                    ),
                ],
                [
                    "コード再生成時に元関数本体を除外",
                    yes_no(
                        source_metadata.get(
                            "original_function_body_excluded_from_regeneration_input"
                        )
                    ),
                ],
                [
                    "置換範囲",
                    source_metadata.get("replacement_scope", "N/A"),
                ],
                [
                    "依存メソッド",
                    ", ".join(source_metadata.get("dependency_methods", []))
                    or "N/A",
                ],
            ],
        )
    )
    lines.append("")

    lines.append("## 4. LLM実行条件")
    lines.append("")
    lines.append(
        markdown_table(
            ["項目", "値"],
            [
                ["Provider", model.get("provider", "N/A")],
                ["Model", f"`{model.get('name', 'N/A')}`"],
                ["Local model ID", f"`{model.get('local_id', 'N/A')}`"],
                ["Architecture", model.get("architecture", "N/A")],
                ["Parameters", model.get("parameters", "N/A")],
                ["Quantization", model.get("quantization", "N/A")],
                ["Ollama", model.get("ollama_version", "N/A")],
                ["temperature", format_number(model.get("temperature"))],
                ["seed", format_number(model.get("seed"))],
                ["num_ctx", format_number(model.get("num_ctx"))],
                ["num_predict", format_number(model.get("num_predict"))],
                ["top_k", format_number(model.get("top_k"))],
                ["top_p", format_number(model.get("top_p"))],
                ["repeat_penalty", format_number(model.get("repeat_penalty"))],
                [
                    "再試行",
                    yes_no(
                        nested(
                            run_config,
                            "conditions",
                            "retry_on_failure",
                        )
                    ),
                ],
                [
                    "自動修正",
                    yes_no(
                        nested(
                            run_config,
                            "conditions",
                            "automatic_repair",
                        )
                    ),
                ],
            ],
        )
    )
    lines.append("")

    lines.append("## 5. 入力ファイル")
    lines.append("")
    lines.append(
        markdown_table(
            ["役割", "パス", "行数", "サイズ", "SHA-256"],
            [
                [
                    item["role"],
                    f"`{item['path']}`",
                    item["line_count"] if item["exists"] else "欠落",
                    item["size_bytes"] if item["exists"] else "欠落",
                    (
                        f"`{item['sha256']}`"
                        if item["sha256"] is not None
                        else "N/A"
                    ),
                ]
                for item in inputs
            ],
        )
    )
    lines.append("")

    lines.append("## 6. 生成物・評価成果物")
    lines.append("")
    lines.append(
        markdown_table(
            ["役割", "パス", "行数", "サイズ", "SHA-256"],
            [
                [
                    item["role"],
                    f"`{item['path']}`",
                    item["line_count"] if item["exists"] else "欠落",
                    item["size_bytes"] if item["exists"] else "欠落",
                    (
                        f"`{item['sha256']}`"
                        if item["sha256"] is not None
                        else "N/A"
                    ),
                ]
                for item in outputs
            ],
        )
    )
    lines.append("")

    lines.append("## 7. 各工程の評価")
    lines.append("")
    lines.append(
        markdown_table(
            ["工程", "結果", "詳細", "時間"],
            [
                [
                    stage["name"],
                    stage["status"],
                    stage["detail"],
                    format_duration(stage["elapsed_seconds"]),
                ]
                for stage in stages
            ],
        )
    )
    lines.append("")

    lines.append("## 8. 元コードと再生成コードのテキスト比較")
    lines.append("")
    if code_comparison["available"]:
        lines.append(
            markdown_table(
                ["項目", "値"],
                [
                    [
                        "完全一致",
                        yes_no(code_comparison["exact_match"]),
                    ],
                    [
                        "空白を除いた一致",
                        yes_no(
                            code_comparison["whitespace_insensitive_match"]
                        ),
                    ],
                    [
                        "文字列類似度",
                        f"{code_comparison['similarity_ratio']:.4f}",
                    ],
                    [
                        "元コード行数",
                        code_comparison["original_lines"],
                    ],
                    [
                        "再生成コード行数",
                        code_comparison["regenerated_lines"],
                    ],
                    [
                        "元コードSHA-256",
                        f"`{code_comparison['original_sha256']}`",
                    ],
                    [
                        "再生成コードSHA-256",
                        f"`{code_comparison['regenerated_sha256']}`",
                    ],
                ],
            )
        )
        lines.append("")
        lines.append(
            "この比較は文字列上の差を示すだけであり，意味的等価性の評価ではない．"
        )
    else:
        lines.append("比較対象ファイルが不足しているため算出できない．")
    lines.append("")

    lines.append("## 9. 評価の解釈")
    lines.append("")
    if evaluation_manifest.get("overall_pass") is True:
        lines.append(
            "再生成コードは，固定環境においてconfigure，build，"
            "直接テスト，全GoogleTest，CTestをすべて通過した．"
        )
    elif evaluation_manifest.get("overall_pass") is False:
        lines.append(
            "再生成コードは，固定した評価工程の少なくとも一つを通過しなかった．"
        )
    else:
        lines.append("総合判定を取得できなかった．")
    lines.append("")
    lines.append(
        "テスト通過は既存テストスイートが観測する範囲での正当性を示すものであり，"
        "未検証機能を含む完全な意味的等価性を保証しない．"
    )
    lines.append("")

    if include_content:
        lines.append("## 10. 内容確認")
        lines.append("")

        content_files = [
            (
                "設計書生成へ与えた元コード",
                input_dir / "design_input.cpp",
                "cpp",
            ),
            (
                "生成された設計文書",
                generated_dir / "design_document.md",
                "markdown",
            ),
            (
                "再生成された関数本体",
                generated_dir / "regenerated_write_body.cpp",
                "cpp",
            ),
            (
                "一時置換差分",
                evaluation_dir / "replacement_diff.patch",
                "diff",
            ),
        ]
        for title, path, language in content_files:
            if path.exists():
                lines.append(
                    collapsible(
                        f"{title}（{relative_path(path, project_root)}）",
                        read_text(path),
                        language,
                    )
                )
                lines.append("")

    lines.append("## 11. 再現性のための主要ファイル")
    lines.append("")
    lines.append(
        "- 実験条件：`configs/run_config.json`\n"
        "- 設計生成プロンプト：`prompts/design_generation_prompt.md`\n"
        "- コード再生成プロンプト：`prompts/code_regeneration_prompt.md`\n"
        "- 設計生成API記録：`raw_output/design_generation_*.json`\n"
        "- コード再生成API記録：`raw_output/code_regeneration_*.json`\n"
        "- 評価マニフェスト：`evaluation/evaluation_manifest.json`\n"
        "- 詳細な標準出力・標準エラー："
        f"`{evaluation_manifest.get('local_raw_log_directory', 'N/A')}`"
    )
    lines.append("")

    return "\n".join(lines).rstrip() + "\n", summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one easy-to-read Markdown overview and one JSON summary "
            "from a round-trip experiment directory."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Research repository root.",
    )
    parser.add_argument(
        "--experiment",
        default=DEFAULT_EXPERIMENT_ID,
        help="Directory name under experiments/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Markdown output path. Default: "
            "experiments/<experiment>/report/experiment_overview.md"
        ),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help=(
            "JSON output path. Default: "
            "experiments/<experiment>/report/experiment_overview.json"
        ),
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="Do not embed source/design/code/diff content in the Markdown.",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    experiment_root = project_root / "experiments" / args.experiment
    if not experiment_root.exists():
        raise FileNotFoundError(
            f"Experiment directory not found: {experiment_root}"
        )

    report_dir = experiment_root / "report"
    markdown_output = (
        args.output.resolve()
        if args.output is not None
        else report_dir / "experiment_overview.md"
    )
    json_output = (
        args.json_output.resolve()
        if args.json_output is not None
        else report_dir / "experiment_overview.json"
    )

    markdown, summary = build_report(
        project_root=project_root,
        experiment_root=experiment_root,
        include_content=not args.no_content,
    )
    write_text(markdown_output, markdown)
    write_json(json_output, summary)

    print(f"Markdown report: {markdown_output}")
    print(f"JSON summary:   {json_output}")
    print(
        "Overall result: "
        + bool_label(summary.get("overall_pass"))
        + f" ({summary.get('stage_passed')}/{summary.get('stage_total')} stages)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
