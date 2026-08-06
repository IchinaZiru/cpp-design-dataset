from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


FORMAL_CONFIG_DIR = Path("configs/rag/targets")
FORMAL_BATCH_REPORT_ROOT = Path("reports/rag/formal/batch")
FORMAL_RUN_MANIFEST = Path("manifests/rag/formal_runs.csv")
EXPECTED_SCHEMA = "rag-formal-target-config-v1"
EXPECTED_CONDITION = "rag-design-context-v1"
EXPECTED_CONTEXT_STATUS = "generated_and_audited"
LEGACY_DESIGN_PROMPT = Path(
    "experiments/ini-writer-minimal/prompts/design_generation_prompt.md"
)


class FormalRunPolicyError(RuntimeError):
    """Raised when a frozen formal RAG execution invariant is violated."""


@dataclass(frozen=True)
class ValidatedFormalTarget:
    config_path: Path
    config: dict[str, Any]
    context_path: Path
    context_sha256: str
    retrieval_manifest_path: Path
    experiment_root: Path

    @property
    def target_id(self) -> str:
        return str(self.config["target_id"])

    @property
    def target_kind(self) -> str:
        return str(self.config.get("target_kind", "standard"))


@dataclass(frozen=True)
class RequestBundle:
    payload: dict[str, Any]
    audit: dict[str, Any]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise FormalRunPolicyError(f"JSON root must be an object: {path}")
    return value


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def resolve_project_path(
    project_root: Path,
    value: str | Path,
    *,
    field: str,
) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise FormalRunPolicyError(f"{field} must be repository-relative")
    root = project_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise FormalRunPolicyError(f"{field} escapes project root: {value}")
    return resolved


def _require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise FormalRunPolicyError(
            f"{label} differs: expected={expected!r}, actual={actual!r}"
        )


def _require_false(label: str, value: Any) -> None:
    if value is not False:
        raise FormalRunPolicyError(f"{label} must be false")


def _require_one(label: str, value: Any) -> None:
    if value != 1:
        raise FormalRunPolicyError(f"{label} must be 1")


def _generation_options(config: Mapping[str, Any]) -> dict[str, Any]:
    generation = config.get("generation")
    if isinstance(generation, Mapping):
        options = generation.get("options")
        if not isinstance(options, Mapping):
            raise FormalRunPolicyError("legacy generation.options is missing")
        return dict(options)

    model = config.get("model")
    if not isinstance(model, Mapping):
        raise FormalRunPolicyError("model configuration is missing")
    keys = (
        "temperature",
        "seed",
        "num_ctx",
        "num_predict",
        "top_k",
        "top_p",
        "repeat_penalty",
    )
    missing = [key for key in keys if key not in model]
    if missing:
        raise FormalRunPolicyError(
            f"model generation options are missing: {missing}"
        )
    return {key: model[key] for key in keys}


def _stream_value(config: Mapping[str, Any]) -> bool:
    generation = config.get("generation")
    if isinstance(generation, Mapping):
        return bool(generation.get("stream", False))
    model = config.get("model")
    if not isinstance(model, Mapping):
        raise FormalRunPolicyError("model configuration is missing")
    return bool(model.get("stream", False))


def _validate_one_shot_policy(config: Mapping[str, Any]) -> None:
    policy = config.get("one_shot_generation_policy")
    if not isinstance(policy, Mapping):
        raise FormalRunPolicyError("one_shot_generation_policy is missing")
    _require_one("design_generation_count", policy.get("design_generation_count"))
    _require_one("code_generation_count", policy.get("code_generation_count"))
    _require_false("retry", policy.get("retry"))
    _require_false("automatic_repair", policy.get("automatic_repair"))
    _require_false("manual_patch", policy.get("manual_patch"))
    _require_false("overwrite", policy.get("overwrite"))

    model = config.get("model")
    if isinstance(model, Mapping):
        if "retry" in model:
            _require_false("model.retry", model.get("retry"))
        if "automatic_repair" in model:
            _require_false(
                "model.automatic_repair",
                model.get("automatic_repair"),
            )
        if "generations" in model:
            _require_one("model.generations", model.get("generations"))

    conditions = config.get("conditions")
    if isinstance(conditions, Mapping):
        _require_false(
            "conditions.retry_on_failure",
            conditions.get("retry_on_failure"),
        )
        _require_false(
            "conditions.automatic_repair",
            conditions.get("automatic_repair"),
        )
        _require_one(
            "conditions.generations_per_stage",
            conditions.get("generations_per_stage"),
        )


def _validate_input_isolation(config: Mapping[str, Any]) -> None:
    isolation = config.get("input_isolation")
    if not isinstance(isolation, Mapping):
        raise FormalRunPolicyError("input_isolation is missing")

    expected_design = {
        "frozen design instruction",
        "frozen target source",
        "frozen context.txt",
    }
    expected_code = {
        "single one-shot generated design document",
        "fixed scaffold equivalent to the corresponding non-RAG target",
    }
    required_forbidden = {
        "original target source body",
        "retrieved context",
        "selected chunks",
        "candidates",
        "query artifact",
        "repository source",
        "design-generation request or prompt",
        "design audit findings",
        "previous generated output",
    }

    design_allowed = set(isolation.get("design_generation_allowed_inputs", []))
    code_allowed = set(isolation.get("code_regeneration_allowed_inputs", []))
    code_forbidden = set(isolation.get("code_regeneration_forbidden_inputs", []))

    _require_equal(
        "design_generation_allowed_inputs",
        design_allowed,
        expected_design,
    )
    _require_equal(
        "code_regeneration_allowed_inputs",
        code_allowed,
        expected_code,
    )
    if not required_forbidden.issubset(code_forbidden):
        missing = sorted(required_forbidden - code_forbidden)
        raise FormalRunPolicyError(
            f"code_regeneration_forbidden_inputs is missing: {missing}"
        )


def validate_formal_target(
    config_path: Path,
    project_root: Path,
    *,
    require_enabled: bool | None = None,
    require_output_absent: bool = True,
) -> ValidatedFormalTarget:
    root = project_root.resolve()
    path = config_path if config_path.is_absolute() else root / config_path
    path = path.resolve()
    if not path.is_file():
        raise FormalRunPolicyError(f"target config is missing: {path}")

    config = read_json(path)
    target_id = str(config.get("target_id", ""))
    if not target_id:
        raise FormalRunPolicyError("target_id is missing")

    _require_equal(
        "artifact_schema_version",
        config.get("artifact_schema_version"),
        EXPECTED_SCHEMA,
    )
    _require_equal(
        "condition_id",
        config.get("condition_id"),
        EXPECTED_CONDITION,
    )
    _require_equal(
        "context_status",
        config.get("context_status"),
        EXPECTED_CONTEXT_STATUS,
    )

    if require_enabled is not None:
        _require_equal("enabled", config.get("enabled"), require_enabled)

    _validate_one_shot_policy(config)
    _validate_input_isolation(config)

    run_id = str(config.get("run_id", ""))
    experiment_id = str(config.get("experiment_id", ""))
    formal_run_id = str(config.get("formal_run_id", run_id))
    if not run_id or not experiment_id:
        raise FormalRunPolicyError("run_id or experiment_id is missing")
    _require_equal("formal_run_id", formal_run_id, run_id)

    output_value = config.get("formal_output_directory")
    _require_equal(
        "formal_output_directory/output_directory",
        output_value,
        config.get("output_directory"),
    )
    output_relative = Path(str(output_value))
    if output_relative.parts[:2] != ("experiments", "rag"):
        raise FormalRunPolicyError(
            "formal output must be under experiments/rag"
        )
    experiment_root = resolve_project_path(
        root,
        output_relative,
        field="formal_output_directory",
    )
    if require_output_absent and experiment_root.exists():
        raise FormalRunPolicyError(
            f"formal output already exists: {experiment_root}"
        )

    context_path = resolve_project_path(
        root,
        str(config.get("context_path", "")),
        field="context_path",
    )
    if not context_path.is_file():
        raise FormalRunPolicyError(f"context is missing: {context_path}")
    context_sha = sha256_file(context_path)
    _require_equal("context_sha256", context_sha, config.get("context_sha256"))

    retrieval_manifest_path = context_path.parent / "retrieval_manifest.json"
    if not retrieval_manifest_path.is_file():
        raise FormalRunPolicyError(
            f"retrieval manifest is missing: {retrieval_manifest_path}"
        )
    retrieval_manifest = read_json(retrieval_manifest_path)
    _require_equal(
        "retrieval target_id",
        retrieval_manifest.get("target_id"),
        target_id,
    )
    _require_equal("retrieval status", retrieval_manifest.get("status"), "pass")
    _require_equal(
        "retrieval deterministic",
        retrieval_manifest.get("deterministic"),
        True,
    )
    _require_equal(
        "retrieval context_sha256",
        retrieval_manifest.get("context_sha256"),
        context_sha,
    )
    _require_equal(
        "retrieval llm_calls",
        retrieval_manifest.get("llm_calls"),
        {"code_regeneration": 0, "design_generation": 0},
    )

    return ValidatedFormalTarget(
        config_path=path,
        config=config,
        context_path=context_path,
        context_sha256=context_sha,
        retrieval_manifest_path=retrieval_manifest_path,
        experiment_root=experiment_root,
    )


def _model_name(config: Mapping[str, Any]) -> str:
    model = config.get("model")
    if not isinstance(model, Mapping) or not isinstance(model.get("name"), str):
        raise FormalRunPolicyError("model.name is missing")
    return str(model["name"])


def _module_output_schema(expected_paths: list[str]) -> dict[str, Any]:
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


def _standard_design_prompt(
    config: Mapping[str, Any],
    context: str,
    design_input: str,
) -> str:
    return f"""# 対象
- target: {config['target_name']}
- granularity: {config['granularity']}

# 記載項目
責務、公開インターフェース、入力、出力、状態、処理手順、例外・失敗条件、依存関係、重要な不変条件を記載してください。

# 検索コンテキスト
以下は同一リポジトリの固定commitから取得した補助情報です。情報が衝突する場合は対象ソースを優先し、設計文書に検索処理のメタ表現を書かないでください。

----- BEGIN RETRIEVED CONTEXT -----
{context.rstrip()}
----- END RETRIEVED CONTEXT -----

# 元コード
{design_input}
"""


def _legacy_design_prompt(
    target: ValidatedFormalTarget,
    project_root: Path,
    context: str,
    design_input: str,
) -> str:
    template_path = resolve_project_path(
        project_root,
        LEGACY_DESIGN_PROMPT,
        field="legacy design prompt",
    )
    if not template_path.is_file():
        raise FormalRunPolicyError(
            f"legacy design prompt is missing: {template_path}"
        )
    template = read_text(template_path)
    marker = "# 対象ソースコード\n\n{{DESIGN_INPUT}}"
    if template.count(marker) != 1:
        raise FormalRunPolicyError(
            "legacy design prompt insertion marker differs"
        )
    replacement = f"""# 検索コンテキスト

以下は同一リポジトリの固定commitから取得した補助情報である．情報が衝突する場合は対象ソースコードを優先し，設計文書に検索処理のメタ表現を書かないこと．

----- BEGIN RETRIEVED CONTEXT -----
{context.rstrip()}
----- END RETRIEVED CONTEXT -----

# 対象ソースコード

{design_input}"""
    return template.replace(marker, replacement)


def build_design_request(
    target: ValidatedFormalTarget,
    project_root: Path,
    design_input: str,
) -> RequestBundle:
    current_sha = sha256_file(target.context_path)
    context = read_text(target.context_path)
    _require_equal(
        "context SHA immediately before design request",
        current_sha,
        target.context_sha256,
    )

    if target.target_kind == "legacy_function":
        system = (
            "Follow the task and output constraints exactly. "
            "Do not add unsupported information."
        )
        prompt = _legacy_design_prompt(
            target,
            project_root,
            context,
            design_input,
        )
    else:
        system = (
            "あなたはC++ソフトウェアのリバースエンジニアリング担当者です。"
            "与えられたコードだけを根拠として、再実装に必要な設計文書を日本語で作成してください。"
            "推測で存在しない機能を追加しないでください。"
        )
        prompt = _standard_design_prompt(
            target.config,
            context,
            design_input,
        )

    payload = {
        "model": _model_name(target.config),
        "system": system,
        "prompt": prompt,
        "stream": _stream_value(target.config),
        "options": _generation_options(target.config),
    }
    audit = {
        "schema_version": "rag-formal-design-request-audit-v1",
        "target_id": target.target_id,
        "allowed_inputs_used": [
            "frozen design instruction",
            "frozen target source",
            "frozen context.txt",
        ],
        "context_path": target.context_path.relative_to(
            project_root.resolve()
        ).as_posix(),
        "context_sha256": current_sha,
        "design_input_sha256": sha256_text(design_input),
        "prompt_sha256": sha256_text(prompt),
        "retrieval_section_precedes_target_source": (
            prompt.index("BEGIN RETRIEVED CONTEXT")
            < prompt.index(
                "# 対象ソースコード"
                if target.target_kind == "legacy_function"
                else "# 元コード"
            )
        ),
        "llm_call_count_before_request": 0,
    }
    if not audit["retrieval_section_precedes_target_source"]:
        raise FormalRunPolicyError(
            "retrieval section does not precede target source"
        )
    return RequestBundle(payload=payload, audit=audit)


def _standard_code_prompt(
    config: Mapping[str, Any],
    design_document: str,
    fixed_scaffold: str,
) -> tuple[str, dict[str, Any] | None]:
    granularity = str(config["granularity"])
    output_schema: dict[str, Any] | None = None
    if granularity == "module_files":
        expected_paths = [str(item) for item in config["source_files"]]
        output_schema = _module_output_schema(expected_paths)
        output_instruction = (
            "出力は指定されたJSON Schemaに一致するJSONのみとし、"
            "Markdownコードフェンスを使用しないでください。"
            "source_filesにある各ファイルを完全な内容として1回ずつ返してください。"
            "C++コード中の改行や引用符はJSON文字列として正しくエスケープしてください。"
        )
    elif granularity == "class_span":
        output_instruction = (
            "対象クラス定義全体だけをC++コードとして返してください。"
            "Markdownコードフェンス、説明文、JSONは出力しないでください。"
        )
    else:
        raise FormalRunPolicyError(
            f"unsupported standard granularity: {granularity}"
        )

    prompt = f"""# 対象
- target: {config['target_name']}
- granularity: {granularity}
- source_files: {json.dumps(config['source_files'], ensure_ascii=False)}

# 出力規則
{output_instruction}

# JSON Schema
{json.dumps(output_schema, ensure_ascii=False, indent=2) if output_schema else "N/A"}

# 設計文書
{design_document}

# 固定インターフェース・スキャフォールド
{fixed_scaffold}
"""
    return prompt, output_schema


def _legacy_code_prompt(
    design_document: str,
    fixed_scaffold: str,
) -> str:
    return f"""# 役割

あなたは，設計文書に基づいてC++コードを再生成するソフトウェア開発者である．

# タスク

設計文書と固定スキャフォールドだけに基づき，`INIWriter::write`の外側の波括弧の内側に入る関数本体だけを生成せよ．

# 制約

- 元の`INIWriter::write`実装は提供されていないものとして扱うこと．
- 設計文書に記載された観測可能な振る舞いを保持すること．
- 固定スキャフォールドのシグネチャ，クラス宣言，名前空間，includeを変更しないこと．
- 新しい補助関数，クラス，include，外部依存を追加しないこと．
- 出力は関数本体の文だけとすること．
- 関数シグネチャを出力しないこと．
- 外側の波括弧を出力しないこと．
- Markdownのコードフェンス，説明文，前置き，後書きを出力しないこと．
- 質問や再試行を行わず，1回の生成で回答すること．

# 設計文書

{design_document}

# 固定スキャフォールド

{fixed_scaffold}
"""


def build_code_request(
    target: ValidatedFormalTarget,
    design_document: str,
    fixed_scaffold: str,
) -> RequestBundle:
    if target.target_kind == "legacy_function":
        system = (
            "Follow the task and output constraints exactly. "
            "Return only the requested C++ body."
        )
        prompt = _legacy_code_prompt(
            design_document,
            fixed_scaffold,
        )
        output_schema = None
    else:
        system = (
            "あなたはC++実装担当者です。設計文書と固定インターフェースだけを根拠に実装してください。"
            "元実装は与えられていません。公開インターフェースとファイル構成を変更しないでください。"
        )
        prompt, output_schema = _standard_code_prompt(
            target.config,
            design_document,
            fixed_scaffold,
        )

    payload: dict[str, Any] = {
        "model": _model_name(target.config),
        "system": system,
        "prompt": prompt,
        "stream": _stream_value(target.config),
        "options": _generation_options(target.config),
    }
    if output_schema is not None:
        payload["format"] = output_schema

    audit = {
        "schema_version": "rag-formal-code-request-audit-v1",
        "target_id": target.target_id,
        "allowed_inputs_used": [
            "single one-shot generated design document",
            "fixed scaffold equivalent to the corresponding non-RAG target",
        ],
        "forbidden_inputs_directly_loaded": [],
        "design_document_sha256": sha256_text(design_document),
        "fixed_scaffold_sha256": sha256_text(fixed_scaffold),
        "prompt_sha256": sha256_text(prompt),
        "retrieved_context_directly_injected": False,
        "target_source_directly_injected": False,
        "dependency_context_loaded": False,
        "llm_call_count_before_request": 0,
    }
    return RequestBundle(payload=payload, audit=audit)


def build_formal_batch_plan(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    config_root = root / FORMAL_CONFIG_DIR
    config_paths = sorted(config_root.glob("*.json"))
    if len(config_paths) != 17:
        raise FormalRunPolicyError(
            f"formal target count must be 17, got {len(config_paths)}"
        )

    targets: list[dict[str, Any]] = []
    run_ids: set[str] = set()
    experiment_ids: set[str] = set()
    for config_path in config_paths:
        target = validate_formal_target(
            config_path,
            root,
            require_enabled=None,
            require_output_absent=True,
        )
        run_id = str(target.config["run_id"])
        experiment_id = str(target.config["experiment_id"])
        if run_id in run_ids:
            raise FormalRunPolicyError(f"duplicate run_id: {run_id}")
        if experiment_id in experiment_ids:
            raise FormalRunPolicyError(
                f"duplicate experiment_id: {experiment_id}"
            )
        run_ids.add(run_id)
        experiment_ids.add(experiment_id)
        targets.append(
            {
                "target_id": target.target_id,
                "status": (
                    "ready"
                    if target.config.get("enabled") is True
                    else "disabled"
                ),
                "config": config_path.relative_to(root).as_posix(),
                "context_path": target.context_path.relative_to(root).as_posix(),
                "context_sha256": target.context_sha256,
                "formal_output_directory": target.experiment_root.relative_to(
                    root
                ).as_posix(),
            }
        )

    counts: dict[str, int] = {}
    for item in targets:
        status = str(item["status"])
        counts[status] = counts.get(status, 0) + 1

    return {
        "artifact_schema_version": "rag-formal-batch-plan-v1",
        "condition_id": EXPECTED_CONDITION,
        "target_count": len(targets),
        "counts": counts,
        "targets": targets,
        "batch_report_root": FORMAL_BATCH_REPORT_ROOT.as_posix(),
        "formal_run_manifest": FORMAL_RUN_MANIFEST.as_posix(),
        "shared_non_rag_batch_report_used": False,
        "shared_non_rag_run_manifest_used": False,
        "force_supported": False,
        "reprocess_existing_supported": False,
    }
