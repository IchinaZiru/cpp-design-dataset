"""Deterministic exact-symbol retrieval over Phase 1 artifacts."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Mapping

from .artifacts import CandidateConfig, LoadedIndex, LoadedQuery
from .canonical import posix_relative_path


_MATCH_TYPE_RANK = {
    "exact_qualified_name": 0,
    "exact_parent_symbol_and_method": 1,
    "resolved_include_path_and_short_name": 2,
    "exact_short_name": 3,
}
_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _canonical(text: str) -> str:
    compact = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    compact = re.sub(r"\s*::\s*", "::", compact)
    compact = re.sub(r"\s*->\s*", "->", compact)
    compact = re.sub(r"\s*\.\s*", ".", compact)
    return compact.lstrip(":")


def _without_templates(text: str) -> str:
    return re.sub(r"<.*>$", "", text)


def _short_name(text: str) -> str:
    value = _canonical(text)
    value = value.rsplit("::", 1)[-1]
    value = value.rsplit("->", 1)[-1]
    value = value.rsplit(".", 1)[-1]
    return _without_templates(value).strip()


def _include_matches_path(include: str, path: str) -> bool:
    include_path = posix_relative_path(include)
    candidate_path = posix_relative_path(path)
    if candidate_path == include_path or candidate_path.endswith("/" + include_path):
        return True
    include_pure = PurePosixPath(include_path)
    if len(include_pure.parts) != 1:
        return False
    return PurePosixPath(candidate_path).name == include_pure.name


def _include_relation(query: LoadedQuery, path: str) -> bool:
    return any(_include_matches_path(include, path) for include in query.includes)


def _directory_distance(query_record: Mapping[str, Any], candidate_path: str) -> int:
    location = query_record.get("location")
    if not isinstance(location, Mapping) or not location.get("path"):
        return 1_000_000
    try:
        source = PurePosixPath(posix_relative_path(str(location["path"]))).parent.parts
        candidate = PurePosixPath(posix_relative_path(candidate_path)).parent.parts
    except ValueError:
        return 1_000_000
    common = 0
    for left, right in zip(source, candidate):
        if left != right:
            break
        common += 1
    return (len(source) - common) + (len(candidate) - common)


def _parent_namespace_match(query_text: str, symbol: Mapping[str, Any]) -> bool:
    canonical = _canonical(query_text)
    if "::" not in canonical:
        return False
    query_parent = canonical.rsplit("::", 1)[0]
    symbol_parent = str(symbol.get("parent_symbol") or "")
    canonical_name = str(symbol.get("canonical_name") or "")
    symbol_namespace = canonical_name.rsplit("::", 1)[0] if "::" in canonical_name else ""
    return query_parent in {symbol_parent, symbol_namespace}


def _match_type(
    query_text: str,
    symbol: Mapping[str, Any],
    *,
    include_relation: bool,
) -> str | None:
    query_canonical = _canonical(query_text)
    query_without_templates = _without_templates(query_canonical)
    canonical_name = _canonical(str(symbol.get("canonical_name", "")))
    short_name = str(symbol.get("short_name", ""))
    parent_symbol = str(symbol.get("parent_symbol") or "")
    parent_method = f"{parent_symbol}::{short_name}" if parent_symbol else ""

    if query_canonical == canonical_name or query_without_templates == canonical_name:
        return "exact_qualified_name"
    if parent_method and query_without_templates == parent_method:
        return "exact_parent_symbol_and_method"
    if _short_name(query_canonical) == short_name and include_relation:
        return "resolved_include_path_and_short_name"
    if _short_name(query_canonical) == short_name:
        return "exact_short_name"
    return None


def exact_retrieve(
    *,
    index: LoadedIndex,
    query: LoadedQuery,
    config: CandidateConfig,
) -> list[dict[str, Any]]:
    """Return all candidates tied at the strongest exact match for each query."""

    if index.repository_id != query.repository_id:
        raise ValueError(
            f"repository mismatch: index={index.repository_id}, query={query.repository_id}"
        )
    if index.repository_commit != query.repository_commit:
        raise ValueError(
            "repository commit mismatch: "
            f"index={index.repository_commit}, query={query.repository_commit}"
        )

    version = str(config.raw["exact_retrieval"]["version"])
    output: list[dict[str, Any]] = []
    for query_record in query.records:
        if query_record["category"] == "includes":
            continue
        matched: list[tuple[int, dict[str, Any]]] = []
        for symbol in index.symbol_records:
            include_match = _include_relation(query, str(symbol["path"]))
            match_type = _match_type(
                str(query_record["canonical_text"]),
                symbol,
                include_relation=include_match,
            )
            if match_type is None:
                continue
            chunk = index.chunks_by_id[str(symbol["chunk_id"])]
            match_rank = _MATCH_TYPE_RANK[match_type]
            parent_match = _parent_namespace_match(
                str(query_record["canonical_text"]), symbol
            )
            index_role_rank = 0 if symbol.get("index_role") == "definition" else 1
            candidate = {
                "artifact_schema_version": str(config.raw["candidate_schema_version"]),
                "repository_commit": index.repository_commit,
                "repository_id": index.repository_id,
                "target_id": query.target_id,
                "query_id": str(query_record["query_id"]),
                "query_category": str(query_record["category"]),
                "query_priority": str(query_record.get("priority", "low")),
                "query_text": str(query_record.get("text", query_record["canonical_text"])),
                "query_canonical_text": str(query_record["canonical_text"]),
                "query_kind": str(query_record.get("kind", "")),
                "query_relation": str(query_record.get("relation", "")),
                "chunk_id": str(chunk["chunk_id"]),
                "path": str(chunk["path"]),
                "start_byte": int(chunk["start_byte"]),
                "end_byte": int(chunk["end_byte"]),
                "start_line": int(chunk.get("start_line", symbol.get("start_line", 0))),
                "end_line": int(chunk.get("end_line", chunk.get("start_line", 0))),
                "symbol": str(chunk.get("symbol", symbol["canonical_name"])),
                "canonical_name": str(symbol["canonical_name"]),
                "short_symbol": str(symbol["short_name"]),
                "parent_symbol": symbol.get("parent_symbol"),
                "kind": str(chunk.get("kind", symbol.get("kind", ""))),
                "signature": str(symbol.get("signature", chunk.get("signature", ""))),
                "index_role": str(symbol.get("index_role", "")),
                "content_sha256": str(chunk["content_sha256"]),
                "source_sha256": str(chunk.get("source_sha256", "")),
                "retrieval_method": "exact_symbol",
                "retrieval_version": version,
                "best_match_type": match_type,
                "match_evidence": [
                    {
                        "lookup_key": str(query_record["canonical_text"]),
                        "lookup_key_type": (
                            "qualified_name"
                            if "::" in str(query_record["canonical_text"])
                            else "short_name"
                        ),
                        "match_type": match_type,
                    }
                ],
                "ranking_basis": {
                    "directory_distance": _directory_distance(
                        query_record, str(chunk["path"])
                    ),
                    "include_relation": include_match,
                    "index_role_rank": index_role_rank,
                    "match_type_rank": match_rank,
                    "namespace_parent_match": parent_match,
                    "query_priority_rank": _PRIORITY_RANK[
                        str(query_record.get("priority", "low"))
                    ],
                    "tier": 0,
                },
                "_content": str(chunk.get("content", "")),
            }
            matched.append((match_rank, candidate))

        if not matched:
            continue
        best_rank = min(rank for rank, _ in matched)
        best = [candidate for rank, candidate in matched if rank == best_rank]
        best.sort(
            key=lambda item: (
                not bool(item["ranking_basis"]["include_relation"]),
                not bool(item["ranking_basis"]["namespace_parent_match"]),
                int(item["ranking_basis"]["directory_distance"]),
                int(item["ranking_basis"]["index_role_rank"]),
                item["path"],
                int(item["start_line"]),
                item["chunk_id"],
            )
        )
        ambiguity_size = len(best)
        for candidate in best:
            candidate["ambiguous"] = ambiguity_size > 1
            candidate["ambiguity_size"] = ambiguity_size
            output.append(candidate)

    output.sort(
        key=lambda item: (
            int(item["ranking_basis"]["query_priority_rank"]),
            item["query_id"],
            int(item["ranking_basis"]["match_type_rank"]),
            not bool(item["ranking_basis"]["include_relation"]),
            not bool(item["ranking_basis"]["namespace_parent_match"]),
            int(item["ranking_basis"]["directory_distance"]),
            int(item["ranking_basis"]["index_role_rank"]),
            item["path"],
            int(item["start_line"]),
            item["chunk_id"],
        )
    )
    return output
