"""Build deterministic exact-retrieval candidate artifacts."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from .artifacts import (
    CandidateConfig,
    LoadedIndex,
    LoadedQuery,
    load_index_artifacts,
    load_query_artifact,
)
from .candidate_filters import apply_candidate_filters
from .canonical import sha256_bytes, write_canonical_json, write_canonical_jsonl
from .exact_retriever import exact_retrieve


class CandidateBuildError(RuntimeError):
    """Raised when deterministic candidate generation cannot be completed."""


_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _candidate_id(candidate: Mapping[str, Any]) -> str:
    identity = "\n".join(
        [
            str(candidate["target_id"]),
            str(candidate["query_id"]),
            str(candidate["chunk_id"]),
            str(candidate["retrieval_version"]),
        ]
    )
    return sha256_bytes(identity.encode("utf-8"))


def _ambiguity_group_id(candidate: Mapping[str, Any]) -> str:
    identity = "\n".join(
        [
            str(candidate["target_id"]),
            str(candidate["query_id"]),
            str(candidate["best_match_type"]),
        ]
    )
    return sha256_bytes(identity.encode("utf-8"))


def _candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    ranking = candidate["ranking_basis"]
    return (
        _PRIORITY_RANK[str(candidate["query_priority"])],
        str(candidate["query_id"]),
        not bool(candidate["eligible"]),
        int(ranking["match_type_rank"]),
        not bool(ranking["include_relation"]),
        not bool(ranking["namespace_parent_match"]),
        int(ranking["directory_distance"]),
        int(ranking["index_role_rank"]),
        str(candidate["path"]),
        int(candidate["start_line"]),
        str(candidate["chunk_id"]),
    )


def build_candidate_records(
    *,
    index: LoadedIndex,
    query: LoadedQuery,
    config: CandidateConfig,
) -> list[dict[str, Any]]:
    raw = exact_retrieve(index=index, query=query, config=config)
    filtered = [
        apply_candidate_filters(candidate, query=query, config=config)
        for candidate in raw
    ]

    by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in filtered:
        candidate["candidate_id"] = _candidate_id(candidate)
        candidate["ambiguity_group_id"] = _ambiguity_group_id(candidate)
        by_query[str(candidate["query_id"])].append(candidate)

    for values in by_query.values():
        eligible_values = sorted(
            (candidate for candidate in values if candidate["eligible"]),
            key=_candidate_sort_key,
        )
        eligible_size = len(eligible_values)
        for rank, candidate in enumerate(eligible_values, start=1):
            ranking = dict(candidate["ranking_basis"])
            ranking["eligible_rank"] = rank
            candidate["ranking_basis"] = ranking
            candidate["eligible_ambiguity_size"] = eligible_size
        for candidate in values:
            if not candidate["eligible"]:
                ranking = dict(candidate["ranking_basis"])
                ranking["eligible_rank"] = None
                candidate["ranking_basis"] = ranking
                candidate["eligible_ambiguity_size"] = eligible_size

    candidates = sorted(filtered, key=_candidate_sort_key)
    ids = [candidate["candidate_id"] for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise CandidateBuildError("duplicate candidate_id generated")
    return candidates


def build_candidate_manifest(
    *,
    index: LoadedIndex,
    query: LoadedQuery,
    config: CandidateConfig,
    candidates: list[dict[str, Any]],
    candidates_sha256: str,
) -> dict[str, Any]:
    by_query: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_query[str(candidate["query_id"])].append(candidate)

    outcomes: list[dict[str, Any]] = []
    for query_record in query.records:
        query_id = str(query_record["query_id"])
        values = by_query.get(query_id, [])
        if query_record["category"] == "includes":
            status = "not_applicable"
            reason = "include_relation_only"
        elif not values:
            status = "unresolved"
            reason = "no_exact_match"
        elif not any(value["eligible"] for value in values):
            status = "excluded"
            reason = "all_exact_candidates_filtered"
        else:
            status = "resolved"
            reason = None
        outcome = {
            "eligible_candidate_count": sum(
                1 for value in values if value["eligible"]
            ),
            "query_category": str(query_record["category"]),
            "query_id": query_id,
            "raw_candidate_count": len(values),
            "reason": reason,
            "status": status,
        }
        outcomes.append(outcome)

    exclusion_counts = Counter(
        reason
        for candidate in candidates
        for reason in candidate["exclusion_reasons"]
    )
    ambiguity_groups = {
        str(candidate["ambiguity_group_id"])
        for candidate in candidates
        if candidate["ambiguous"]
    }
    return {
        "artifact_hashes": {"candidates.jsonl": candidates_sha256},
        "artifact_schema_version": "rag-candidate-manifest-v1",
        "candidate_config_sha256": config.sha256,
        "candidate_count": len(candidates),
        "candidate_schema_version": str(config.raw["candidate_schema_version"]),
        "condition_id": str(config.raw["condition_id"]),
        "deterministic": None,
        "eligible_candidate_count": sum(
            1 for candidate in candidates if candidate["eligible"]
        ),
        "exact_ambiguity_group_count": len(ambiguity_groups),
        "exact_retrieval_version": str(config.raw["exact_retrieval"]["version"]),
        "excluded_candidate_count": sum(
            1 for candidate in candidates if not candidate["eligible"]
        ),
        "exclusion_reason_counts": dict(sorted(exclusion_counts.items())),
        "filter_version": str(config.raw["filtering"]["version"]),
        "index_artifact_hashes": dict(sorted(index.artifact_hashes.items())),
        "llm_called": False,
        "query_outcomes": outcomes,
        "query_sha256": query.sha256,
        "repository_commit": index.repository_commit,
        "repository_id": index.repository_id,
        "target_id": query.target_id,
        "target_specific_manual_query": False,
        "top_k_applied": False,
        "context_budget_applied": False,
    }


def write_candidate_artifacts(
    *,
    index_dir: str | Path,
    query_path: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
) -> dict[str, str]:
    index = load_index_artifacts(index_dir)
    query = load_query_artifact(query_path)
    config = CandidateConfig.load(config_path)
    candidates = build_candidate_records(index=index, query=query, config=config)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    candidates_sha = write_canonical_jsonl(output / "candidates.jsonl", candidates)
    manifest = build_candidate_manifest(
        index=index,
        query=query,
        config=config,
        candidates=candidates,
        candidates_sha256=candidates_sha,
    )
    manifest_sha = write_canonical_json(output / "candidate_manifest.json", manifest)
    return {
        "candidate_manifest.json": manifest_sha,
        "candidates.jsonl": candidates_sha,
    }
