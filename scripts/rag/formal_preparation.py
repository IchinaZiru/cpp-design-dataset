"""Validation and planning primitives for the frozen 17-target formal RAG run.

This module is intentionally generation-server free.  It resolves every query and
index from frozen artifacts and never regenerates a query or invokes Git through a
subprocess.  The external-pilot config loader is deliberately not used because a
formal config has ``formal_experiment=true``.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .artifacts import CandidateConfig, LoadedIndex, LoadedQuery, load_query_artifact
from .canonical import (
    canonical_json_bytes,
    canonical_jsonl_bytes,
    posix_relative_path,
    sha256_bytes,
    sha256_file,
)


class FormalPreparationError(RuntimeError):
    """Raised when frozen formal preparation evidence is incomplete or changed."""


EXTERNAL_RETRIEVAL_SHA256 = (
    "f8bb1a42f232788aee72e785a713e74aeb78ddf93ff303901b485f36ac538545"
)
COMMON_CONFIG_PATH = "configs/rag/formal_retrieval_pipeline_v1.json"
TARGET_REGISTRY_PATH = "configs/rag/query_targets_v1.json"
CANDIDATE_CONFIG_PATH = "configs/rag/candidates_v1.json"
TARGET_CONFIG_DIRECTORY = "configs/rag/targets"

EXPECTED_ALLOWED_RELATIONS = [
    "alias_target",
    "base_type",
    "enum_type",
    "field_type",
    "nested_type",
    "parameter_type",
    "return_type",
    "template_argument_type",
    "wrapper_direct_call",
]
EXPECTED_RANKING = {
    "tie_break": [
        "tier_asc",
        "exact_match_rank_asc",
        "usage_classification_rank_asc",
        "direct_relation_desc",
        "original_case_match_desc",
        "bm25_score_desc",
        "directory_distance_asc",
        "path_asc",
        "start_line_asc",
        "chunk_id_asc",
    ],
    "tiers": {
        "auxiliary_bm25": 3,
        "direct_dependency": 1,
        "exact_symbol": 0,
        "usage_or_call_site": 2,
    },
    "version": "retrieval-ranking-v1",
}
EXPECTED_FILTERING = {
    "content_deduplication": "content-sha256-v1",
    "forbidden_path_filter": True,
    "generated_report_test_llm_filter": True,
    "overlap_method": "path_byte_overlap_v1",
    "target_source_overlap_filter": True,
    "version": "retrieval-filter-dedup-v1",
}
EXPECTED_CANONICAL_SERIALIZATION = {
    "encoding": "utf-8",
    "final_newline_count": 1,
    "json_key_order": "lexicographic",
    "line_endings": "lf",
    "path_format": "repository-relative-posix",
    "timestamps_in_content_hash": False,
}
EXPECTED_INPUT_ISOLATION = {
    "design_generation_allowed_inputs": [
        "frozen design instruction",
        "frozen target source",
        "frozen context.txt",
    ],
    "code_regeneration_allowed_inputs": [
        "single one-shot generated design document",
        "fixed scaffold equivalent to the corresponding non-RAG target",
    ],
    "code_regeneration_forbidden_inputs": [
        "original target source body",
        "retrieved context",
        "selected chunks",
        "candidates",
        "query artifact",
        "repository source",
        "design-generation request or prompt",
        "design audit findings",
        "previous generated output",
    ],
}
STANDARD_PROTECTED_FIELDS = (
    "target_id",
    "repository_id",
    "repository_path",
    "repository_commit",
    "target_name",
    "granularity",
    "source_files",
    "locator",
    "test_files",
    "model",
    "evaluation",
    "readiness",
)


@dataclass(frozen=True)
class FormalCommonConfig:
    path: Path
    relative_path: str
    sha256: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class FormalTarget:
    path: Path
    relative_path: str
    sha256: str
    raw: dict[str, Any]
    query: LoadedQuery
    query_validation_path: Path
    query_validation_relative_path: str
    query_validation_sha256: str
    index: LoadedIndex
    index_validation_path: Path
    index_validation_relative_path: str
    index_validation_sha256: str
    repository_root: Path

    @property
    def target_id(self) -> str:
        return str(self.raw["target_id"])


@dataclass(frozen=True)
class FormalPreparation:
    project_root: Path
    branch: str
    project_head: str
    protocol_version: str
    protocol_status: str
    formal_execution_status: str
    common: FormalCommonConfig
    candidate_config: CandidateConfig
    registry_path: Path
    registry_sha256: str
    targets: tuple[FormalTarget, ...]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalPreparationError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FormalPreparationError(f"JSON root must be an object: {path}")
    return value


def _relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise FormalPreparationError(f"path escapes project root: {path}") from exc


def _resolve(root: Path, value: Any, *, field: str) -> Path:
    try:
        relative = posix_relative_path(str(value))
    except ValueError as exc:
        raise FormalPreparationError(f"invalid {field}: {value!r}") from exc
    path = root.joinpath(*relative.split("/"))
    _relative(root, path)
    return path


def _verify_hash(path: Path, expected: Any, *, field: str) -> str:
    text = str(expected).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise FormalPreparationError(f"{field} is not a full SHA-256")
    if not path.is_file():
        raise FormalPreparationError(f"missing {field}: {path}")
    actual = sha256_file(path)
    if actual != text:
        raise FormalPreparationError(
            f"{field} hash mismatch: expected {text}, got {actual}"
        )
    return actual


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FormalPreparationError(f"cannot load JSONL {path}: {exc}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line:
            raise FormalPreparationError(f"blank JSONL record at {path}:{line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FormalPreparationError(
                f"invalid JSONL record at {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise FormalPreparationError(
                f"JSONL record must be an object at {path}:{line_number}"
            )
        records.append(value)
    return records


def _full_sha256(value: Any, *, field: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise FormalPreparationError(f"{field} is not a full SHA-256")
    return text


def load_formal_index_artifacts(index_dir: str | Path) -> LoadedIndex:
    """Load an index using its canonical LF JSON/JSONL byte contract.

    Git may check text JSONL files out with CRLF on Windows.  The frozen hashes
    are explicitly defined over canonical LF serialization, so formal planning
    verifies parsed content reserialized with the repository's canonical helpers
    without writing a normalized copy to disk.
    """

    root = Path(index_dir)
    required = {
        "corpus_manifest.json",
        "chunks.jsonl",
        "symbol_index.jsonl",
        "index_validation.json",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise FormalPreparationError("missing index artifacts: " + ", ".join(missing))
    manifest = _load_json(root / "corpus_manifest.json")
    validation = _load_json(root / "index_validation.json")
    _require(validation.get("status") == "pass", "index validation status is not pass")
    _require(validation.get("deterministic") is True, "index is not independently deterministic")
    _require(int(validation.get("unhandled_parser_error_count", -1)) == 0, "index contains unhandled parser errors")
    repository_id = str(manifest.get("repository", ""))
    repository_commit = str(manifest.get("repository_commit", "")).lower()
    _require(
        len(repository_commit) == 40
        and all(character in "0123456789abcdef" for character in repository_commit),
        "corpus repository_commit is not a full SHA-1",
    )
    _require(validation.get("repository") == repository_id, "manifest/validation repository mismatch")
    _require(str(validation.get("repository_commit", "")).lower() == repository_commit, "manifest/validation commit mismatch")

    chunks = _load_jsonl(root / "chunks.jsonl")
    symbols = _load_jsonl(root / "symbol_index.jsonl")
    actual_hashes = {
        "corpus_manifest.json": sha256_bytes(canonical_json_bytes(manifest)),
        "chunks.jsonl": sha256_bytes(canonical_jsonl_bytes(chunks)),
        "symbol_index.jsonl": sha256_bytes(canonical_jsonl_bytes(symbols)),
    }
    declared_hashes = validation.get("artifact_hashes")
    _require(isinstance(declared_hashes, Mapping), "index validation lacks artifact hashes")
    for name, actual in actual_hashes.items():
        expected = _full_sha256(declared_hashes.get(name), field=f"index hash {name}")
        _require(actual == expected, f"index artifact hash mismatch for {name}: expected {expected}, got {actual}")

    chunks_by_id: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        chunk_id = _full_sha256(chunk.get("chunk_id"), field="chunk_id")
        _require(chunk_id not in chunks_by_id, f"duplicate chunk_id: {chunk_id}")
        try:
            path_value = posix_relative_path(str(chunk.get("path", "")))
        except ValueError as exc:
            raise FormalPreparationError(f"invalid chunk path: {chunk.get('path')}") from exc
        start = int(chunk.get("start_byte", -1))
        end = int(chunk.get("end_byte", -1))
        _require(start >= 0 and end > start, f"invalid chunk range: {chunk_id}")
        normalized = dict(chunk)
        normalized["path"] = path_value
        normalized["start_byte"] = start
        normalized["end_byte"] = end
        normalized["content_sha256"] = _full_sha256(
            chunk.get("content_sha256"), field="chunk content_sha256"
        )
        content = str(chunk.get("content", ""))
        _require(
            sha256_bytes(content.encode("utf-8")) == normalized["content_sha256"],
            f"chunk content hash mismatch: {chunk_id}",
        )
        _require(str(chunk.get("repository", "")) == repository_id, f"chunk repository mismatch: {chunk_id}")
        _require(str(chunk.get("repository_commit", "")).lower() == repository_commit, f"chunk commit mismatch: {chunk_id}")
        chunks_by_id[chunk_id] = normalized
    expected_chunks = sorted(
        chunks_by_id.values(),
        key=lambda item: (
            item["path"],
            item["start_byte"],
            item["end_byte"],
            str(item.get("kind", "")),
            item["chunk_id"],
        ),
    )
    _require(list(chunks_by_id.values()) == expected_chunks, "chunks.jsonl is not in canonical order")

    normalized_symbols: list[dict[str, Any]] = []
    symbols_by_lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for symbol in symbols:
        chunk_id = _full_sha256(symbol.get("chunk_id"), field="symbol chunk_id")
        chunk = chunks_by_id.get(chunk_id)
        _require(chunk is not None, f"symbol references unknown chunk: {chunk_id}")
        try:
            path_value = posix_relative_path(str(symbol.get("path", "")))
        except ValueError as exc:
            raise FormalPreparationError(f"invalid symbol path: {symbol.get('path')}") from exc
        _require(path_value == chunk["path"], f"symbol/chunk path mismatch: {chunk_id}")
        _require(str(symbol.get("kind", "")) == str(chunk.get("kind", "")), f"symbol/chunk kind mismatch: {chunk_id}")
        record = dict(symbol)
        record["path"] = path_value
        record["canonical_name"] = str(symbol.get("canonical_name", ""))
        record["short_name"] = str(symbol.get("short_name", ""))
        _require(bool(record["canonical_name"] and record["short_name"]), f"symbol identity is incomplete: {chunk_id}")
        lookup_values = symbol.get("lookup_keys", [])
        _require(isinstance(lookup_values, list), f"lookup_keys must be an array: {chunk_id}")
        lookup_keys = sorted(
            {
                str(value)
                for value in [
                    record["canonical_name"],
                    record["short_name"],
                    *lookup_values,
                ]
                if str(value)
            }
        )
        record["lookup_keys"] = lookup_keys
        normalized_symbols.append(record)
        for key in lookup_keys:
            symbols_by_lookup[key].append(record)
    normalized_symbols.sort(
        key=lambda item: (
            item["canonical_name"],
            str(item.get("index_role", "")),
            item["path"],
            int(item.get("start_line", 0)),
            item["chunk_id"],
        )
    )
    _require(symbols == normalized_symbols, "symbol_index.jsonl is not in canonical order")
    frozen_lookup = {
        key: tuple(
            sorted(
                values,
                key=lambda item: (
                    item["canonical_name"],
                    str(item.get("index_role", "")),
                    item["path"],
                    int(item.get("start_line", 0)),
                    item["chunk_id"],
                ),
            )
        )
        for key, values in sorted(symbols_by_lookup.items())
    }
    return LoadedIndex(
        root=root,
        repository_id=repository_id,
        repository_commit=repository_commit,
        corpus_manifest=manifest,
        index_validation=validation,
        chunks=tuple(expected_chunks),
        chunks_by_id=chunks_by_id,
        symbol_records=tuple(normalized_symbols),
        symbols_by_lookup_key=frozen_lookup,
        artifact_hashes=actual_hashes,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FormalPreparationError(message)


def _git_directory(worktree: Path) -> Path:
    marker = worktree / ".git"
    if marker.is_dir():
        return marker.resolve()
    if not marker.is_file():
        raise FormalPreparationError(f"Git metadata is missing: {worktree}")
    line = marker.read_text(encoding="utf-8").strip()
    if not line.startswith("gitdir:"):
        raise FormalPreparationError(f"invalid .git indirection: {marker}")
    target = Path(line.split(":", 1)[1].strip())
    if not target.is_absolute():
        target = marker.parent / target
    return target.resolve()


def _common_git_directory(git_dir: Path) -> Path:
    marker = git_dir / "commondir"
    if not marker.is_file():
        return git_dir
    target = Path(marker.read_text(encoding="utf-8").strip())
    if not target.is_absolute():
        target = git_dir / target
    return target.resolve()


def _read_packed_ref(common_dir: Path, reference: str) -> str | None:
    packed = common_dir / "packed-refs"
    if not packed.is_file():
        return None
    for line in packed.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(("#", "^")):
            continue
        value, name = line.split(" ", 1)
        if name == reference:
            return value.lower()
    return None


def read_git_identity(worktree: Path) -> tuple[str, str]:
    """Read branch and HEAD without executing Git or any other subprocess."""

    git_dir = _git_directory(worktree)
    common_dir = _common_git_directory(git_dir)
    head_text = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
    if head_text.startswith("ref:"):
        reference = head_text.split(":", 1)[1].strip()
        candidates = (git_dir / reference, common_dir / reference)
        commit = next(
            (
                path.read_text(encoding="utf-8").strip().lower()
                for path in candidates
                if path.is_file()
            ),
            None,
        )
        if commit is None:
            commit = _read_packed_ref(common_dir, reference)
        if commit is None:
            raise FormalPreparationError(f"cannot resolve Git reference: {reference}")
        branch = reference.removeprefix("refs/heads/")
    else:
        commit = head_text.lower()
        branch = "DETACHED"
    _require(
        len(commit) == 40 and all(character in "0123456789abcdef" for character in commit),
        f"invalid Git HEAD in {worktree}",
    )
    return branch, commit


def _protocol_metadata(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8")
    patterns = {
        "version": r"^- Protocol version: `([^`]+)`$",
        "status": r"^- Protocol status: (.+)$",
        "execution": r"^- Formal execution status: (.+)$",
    }
    values: dict[str, str] = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match is None:
            raise FormalPreparationError(f"protocol lacks {name} metadata")
        values[name] = match.group(1).strip().strip("`")
    return values["version"], values["status"], values["execution"]


def load_common_config(
    project_root: str | Path,
    path: str | Path = COMMON_CONFIG_PATH,
) -> FormalCommonConfig:
    root = Path(project_root).resolve()
    source = Path(path)
    if not source.is_absolute():
        source = _resolve(root, source, field="common config path")
    raw = _load_json(source)
    _require(
        raw.get("artifact_schema_version") == "rag-retrieval-pipeline-config-v1",
        "unsupported formal retrieval config schema",
    )
    _require(raw.get("version") == "formal-retrieval-pipeline-v1", "formal config version mismatch")
    _require(raw.get("condition_id") == "rag-design-context-v1", "formal condition ID mismatch")
    _require(raw.get("repository_scope") == "multi-repository", "formal config is repository-specific")

    selection = raw.get("selection")
    _require(isinstance(selection, Mapping), "formal selection must be an object")
    _require(selection.get("retrieval_top_k") == 12, "retrieval_top_k must be 12")
    _require(selection.get("fixed_quotas") == {"0": 4, "1": 4, "2": 3, "3": 1}, "formal tier quotas differ")
    _require(selection.get("retrieval_top_k_semantics") == "maximum", "top-k must be a cap")
    _require(selection.get("quota_semantics") == "maximum", "tier quotas must be caps")
    _require(selection.get("fill_requirement") is False, "formal selection must not require quota filling")
    _require(selection.get("per_target_overrides") is False, "per-target override is prohibited")
    _require(selection.get("per_target_override_policy") == "prohibited", "override policy mismatch")
    _require(selection.get("target_count") == 17, "formal target count must be 17")
    _require(raw.get("target_specific_manual_query") is False, "manual target query is prohibited")
    _require(raw.get("target_specific_manual_query_policy") == "prohibited", "manual query policy mismatch")

    context = raw.get("context")
    _require(isinstance(context, Mapping), "formal context config must be an object")
    _require(context.get("budget_tokens") == 6000, "context budget must be 6000")
    _require(context.get("token_counter_version") == "cpp-lexical-token-count-v1", "token counter mismatch")
    _require(context.get("format") == "combined-path-role-v1", "context format mismatch")

    bm25 = raw.get("bm25")
    _require(isinstance(bm25, Mapping), "BM25 config must be an object")
    expected_bm25 = {
        "implementation": "in-repository BM25Okapi",
        "version": "in-repository-bm25-okapi-v1",
        "k1": 1.2,
        "k1_scaled": 1_200_000,
        "b": 0.75,
        "b_scaled": 750_000,
        "score_scale": 1_000_000,
        "candidate_limit": 64,
        "tokenizer_version": "cpp-identifier-path-tokenizer-v1",
    }
    for key, value in expected_bm25.items():
        _require(bm25.get(key) == value, f"BM25 field differs: {key}")

    one_hop = raw.get("one_hop")
    _require(isinstance(one_hop, Mapping), "one-hop config must be an object")
    _require(one_hop.get("maximum_hops") == 1, "maximum hops must be one")
    _require(one_hop.get("candidate_limit") == 128, "one-hop candidate limit mismatch")
    _require(one_hop.get("allowed_relations") == EXPECTED_ALLOWED_RELATIONS, "allowed relation set/order differs")
    _require(
        one_hop.get("version") == "direct-dependency-one-hop-v2-class-interface-method-relations",
        "one-hop version mismatch",
    )
    _require(raw.get("ranking") == EXPECTED_RANKING, "ranking freeze differs")
    _require(raw.get("filtering") == EXPECTED_FILTERING, "filtering freeze differs")
    _require(raw.get("canonical_serialization") == EXPECTED_CANONICAL_SERIALIZATION, "canonical serialization differs")
    stages = raw.get("stages", {})
    for name in (
        "bm25_usage_and_call_site",
        "candidate_filtering",
        "context_serialization",
        "exact_symbol_retrieval",
        "one_hop_expansion",
        "query_extraction",
        "formal_experiment",
    ):
        _require(stages.get(name) is True, f"formal retrieval stage disabled: {name}")
    for name in ("design_generation_llm", "code_regeneration_llm"):
        _require(stages.get(name) is False, f"generation stage enabled: {name}")

    serialized = json.dumps(raw, ensure_ascii=False, sort_keys=True)
    for forbidden in ("yaml-cpp", "external-pilot", "candidate-selection", "failed-preparation"):
        _require(forbidden not in serialized, f"pilot-specific reference in formal config: {forbidden}")

    dependencies = raw.get("dependencies")
    _require(isinstance(dependencies, Mapping), "formal dependencies must be an object")
    for key, value in sorted(dependencies.items()):
        if not key.endswith("_path"):
            continue
        hash_key = key.removesuffix("_path") + "_sha256"
        _require(hash_key in dependencies, f"dependency lacks SHA-256: {key}")
        dependency_path = _resolve(root, value, field=key)
        _verify_hash(dependency_path, dependencies[hash_key], field=key)
    implementation_path = _resolve(
        root, dependencies.get("retrieval_implementation_path"), field="retrieval implementation"
    )
    _require(
        sha256_file(implementation_path) == EXTERNAL_RETRIEVAL_SHA256,
        "external_retrieval.py fixed SHA-256 changed",
    )
    return FormalCommonConfig(
        path=source,
        relative_path=_relative(root, source),
        sha256=sha256_file(source),
        raw=raw,
    )


def _validate_query_validation(
    target_id: str,
    query_path: Path,
    query_sha256: str,
) -> tuple[Path, dict[str, Any]]:
    path = query_path.parent / "query_validation.json"
    raw = _load_json(path)
    _require(raw.get("status") == "pass", f"query validation is not pass: {target_id}")
    _require(raw.get("deterministic") is True, f"query is not deterministic: {target_id}")
    _require(raw.get("independent_build_count") == 2, f"query was not built twice: {target_id}")
    _require(raw.get("target_id") == target_id, f"query validation target mismatch: {target_id}")
    hashes = raw.get("artifact_hashes", {})
    _require(hashes.get("query.json") == query_sha256, f"query validation hash mismatch: {target_id}")
    comparison = raw.get("build_hash_comparison", {}).get("query.json", {})
    _require(comparison.get("match") is True, f"query builds differ: {target_id}")
    _require(comparison.get("build_a_sha256") == query_sha256, f"query build-a hash differs: {target_id}")
    _require(comparison.get("build_b_sha256") == query_sha256, f"query build-b hash differs: {target_id}")
    return path, raw


def _validate_standard_target(raw: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
    for field in STANDARD_PROTECTED_FIELDS:
        _require(raw.get(field) == evidence.get(field), f"protected field changed: {raw.get('target_id')}.{field}")


def _legacy_evidence_map(root: Path, raw: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values = raw.get("legacy_mapping_evidence")
    _require(isinstance(values, list) and values, "legacy mapping evidence is missing")
    result: dict[str, dict[str, Any]] = {}
    for item in values:
        _require(isinstance(item, Mapping), "legacy evidence entry must be an object")
        role = str(item.get("role", ""))
        _require(bool(role) and role not in result, f"invalid duplicate legacy evidence role: {role}")
        path = _resolve(root, item.get("path"), field=f"legacy evidence {role}")
        _verify_hash(path, item.get("sha256"), field=f"legacy evidence {role}")
        result[role] = {"path": path, "raw": _load_json(path) if path.suffix == ".json" else None}
    return result


def _validate_legacy_target(root: Path, raw: Mapping[str, Any]) -> None:
    evidence = _legacy_evidence_map(root, raw)
    required_roles = {
        "run_config",
        "source_metadata",
        "evaluation_manifest",
        "build_result",
        "direct_test_result",
        "full_test_result",
        "ctest_result",
        "generation_script",
        "evaluation_script",
    }
    _require(set(evidence) == required_roles, "legacy evidence role set differs")
    run = evidence["run_config"]["raw"]
    metadata = evidence["source_metadata"]["raw"]
    manifest = evidence["evaluation_manifest"]["raw"]
    build = evidence["build_result"]["raw"]
    direct = evidence["direct_test_result"]["raw"]
    full = evidence["full_test_result"]["raw"]
    ctest = evidence["ctest_result"]["raw"]
    _require(raw.get("repository_name") == metadata.get("repository") == "SSARCandy/ini-cpp", "legacy repository differs")
    _require(raw.get("repository_commit") == metadata.get("repository_commit"), "legacy repository commit differs")
    _require(raw.get("target_name") == metadata.get("target_function") == "INIWriter::write", "legacy target differs")
    _require(raw.get("source_file") == metadata.get("source_file") == "ini/ini.h", "legacy source differs")
    _require(raw.get("source_sha256") == metadata.get("source_sha256"), "legacy source hash differs")
    _require(raw.get("granularity") == metadata.get("target_granularity") == "function_body", "legacy granularity differs")
    _require(raw.get("replacement_scope") == metadata.get("replacement_scope"), "legacy replacement scope differs")
    _require(raw.get("model") == run.get("model"), "legacy model changed")
    _require(raw.get("generation") == run.get("generation"), "legacy generation options changed")
    _require(raw.get("conditions") == run.get("conditions"), "legacy conditions changed")
    evaluation = raw.get("evaluation", {})
    _require(evaluation.get("docker_image") == manifest.get("docker_image"), "legacy Docker image changed")
    _require(evaluation.get("docker_image_id") == manifest.get("docker_image_id"), "legacy Docker image ID changed")
    _require(evaluation.get("expected_direct_tests") == manifest.get("expected_direct_tests"), "legacy direct test count changed")
    _require(evaluation.get("expected_full_tests") == manifest.get("expected_full_tests"), "legacy full test count changed")
    for field, expected in (
        ("configure_command", build["configure"]["command"]),
        ("build_command", build["build"]["command"]),
        ("direct_test_command", direct["command"]),
        ("full_test_command", full["command"]),
        ("ctest_command", ctest["command"]),
    ):
        _require(evaluation.get(field) == expected, f"legacy {field} changed")


def _generation_top_k(raw: Mapping[str, Any]) -> int:
    model = raw.get("model", {})
    if isinstance(model, Mapping) and "top_k" in model:
        return int(model["top_k"])
    generation = raw.get("generation", {})
    if isinstance(generation, Mapping):
        options = generation.get("options", {})
        if isinstance(options, Mapping) and "top_k" in options:
            return int(options["top_k"])
    raise FormalPreparationError(f"generation top_k is missing: {raw.get('target_id')}")


def _validate_query_source_ranges(
    repository_root: Path,
    query: LoadedQuery,
) -> None:
    for source_range in query.source_ranges:
        path = _resolve(
            repository_root,
            source_range["path"],
            field=f"target source {query.target_id}",
        )
        if not path.is_file():
            raise FormalPreparationError(
                f"target source is missing: {query.target_id}/{source_range['path']}"
            )
        raw = path.read_bytes()
        try:
            normalized = (
                raw.decode("utf-8-sig")
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .encode("utf-8")
            )
        except UnicodeDecodeError as exc:
            raise FormalPreparationError(
                f"target source is not UTF-8: {query.target_id}/{source_range['path']}"
            ) from exc
        normalized_hash = sha256_bytes(normalized)
        _require(
            normalized_hash == source_range.get("normalized_source_sha256"),
            f"target normalized source hash differs: {query.target_id}/{source_range['path']}",
        )
        raw_hash = sha256_bytes(raw)
        _require(
            source_range.get("git_blob_sha256") in {raw_hash, normalized_hash},
            f"target Git blob hash differs: {query.target_id}/{source_range['path']}",
        )
        start = int(source_range["start_byte"])
        end = int(source_range["end_byte"])
        _require(
            0 <= start < end <= len(normalized),
            f"target source range is invalid: {query.target_id}/{source_range['path']}",
        )
        _require(
            sha256_bytes(normalized[start:end])
            == source_range.get("normalized_range_sha256"),
            f"target source range hash differs: {query.target_id}/{source_range['path']}",
        )


def load_target_configs(
    project_root: str | Path,
    common: FormalCommonConfig,
    *,
    registry_path: str | Path = TARGET_REGISTRY_PATH,
    target_directory: str | Path = TARGET_CONFIG_DIRECTORY,
    expected_target_count: int = 17,
    require_absent_outputs: bool = True,
) -> tuple[Path, str, tuple[FormalTarget, ...]]:
    root = Path(project_root).resolve()
    registry_source = _resolve(root, registry_path, field="target registry path")
    registry = _load_json(registry_source)
    _require(registry.get("condition_id") == "rag-design-context-v1", "registry condition differs")
    entries = registry.get("targets")
    _require(isinstance(entries, list), "target registry lacks target array")
    _require(len(entries) == expected_target_count, "target registry count mismatch")
    registry_ids = [str(item.get("target_id", "")) for item in entries]
    _require(len(set(registry_ids)) == expected_target_count, "duplicate target ID in registry")
    entry_by_id = {str(item["target_id"]): item for item in entries}

    directory = _resolve(root, target_directory, field="target config directory")
    paths = sorted(directory.glob("*.json"))
    _require(len(paths) == expected_target_count, f"target config count mismatch: expected {expected_target_count}, got {len(paths)}")
    raw_targets = [(path, _load_json(path)) for path in paths]
    target_ids = [str(raw.get("target_id", "")) for _, raw in raw_targets]
    _require(len(set(target_ids)) == expected_target_count, "duplicate target ID")
    _require(set(target_ids) == set(registry_ids), "target ID set differs from registry")
    run_ids = [str(raw.get("run_id", "")) for _, raw in raw_targets]
    _require(all(run_ids) and len(set(run_ids)) == expected_target_count, "duplicate or empty formal run ID")
    output_paths = [str(raw.get("output_directory", "")) for _, raw in raw_targets]
    _require(all(output_paths) and len(set(output_paths)) == expected_target_count, "duplicate or empty formal output path")

    candidate_path = _resolve(root, CANDIDATE_CONFIG_PATH, field="candidate config path")
    try:
        candidate_config = CandidateConfig.load(candidate_path)
    except Exception as exc:
        raise FormalPreparationError(f"candidate config validation failed: {exc}") from exc
    del candidate_config

    index_cache: dict[Path, LoadedIndex] = {}
    targets: list[FormalTarget] = []
    for path, raw in raw_targets:
        target_id = str(raw.get("target_id", ""))
        _require(raw.get("artifact_schema_version") == "rag-formal-target-config-v1", f"target schema differs: {target_id}")
        _require(raw.get("enabled") is False, f"formal target is enabled: {target_id}")
        _require(raw.get("condition_id") == "rag-design-context-v1", f"condition differs: {target_id}")
        expected_run_id = f"rag-v1-formal-{target_id}"
        _require(raw.get("run_id") == expected_run_id, f"run ID differs: {target_id}")
        _require(raw.get("formal_run_id") == expected_run_id, f"formal run ID differs: {target_id}")
        expected_output = f"experiments/rag/{expected_run_id}"
        _require(raw.get("output_directory") == expected_output, f"output path differs: {target_id}")
        _require(raw.get("formal_output_directory") == expected_output, f"formal output path differs: {target_id}")
        _require(raw.get("context_status") == "not_generated", f"context status is pre-populated: {target_id}")
        _require(raw.get("context_sha256") is None, f"context SHA-256 is pre-populated: {target_id}")
        expected_context = f"rag/retrieval/formal/{target_id}/context.txt"
        _require(raw.get("context_path") == expected_context, f"context path differs: {target_id}")
        _require(raw.get("common_formal_config", {}).get("path") == common.relative_path, f"common config path differs: {target_id}")
        _require(raw.get("common_formal_config", {}).get("sha256") == common.sha256, f"common config hash mismatch: {target_id}")
        settings = raw.get("retrieval_settings", {})
        _require(settings.get("retrieval_top_k") == 12, f"target retrieval top-k differs: {target_id}")
        _require(settings.get("context_budget_tokens") == 6000, f"target context budget differs: {target_id}")
        _require(settings.get("category_quotas") == {"0": 4, "1": 4, "2": 3, "3": 1}, f"target quota differs: {target_id}")
        _require(settings.get("per_target_override") is False, f"per-target override is enabled: {target_id}")
        _require(settings.get("target_specific_manual_query") is False, f"manual query is enabled: {target_id}")
        _require(raw.get("input_isolation") == EXPECTED_INPUT_ISOLATION, f"input isolation differs: {target_id}")
        one_shot = raw.get("one_shot_generation_policy", {})
        _require(one_shot.get("design_generation_count") == 1, f"design generation count differs: {target_id}")
        _require(one_shot.get("code_generation_count") == 1, f"code generation count differs: {target_id}")
        for field in ("retry", "automatic_repair", "manual_patch", "overwrite"):
            _require(one_shot.get(field) is False, f"one-shot policy enables {field}: {target_id}")
        _require(_generation_top_k(raw) != int(settings["retrieval_top_k"]), f"model.top_k and retrieval_top_k are conflated: {target_id}")

        context_path = _resolve(root, expected_context, field="planned context path")
        output_path = _resolve(root, expected_output, field="formal output path")
        if require_absent_outputs:
            _require(not context_path.exists(), f"formal context already exists: {target_id}")
            _require(not output_path.exists(), f"formal output directory already exists: {target_id}")
            for marker_name in ("attempt.json", "attempt.marker", "result.json", "failure.json", "failed.json"):
                _require(not (output_path / marker_name).exists(), f"formal marker already exists: {target_id}/{marker_name}")

        evidence = raw.get("non_rag_evidence", {})
        evidence_path = _resolve(root, evidence.get("config_path"), field=f"non-RAG config {target_id}")
        _verify_hash(evidence_path, evidence.get("config_sha256"), field=f"non-RAG config {target_id}")
        metadata_path = _resolve(root, evidence.get("source_metadata_path"), field=f"source metadata {target_id}")
        _verify_hash(metadata_path, evidence.get("source_metadata_sha256"), field=f"source metadata {target_id}")
        registry_entry = entry_by_id[target_id]
        _require(registry_entry.get("source_metadata_path") == evidence.get("source_metadata_path"), f"registry metadata path differs: {target_id}")
        if raw.get("target_kind") == "standard":
            _require(registry_entry.get("target_kind") == "standard", f"registry target kind differs: {target_id}")
            _require(registry_entry.get("frozen_target_config_path") == evidence.get("config_path"), f"registry non-RAG config path differs: {target_id}")
            _validate_standard_target(raw, _load_json(evidence_path))
        elif raw.get("target_kind") == "legacy_function":
            _require(registry_entry.get("target_kind") == "legacy_function", f"registry legacy kind differs: {target_id}")
            _validate_legacy_target(root, raw)
        else:
            raise FormalPreparationError(f"unsupported target kind: {target_id}")

        query_info = raw.get("frozen_query", {})
        query_path = _resolve(root, query_info.get("path"), field=f"frozen query {target_id}")
        query_sha = _verify_hash(query_path, query_info.get("sha256"), field=f"frozen query {target_id}")
        try:
            query = load_query_artifact(query_path)
        except Exception as exc:
            raise FormalPreparationError(f"frozen query validation failed for {target_id}: {exc}") from exc
        _require(query.target_id == target_id, f"query target ID differs: {target_id}")
        _require(query.repository_id == str(raw.get("repository_id")), f"query repository ID differs: {target_id}")
        _require(query.repository_commit == str(raw.get("repository_commit")), f"query repository commit differs: {target_id}")
        query_granularity = "function" if raw.get("target_kind") == "legacy_function" else raw.get("granularity")
        _require(query.granularity == query_granularity, f"query granularity differs: {target_id}")
        _require(query.document.get("target_specific_manual_additions") is False, f"query contains manual additions: {target_id}")
        query_validation_path, _ = _validate_query_validation(target_id, query_path, query_sha)

        for prefix in ("query_config", "retrieval_config", "target_registry"):
            path_key = f"{prefix}_path"
            hash_key = f"{prefix}_sha256"
            if path_key in query.document:
                dependency_path = _resolve(root, query.document[path_key], field=f"query {path_key}")
                _verify_hash(dependency_path, query.document.get(hash_key), field=f"query {path_key}")
        index_validation_path = _resolve(
            root,
            query.document.get("phase1_index_validation_path"),
            field=f"index validation {target_id}",
        )
        index_validation_sha = _verify_hash(
            index_validation_path,
            query.document.get("phase1_index_validation_sha256"),
            field=f"index validation {target_id}",
        )
        index_dir = index_validation_path.parent
        index = index_cache.get(index_dir)
        if index is None:
            try:
                index = load_formal_index_artifacts(index_dir)
            except Exception as exc:
                raise FormalPreparationError(f"index validation failed for {target_id}: {exc}") from exc
            index_cache[index_dir] = index
        _require(index.repository_id == query.repository_id, f"index repository differs: {target_id}")
        _require(index.repository_commit == query.repository_commit, f"index commit differs: {target_id}")
        symbol_path = _resolve(root, query.document.get("phase1_symbol_index_path"), field=f"symbol index {target_id}")
        _require(symbol_path.resolve() == (index_dir / "symbol_index.jsonl").resolve(), f"symbol index path differs: {target_id}")
        _require(
            query.document.get("phase1_symbol_index_sha256")
            == index.artifact_hashes["symbol_index.jsonl"],
            f"symbol index hash differs: {target_id}",
        )

        repository_root = _resolve(root, raw.get("repository_path"), field=f"repository path {target_id}")
        _, repository_head = read_git_identity(repository_root)
        _require(repository_head == query.repository_commit, f"repository HEAD differs: {target_id}")
        _validate_query_source_ranges(repository_root, query)
        range_paths = {str(item["path"]) for item in query.source_ranges}
        expected_source_paths = (
            {str(raw.get("source_file"))}
            if raw.get("target_kind") == "legacy_function"
            else {str(item) for item in raw.get("source_files", [])}
        )
        _require(range_paths == expected_source_paths, f"query source paths differ: {target_id}")

        targets.append(
            FormalTarget(
                path=path,
                relative_path=_relative(root, path),
                sha256=sha256_file(path),
                raw=raw,
                query=query,
                query_validation_path=query_validation_path,
                query_validation_relative_path=_relative(root, query_validation_path),
                query_validation_sha256=sha256_file(query_validation_path),
                index=index,
                index_validation_path=index_validation_path,
                index_validation_relative_path=_relative(root, index_validation_path),
                index_validation_sha256=index_validation_sha,
                repository_root=repository_root,
            )
        )
    return registry_source, sha256_file(registry_source), tuple(sorted(targets, key=lambda item: item.target_id))


def prepare_formal_contexts(
    project_root: str | Path,
    *,
    common_config_path: str | Path = COMMON_CONFIG_PATH,
    registry_path: str | Path = TARGET_REGISTRY_PATH,
    target_directory: str | Path = TARGET_CONFIG_DIRECTORY,
    expected_target_count: int = 17,
    require_absent_outputs: bool = True,
) -> FormalPreparation:
    root = Path(project_root).resolve()
    branch, head = read_git_identity(root)
    common = load_common_config(root, common_config_path)
    registry_source, registry_sha, targets = load_target_configs(
        root,
        common,
        registry_path=registry_path,
        target_directory=target_directory,
        expected_target_count=expected_target_count,
        require_absent_outputs=require_absent_outputs,
    )
    candidate_path = _resolve(root, CANDIDATE_CONFIG_PATH, field="candidate config path")
    try:
        candidate_config = CandidateConfig.load(candidate_path)
    except Exception as exc:
        raise FormalPreparationError(f"candidate config validation failed: {exc}") from exc
    protocol_path = _resolve(root, common.raw["dependencies"]["formal_protocol_path"], field="formal protocol path")
    protocol_version, protocol_status, formal_execution_status = _protocol_metadata(protocol_path)
    _require(protocol_version == "1.0", "protocol version is not 1.0")
    _require(protocol_status == "post-pilot formal freeze", "protocol status differs")
    _require(formal_execution_status == "not started", "formal execution already started")
    return FormalPreparation(
        project_root=root,
        branch=branch,
        project_head=head,
        protocol_version=protocol_version,
        protocol_status=protocol_status,
        formal_execution_status=formal_execution_status,
        common=common,
        candidate_config=candidate_config,
        registry_path=registry_source,
        registry_sha256=registry_sha,
        targets=targets,
    )


def build_plan(preparation: FormalPreparation) -> dict[str, Any]:
    targets = [
        {
            "canonical_output_exists": _resolve(
                preparation.project_root,
                target.raw["context_path"],
                field="planned context",
            ).parent.exists(),
            "config_path": target.relative_path,
            "config_sha256": target.sha256,
            "index_validation_path": target.index_validation_relative_path,
            "index_validation_sha256": target.index_validation_sha256,
            "planned_context_output_path": str(target.raw["context_path"]),
            "query_path": _relative(preparation.project_root, target.query.path),
            "query_sha256": target.query.sha256,
            "query_validation_path": target.query_validation_relative_path,
            "query_validation_sha256": target.query_validation_sha256,
            "repository_commit": target.query.repository_commit,
            "repository_path": str(target.raw["repository_path"]),
            "target_id": target.target_id,
        }
        for target in preparation.targets
    ]
    return {
        "artifact_schema_version": "rag-formal-context-build-plan-v1",
        "branch": preparation.branch,
        "build_or_test_executed": False,
        "common_config_path": preparation.common.relative_path,
        "common_config_sha256": preparation.common.sha256,
        "context_generated": False,
        "context_generated_count": 0,
        "context_sha256_populated_count": 0,
        "docker_executed": False,
        "enabled_target_count": 0,
        "formal_execution_status": preparation.formal_execution_status,
        "formal_target_executed": False,
        "generation_server_contacted": False,
        "llm_call_count": 0,
        "manual_query_count": 0,
        "mode": "plan-only",
        "per_target_override_count": 0,
        "project_head": preparation.project_head,
        "protocol_status": preparation.protocol_status,
        "protocol_version": preparation.protocol_version,
        "retrieval_executed": False,
        "source_replaced": False,
        "status": "ready_for_remote_audit_before_context_generation",
        "target_count": len(targets),
        "targets": targets,
    }


def render_plan_markdown(plan: Mapping[str, Any]) -> str:
    lines = [
        "# Formal RAG context build plan v1",
        "",
        f"- Status: `{plan['status']}`",
        f"- Mode: `{plan['mode']}`",
        f"- Branch: `{plan['branch']}`",
        f"- Project HEAD: `{plan['project_head']}`",
        f"- Protocol: `{plan['protocol_version']}` / `{plan['protocol_status']}`",
        f"- Common config: `{plan['common_config_path']}` (`{plan['common_config_sha256']}`)",
        f"- Targets: `{plan['target_count']}` (enabled: `{plan['enabled_target_count']}`)",
        "- Retrieval/context generation: not executed",
        "- LLM/Ollama/Docker/build/test/source replacement: not executed",
        "",
        "## Planned targets",
        "",
        "| Target | Repository commit | Query SHA-256 | Index validation SHA-256 | Planned context |",
        "|---|---|---|---|---|",
    ]
    for target in plan["targets"]:
        lines.append(
            "| `{target_id}` | `{repository_commit}` | `{query_sha256}` | "
            "`{index_validation_sha256}` | `{planned_context_output_path}` |".format(**target)
        )
    lines.extend(
        [
            "",
            "All canonical outputs are absent. Formal execution has not started; remote audit is required before context generation.",
            "",
        ]
    )
    return "\n".join(lines)
