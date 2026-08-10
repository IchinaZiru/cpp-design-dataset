"""Design-only C++ round-trip A/B protocol implementation.

This module is intentionally separate from the frozen V1-V6/formal runner.  It
builds byte-identical base design prompts for Conditions A and B, adds only a
deterministically retrieved RAG_CONTEXT to B, and constructs code-generation
requests from a final design document without loading repository inputs.
"""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from scripts.rag.canonical import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    sha256_bytes,
    sha256_file,
)


SCHEMA_VERSION = "roundtrip-design-only-ab-target-v1"
CONDITIONS = ("A", "B")
FORBIDDEN_PATH_PARTS = {
    "benchmark",
    "benchmarks",
    "build",
    "experiment",
    "experiments",
    "generated",
    "log",
    "logs",
    "report",
    "reports",
    "test",
    "tests",
    "testing",
}
HTML_ENTITIES = ("&lt;", "&gt;", "&amp;", "&quot;", "&#")


class RoundtripABError(RuntimeError):
    """Raised when the new A/B protocol would be violated."""


@dataclass(frozen=True)
class TargetInput:
    file_id: str
    unit_id: str
    path: str
    replacement_required: bool
    role: str
    content: str
    source_file_sha256: str
    content_sha256: str


@dataclass(frozen=True)
class RetrievalBundle:
    context: str
    query: dict[str, Any]
    fixed_design_knowledge: str
    dependency_records: tuple[dict[str, Any], ...]
    manifest: dict[str, Any]


@dataclass(frozen=True)
class RequestBundle:
    payload: dict[str, Any]
    prompt: str
    audit: dict[str, Any]


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RoundtripABError(f"{field} must be an object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoundtripABError(f"cannot load JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RoundtripABError(f"JSON root must be an object: {path}")
    return value


def read_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def resolve_project_path(project_root: Path, value: str, *, field: str) -> Path:
    relative = Path(value)
    if relative.is_absolute():
        raise RoundtripABError(f"{field} must be project-relative")
    root = project_root.resolve()
    resolved = (root / relative).resolve()
    if resolved != root and root not in resolved.parents:
        raise RoundtripABError(f"{field} escapes project root: {value}")
    return resolved


def resolve_repository_root(config: Mapping[str, Any], project_root: Path) -> Path:
    repository = _mapping(config.get("repository"), "repository")
    path = Path(str(repository.get("path", "")))
    if repository.get("external") is True:
        resolved = (project_root.resolve() / path).resolve()
    else:
        resolved = resolve_project_path(project_root, str(path), field="repository.path")
    if not resolved.is_dir():
        raise RoundtripABError(f"repository does not exist: {resolved}")
    return resolved


def git_output(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RoundtripABError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def verify_repository(config: Mapping[str, Any], repository_root: Path) -> dict[str, Any]:
    repository = _mapping(config.get("repository"), "repository")
    actual = git_output(repository_root, "rev-parse", "HEAD")
    expected = str(repository.get("commit", ""))
    if actual != expected:
        raise RoundtripABError(
            f"repository commit mismatch: expected {expected}, got {actual}"
        )
    status = git_output(repository_root, "status", "--short")
    if status:
        raise RoundtripABError(f"repository is not clean: {repository_root}")
    return {"commit": actual, "clean": True}


def validate_target_config(config: Mapping[str, Any]) -> None:
    if config.get("artifact_schema_version") != SCHEMA_VERSION:
        raise RoundtripABError("target config schema differs")
    if config.get("formal_execution_authorized") is not False:
        raise RoundtripABError("formal_execution_authorized must be false")
    inputs = config.get("target_owned_inputs")
    if not isinstance(inputs, list) or not inputs:
        raise RoundtripABError("target_owned_inputs must be a non-empty array")
    seen: set[tuple[str, str]] = set()
    for item in inputs:
        record = _mapping(item, "target_owned_inputs item")
        pair = (str(record.get("file_id", "")), str(record.get("unit_id", "")))
        if not re.fullmatch(r"F\d{2}", pair[0]) or not re.fullmatch(r"U\d{2}", pair[1]):
            raise RoundtripABError("target input IDs must use Fxx/Uxx")
        if pair in seen:
            raise RoundtripABError(f"duplicate target input IDs: {pair}")
        seen.add(pair)
        if record.get("scope") not in {"full_file", "byte_span"}:
            raise RoundtripABError("target input scope must be full_file or byte_span")
    one_shot = _mapping(config.get("one_shot"), "one_shot")
    required = {
        "design_generation_count": 1,
        "code_generation_count": 1,
        "retry": False,
        "automatic_repair": False,
        "manual_patch": False,
        "overwrite": False,
    }
    for key, expected in required.items():
        if one_shot.get(key) != expected:
            raise RoundtripABError(f"one_shot.{key} must be {expected!r}")


def _normalized_text(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RoundtripABError("target input is not UTF-8") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def load_target_inputs(
    config: Mapping[str, Any], repository_root: Path
) -> tuple[TargetInput, ...]:
    records: list[TargetInput] = []
    for raw_record in config["target_owned_inputs"]:
        item = _mapping(raw_record, "target_owned_inputs item")
        relative = str(item["path"]).replace("\\", "/")
        path = (repository_root / relative).resolve()
        if repository_root.resolve() not in path.parents:
            raise RoundtripABError(f"target input escapes repository: {relative}")
        raw = path.read_bytes()
        if item["scope"] == "byte_span":
            start = int(item["start_byte"])
            end = int(item["end_byte"])
            if not (0 <= start < end <= len(raw)):
                raise RoundtripABError(f"invalid target byte span: {relative}")
            content = _normalized_text(raw[start:end])
        else:
            content = _normalized_text(raw)
        expected_file = item.get("source_file_sha256")
        if expected_file and sha256_bytes(raw) != expected_file:
            raise RoundtripABError(f"target source file hash mismatch: {relative}")
        expected_content = item.get("content_sha256")
        if expected_content and sha256_bytes(content.encode("utf-8")) != expected_content:
            raise RoundtripABError(f"target content hash mismatch: {relative}")
        records.append(
            TargetInput(
                file_id=str(item["file_id"]),
                unit_id=str(item["unit_id"]),
                path=relative,
                replacement_required=bool(item.get("replacement_required", False)),
                role=str(item["role"]),
                content=content,
                source_file_sha256=sha256_bytes(raw),
                content_sha256=sha256_bytes(content.encode("utf-8")),
            )
        )
    return tuple(records)


def load_fixed_design_knowledge(
    config: Mapping[str, Any], project_root: Path
) -> str:
    retrieval = _mapping(config.get("retrieval"), "retrieval")
    if retrieval.get("design_knowledge_mode") != "fixed-v4-v5-verbatim-all-targets-v1":
        raise RoundtripABError("design knowledge must use the frozen V4/V5 verbatim mode")
    if retrieval.get("source_feature_selection") is not False:
        raise RoundtripABError("source-feature knowledge selection must be disabled")
    prohibited = {
        "knowledge_index_path",
        "knowledge_index_sha256",
        "knowledge_top_k",
        "pilot_top_k",
    }
    present = sorted(prohibited & set(retrieval))
    if present:
        raise RoundtripABError(
            "knowledge index/Top-K fields are prohibited: " + ", ".join(present)
        )
    path = resolve_project_path(
        project_root,
        str(retrieval["fixed_design_knowledge_path"]),
        field="fixed design knowledge",
    )
    expected_file_hash = str(retrieval.get("fixed_design_knowledge_sha256", ""))
    if sha256_file(path) != expected_file_hash:
        raise RoundtripABError("fixed design knowledge file SHA-256 mismatch")
    text = read_prompt(path)
    expected_content_hash = str(
        retrieval.get("fixed_design_knowledge_content_sha256", "")
    )
    if sha256_bytes(text.encode("utf-8")) != expected_content_hash:
        raise RoundtripABError("fixed design knowledge content SHA-256 mismatch")
    return text


def _quoted_includes(text: str) -> tuple[str, ...]:
    return tuple(
        match.group(1)
        for match in re.finditer(
            r'^\s*#\s*include\s*"([^"\r\n]+)"',
            text,
            flags=re.MULTILINE,
        )
    )


def _forbidden_path(relative: str) -> bool:
    parts = {part.lower() for part in Path(relative).parts}
    return bool(parts & FORBIDDEN_PATH_PARTS)


def _resolve_local_include(
    repository_root: Path,
    owner_path: str,
    include: str,
    include_roots: Sequence[str],
) -> str | None:
    candidates = [Path(owner_path).parent / include]
    candidates.extend(Path(root) / include for root in include_roots)
    root = repository_root.resolve()
    for candidate in candidates:
        path = (root / candidate).resolve()
        if path.is_file() and root in path.parents:
            return path.relative_to(root).as_posix()
    return None


def retrieve_dependency_headers(
    config: Mapping[str, Any],
    repository_root: Path,
    inputs: Sequence[TargetInput],
) -> tuple[dict[str, Any], ...]:
    retrieval = _mapping(config.get("retrieval"), "retrieval")
    expected_mode = "direct-project-local-quoted-include-whole-file-one-hop-v1"
    if retrieval.get("dependency_header_mode") != expected_mode:
        raise RoundtripABError(f"dependency_header_mode must be {expected_mode}")
    expected_normalization = "utf8-bom-aware-newlines-to-lf-v1"
    if retrieval.get("dependency_header_normalization") != expected_normalization:
        raise RoundtripABError(
            f"dependency_header_normalization must be {expected_normalization}"
        )
    include_roots = [str(item) for item in retrieval.get("include_roots", [])]
    target_paths = {item.path for item in inputs}
    selected: dict[str, dict[str, Any]] = {}
    for item in inputs:
        full_text = _normalized_text((repository_root / item.path).read_bytes())
        for include in _quoted_includes(full_text):
            resolved = _resolve_local_include(
                repository_root, item.path, include, include_roots
            )
            if resolved is None or resolved in target_paths or _forbidden_path(resolved):
                continue
            path = repository_root / resolved
            raw = path.read_bytes()
            context_content = _normalized_text(raw)
            context_bytes = context_content.encode("utf-8")
            selected.setdefault(
                resolved,
                {
                    "content": context_content,
                    "content_bytes": len(context_bytes),
                    "content_sha256": sha256_bytes(context_bytes),
                    "include_spelling": include,
                    "normalization": expected_normalization,
                    "owner_paths": [],
                    "path": resolved,
                    "selection_reason": (
                        "direct_project_local_quoted_include_whole_file_one_hop"
                    ),
                    "source_bytes": len(raw),
                    "source_sha256": sha256_bytes(raw),
                },
            )
            selected[resolved]["owner_paths"].append(item.path)
    records: list[dict[str, Any]] = []
    for path in sorted(selected):
        record = selected[path]
        record["owner_paths"] = sorted(set(record["owner_paths"]))
        records.append(record)
    maximum = int(retrieval.get("maximum_dependency_headers", 32))
    if len(records) > maximum:
        raise RoundtripABError("direct dependency header limit exceeded")
    return tuple(records)


def compose_rag_context(
    fixed_design_knowledge: str,
    dependencies: Sequence[Mapping[str, Any]],
) -> str:
    if not fixed_design_knowledge:
        raise RoundtripABError("fixed V4/V5 design knowledge is empty")
    chunks = [
        "RAG_CONTEXT v3\n\n",
        "===== BEGIN FIXED V4/V5 DESIGN KNOWLEDGE =====\n",
        fixed_design_knowledge,
        "\n===== END FIXED V4/V5 DESIGN KNOWLEDGE =====\n\n",
        "===== BEGIN DIRECT DEPENDENCY HEADER CONTEXT =====\n",
    ]
    for record in dependencies:
        path = str(record["path"])
        chunks.append(
            f"### PATH: {path}\n"
            f"SOURCE_SHA256: {record['source_sha256']}\n"
            f"CONTENT_SHA256: {record['content_sha256']}\n"
            f"CONTENT_BYTES: {record['content_bytes']}\n"
            f"----- BEGIN DEPENDENCY HEADER CONTENT: {path} -----\n"
        )
        chunks.append(str(record["content"]))
        chunks.append(f"\n----- END DEPENDENCY HEADER CONTENT: {path} -----\n\n")
    chunks.append("===== END DIRECT DEPENDENCY HEADER CONTEXT =====\n")
    return "".join(chunks)


def build_retrieval_bundle(
    config: Mapping[str, Any],
    project_root: Path,
    repository_root: Path,
) -> RetrievalBundle:
    validate_target_config(config)
    inputs = load_target_inputs(config, repository_root)
    retrieval = _mapping(config.get("retrieval"), "retrieval")
    if retrieval.get("target_specific_manual_query") is not False:
        raise RoundtripABError("target-specific manual query is prohibited")
    knowledge = load_fixed_design_knowledge(config, project_root)
    dependencies = retrieve_dependency_headers(config, repository_root, inputs)
    context = compose_rag_context(knowledge, dependencies)
    expected = retrieval.get("expected_evidence", [])
    checks: list[dict[str, Any]] = []
    for raw_check in expected:
        check = _mapping(raw_check, "expected_evidence item")
        path = str(check["path"])
        symbol = str(check["symbol"])
        matches = [record for record in dependencies if record["path"] == path]
        passed = bool(matches and symbol in str(matches[0]["content"]))
        checks.append({"path": path, "symbol": symbol, "passed": passed})
    dependency_text = "\n".join(str(item["content"]) for item in dependencies)
    test_content = bool(
        re.search(
            r"\b(?:TEST|TEST_F|EXPECT_[A-Z_]+|ASSERT_[A-Z_]+)\s*\(",
            dependency_text,
        )
    )
    previous_artifact = bool(
        re.search(
            r"(?:previous LLM output|generated design document|experiment result)",
            dependency_text,
            flags=re.IGNORECASE,
        )
    )
    leakage = {
        "forbidden_path_count": sum(
            1 for item in dependencies if _forbidden_path(str(item["path"]))
        ),
        "target_owned_path_overlap_count": sum(
            1 for item in dependencies if item["path"] in {x.path for x in inputs}
        ),
        "test_content_injected": test_content,
        "previous_generated_artifact_injected": previous_artifact,
    }
    leakage_failed = any(
        (
            int(leakage["forbidden_path_count"]),
            int(leakage["target_owned_path_overlap_count"]),
            bool(leakage["test_content_injected"]),
            bool(leakage["previous_generated_artifact_injected"]),
        )
    )
    status = "pass" if all(item["passed"] for item in checks) and not leakage_failed else "fail"
    query = {
        "artifact_schema_version": "roundtrip-ab-retrieval-query-v3",
        "dependency_header_mode": retrieval["dependency_header_mode"],
        "dependency_header_normalization": retrieval[
            "dependency_header_normalization"
        ],
        "target_id": config["target_id"],
        "design_knowledge_mode": retrieval["design_knowledge_mode"],
        "fixed_design_knowledge_content_sha256": sha256_bytes(
            knowledge.encode("utf-8")
        ),
        "knowledge_top_k_used": False,
        "manual_query_used": False,
        "source_feature_selection_used": False,
        "target_specific_override_used": False,
    }
    manifest = {
        "artifact_schema_version": "roundtrip-ab-retrieval-manifest-v3",
        "callable_bodies_removed": False,
        "condition": "B",
        "context_bytes": len(context.encode("utf-8")),
        "context_characters": len(context),
        "context_sha256": sha256_bytes(context.encode("utf-8")),
        "dependency_header_count": len(dependencies),
        "dependency_header_mode": retrieval["dependency_header_mode"],
        "dependency_header_normalization": retrieval[
            "dependency_header_normalization"
        ],
        "design_knowledge_mode": retrieval["design_knowledge_mode"],
        "deterministic": True,
        "expected_evidence": checks,
        "fixed_design_knowledge_bytes": len(knowledge.encode("utf-8")),
        "fixed_design_knowledge_content_sha256": sha256_bytes(
            knowledge.encode("utf-8")
        ),
        "knowledge_top_k_used": False,
        "leakage": leakage,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "header_comments_removed": False,
        "header_includes_removed": False,
        "source_feature_selection_used": False,
        "status": status,
        "target_id": config["target_id"],
    }
    return RetrievalBundle(
        context=context,
        query=query,
        fixed_design_knowledge=knowledge,
        dependency_records=tuple(dict(item) for item in dependencies),
        manifest=manifest,
    )


def _input_envelope(inputs: Sequence[TargetInput]) -> str:
    parts = [
        "TARGET-OWNED INPUTS",
        "各Fxx/Uxx識別子と対象コードの対応を最終設計仕様書に保持してください。",
    ]
    for item in inputs:
        parts.extend(
            [
                "",
                f"===== BEGIN {item.file_id}/{item.unit_id} =====",
                f"path: {item.path}",
                f"role: {item.role}",
                f"replacement_required: {str(item.replacement_required).lower()}",
                item.content.rstrip(),
                f"===== END {item.file_id}/{item.unit_id} =====",
            ]
        )
    return "\n".join(parts)


def compose_design_prompt(
    base_prompt: str,
    inputs: Sequence[TargetInput],
    *,
    condition: str,
    rag_context: str | None,
) -> str:
    if condition not in CONDITIONS:
        raise RoundtripABError(f"unknown condition: {condition}")
    if condition == "A" and rag_context is not None:
        raise RoundtripABError("Condition A must not receive RAG_CONTEXT")
    if condition == "B" and not rag_context:
        raise RoundtripABError("Condition B requires RAG_CONTEXT")
    parts = [base_prompt.rstrip(), "", _input_envelope(inputs)]
    if condition == "B":
        parts.extend(
            [
                "",
                "===== BEGIN RAG_CONTEXT =====",
                str(rag_context).rstrip(),
                "===== END RAG_CONTEXT =====",
            ]
        )
    return "\n".join(parts).rstrip() + "\n"


def _common_paths(common: Mapping[str, Any], project_root: Path) -> dict[str, Path]:
    prompts = _mapping(common.get("prompts"), "common.prompts")
    return {
        name: resolve_project_path(project_root, str(prompts[name]), field=name)
        for name in (
            "design_generation",
            "code_generation_system",
            "code_generation_user",
            "code_generation_schema",
        )
    }


def load_common_config(path: Path, project_root: Path) -> dict[str, Any]:
    common = load_json(path)
    if common.get("artifact_schema_version") != "roundtrip-design-only-ab-common-v1":
        raise RoundtripABError("common config schema differs")
    if common.get("formal_execution_authorized") is not False:
        raise RoundtripABError("common formal execution must remain unauthorized")
    generation = _mapping(common.get("generation"), "common.generation")
    if generation.get("stream") is not False:
        raise RoundtripABError("streaming generation is prohibited")
    paths = _common_paths(common, project_root)
    prompts = _mapping(common.get("prompts"), "common.prompts")
    for name, resolved in paths.items():
        expected = str(prompts.get(f"{name}_sha256", ""))
        actual = sha256_file(resolved)
        if actual != expected:
            raise RoundtripABError(
                f"common prompt/schema hash mismatch for {name}: "
                f"expected {expected}, got {actual}"
            )
    isolation = _mapping(common.get("input_isolation"), "common.input_isolation")
    if isolation.get("code_generation_allowed_semantic_inputs") != [
        "final design specification"
    ]:
        raise RoundtripABError("code-generation semantic input is not design-only")
    return common


def build_design_request(
    config: Mapping[str, Any],
    common: Mapping[str, Any],
    project_root: Path,
    inputs: Sequence[TargetInput],
    *,
    condition: str,
    rag_context: str | None,
) -> RequestBundle:
    paths = _common_paths(common, project_root)
    base_prompt = read_prompt(paths["design_generation"])
    prompt = compose_design_prompt(
        base_prompt, inputs, condition=condition, rag_context=rag_context
    )
    generation = _mapping(common.get("generation"), "common.generation")
    payload = {
        "model": generation["model"],
        "prompt": prompt,
        "stream": False,
        "options": dict(_mapping(generation.get("options"), "generation.options")),
    }
    audit = {
        "artifact_schema_version": "roundtrip-ab-design-request-audit-v1",
        "base_prompt_path": paths["design_generation"].relative_to(
            project_root.resolve()
        ).as_posix(),
        "base_prompt_sha256": sha256_bytes(base_prompt.encode("utf-8")),
        "condition": condition,
        "dependency_header_direct_input": False,
        "fixed_scaffold_loaded": False,
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "rag_context_injected": condition == "B",
        "target_id": config["target_id"],
    }
    return RequestBundle(payload=payload, prompt=prompt, audit=audit)


def build_code_request(
    final_design_document: str,
    common: Mapping[str, Any],
    project_root: Path,
) -> RequestBundle:
    """Build codegen from the design only; no target config is accepted."""

    if not final_design_document.strip():
        raise RoundtripABError("final design document is empty")
    paths = _common_paths(common, project_root)
    system = read_prompt(paths["code_generation_system"])
    template = read_prompt(paths["code_generation_user"])
    marker = "{{FINAL_DESIGN_SPECIFICATION}}"
    if template.count(marker) != 1:
        raise RoundtripABError("code-generation design marker must occur once")
    prompt = template.replace(marker, final_design_document)
    schema = load_json(paths["code_generation_schema"])
    generation = _mapping(common.get("generation"), "common.generation")
    payload = {
        "format": schema,
        "model": generation["model"],
        "options": dict(_mapping(generation.get("options"), "generation.options")),
        "prompt": prompt,
        "stream": False,
        "system": system,
    }
    audit = {
        "artifact_schema_version": "roundtrip-ab-code-request-audit-v1",
        "allowed_semantic_inputs": ["final design specification"],
        "code_prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "dependency_header_loaded": False,
        "fixed_scaffold_loaded": False,
        "original_target_source_loaded": False,
        "rag_context_loaded": False,
        "repository_access_used": False,
        "schema_sha256": sha256_file(paths["code_generation_schema"]),
        "test_or_build_result_loaded": False,
    }
    return RequestBundle(payload=payload, prompt=prompt, audit=audit)


def validate_generated_units(
    text: str, expected_units: Sequence[Mapping[str, Any]]
) -> dict[tuple[str, str], str]:
    if any(entity in text for entity in HTML_ENTITIES):
        raise RoundtripABError("generated JSON contains HTML entities")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RoundtripABError(f"code response is not valid JSON: {exc}") from exc
    if not isinstance(value, dict) or set(value) != {"units"}:
        raise RoundtripABError("code response must contain only units")
    units = value["units"]
    if not isinstance(units, list) or not units:
        raise RoundtripABError("units must be a non-empty array")
    parsed: dict[tuple[str, str], str] = {}
    for raw in units:
        if not isinstance(raw, dict) or set(raw) != {"file_id", "unit_id", "content"}:
            raise RoundtripABError("unit fields differ from common schema")
        pair = (str(raw["file_id"]), str(raw["unit_id"]))
        content = raw["content"]
        if pair in parsed or not isinstance(content, str) or not content:
            raise RoundtripABError("duplicate or empty generated unit")
        parsed[pair] = content
    expected = {
        (str(item["file_id"]), str(item["unit_id"])) for item in expected_units
    }
    if set(parsed) != expected:
        raise RoundtripABError(
            f"generated unit set differs: expected={sorted(expected)}, actual={sorted(parsed)}"
        )
    return parsed


class SourceReplacementTransaction:
    def __init__(
        self,
        repository_root: Path,
        unit_configs: Sequence[Mapping[str, Any]],
        generated: Mapping[tuple[str, str], str],
    ) -> None:
        self.repository_root = repository_root.resolve()
        self.unit_configs = tuple(unit_configs)
        self.generated = generated
        self.originals: dict[str, bytes] = {}
        self.replacement_hashes: dict[str, str] = {}

    def apply(self) -> None:
        by_path: dict[str, list[Mapping[str, Any]]] = {}
        for unit in self.unit_configs:
            by_path.setdefault(str(unit["path"]), []).append(unit)
        for relative, units in by_path.items():
            path = (self.repository_root / relative).resolve()
            if self.repository_root not in path.parents:
                raise RoundtripABError(f"replacement path escapes repository: {relative}")
            original = path.read_bytes()
            expected = units[0].get("source_file_sha256")
            if expected and sha256_bytes(original) != expected:
                raise RoundtripABError(f"replacement source hash mismatch: {relative}")
            self.originals[relative] = original
            replacements: list[tuple[int, int, bytes]] = []
            for unit in units:
                pair = (str(unit["file_id"]), str(unit["unit_id"]))
                generated_text = self.generated[pair].replace("\r\n", "\n").replace("\r", "\n")
                if unit["scope"] == "byte_span" and b"\r\n" in original:
                    generated_text = generated_text.replace("\n", "\r\n")
                content = generated_text.encode("utf-8")
                if unit["scope"] == "full_file":
                    start, end = 0, len(original)
                else:
                    start, end = int(unit["start_byte"]), int(unit["end_byte"])
                if not (0 <= start < end <= len(original)):
                    raise RoundtripABError(f"replacement span is invalid: {relative}")
                expected_span = unit.get("content_sha256")
                if expected_span and sha256_bytes(original[start:end]) != expected_span:
                    raise RoundtripABError(f"replacement span hash mismatch: {relative}")
                replacements.append((start, end, content))
            modified = original
            for start, end, content in sorted(replacements, reverse=True):
                modified = modified[:start] + content + modified[end:]
            path.write_bytes(modified)
            self.replacement_hashes[relative] = sha256_bytes(modified)

    def restore(self) -> dict[str, str]:
        restored: dict[str, str] = {}
        for relative, original in self.originals.items():
            path = self.repository_root / relative
            path.write_bytes(original)
            actual = path.read_bytes()
            if actual != original:
                raise RoundtripABError(f"exact-byte restoration failed: {relative}")
            restored[relative] = sha256_bytes(actual)
        return restored


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise RoundtripABError(f"refusing to overwrite artifact: {path}") from exc


def write_retrieval_bundle(output_root: Path, bundle: RetrievalBundle) -> None:
    if output_root.exists() and any(output_root.iterdir()):
        raise RoundtripABError(f"retrieval output already exists: {output_root}")
    _write_exclusive(output_root / "query.json", canonical_json_bytes(bundle.query))
    _write_exclusive(
        output_root / "fixed_design_knowledge.txt",
        (bundle.fixed_design_knowledge.rstrip("\n") + "\n").encode("utf-8"),
    )
    _write_exclusive(
        output_root / "dependency_headers.jsonl",
        canonical_jsonl_bytes(bundle.dependency_records),
    )
    _write_exclusive(output_root / "context.txt", bundle.context.encode("utf-8"))
    manifest = dict(bundle.manifest)
    manifest["artifact_hashes"] = {
        "context.txt": sha256_bytes(bundle.context.encode("utf-8")),
        "dependency_headers.jsonl": sha256_bytes(
            canonical_jsonl_bytes(bundle.dependency_records)
        ),
        "fixed_design_knowledge.txt": sha256_bytes(
            (bundle.fixed_design_knowledge.rstrip("\n") + "\n").encode("utf-8")
        ),
        "query.json": sha256_bytes(canonical_json_bytes(bundle.query)),
    }
    _write_exclusive(
        output_root / "retrieval_manifest.json", canonical_json_bytes(manifest)
    )


def build_plan(
    config: Mapping[str, Any], common: Mapping[str, Any], project_root: Path
) -> dict[str, Any]:
    repository_root = resolve_repository_root(config, project_root)
    repository_state = verify_repository(config, repository_root)
    inputs = load_target_inputs(config, repository_root)
    retrieval = build_retrieval_bundle(config, project_root, repository_root)
    requests = {
        "A": build_design_request(
            config,
            common,
            project_root,
            inputs,
            condition="A",
            rag_context=None,
        ),
        "B": build_design_request(
            config,
            common,
            project_root,
            inputs,
            condition="B",
            rag_context=retrieval.context,
        ),
    }
    if requests["A"].audit["base_prompt_sha256"] != requests["B"].audit["base_prompt_sha256"]:
        raise RoundtripABError("A/B base design prompt hashes differ")
    if requests["A"].payload["model"] != requests["B"].payload["model"]:
        raise RoundtripABError("A/B design models differ")
    if requests["A"].payload["options"] != requests["B"].payload["options"]:
        raise RoundtripABError("A/B generation options differ")
    return {
        "artifact_schema_version": "roundtrip-ab-plan-v1",
        "base_design_prompt_sha256": requests["A"].audit["base_prompt_sha256"],
        "code_generation_semantic_input": "final_design_specification_only",
        "conditions": {
            key: {
                "design_prompt_sha256": sha256_bytes(bundle.prompt.encode("utf-8")),
                "design_request_sha256": sha256_bytes(
                    canonical_json_bytes(bundle.payload)
                ),
                "rag_context_injected": bundle.audit["rag_context_injected"],
            }
            for key, bundle in requests.items()
        },
        "formal_execution_authorized": False,
        "generation_server_contacted": False,
        "llm_call_count": 0,
        "repository": repository_state,
        "retrieval_context_sha256": retrieval.manifest["context_sha256"],
        "retrieval_status": retrieval.manifest["status"],
        "target_id": config["target_id"],
    }


def write_plan_artifacts(
    config: Mapping[str, Any],
    common: Mapping[str, Any],
    project_root: Path,
) -> dict[str, Any]:
    execution = _mapping(config.get("execution"), "execution")
    plan_value = execution.get("plan_root")
    if not isinstance(plan_value, str) or not plan_value:
        raise RoundtripABError("execution.plan_root is required for plan-only")
    plan_root = resolve_project_path(project_root, plan_value, field="plan_root")
    if plan_root.exists():
        raise RoundtripABError(f"plan output already exists: {plan_root}")
    repository_root = resolve_repository_root(config, project_root)
    verify_repository(config, repository_root)
    inputs = load_target_inputs(config, repository_root)
    retrieval = build_retrieval_bundle(config, project_root, repository_root)
    requests = {
        "A": build_design_request(
            config,
            common,
            project_root,
            inputs,
            condition="A",
            rag_context=None,
        ),
        "B": build_design_request(
            config,
            common,
            project_root,
            inputs,
            condition="B",
            rag_context=retrieval.context,
        ),
    }
    manifest = build_plan(config, common, project_root)
    for condition, request in requests.items():
        root = plan_root / f"condition-{condition.lower()}"
        _write_exclusive(root / "design_prompt.txt", request.prompt.encode("utf-8"))
        _write_exclusive(
            root / "design_request.json", canonical_json_bytes(request.payload)
        )
        _write_exclusive(root / "design_request_audit.json", canonical_json_bytes(request.audit))
    retrieval_root = plan_root / "condition-b" / "retrieval"
    write_retrieval_bundle(retrieval_root, retrieval)
    common_paths = _common_paths(common, project_root)
    manifest["code_generation_common"] = {
        "schema_sha256": sha256_file(common_paths["code_generation_schema"]),
        "system_prompt_sha256": sha256_file(
            common_paths["code_generation_system"]
        ),
        "user_prompt_template_sha256": sha256_file(
            common_paths["code_generation_user"]
        ),
    }
    _write_exclusive(plan_root / "plan_manifest.json", canonical_json_bytes(manifest))
    return manifest


def run_retrieval_only(
    config: Mapping[str, Any], project_root: Path
) -> dict[str, Any]:
    repository_root = resolve_repository_root(config, project_root)
    verify_repository(config, repository_root)
    bundle = build_retrieval_bundle(config, project_root, repository_root)
    output = _mapping(config.get("output"), "output")
    output_root = resolve_project_path(
        project_root, str(output["retrieval_root"]), field="retrieval_root"
    )
    write_retrieval_bundle(output_root, bundle)
    return bundle.manifest


GenerationCall = Callable[[str, Mapping[str, str], bytes, int], bytes]


def contact_generation_server(
    endpoint: str, headers: Mapping[str, str], request_bytes: bytes, timeout: int
) -> bytes:
    request = urllib.request.Request(
        endpoint,
        data=request_bytes,
        headers=dict(headers),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ollama_text(response_bytes: bytes, stage: str) -> str:
    try:
        value = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RoundtripABError(f"{stage} response is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RoundtripABError(f"{stage} response root is not an object")
    if value.get("done_reason") == "length":
        raise RoundtripABError(f"{stage} response was truncated")
    text = value.get("response")
    if not isinstance(text, str) or not text.strip():
        raise RoundtripABError(f"{stage} response is empty")
    return text


def _render_command(
    command: Sequence[str], repository_root: Path, workspace: Path
) -> list[str]:
    return [
        str(item)
        .replace("<REPOSITORY_ROOT>", str(repository_root))
        .replace("<EVALUATION_WORKSPACE>", str(workspace))
        for item in command
    ]


def _run_stage(
    stage: str,
    command: Sequence[str],
    repository_root: Path,
    workspace: Path,
    timeout: int,
) -> dict[str, Any]:
    rendered = _render_command(command, repository_root, workspace)
    try:
        result = subprocess.run(
            rendered,
            cwd=repository_root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "command": rendered,
            "returncode": result.returncode,
            "stage": stage,
            "status": "pass" if result.returncode == 0 else "fail",
            "stderr": result.stderr,
            "stdout": result.stdout,
            "timeout": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": rendered,
            "returncode": None,
            "stage": stage,
            "status": "fail",
            "stderr": str(exc.stderr or ""),
            "stdout": str(exc.stdout or ""),
            "timeout": True,
        }


def execute_condition_once(
    config: Mapping[str, Any],
    common: Mapping[str, Any],
    project_root: Path,
    condition: str,
    *,
    call_generation: GenerationCall = contact_generation_server,
) -> dict[str, Any]:
    """Execute one formal-excluded pilot condition exactly once.

    The function exists for the later mechanics pilot.  Formal target configs
    have execution.enabled=false and are rejected here.
    """

    if condition not in CONDITIONS:
        raise RoundtripABError("condition must be A or B")
    validate_target_config(config)
    execution = _mapping(config.get("execution"), "execution")
    if execution.get("enabled") is not True:
        raise RoundtripABError("execution is disabled for this target")
    if config.get("formal_target_member") is not False:
        raise RoundtripABError("formal target execution is prohibited by this runner version")
    repository_root = resolve_repository_root(config, project_root)
    repository_state = verify_repository(config, repository_root)
    base_root = resolve_project_path(
        project_root, str(execution["output_root"]), field="execution.output_root"
    )
    run_root = base_root / f"condition-{condition.lower()}"
    if run_root.exists():
        raise RoundtripABError(f"one-shot output already exists: {run_root}")
    attempt = {
        "artifact_schema_version": "roundtrip-ab-attempt-v1",
        "condition": condition,
        "code_generation_limit": 1,
        "design_generation_limit": 1,
        "formal_target_member": False,
        "reserved_at_utc": utc_now(),
        "retry_allowed": False,
        "target_id": config["target_id"],
    }
    _write_exclusive(run_root / "attempt.json", canonical_json_bytes(attempt))
    inputs = load_target_inputs(config, repository_root)
    rag_context: str | None = None
    if condition == "B":
        rag_context = build_retrieval_bundle(
            config, project_root, repository_root
        ).context
    design_request = build_design_request(
        config,
        common,
        project_root,
        inputs,
        condition=condition,
        rag_context=rag_context,
    )
    _write_exclusive(
        run_root / "design" / "prompt.txt", design_request.prompt.encode("utf-8")
    )
    design_request_bytes = canonical_json_bytes(design_request.payload)
    _write_exclusive(run_root / "design" / "request.json", design_request_bytes)
    _write_exclusive(
        run_root / "design" / "request_audit.json",
        canonical_json_bytes(design_request.audit),
    )
    generation = _mapping(common.get("generation"), "common.generation")
    headers = dict(_mapping(generation.get("headers"), "generation.headers"))
    endpoint = str(generation["endpoint"])
    timeout = int(generation["timeout_seconds"])
    transaction: SourceReplacementTransaction | None = None
    restored: dict[str, str] = {}
    stage_records: dict[str, Any] = {}
    contact_count = 0
    try:
        _write_exclusive(
            run_root / "design" / "contact.json",
            canonical_json_bytes(
                {
                    "contact_attempted": True,
                    "request_sha256": sha256_bytes(design_request_bytes),
                    "retry": False,
                    "started_at_utc": utc_now(),
                }
            ),
        )
        contact_count += 1
        design_response = call_generation(
            endpoint, headers, design_request_bytes, timeout
        )
        _write_exclusive(run_root / "design" / "response.json", design_response)
        design_document = _ollama_text(design_response, "design generation")
        _write_exclusive(
            run_root / "design" / "final_design.md",
            design_document.encode("utf-8"),
        )

        code_request = build_code_request(design_document, common, project_root)
        code_request_bytes = canonical_json_bytes(code_request.payload)
        _write_exclusive(run_root / "code" / "prompt.txt", code_request.prompt.encode("utf-8"))
        _write_exclusive(run_root / "code" / "request.json", code_request_bytes)
        _write_exclusive(
            run_root / "code" / "request_audit.json",
            canonical_json_bytes(code_request.audit),
        )
        _write_exclusive(
            run_root / "code" / "contact.json",
            canonical_json_bytes(
                {
                    "contact_attempted": True,
                    "request_sha256": sha256_bytes(code_request_bytes),
                    "retry": False,
                    "started_at_utc": utc_now(),
                }
            ),
        )
        contact_count += 1
        code_response = call_generation(endpoint, headers, code_request_bytes, timeout)
        _write_exclusive(run_root / "code" / "response.json", code_response)
        code_text = _ollama_text(code_response, "code generation")
        replacement_units = config.get("replacement_units")
        if not isinstance(replacement_units, list) or not replacement_units:
            raise RoundtripABError("replacement_units are missing")
        generated = validate_generated_units(code_text, replacement_units)
        _write_exclusive(
            run_root / "code" / "validated_units.json",
            canonical_json_bytes(
                {
                    "units": [
                        {
                            "content": content,
                            "file_id": pair[0],
                            "unit_id": pair[1],
                        }
                        for pair, content in sorted(generated.items())
                    ]
                }
            ),
        )

        transaction = SourceReplacementTransaction(
            repository_root, replacement_units, generated
        )
        transaction.apply()
        workspace = run_root / "evaluation-workspace"
        workspace.mkdir(parents=True, exist_ok=False)
        commands = _mapping(execution.get("commands"), "execution.commands")
        timeouts = _mapping(
            execution.get("stage_timeouts_seconds"),
            "execution.stage_timeouts_seconds",
        )
        for stage in ("configure", "build", "direct_test", "full_test"):
            command = commands.get(stage)
            if not isinstance(command, list) or not command:
                raise RoundtripABError(f"execution command is missing: {stage}")
            record = _run_stage(
                stage,
                [str(item) for item in command],
                repository_root,
                workspace,
                int(timeouts[stage]),
            )
            stage_records[stage] = record
            _write_exclusive(
                run_root / "evaluation" / f"{stage}.json",
                canonical_json_bytes(record),
            )
            if record["status"] != "pass":
                break
    except Exception as exc:
        if transaction is not None:
            restored = transaction.restore()
        failure = {
            "artifact_schema_version": "roundtrip-ab-result-v1",
            "condition": condition,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "generation_server_contact_count": contact_count,
            "repository_clean_after_restoration": (
                git_output(repository_root, "status", "--short") == ""
            ),
            "restored_hashes": restored,
            "retry_performed": False,
            "status": "fail",
            "target_id": config["target_id"],
        }
        _write_exclusive(run_root / "failure.json", canonical_json_bytes(failure))
        raise
    finally:
        if transaction is not None and not restored:
            restored = transaction.restore()

    all_stages_pass = set(stage_records) == {
        "configure",
        "build",
        "direct_test",
        "full_test",
    } and all(record["status"] == "pass" for record in stage_records.values())
    repository_clean = git_output(repository_root, "status", "--short") == ""
    result = {
        "artifact_schema_version": "roundtrip-ab-result-v1",
        "condition": condition,
        "generation_server_contact_count": contact_count,
        "llm_call_count": contact_count,
        "overall_pass": all_stages_pass and repository_clean,
        "repository_clean_after_restoration": repository_clean,
        "repository_commit": repository_state["commit"],
        "restored_hashes": restored,
        "retry_performed": False,
        "stages": {
            stage: record["status"] for stage, record in stage_records.items()
        },
        "status": "pass" if all_stages_pass and repository_clean else "fail",
        "target_id": config["target_id"],
    }
    _write_exclusive(run_root / "result.json", canonical_json_bytes(result))
    return result
