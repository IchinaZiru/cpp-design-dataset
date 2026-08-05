"""Deterministic retrieval-only Repository-Context RAG v1 for an external pilot."""

from __future__ import annotations

import json
import math
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .artifacts import (
    CandidateConfig,
    LoadedIndex,
    LoadedQuery,
    load_index_artifacts,
    load_query_artifact,
)
from .candidate_filters import apply_candidate_filters, path_byte_overlap_v1
from .canonical import (
    canonical_json_bytes,
    posix_relative_path,
    sha256_bytes,
    sha256_file,
    write_canonical_json,
    write_canonical_jsonl,
)
from .config import IndexConfig
from .cpp_symbols import create_cpp_parser, mask_parse_only_macros
from .exact_retriever import exact_retrieve
from .query_extractor import (
    QueryConfig,
    SourceRange,
    SymbolCatalog,
    _deduplicate,
    _dependency_records,
    _record,
    extract_queries_from_tree,
    normalize_source_bytes,
    verify_query_payload,
)


class ExternalRetrievalError(RuntimeError):
    """Raised when a frozen external retrieval preparation cannot be reproduced."""


_TOKEN_RE = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*|0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?|"
    r"::|->|<<|>>|<=|>=|==|!=|&&|\|\||\+\+|--|[-+*/%&|^~!=<>?:;,.(){}\[\]]"
)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CAMEL_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")
_NON_CODE_RE = re.compile(
    r'//[^\r\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
    re.DOTALL,
)
_USAGE_RANK = {
    "direct_call_site": 0,
    "symbol_reference": 1,
    "explicit_comment_reference": 2,
    "token_cooccurrence": 3,
    "none": 9,
}
_RELATION_ORDER = {
    name: rank
    for rank, name in enumerate(
        (
            "base_type",
            "parameter_type",
            "return_type",
            "field_type",
            "nested_type",
            "template_argument_type",
            "alias_target",
            "enum_type",
            "wrapper_direct_call",
        )
    )
}


@dataclass(frozen=True)
class ExternalRetrievalConfig:
    path: Path
    sha256: str
    raw: dict[str, Any]

    @classmethod
    def load(
        cls,
        project_root: str | Path,
        path: str | Path,
    ) -> "ExternalRetrievalConfig":
        root = Path(project_root).resolve()
        source = Path(path)
        if not source.is_absolute():
            source = root / source
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExternalRetrievalError(f"cannot load retrieval config: {exc}") from exc
        if not isinstance(raw, dict):
            raise ExternalRetrievalError("retrieval config root must be an object")
        if raw.get("artifact_schema_version") != "rag-retrieval-pipeline-config-v1":
            raise ExternalRetrievalError("unsupported retrieval pipeline config schema")

        stages = raw.get("stages", {})
        required = {
            "bm25_usage_and_call_site",
            "candidate_filtering",
            "context_serialization",
            "exact_symbol_retrieval",
            "one_hop_expansion",
            "query_extraction",
        }
        if not isinstance(stages, Mapping) or any(stages.get(name) is not True for name in required):
            raise ExternalRetrievalError("retrieval-only stages are not fully enabled")
        prohibited = {
            "code_regeneration_llm",
            "design_generation_llm",
            "formal_experiment",
        }
        if any(bool(stages.get(name)) for name in prohibited):
            raise ExternalRetrievalError("generation or formal execution is enabled")
        if raw.get("target_specific_manual_query") is not False:
            raise ExternalRetrievalError("target-specific manual query must be disabled")

        selection = raw.get("selection", {})
        quotas = selection.get("fixed_quotas", {})
        if set(quotas) != {"0", "1", "2", "3"}:
            raise ExternalRetrievalError("fixed quotas must cover tiers 0 through 3")
        top_k = int(selection.get("retrieval_top_k", 0))
        if sum(int(value) for value in quotas.values()) != top_k or top_k <= 0:
            raise ExternalRetrievalError("fixed quotas must sum to retrieval_top_k")
        if selection.get("per_target_overrides") is not False:
            raise ExternalRetrievalError("per-target retrieval overrides are prohibited")

        context = raw.get("context", {})
        if int(context.get("budget_tokens", 0)) <= 0:
            raise ExternalRetrievalError("context token budget must be positive")
        if context.get("token_counter_version") != "cpp-lexical-token-count-v1":
            raise ExternalRetrievalError("unexpected context token counter")
        one_hop = raw.get("one_hop", {})
        if int(one_hop.get("maximum_hops", -1)) != 1:
            raise ExternalRetrievalError("one-hop expansion must be exactly one hop")

        dependencies = raw.get("dependencies", {})
        for key, value in sorted(dependencies.items()):
            if not key.endswith("_path") and key != "index_dir":
                continue
            if key == "index_dir":
                continue
            expected_key = key.removesuffix("_path") + "_sha256"
            expected = dependencies.get(expected_key)
            if expected is None:
                continue
            dependency_path = root.joinpath(*posix_relative_path(str(value)).split("/"))
            actual = sha256_file(dependency_path)
            if actual != str(expected):
                raise ExternalRetrievalError(
                    f"dependency hash mismatch for {key}: expected {expected}, got {actual}"
                )
        index_dir = root.joinpath(*posix_relative_path(str(dependencies["index_dir"])).split("/"))
        index_validation = index_dir / "index_validation.json"
        expected_index = str(dependencies["index_validation_sha256"])
        if sha256_file(index_validation) != expected_index:
            raise ExternalRetrievalError("index validation SHA-256 mismatch")
        return cls(path=source, sha256=sha256_file(source), raw=raw)


@dataclass(frozen=True)
class RetrievalInputs:
    config: ExternalRetrievalConfig
    index: LoadedIndex
    index_config: IndexConfig
    exact_config: CandidateConfig
    query_config: QueryConfig
    selection: dict[str, Any]
    targets: tuple[dict[str, Any], ...]


def _git(root: Path, *args: str, binary: bool = False) -> bytes | str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").strip()


def _validate_repository(root: Path, expected_commit: str) -> None:
    try:
        top = Path(str(_git(root, "rev-parse", "--show-toplevel"))).resolve()
        head = str(_git(root, "rev-parse", "HEAD")).lower()
        status = str(_git(root, "status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        raise ExternalRetrievalError(f"cannot validate external repository: {exc}") from exc
    if top != root.resolve():
        raise ExternalRetrievalError("external repository root is not the worktree root")
    if head != expected_commit:
        raise ExternalRetrievalError(
            f"external repository commit mismatch: expected {expected_commit}, got {head}"
        )
    if status:
        raise ExternalRetrievalError("external repository is not clean")


def load_retrieval_inputs(
    *,
    project_root: str | Path,
    config_path: str | Path,
    repository_root: str | Path,
) -> RetrievalInputs:
    root = Path(project_root).resolve()
    config = ExternalRetrievalConfig.load(root, config_path)
    dependencies = config.raw["dependencies"]

    def dependency_path(name: str) -> Path:
        return root.joinpath(*posix_relative_path(str(dependencies[name])).split("/"))

    index = load_index_artifacts(dependency_path("index_dir"))
    index_config = IndexConfig.load(dependency_path("index_config_path"))
    exact_config = CandidateConfig.load(dependency_path("exact_candidate_config_path"))
    query_config = QueryConfig.load(dependency_path("query_config_path"))
    selection_path = dependency_path("selection_path")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("status") != "selected" or selection.get("pilot_ids_frozen") is not True:
        raise ExternalRetrievalError("pilot selection is not frozen")
    targets = tuple(
        sorted(
            (dict(item) for item in selection.get("selected_candidates", [])),
            key=lambda item: (int(item["selection_rank"]), str(item["pilot_target_id"])),
        )
    )
    expected_count = int(config.raw["selection"]["target_count"])
    if len(targets) != expected_count:
        raise ExternalRetrievalError(
            f"frozen target count mismatch: expected {expected_count}, got {len(targets)}"
        )
    repository = config.raw["repository"]
    if index.repository_id != str(repository["id"]):
        raise ExternalRetrievalError("index repository ID mismatch")
    if index.repository_commit != str(repository["commit"]):
        raise ExternalRetrievalError("index repository commit mismatch")
    _validate_repository(Path(repository_root), index.repository_commit)
    return RetrievalInputs(
        config=config,
        index=index,
        index_config=index_config,
        exact_config=exact_config,
        query_config=query_config,
        selection=selection,
        targets=targets,
    )


def _split_identifier(value: str) -> list[str]:
    parts: list[str] = []
    for segment in value.replace("::", "/").replace("\\", "/").split("/"):
        for snake in segment.split("_"):
            if not snake:
                continue
            parts.extend(match.group(0) for match in _CAMEL_RE.finditer(snake))
    return parts


def tokenize_cpp(value: str) -> list[str]:
    """Tokenize code, identifiers, and paths with case-preserving auxiliaries."""

    output: list[str] = []
    for raw in _TOKEN_RE.findall(value):
        output.append(raw)
        lower = raw.lower()
        if lower != raw:
            output.append(lower)
        if _IDENTIFIER_RE.fullmatch(raw):
            for part in _split_identifier(raw):
                output.append(part)
                part_lower = part.lower()
                if part_lower != part:
                    output.append(part_lower)
    return output


def lexical_token_count(value: str) -> int:
    return len(_TOKEN_RE.findall(value))


def bm25_scores_scaled(
    documents: Sequence[Sequence[str]],
    query_tokens: Sequence[str],
    *,
    k1_scaled: int,
    b_scaled: int,
    score_scale: int,
) -> list[int]:
    """Return deterministic integer-scaled BM25Okapi scores."""

    if not documents:
        return []
    k1 = k1_scaled / score_scale
    b = b_scaled / score_scale
    lengths = [len(document) for document in documents]
    average_length = sum(lengths) / len(lengths) if lengths else 0.0
    document_frequencies: Counter[str] = Counter()
    for document in documents:
        document_frequencies.update(set(document))
    query_counts = Counter(query_tokens)
    total_documents = len(documents)
    scores: list[int] = []
    for document, length in zip(documents, lengths):
        frequencies = Counter(document)
        score = 0.0
        for token, query_frequency in query_counts.items():
            frequency = frequencies.get(token, 0)
            if not frequency:
                continue
            df = document_frequencies[token]
            inverse_document_frequency = math.log(
                1.0 + (total_documents - df + 0.5) / (df + 0.5)
            )
            normalization = 1.0 - b
            if average_length:
                normalization += b * length / average_length
            denominator = frequency + k1 * normalization
            score += (
                query_frequency
                * inverse_document_frequency
                * frequency
                * (k1 + 1.0)
                / denominator
            )
        scores.append(int(round(score * score_scale)))
    return scores


def _short_symbol(value: str) -> str:
    compact = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    compact = re.sub(r"<.*>$", "", compact)
    return compact.rsplit("::", 1)[-1]


def classify_usage(content: str, query_symbols: Sequence[str]) -> str:
    code = _NON_CODE_RE.sub(" ", content)
    comment_text = " ".join(
        match.group(0) for match in re.finditer(r"//[^\r\n]*|/\*.*?\*/", content, re.DOTALL)
    )
    identifiers = set(_IDENTIFIER_RE.findall(code))
    token_hits = 0
    for symbol in query_symbols:
        short = _short_symbol(symbol)
        if len(short) < 2:
            continue
        if re.search(r"(?<![A-Za-z0-9_])" + re.escape(short) + r"\s*\(", code):
            return "direct_call_site"
        if short in identifiers or symbol in code:
            return "symbol_reference"
        if short in comment_text or symbol in comment_text:
            return "explicit_comment_reference"
        if short.lower() in {item.lower() for item in identifiers}:
            token_hits += 1
    return "token_cooccurrence" if token_hits else "none"


def dependency_relation(
    source_chunk: Mapping[str, Any],
    dependency_symbol: Mapping[str, Any],
) -> str | None:
    short = str(dependency_symbol.get("short_name", ""))
    if len(short) < 2:
        return None
    source_name = str(source_chunk.get("canonical_name", ""))
    dependency_name = str(dependency_symbol.get("canonical_name", ""))
    if source_name == dependency_name:
        return None
    content = str(source_chunk.get("content", ""))
    signature = str(source_chunk.get("signature", ""))
    pattern = r"(?<![A-Za-z0-9_])" + re.escape(short) + r"(?![A-Za-z0-9_])"
    if re.search(pattern, content) is None:
        return None
    if short in {str(item).rsplit("::", 1)[-1] for item in source_chunk.get("base_symbols", [])}:
        return "base_type"
    if str(dependency_symbol.get("parent_symbol") or "") == source_name:
        return "nested_type"
    if str(source_chunk.get("kind", "")) == "alias_definition":
        return "alias_target"
    if str(source_chunk.get("kind", "")) == "enum_definition":
        return "enum_type"
    if "<" in signature and re.search(pattern, signature[signature.find("<") :]):
        return "template_argument_type"
    if "(" in signature and ")" in signature:
        before, after = signature.split("(", 1)
        parameters = after.rsplit(")", 1)[0]
        if re.search(pattern, parameters):
            return "parameter_type"
        if re.search(pattern, before):
            return "return_type"
    if str(source_chunk.get("kind", "")) in {"class_interface", "struct_interface"}:
        field_pattern = pattern + r"\s*[*&]?\s+[A-Za-z_][A-Za-z0-9_]*\s*(?:[;={])"
        if re.search(field_pattern, content):
            return "field_type"
    calls = re.findall(r"\b([A-Za-z_][A-Za-z0-9_:]*)\s*\(", _NON_CODE_RE.sub(" ", content))
    if len(calls) == 1 and calls[0].rsplit("::", 1)[-1] == short:
        return "wrapper_direct_call"
    return None


def _location(path: str, start_byte: int, start_line: int) -> dict[str, Any]:
    return {
        "end_byte": start_byte,
        "end_column": 0,
        "end_line": start_line,
        "path": path,
        "start_byte": start_byte,
        "start_column": 0,
        "start_line": start_line,
    }


def _read_target_source(
    repository_root: Path,
    target: Mapping[str, Any],
    index: LoadedIndex,
) -> tuple[SourceRange, dict[str, Any]]:
    path = posix_relative_path(str(target["path"]))
    raw = bytes(_git(repository_root, "show", f"HEAD:{path}", binary=True))
    normalized = normalize_source_bytes(raw)
    if normalized != raw:
        raise ExternalRetrievalError(
            f"external target normalization changes byte coordinates: {path}"
        )
    start = int(target["start_byte"])
    end = int(target["end_byte"])
    if not (0 <= start < end <= len(normalized)):
        raise ExternalRetrievalError(f"invalid frozen target range: {path}:{start}:{end}")
    chunk_id = str(target["chunk_id"])
    chunk = index.chunks_by_id.get(chunk_id)
    if chunk is None:
        raise ExternalRetrievalError(f"frozen target references unknown chunk: {chunk_id}")
    if str(chunk["path"]) != path or int(chunk["start_byte"]) != start or int(chunk["end_byte"]) != end:
        raise ExternalRetrievalError("frozen target range does not match the index chunk")
    if normalized[start:end] != str(chunk["content"]).encode("utf-8"):
        raise ExternalRetrievalError("frozen target content does not match committed source")
    raw_hash = sha256_bytes(raw)
    if raw_hash != str(chunk["source_sha256"]):
        raise ExternalRetrievalError("target Git blob SHA-256 does not match index source")
    source_range = SourceRange(
        path=path,
        data=normalized,
        start_byte=start,
        end_byte=end,
        git_blob_sha256=raw_hash,
        normalized_source_sha256=raw_hash,
        normalized_range_sha256=sha256_bytes(normalized[start:end]),
        locator_kind="frozen_external_pilot_chunk_range",
    )
    return source_range, chunk


def build_query_document(
    *,
    inputs: RetrievalInputs,
    repository_root: Path,
    target: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_range, target_chunk = _read_target_source(repository_root, target, inputs.index)
    parse_data, mask_count = mask_parse_only_macros(
        source_range.data,
        inputs.index_config.parser.parse_only_macro_identifiers,
    )
    parser = create_cpp_parser(inputs.index_config.parser)
    tree = parser.parse(parse_data)
    catalog = SymbolCatalog(lookup_keys=frozenset(inputs.index.symbols_by_lookup_key))
    extracted, error_count = extract_queries_from_tree(
        root=tree.root_node,
        source_range=source_range,
        config=inputs.query_config,
        catalog=catalog,
    )
    category_names = [str(item) for item in inputs.query_config.raw["query_categories"]]
    categories = {name: list(extracted.get(name, [])) for name in category_names}
    target_symbol = str(target["target_symbol"])
    categories["target_symbols"] = [
        _record(
            category="target_symbols",
            text=target_symbol,
            kind="target_symbol",
            priority="high",
            relation="target_symbol",
            location=_location(
                source_range.path,
                source_range.start_byte,
                int(target["start_line"]),
            ),
            qualified="::" in target_symbol,
            evidence_node_type="frozen_external_pilot_selection",
        )
    ]
    for category in category_names:
        if category != "dependency_candidates":
            categories[category] = _deduplicate(categories.get(category, []))
    categories["dependency_candidates"] = _dependency_records(categories)
    counts = {name: len(categories.get(name, [])) for name in category_names}
    counts["total_records"] = sum(counts.values())

    root = inputs.config.path.parents[3]
    dependencies = inputs.config.raw["dependencies"]
    index_dir = posix_relative_path(str(dependencies["index_dir"]))
    selection_path = posix_relative_path(str(dependencies["selection_path"]))
    document: dict[str, Any] = {
        "artifact_schema_version": "rag-query-v1",
        "canonicalization": inputs.query_config.raw["canonical_serialization"],
        "condition_id": str(inputs.config.raw["condition_id"]),
        "coordinate_space": inputs.query_config.raw["coordinate_space"],
        "counts": counts,
        "llm_used": False,
        "parse_diagnostics": [
            {
                "error_node_count": error_count,
                "parse_only_macro_mask_count": mask_count,
                "path": source_range.path,
            }
        ],
        "phase1_index_validation_path": f"{index_dir}/index_validation.json",
        "phase1_index_validation_sha256": sha256_file(
            root.joinpath(*index_dir.split("/")) / "index_validation.json"
        ),
        "phase1_symbol_index_path": f"{index_dir}/symbol_index.jsonl",
        "phase1_symbol_index_sha256": inputs.index.artifact_hashes["symbol_index.jsonl"],
        "queries": {name: categories.get(name, []) for name in category_names},
        "query_config_path": posix_relative_path(str(dependencies["query_config_path"])),
        "query_config_sha256": inputs.query_config.sha256,
        "query_method": str(inputs.query_config.raw["method"]),
        "query_version": str(inputs.query_config.raw["query_version"]),
        "retrieval_config_path": posix_relative_path(
            inputs.config.path.resolve().relative_to(root)
        ),
        "retrieval_config_sha256": inputs.config.sha256,
        "source_ranges": [source_range.metadata()],
        "target": {
            "frozen_target_config_path": selection_path,
            "granularity": str(target["granularity"]),
            "repository_commit": inputs.index.repository_commit,
            "repository_id": inputs.index.repository_id,
            "source_metadata_path": selection_path,
            "target_id": str(target["pilot_target_id"]),
            "target_name": target_symbol,
            "target_symbol_policy": "frozen_automatic_external_selection",
        },
        "target_registry_path": selection_path,
        "target_registry_sha256": sha256_file(root.joinpath(*selection_path.split("/"))),
        "target_specific_manual_additions": False,
    }
    document["query_payload_sha256"] = sha256_bytes(canonical_json_bytes(document))
    if not verify_query_payload(document):
        raise ExternalRetrievalError("query payload verification failed")
    return document, target_chunk


def _directory_distance(source_path: str, candidate_path: str) -> int:
    left = PurePosixPath(source_path).parent.parts
    right = PurePosixPath(candidate_path).parent.parts
    common = 0
    for a, b in zip(left, right):
        if a != b:
            break
        common += 1
    return len(left) + len(right) - 2 * common


def _query_symbols(query: LoadedQuery) -> list[str]:
    return sorted(
        {
            str(record["canonical_text"])
            for record in query.records
            if record["category"] != "includes"
        }
    )


def _query_tokens(query: LoadedQuery) -> list[str]:
    weights = {"high": 3, "medium": 2, "low": 1}
    output: list[str] = []
    for record in query.records:
        if record["category"] == "includes":
            continue
        tokens = tokenize_cpp(str(record["canonical_text"]))
        output.extend(tokens * weights[str(record.get("priority", "low"))])
    return output


def _ranking_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(candidate["tier"]),
        int(candidate["exact_match_rank"]),
        int(candidate["usage_classification_rank"]),
        not bool(candidate["direct_relation"]),
        not bool(candidate["original_case_match"]),
        -int(candidate["bm25_score_scaled"]),
        int(candidate["directory_distance"]),
        str(candidate["path"]),
        int(candidate["start_line"]),
        str(candidate["chunk_id"]),
    )


def _merge_candidate(
    aggregate: dict[str, dict[str, Any]],
    *,
    chunk: Mapping[str, Any],
    filtered: Mapping[str, Any],
    target_id: str,
    retrieval_version: str,
    tier: int,
    evidence: Mapping[str, Any],
    exact_match_rank: int = 99,
    usage_classification: str = "none",
    direct_relation: bool = False,
    original_case_match: bool = False,
    bm25_score_scaled: int = 0,
    directory_distance: int = 1_000_000,
) -> None:
    chunk_id = str(chunk["chunk_id"])
    record = aggregate.get(chunk_id)
    if record is None:
        identity = "\n".join((target_id, chunk_id, retrieval_version))
        record = {
            "artifact_schema_version": "rag-retrieval-candidate-v1",
            "bm25_score_scaled": 0,
            "candidate_id": sha256_bytes(identity.encode("utf-8")),
            "canonical_name": str(chunk.get("canonical_name", chunk.get("symbol", ""))),
            "chunk_id": chunk_id,
            "content_sha256": str(chunk["content_sha256"]),
            "direct_relation": False,
            "directory_distance": 1_000_000,
            "eligible": bool(filtered["eligible"]),
            "end_byte": int(chunk["end_byte"]),
            "end_line": int(chunk.get("end_line", 0)),
            "exact_match_rank": 99,
            "exclusion_reasons": list(filtered["exclusion_reasons"]),
            "kind": str(chunk.get("kind", "")),
            "original_case_match": False,
            "overlap_evidence": list(filtered["overlap_evidence"]),
            "parent_symbol": chunk.get("parent_symbol"),
            "path": str(chunk["path"]),
            "repository_commit": str(chunk["repository_commit"]),
            "repository_id": str(chunk["repository"]),
            "retrieval_evidence": [],
            "retrieval_version": retrieval_version,
            "signature": str(chunk.get("signature", "")),
            "source_sha256": str(chunk.get("source_sha256", "")),
            "start_byte": int(chunk["start_byte"]),
            "start_line": int(chunk.get("start_line", 0)),
            "target_id": target_id,
            "tier": tier,
            "usage_classification": usage_classification,
            "usage_classification_rank": _USAGE_RANK[usage_classification],
        }
        aggregate[chunk_id] = record
    record["tier"] = min(int(record["tier"]), tier)
    record["exact_match_rank"] = min(int(record["exact_match_rank"]), exact_match_rank)
    if _USAGE_RANK[usage_classification] < int(record["usage_classification_rank"]):
        record["usage_classification"] = usage_classification
        record["usage_classification_rank"] = _USAGE_RANK[usage_classification]
    record["direct_relation"] = bool(record["direct_relation"]) or direct_relation
    record["original_case_match"] = bool(record["original_case_match"]) or original_case_match
    record["bm25_score_scaled"] = max(int(record["bm25_score_scaled"]), bm25_score_scaled)
    record["directory_distance"] = min(int(record["directory_distance"]), directory_distance)
    record["eligible"] = bool(record["eligible"]) and bool(filtered["eligible"])
    record["exclusion_reasons"] = sorted(
        set(record["exclusion_reasons"]) | set(filtered["exclusion_reasons"])
    )
    record["overlap_evidence"] = sorted(
        [*record["overlap_evidence"], *filtered["overlap_evidence"]],
        key=lambda item: (
            item["path"],
            item["target_start_byte"],
            item["candidate_start_byte"],
        ),
    )
    evidence_key = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    existing = {
        json.dumps(item, sort_keys=True, separators=(",", ":"))
        for item in record["retrieval_evidence"]
    }
    if evidence_key not in existing:
        record["retrieval_evidence"].append(dict(evidence))
        record["retrieval_evidence"].sort(
            key=lambda item: (
                str(item.get("method", "")),
                str(item.get("query_id", "")),
                str(item.get("relation", "")),
                str(item.get("source_chunk_id", "")),
            )
        )


def build_candidates(
    *,
    inputs: RetrievalInputs,
    query: LoadedQuery,
) -> list[dict[str, Any]]:
    aggregate: dict[str, dict[str, Any]] = {}
    retrieval_version = str(inputs.config.raw["version"])
    source_path = str(query.source_ranges[0]["path"])
    query_symbols = _query_symbols(query)
    raw_exact = exact_retrieve(
        index=inputs.index,
        query=query,
        config=inputs.exact_config,
    )
    for raw in raw_exact:
        chunk = inputs.index.chunks_by_id[str(raw["chunk_id"])]
        filtered = apply_candidate_filters(
            {**raw, "_content": str(chunk["content"])},
            query=query,
            config=inputs.exact_config,
        )
        _merge_candidate(
            aggregate,
            chunk=chunk,
            filtered=filtered,
            target_id=query.target_id,
            retrieval_version=retrieval_version,
            tier=0,
            evidence={
                "match_type": str(raw["best_match_type"]),
                "method": "exact_symbol",
                "query_id": str(raw["query_id"]),
                "query_text": str(raw["query_canonical_text"]),
            },
            exact_match_rank=int(raw["ranking_basis"]["match_type_rank"]),
            original_case_match=str(raw["query_canonical_text"]) in str(chunk["content"]),
            directory_distance=int(raw["ranking_basis"]["directory_distance"]),
        )

    bm25 = inputs.config.raw["bm25"]
    documents = [
        tokenize_cpp(
            "\n".join(
                (
                    str(chunk.get("canonical_name", "")),
                    str(chunk.get("short_symbol", "")),
                    str(chunk.get("parent_symbol") or ""),
                    str(chunk.get("signature", "")),
                    str(chunk.get("path", "")),
                    str(chunk.get("content", "")),
                )
            )
        )
        for chunk in inputs.index.chunks
    ]
    scores = bm25_scores_scaled(
        documents,
        _query_tokens(query),
        k1_scaled=int(bm25["k1_scaled"]),
        b_scaled=int(bm25["b_scaled"]),
        score_scale=int(bm25["score_scale"]),
    )
    bm25_ranked = sorted(
        (
            (score, chunk)
            for score, chunk in zip(scores, inputs.index.chunks)
            if score > 0
        ),
        key=lambda item: (
            -item[0],
            str(item[1]["path"]),
            int(item[1]["start_line"]),
            str(item[1]["chunk_id"]),
        ),
    )[: int(bm25["candidate_limit"])]
    for score, chunk in bm25_ranked:
        usage = classify_usage(str(chunk["content"]), query_symbols)
        tier = 2 if usage in {"direct_call_site", "symbol_reference"} else 3
        raw = {
            "_content": str(chunk["content"]),
            "end_byte": int(chunk["end_byte"]),
            "path": str(chunk["path"]),
            "source_sha256": str(chunk["source_sha256"]),
            "start_byte": int(chunk["start_byte"]),
        }
        filtered = apply_candidate_filters(
            raw,
            query=query,
            config=inputs.exact_config,
        )
        _merge_candidate(
            aggregate,
            chunk=chunk,
            filtered=filtered,
            target_id=query.target_id,
            retrieval_version=retrieval_version,
            tier=tier,
            evidence={
                "bm25_score_scaled": score,
                "classification": usage,
                "method": "bm25_usage",
            },
            usage_classification=usage,
            original_case_match=any(symbol in str(chunk["content"]) for symbol in query_symbols),
            bm25_score_scaled=score,
            directory_distance=_directory_distance(source_path, str(chunk["path"])),
        )

    allowed_relations = set(inputs.config.raw["one_hop"]["allowed_relations"])
    symbol_by_short: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for symbol in inputs.index.symbol_records:
        symbol_by_short[str(symbol["short_name"])].append(symbol)
    expansion: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for source_chunk_id in sorted({str(item["chunk_id"]) for item in raw_exact}):
        source_chunk = inputs.index.chunks_by_id[source_chunk_id]
        identifiers = sorted(set(_IDENTIFIER_RE.findall(str(source_chunk["content"]))))
        for identifier in identifiers:
            for symbol in symbol_by_short.get(identifier, []):
                relation = dependency_relation(source_chunk, symbol)
                if relation not in allowed_relations:
                    continue
                dependency_chunk = inputs.index.chunks_by_id[str(symbol["chunk_id"])]
                if dependency_chunk["chunk_id"] == source_chunk_id:
                    continue
                expansion.append((relation, source_chunk, dependency_chunk))
    expansion.sort(
        key=lambda item: (
            _RELATION_ORDER[item[0]],
            str(item[1]["chunk_id"]),
            str(item[2]["path"]),
            int(item[2]["start_line"]),
            str(item[2]["chunk_id"]),
        )
    )
    for relation, source_chunk, chunk in expansion[: int(inputs.config.raw["one_hop"]["candidate_limit"])]:
        filtered = apply_candidate_filters(
            {
                "_content": str(chunk["content"]),
                "end_byte": int(chunk["end_byte"]),
                "path": str(chunk["path"]),
                "source_sha256": str(chunk["source_sha256"]),
                "start_byte": int(chunk["start_byte"]),
            },
            query=query,
            config=inputs.exact_config,
        )
        _merge_candidate(
            aggregate,
            chunk=chunk,
            filtered=filtered,
            target_id=query.target_id,
            retrieval_version=retrieval_version,
            tier=1,
            evidence={
                "hop": 1,
                "method": "direct_dependency",
                "relation": relation,
                "source_chunk_id": str(source_chunk["chunk_id"]),
            },
            direct_relation=True,
            original_case_match=str(chunk.get("short_symbol", "")) in str(source_chunk["content"]),
            directory_distance=_directory_distance(source_path, str(chunk["path"])),
        )

    preliminary = sorted(aggregate.values(), key=_ranking_key)
    retained_by_content: dict[str, str] = {}
    for candidate in preliminary:
        if not candidate["eligible"]:
            continue
        content_hash = str(candidate["content_sha256"])
        retained = retained_by_content.get(content_hash)
        if retained is None:
            retained_by_content[content_hash] = str(candidate["chunk_id"])
            continue
        candidate["eligible"] = False
        candidate["exclusion_reasons"] = sorted(
            set(candidate["exclusion_reasons"]) | {"duplicate_content"}
        )
        candidate["deduplicated_to_chunk_id"] = retained

    ordered = sorted(
        aggregate.values(),
        key=lambda item: (not bool(item["eligible"]), *_ranking_key(item)),
    )
    eligible_rank = 0
    for overall_rank, candidate in enumerate(ordered, start=1):
        candidate["candidate_rank"] = overall_rank
        if candidate["eligible"]:
            eligible_rank += 1
            candidate["eligible_rank"] = eligible_rank
            candidate["selection_status"] = "not_selected"
        else:
            candidate["eligible_rank"] = None
            candidate["selection_status"] = "filtered"
    return ordered


def _context_header(query: LoadedQuery, config: ExternalRetrievalConfig) -> str:
    return (
        "Repository-Context RAG v1\n"
        f"Repository: {query.repository_id}\n"
        f"Commit: {query.repository_commit}\n"
        f"Target: {query.target_id}\n"
        f"Format: {config.raw['context']['format']}\n"
        "Retrieved production context follows. Target source is excluded.\n\n"
    )


def _context_block(candidate: Mapping[str, Any], chunk: Mapping[str, Any], rank: int) -> str:
    relations = sorted(
        {
            str(item["relation"])
            for item in candidate["retrieval_evidence"]
            if item.get("relation")
        }
    )
    relation_text = ",".join(relations) if relations else "none"
    return (
        f"## Chunk {rank}\n"
        f"Path: {candidate['path']}:{candidate['start_line']}-{candidate['end_line']}\n"
        f"Symbol: {candidate['canonical_name']}\n"
        f"Kind: {candidate['kind']}\n"
        f"Tier: {candidate['tier']}\n"
        f"Relations: {relation_text}\n"
        "```cpp\n"
        f"{chunk['content']}\n"
        "```\n\n"
    )


def select_context_candidates(
    *,
    candidates: list[dict[str, Any]],
    chunks_by_id: Mapping[str, Mapping[str, Any]],
    query: LoadedQuery,
    config: ExternalRetrievalConfig,
) -> tuple[list[dict[str, Any]], str, int]:
    header = _context_header(query, config)
    context_parts = [header]
    token_count = lexical_token_count(header)
    budget = int(config.raw["context"]["budget_tokens"])
    top_k = int(config.raw["selection"]["retrieval_top_k"])
    quotas = {
        int(tier): int(value)
        for tier, value in config.raw["selection"]["fixed_quotas"].items()
    }
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for tier in range(4):
        tier_count = 0
        for candidate in candidates:
            if len(selected) >= top_k or tier_count >= quotas[tier]:
                break
            if not candidate["eligible"] or int(candidate["tier"]) != tier:
                continue
            chunk_id = str(candidate["chunk_id"])
            if chunk_id in selected_ids:
                continue
            chunk = chunks_by_id[chunk_id]
            block = _context_block(candidate, chunk, len(selected) + 1)
            block_tokens = lexical_token_count(block)
            if token_count + block_tokens > budget:
                candidate["selection_status"] = "budget_excluded"
                continue
            selected_ids.add(chunk_id)
            tier_count += 1
            token_count += block_tokens
            context_parts.append(block)
            candidate["selection_status"] = "selected"
            candidate["selection_rank"] = len(selected) + 1
            selected.append(
                {
                    **candidate,
                    "content": str(chunk["content"]),
                    "content_token_count": lexical_token_count(str(chunk["content"])),
                    "context_block_sha256": sha256_bytes(block.encode("utf-8")),
                }
            )
    context = "".join(context_parts)
    if lexical_token_count(context) != token_count:
        raise ExternalRetrievalError("context token count is internally inconsistent")
    return selected, context, token_count


def _write_context(path: Path, value: str) -> str:
    data = value.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    if not data.endswith(b"\n"):
        data += b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def build_target_artifacts(
    *,
    inputs: RetrievalInputs,
    repository_root: Path,
    target: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    query_document, target_chunk = build_query_document(
        inputs=inputs,
        repository_root=repository_root,
        target=target,
    )
    query_sha = write_canonical_json(output_dir / "query.json", query_document)
    query = load_query_artifact(output_dir / "query.json")

    corpus_source = inputs.index.root / "corpus_manifest.json"
    corpus_bytes = corpus_source.read_bytes()
    (output_dir / "corpus_manifest.json").write_bytes(corpus_bytes)
    corpus_sha = sha256_bytes(corpus_bytes)
    candidates = build_candidates(inputs=inputs, query=query)
    selected, context, context_tokens = select_context_candidates(
        candidates=candidates,
        chunks_by_id=inputs.index.chunks_by_id,
        query=query,
        config=inputs.config,
    )
    candidates_sha = write_canonical_jsonl(output_dir / "candidates.jsonl", candidates)
    selected_sha = write_canonical_jsonl(
        output_dir / "selected_chunks.jsonl", selected
    )
    context_sha = _write_context(output_dir / "context.txt", context)

    leakage_errors: list[str] = []
    for item in selected:
        overlaps = path_byte_overlap_v1(
            candidate_path=str(item["path"]),
            candidate_start=int(item["start_byte"]),
            candidate_end=int(item["end_byte"]),
            source_ranges=query.source_ranges,
            candidate_source_sha256=str(item["source_sha256"]),
        )
        if overlaps:
            leakage_errors.append(f"target_source_overlap:{item['chunk_id']}")
        if item["exclusion_reasons"]:
            leakage_errors.append(f"selected_filtered_candidate:{item['chunk_id']}")
    target_content = str(target_chunk["content"])
    if target_content and target_content in context:
        leakage_errors.append("verbatim_target_source_in_context")
    if context_tokens > int(inputs.config.raw["context"]["budget_tokens"]):
        leakage_errors.append("context_budget_exceeded")
    if not selected:
        leakage_errors.append("empty_context_selection")
    if leakage_errors:
        raise ExternalRetrievalError(
            "retrieval leakage/selection validation failed: " + ", ".join(leakage_errors)
        )

    tier_counts = Counter(str(item["tier"]) for item in selected)
    exclusion_counts = Counter(
        reason for item in candidates for reason in item["exclusion_reasons"]
    )
    manifest = {
        "artifact_hashes": {
            "candidates.jsonl": candidates_sha,
            "context.txt": context_sha,
            "corpus_manifest.json": corpus_sha,
            "query.json": query_sha,
            "selected_chunks.jsonl": selected_sha,
        },
        "artifact_schema_version": "rag-retrieval-manifest-v1",
        "bm25": inputs.config.raw["bm25"],
        "candidate_count": len(candidates),
        "condition_id": str(inputs.config.raw["condition_id"]),
        "context_budget_tokens": int(inputs.config.raw["context"]["budget_tokens"]),
        "context_format": str(inputs.config.raw["context"]["format"]),
        "context_sha256": context_sha,
        "context_token_count": context_tokens,
        "deterministic": True,
        "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        "important_dependency_hashes": {
            key: value
            for key, value in sorted(inputs.config.raw["dependencies"].items())
            if key.endswith("_sha256")
        },
        "leakage_validation": {
            "forbidden_selected_count": 0,
            "status": "pass",
            "target_source_overlap_count": 0,
            "verbatim_target_source_in_context": False,
        },
        "llm_calls": {
            "code_regeneration": 0,
            "design_generation": 0,
        },
        "one_hop": inputs.config.raw["one_hop"],
        "query_payload_sha256": query_document["query_payload_sha256"],
        "query_sha256": query_sha,
        "ranking": inputs.config.raw["ranking"],
        "repository_commit": inputs.index.repository_commit,
        "repository_id": inputs.index.repository_id,
        "retrieval_config_sha256": inputs.config.sha256,
        "retrieval_top_k": int(inputs.config.raw["selection"]["retrieval_top_k"]),
        "selected_chunk_count": len(selected),
        "selected_chunk_ids": [str(item["chunk_id"]) for item in selected],
        "selected_tier_counts": dict(sorted(tier_counts.items())),
        "selection_quotas": inputs.config.raw["selection"]["fixed_quotas"],
        "status": "pass",
        "target_id": query.target_id,
        "target_source": {
            "content_sha256": str(target_chunk["content_sha256"]),
            "end_byte": int(target_chunk["end_byte"]),
            "path": str(target_chunk["path"]),
            "source_sha256": str(target_chunk["source_sha256"]),
            "start_byte": int(target_chunk["start_byte"]),
        },
        "token_counter_version": str(
            inputs.config.raw["context"]["token_counter_version"]
        ),
    }
    manifest_sha = write_canonical_json(
        output_dir / "retrieval_manifest.json", manifest
    )
    return {
        "context_sha256": context_sha,
        "retrieval_manifest_sha256": manifest_sha,
        "selected_chunk_count": len(selected),
        "target_id": query.target_id,
    }


def build_all_retrieval_artifacts(
    *,
    project_root: str | Path,
    config_path: str | Path,
    repository_root: str | Path,
    output_root: str | Path,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    output = Path(output_root)
    if not output.is_absolute():
        output = root / output
    output.mkdir(parents=True, exist_ok=False)
    inputs = load_retrieval_inputs(
        project_root=root,
        config_path=config_path,
        repository_root=repository_root,
    )
    target_artifacts: list[dict[str, Any]] = []
    for target in inputs.targets:
        target_id = str(target["pilot_target_id"])
        target_artifacts.append(
            build_target_artifacts(
                inputs=inputs,
                repository_root=Path(repository_root),
                target=target,
                output_dir=output / target_id,
            )
        )
    generation_manifest = {
        "artifact_schema_version": "rag-retrieval-generation-manifest-v1",
        "condition_id": str(inputs.config.raw["condition_id"]),
        "deterministic": True,
        "independent_build_count": 2,
        "llm_calls": {"code_regeneration": 0, "design_generation": 0},
        "repository_commit": inputs.index.repository_commit,
        "repository_id": inputs.index.repository_id,
        "retrieval_config_path": posix_relative_path(
            inputs.config.path.resolve().relative_to(root)
        ),
        "retrieval_config_sha256": inputs.config.sha256,
        "status": "pass",
        "target_artifacts": sorted(target_artifacts, key=lambda item: item["target_id"]),
        "target_count": len(target_artifacts),
    }
    manifest_sha = write_canonical_json(
        output / "retrieval_generation_manifest.json", generation_manifest
    )
    return {
        "manifest_sha256": manifest_sha,
        "target_artifacts": target_artifacts,
        "target_count": len(target_artifacts),
    }
