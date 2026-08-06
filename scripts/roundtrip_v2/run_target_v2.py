from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
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


TARGET_SPAN_GRANULARITIES = {
    "target_span",
    "class_span",
    "function",
    "function_body",
}
HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx"}
REQUIRED_EVALUATION_KEYS = {
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


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"stdout", "stderr"}}


def ensure_clean(repository: Path) -> None:
    status = git_output(repository, "status", "--short", "--untracked-files=no")
    if status:
        raise RuntimeError(f"Repository has tracked changes before run:\n{status}")


def normalized_granularity(config: dict[str, Any]) -> str:
    raw = config.get("granularity")
    locator = config.get("locator") or {}
    locator_kind = locator.get("kind") if isinstance(locator, dict) else None

    if raw is None:
        if locator_kind in {"class", "function"}:
            return "target_span"
        raise ValueError("Config requires granularity or a class/function locator")

    if raw == "module_files":
        return "module_files"
    if raw in TARGET_SPAN_GRANULARITIES:
        return "target_span"
    raise ValueError(f"Unsupported granularity: {raw!r}")


def validate_relative_paths(values: Any, field_name: str) -> list[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{field_name} must be a non-empty list")

    paths: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} entries must be non-empty strings")
        value = item.replace("\\", "/")
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value.startswith("./"):
            raise ValueError(f"Unsafe relative path in {field_name}: {item!r}")
        normalized = path.as_posix()
        if normalized in seen:
            raise ValueError(f"Duplicate path in {field_name}: {normalized}")
        seen.add(normalized)
        paths.append(normalized)
    return paths


def source_files_for(config: dict[str, Any]) -> list[str]:
    granularity = normalized_granularity(config)
    if granularity == "module_files":
        return validate_relative_paths(config.get("source_files"), "source_files")

    target_source_file = config.get("target_source_file")
    if isinstance(target_source_file, str) and target_source_file:
        return validate_relative_paths([target_source_file], "target_source_file")

    source_files = validate_relative_paths(config.get("source_files"), "source_files")
    if len(source_files) != 1:
        raise ValueError("target_span requires exactly one target source file")
    return source_files


def observation_files_for(config: dict[str, Any]) -> list[str]:
    configured = config.get("observation_files")
    if configured is None:
        return source_files_for(config)
    return validate_relative_paths(configured, "observation_files")


def target_source_file_for(config: dict[str, Any]) -> str:
    if normalized_granularity(config) != "target_span":
        raise ValueError("module_files does not have a single target_source_file")
    return source_files_for(config)[0]


def validate_config(
    config: dict[str, Any],
    *,
    project_root: Path | None = None,
    check_files: bool = False,
) -> dict[str, Any]:
    required_top_level = {
        "target_id",
        "experiment_id",
        "run_id",
        "repository_id",
        "repository_path",
        "repository_commit",
        "target_name",
        "model",
        "evaluation",
    }
    missing = sorted(required_top_level - set(config))
    if missing:
        raise ValueError(f"Missing required config fields: {missing}")

    granularity = normalized_granularity(config)
    source_files = source_files_for(config)
    observation_files = observation_files_for(config)
    missing_observations = sorted(set(source_files) - set(observation_files))
    if missing_observations:
        raise ValueError(
            "Every replacement source file must be included in observation_files: "
            f"{missing_observations}"
        )

    locator = config.get("locator") or {}
    if not isinstance(locator, dict):
        raise ValueError("locator must be an object")
    if granularity == "target_span":
        kind = locator.get("kind")
        symbol = locator.get("symbol")
        if kind not in {"class", "function"}:
            raise ValueError("target_span locator.kind must be 'class' or 'function'")
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("target_span locator.symbol is required")
        if kind == "function":
            signature_regex = locator.get("signature_regex")
            if not isinstance(signature_regex, str) or not signature_regex.strip():
                raise ValueError("Function locator requires signature_regex")
            re.compile(signature_regex, re.MULTILINE)
    elif locator:
        raise ValueError("module_files locator must be empty or omitted")

    model = config["model"]
    if not isinstance(model, dict):
        raise ValueError("model must be an object")
    if model.get("generations", 1) != 1:
        raise ValueError("model.generations must be 1")
    if model.get("retry", False) is not False:
        raise ValueError("model.retry must be false")
    if model.get("automatic_repair", False) is not False:
        raise ValueError("model.automatic_repair must be false")

    evaluation = config["evaluation"]
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation must be an object")
    missing_evaluation = sorted(REQUIRED_EVALUATION_KEYS - set(evaluation))
    if missing_evaluation:
        raise ValueError(f"Missing evaluation fields: {missing_evaluation}")
    if evaluation["full_test_kind"] not in {"gtest", "ctest"}:
        raise ValueError("evaluation.full_test_kind must be 'gtest' or 'ctest'")

    knowledge = config.get("design_knowledge") or {}
    if not isinstance(knowledge, dict):
        raise ValueError("design_knowledge must be an object")
    if knowledge.get("enabled", False):
        context_file = knowledge.get("context_file")
        if not isinstance(context_file, str) or not context_file:
            raise ValueError("Enabled design_knowledge requires context_file")
        instruction_mode = knowledge.get("instruction_mode", "reference")
        if instruction_mode not in {"reference", "required_additional_artifacts"}:
            raise ValueError(
                "design_knowledge.instruction_mode must be "
                "'reference' or 'required_additional_artifacts'"
            )

    if check_files:
        if project_root is None:
            raise ValueError("project_root is required when check_files=True")
        repository = project_root / str(config["repository_path"])
        if not repository.is_dir():
            raise FileNotFoundError(repository)
        for relative in observation_files:
            path = repository / relative
            if not path.is_file():
                raise FileNotFoundError(path)
        if knowledge.get("enabled", False):
            knowledge_path = project_root / str(knowledge["context_file"])
            if not knowledge_path.is_file():
                raise FileNotFoundError(knowledge_path)

    return {
        "target_id": str(config["target_id"]),
        "run_id": str(config["run_id"]),
        "granularity": granularity,
        "source_files": source_files,
        "observation_files": observation_files,
        "enabled": bool(config.get("enabled", False)),
        "retry": False,
        "automatic_repair": False,
    }


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


def expand_class_template_prefix(text: str, class_start: int) -> int:
    """Include contiguous template declarations immediately before a class."""
    expanded_start = class_start

    while True:
        cursor = expanded_start
        while cursor > 0 and text[cursor - 1].isspace():
            cursor -= 1

        if cursor == 0 or text[cursor - 1] != ">":
            break

        close_angle = cursor - 1
        depth = 0
        open_angle = -1
        for index in range(close_angle, -1, -1):
            char = text[index]
            if char == ">":
                depth += 1
            elif char == "<":
                depth -= 1
                if depth == 0:
                    open_angle = index
                    break

        if open_angle < 0:
            break

        match = re.search(r"\btemplate\s*$", text[:open_angle])
        if match is None:
            break
        if text[match.end():open_angle].strip():
            break

        line_start = text.rfind("\n", 0, match.start()) + 1
        if text[line_start:match.start()].strip():
            break

        expanded_start = line_start

    return expanded_start


def locate_target_span(text: str, locator: dict[str, Any]) -> tuple[int, int]:
    kind = locator.get("kind")
    symbol = locator.get("symbol")
    if kind == "class":
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("Class locator requires symbol")
        start, end = locate_class_span(text, symbol)
        return expand_class_template_prefix(text, start), end
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


def build_module_scaffold(repository: Path, source_files: list[str]) -> str:
    parts: list[str] = []
    for relative in source_files:
        path = repository / relative
        if path.suffix.lower() not in HEADER_SUFFIXES:
            continue
        scaffold = strip_inline_callable_bodies(read_text(path))
        parts.append(f"===== FILE: {relative} =====\n{scaffold.rstrip()}\n")
    return "\n".join(parts)


def build_dependency_context(repository: Path, observation_files: list[str]) -> str:
    includes: list[str] = []
    for relative in observation_files:
        includes.extend(extract_includes(read_text(repository / relative)))
    return "\n".join(dict.fromkeys(includes)) + "\n"


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
                        "content": {"type": "string", "minLength": 1},
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

    if not isinstance(value, dict) or set(value) != {"files"}:
        raise RuntimeError("Module output must contain only the files array")
    items = value["files"]
    if not isinstance(items, list):
        raise RuntimeError("Module output files must be an array")
    if len(items) != len(expected_paths):
        raise RuntimeError(
            "Generated file count mismatch. "
            f"expected={len(expected_paths)}, actual={len(items)}"
        )

    expected = set(expected_paths)
    files: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {"path", "content"}:
            raise RuntimeError("Each files item must contain only path and content")
        path = item["path"]
        content = item["content"]
        if not isinstance(path, str) or not isinstance(content, str):
            raise RuntimeError("Each generated file requires string path and content")
        if path not in expected:
            raise RuntimeError(f"Unexpected generated file path: {path!r}")
        if path in files:
            raise RuntimeError(f"Duplicate generated file path: {path!r}")
        if not content.strip():
            raise RuntimeError(f"Generated file content is empty: {path!r}")
        files[path] = content

    missing = sorted(expected - set(files))
    if missing:
        raise RuntimeError(f"Generated files are missing expected paths: {missing}")
    return {path: files[path] for path in expected_paths}


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

    context_file = str(knowledge["context_file"])
    source_path = project_root / context_file
    text = read_text(source_path).strip()
    if not text:
        raise ValueError("Design knowledge context is empty")

    retrieval_dir = experiment_root / "retrieval"
    write_text(retrieval_dir / "context.txt", text + "\n")
    instruction_mode = knowledge.get("instruction_mode", "reference")

    write_json(
        retrieval_dir / "retrieval_manifest.json",
        {
            "schema_version": "1.1",
            "condition": config.get("condition"),
            "knowledge_type": "general_detailed_design",
            "retrieval_mode": "fixed_query_fixed_knowledge",
            "instruction_mode": instruction_mode,
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
    summary = validate_config(config, project_root=project_root, check_files=True)
    repository = project_root / str(config["repository_path"])
    ensure_clean(repository)

    head = git_output(repository, "rev-parse", "HEAD")
    if head != config["repository_commit"]:
        raise RuntimeError(f"Repository commit mismatch: {head}")

    granularity = str(summary["granularity"])
    source_files = list(summary["source_files"])
    observation_files = list(summary["observation_files"])
    input_dir = experiment_root / "input"
    backup_dir = experiment_root / "backup"

    for relative in observation_files:
        source = repository / relative
        backup = backup_dir / "files" / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, backup)

    design_input = build_observation_bundle(repository, observation_files)
    dependency_context = build_dependency_context(repository, observation_files)

    metadata: dict[str, Any] = {
        "schema_version": "2.1",
        "target_id": config["target_id"],
        "target_name": config["target_name"],
        "condition": config.get("condition"),
        "repository_id": config["repository_id"],
        "repository_commit": head,
        "granularity": granularity,
        "observation_scope": "full_files",
        "observation_files": observation_files,
        "source_files": source_files,
        "observation_file_hashes": {
            relative: sha256_file(repository / relative)
            for relative in observation_files
        },
        "source_file_hashes": {
            relative: sha256_file(repository / relative)
            for relative in source_files
        },
        "prepared_at_utc": utc_now(),
    }

    if granularity == "module_files":
        scaffold = build_module_scaffold(repository, source_files)
        metadata.update(
            {
                "replacement_scope": "module_files",
                "locator": {},
            }
        )
    else:
        target_source_file = target_source_file_for(config)
        locator = dict(config["locator"])
        target_source_text = read_text(repository / target_source_file)
        start, end = locate_target_span(target_source_text, locator)
        original_target = target_source_text[start:end]
        scaffold = make_target_scaffold(original_target, locator)
        write_text(backup_dir / "original_target.cpp", original_target + "\n")
        metadata.update(
            {
                "target_source_file": target_source_file,
                "replacement_scope": "target_span",
                "locator": locator,
                "target_start_offset": start,
                "target_end_offset": end,
                "target_sha256": sha256_bytes(original_target.encode("utf-8")),
            }
        )

    write_text(input_dir / "design_input.txt", design_input)
    write_text(input_dir / "fixed_scaffold.txt", scaffold.rstrip() + "\n")
    write_text(input_dir / "dependency_context.txt", dependency_context)
    write_json(input_dir / "source_metadata.json", metadata)
    write_json(experiment_root / "configs" / "target_config.json", config)
    return metadata


def knowledge_prompt_section(
    config: dict[str, Any],
    knowledge_text: str,
) -> str:
    if not knowledge_text:
        return ""
    knowledge = config.get("design_knowledge") or {}
    instruction_mode = knowledge.get("instruction_mode", "reference")
    if instruction_mode == "required_additional_artifacts":
        intro = """# RAGによる追加成果物要件
以下の検索コンテキストは単なる参考情報ではありません。
元の「記載項目」に追加して満たす必須の出力要件です。
検索コンテキストで指定された成果物を、独立した見出しとして出力してください。
対象に該当しない成果物も省略せず、「該当なし」とコード上の判断根拠を記載してください。
図が要求される場合は、指定されたMermaid形式で出力してください。
ただし、元コードで確認できない呼び出し元、利用目的、状態、例外、依存関係を推測で作らないでください。"""
    else:
        intro = """# 検索コンテキスト
以下は、対象コードに依存しない汎用的な詳細設計知識です。
元コードに存在する事実を優先し、該当しない項目を推測で補完しないでください。"""
    return f"""
{intro}

----- BEGIN RETRIEVED CONTEXT -----
{knowledge_text}
----- END RETRIEVED CONTEXT -----
"""


def generate_design(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> dict[str, Any]:
    design_input = read_text(experiment_root / "input" / "design_input.txt")
    knowledge_text = resolve_design_knowledge(config, project_root, experiment_root)
    knowledge_section = knowledge_prompt_section(config, knowledge_text)
    granularity = normalized_granularity(config)

    system = (
        "あなたはC++ソフトウェアのリバースエンジニアリング担当者です。"
        "与えられたコードだけを根拠として、再実装に必要な設計文書を日本語で作成してください。"
        "推測で存在しない機能を追加しないでください。"
    )

    if granularity == "module_files":
        source_files = source_files_for(config)
        target_description = f"""- target: {config['target_name']}
- granularity: module_files
- source_files: {json.dumps(source_files, ensure_ascii=False)}"""
        scope_description = """元コードとして示したsource_files全体を1つのモジュールとして扱ってください。
設計文書は、各ファイルの責務、ファイル間の関係、公開インターフェース、実装上の処理を含めて作成してください。
再実装ではsource_filesにある各ファイル全体を生成するため、ファイルごとの構造と責務を区別してください。"""
    else:
        locator = dict(config["locator"])
        target_description = f"""- target: {config['target_name']}
- granularity: target_span
- target_kind: {locator['kind']}
- target_symbol: {locator['symbol']}"""
        scope_description = """元コード全体は対象部分を理解するための文脈として参照してください。
設計文書はtarget_symbolで指定した対象部分だけについて作成してください。
対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。"""

    prompt = f"""# 対象
{target_description}

# 対象範囲
{scope_description}

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


def materialize_regeneration_output(
    config: dict[str, Any],
    experiment_root: Path,
    text: str,
) -> dict[str, Any]:
    granularity = normalized_granularity(config)
    allowed_languages = {"", "json"} if granularity == "module_files" else {
        "",
        "cpp",
        "c++",
        "cc",
        "cxx",
    }
    normalized, normalization = normalize_outer_markdown_fence(
        text,
        allowed_languages,
    )
    raw_dir = experiment_root / "raw_output"
    write_json(raw_dir / "code_regeneration_normalization.json", normalization)
    generated_dir = experiment_root / "generated"

    if granularity == "module_files":
        expected_paths = source_files_for(config)
        files = parse_module_output(normalized, expected_paths)
        manifest_files: list[dict[str, Any]] = []
        for relative in expected_paths:
            content = files[relative]
            write_text(generated_dir / "files" / relative, content)
            manifest_files.append(
                {
                    "path": relative,
                    "sha256": sha256_bytes(content.encode("utf-8")),
                    "character_count": len(content),
                }
            )
        write_json(
            generated_dir / "generated_files_manifest.json",
            {
                "schema_version": "1.0",
                "files": manifest_files,
            },
        )
    else:
        write_text(generated_dir / "regenerated_target.cpp", normalized)
    return normalization


def regenerate(config: dict[str, Any], experiment_root: Path) -> dict[str, Any]:
    design = read_text(experiment_root / "generated" / "design_document.md")
    scaffold = read_text(experiment_root / "input" / "fixed_scaffold.txt")
    dependency = read_text(experiment_root / "input" / "dependency_context.txt")
    granularity = normalized_granularity(config)
    output_schema: dict[str, Any] | None = None

    if granularity == "module_files":
        expected_paths = source_files_for(config)
        output_schema = module_output_schema(expected_paths)
        output_instruction = (
            "出力は指定されたJSON Schemaに一致するJSONのみとし、"
            "Markdownコードフェンスを使用しないでください。"
            "source_filesにある各ファイルを完全な内容として1回ずつ返してください。"
            "pathはsource_filesの文字列をそのまま使用し、追加・省略・重複させないでください。"
            "C++コード中の改行や引用符はJSON文字列として正しくエスケープしてください。"
            "固定インターフェース・スキャフォールドに示された宣言とファイル構成を変更しないでください。"
        )
        target_description = f"""- target: {config['target_name']}
- granularity: module_files
- source_files: {json.dumps(expected_paths, ensure_ascii=False)}"""
    else:
        locator = dict(config["locator"])
        kind = locator["kind"]
        if kind == "class":
            output_instruction = (
                "固定インターフェース・スキャフォールドの宣言内容を変更せず、"
                "対象クラスまたは構造体の定義全体だけをC++コードとして返してください。"
                "template宣言の個数と内容、class/struct宣言、継承、可視性、"
                "メンバ名と型、すべての関数・演算子の戻り値、引数、修飾を保持してください。"
                "一般的なC++慣習に合わせる目的でも、特殊または非標準的に見えるシグネチャを変更しないでください。"
                "スキャフォールドに存在しない宣言を追加せず、関数本体だけを実装してください。"
                "Markdownコードフェンス、説明文、JSONは出力しないでください。"
            )
        elif kind == "function":
            output_instruction = (
                "固定インターフェース・スキャフォールドに示された対象関数の定義全体だけをC++コードとして返してください。"
                "戻り値、関数名、引数、既定値、修飾を含む関数シグネチャを変更しないでください。"
                "Markdownコードフェンス、説明文、JSONは出力しないでください。"
            )
        else:
            raise ValueError(f"Unsupported locator kind: {kind!r}")
        target_description = f"""- target: {config['target_name']}
- granularity: target_span
- target_kind: {kind}
- target_symbol: {locator['symbol']}
- source_file: {target_source_file_for(config)}"""

    system = (
        "あなたはC++実装担当者です。設計文書と固定インターフェースだけを根拠に実装してください。"
        "元実装は与えられていません。公開インターフェースとファイル構成を変更しないでください。"
    )
    schema_section = (
        json.dumps(output_schema, ensure_ascii=False, indent=2)
        if output_schema is not None
        else "N/A"
    )
    prompt = f"""# 対象
{target_description}

# 出力規則
{output_instruction}

# JSON Schema
{schema_section}

# 設計文書
{design}

# 固定インターフェース・スキャフォールド
{scaffold}

# 依存情報
{dependency}
"""

    payload: dict[str, Any] = {
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
    materialize_regeneration_output(config, experiment_root, text)
    return metadata


def replace_generated_sources(
    config: dict[str, Any],
    repository: Path,
    experiment_root: Path,
) -> None:
    granularity = normalized_granularity(config)
    if granularity == "module_files":
        for relative in source_files_for(config):
            generated = experiment_root / "generated" / "files" / relative
            if not generated.is_file():
                raise FileNotFoundError(generated)
            (repository / relative).write_bytes(generated.read_bytes())
        return

    target_source_file = target_source_file_for(config)
    source_path = repository / target_source_file
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


def evaluate(
    config: dict[str, Any],
    project_root: Path,
    experiment_root: Path,
) -> dict[str, Any]:
    repository = project_root / str(config["repository_path"])
    replacement_files = source_files_for(config)
    originals = {
        relative: (repository / relative).read_bytes()
        for relative in replacement_files
    }
    original_hashes = {
        relative: sha256_bytes(data)
        for relative, data in originals.items()
    }

    records: dict[str, Any] = {}
    error: str | None = None
    evaluation_dir = experiment_root / "evaluation"
    log_root = project_root / "logs" / "roundtrip_v2" / str(config["run_id"])

    try:
        replace_generated_sources(config, repository, experiment_root)
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
                        records[remaining] = {
                            "stage": remaining,
                            "passed": False,
                            "skipped": True,
                        }
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        for relative, data in originals.items():
            (repository / relative).write_bytes(data)

    restoration_files: list[dict[str, Any]] = []
    all_restored = True
    for relative in replacement_files:
        restored_hash = sha256_file(repository / relative)
        restored = restored_hash == original_hashes[relative]
        all_restored = all_restored and restored
        restoration_files.append(
            {
                "path": relative,
                "original_hash": original_hashes[relative],
                "restored_hash": restored_hash,
                "restored": restored,
            }
        )

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
        and all_restored
        and repository_clean
    )

    restoration: dict[str, Any] = {
        "restored": all_restored,
        "files": restoration_files,
        "repository_clean": repository_clean,
        "tracked_status": tracked_status,
    }
    if len(restoration_files) == 1:
        restoration["original_hash"] = restoration_files[0]["original_hash"]
        restoration["restored_hash"] = restoration_files[0]["restored_hash"]

    result = {
        "schema_version": "2.1",
        "target_id": config["target_id"],
        "run_id": config["run_id"],
        "condition": config.get("condition"),
        "granularity": normalized_granularity(config),
        "completed_at_utc": utc_now(),
        "overall_pass": overall,
        "error": error,
        "stages": records,
        "restoration": restoration,
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
            "schema_version": "2.1",
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
        description=(
            "Run one full-source observation round-trip experiment for a "
            "target span or complete module files."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--validate-config-only",
        action="store_true",
        help="Validate config and referenced files without calling LLM, Docker, build, or tests.",
    )
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    config_path = (
        args.config if args.config.is_absolute() else project_root / args.config
    )
    config = load_json(config_path)

    if args.validate_config_only:
        summary = validate_config(config, project_root=project_root, check_files=True)
        print(json.dumps({"valid": True, **summary}, ensure_ascii=False, indent=2))
        return 0

    validate_config(config, project_root=project_root, check_files=True)
    if not config.get("enabled", False):
        raise RuntimeError("Target config is disabled")

    experiment_root = resolve_experiment_root(config, project_root)
    if experiment_root.exists():
        raise FileExistsError(
            f"Experiment directory already exists: {experiment_root}. "
            "Use a new experiment_id and run_id; do not overwrite a run."
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
