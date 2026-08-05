"""Deterministic candidate discovery and selection for the external tinyxml2 pilot."""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import CandidateConfig, LoadedIndex
from .canonical import posix_relative_path, sha256_bytes
from .pilot_candidates import (
    _PILOT_KINDS,
    _project_symbol_paths,
    _structural_features,
    _test_evidence,
)


_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _string_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty array")
    result: list[str] = []
    for item in value:
        result.append(posix_relative_path(str(item)))
    if len(result) != len(set(result)):
        raise ValueError(f"{field} contains duplicate paths")
    return result


def external_policy(config: CandidateConfig) -> dict[str, Any]:
    raw = config.raw
    pilot = _mapping(raw.get("pilot"), field="pilot")
    filtering = _mapping(raw.get("filtering"), field="filtering")
    selection = _mapping(raw.get("selection"), field="selection")

    repository_id = str(pilot.get("repository_id", ""))
    repository_commit = str(pilot.get("repository_commit", "")).lower()
    if not repository_id:
        raise ValueError("pilot.repository_id is required")
    if not _COMMIT_RE.fullmatch(repository_commit):
        raise ValueError("pilot.repository_commit must be a full SHA-1")
    if pilot.get("formal_target_member") is not False:
        raise ValueError("external pilot must not be a formal target member")
    if filtering.get("formal_overlap_policy") != "not-applicable-external-repository":
        raise ValueError("external formal-overlap policy is not frozen")
    if filtering.get("source_corpus_policy") != "production-index-only":
        raise ValueError("external pilot must use the production-only index")
    if filtering.get("test_evidence_policy") != "explicit-tracked-paths-owner-aware":
        raise ValueError("external test-evidence policy is not frozen")

    evidence_paths = _string_list(
        filtering.get("test_evidence_paths"), field="filtering.test_evidence_paths"
    )
    required_count = int(selection.get("required_count", 0))
    if required_count < 3 or required_count > 5:
        raise ValueError("selection.required_count must be between 3 and 5")
    if selection.get("insufficient_policy") != "stop-without-freezing":
        raise ValueError("selection.insufficient_policy is not frozen")

    eligible_granularities = [str(item) for item in selection.get("eligible_granularities", [])]
    if eligible_granularities != ["class_span", "function"]:
        raise ValueError("eligible granularity order must be class_span, function")

    minimum_per = _mapping(
        selection.get("minimum_per_granularity"),
        field="selection.minimum_per_granularity",
    )
    normalized_minimum = {
        granularity: int(minimum_per.get(granularity, 0))
        for granularity in eligible_granularities
    }
    if any(value < 0 for value in normalized_minimum.values()):
        raise ValueError("minimum_per_granularity cannot be negative")
    if sum(normalized_minimum.values()) > required_count:
        raise ValueError("granularity minimums exceed required_count")

    minimum_files = int(selection.get("minimum_distinct_source_files", 0))
    if minimum_files < 1 or minimum_files > required_count:
        raise ValueError("minimum_distinct_source_files is invalid")

    raw_weights = _mapping(selection.get("feature_weights"), field="selection.feature_weights")
    feature_weights = {str(key): int(value) for key, value in raw_weights.items()}
    if any(value <= 0 for value in feature_weights.values()):
        raise ValueError("feature weights must be positive integers")

    expected_tie_break = [
        "structural_score_desc",
        "structural_feature_count_desc",
        "project_dependency_count_desc",
        "static_test_reference_count_desc",
        "line_count_desc",
        "path_asc",
        "start_byte_asc",
        "chunk_id_asc",
    ]
    if selection.get("ranking_tie_break") != expected_tie_break:
        raise ValueError("selection ranking tie-break is not frozen")

    return {
        "eligible_granularities": eligible_granularities,
        "evidence_paths": evidence_paths,
        "feature_weights": feature_weights,
        "minimum_distinct_source_files": minimum_files,
        "minimum_per_granularity": normalized_minimum,
        "repository_commit": repository_commit,
        "repository_id": repository_id,
        "required_count": required_count,
        "selection_version": str(selection.get("version", "")),
    }


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def validate_external_repository(
    repository_root: Path,
    *,
    expected_commit: str,
    evidence_paths: Sequence[str],
) -> list[tuple[str, Path]]:
    root = repository_root.resolve()
    try:
        top_level = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
        head = _git(root, "rev-parse", "HEAD").lower()
        status = _git(root, "status", "--porcelain")
        tracked_raw = _git(root, "ls-files", "-z")
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"cannot validate external pilot repository: {exc}") from exc

    if top_level != root:
        raise ValueError("external pilot repository root is not the Git worktree root")
    if head != expected_commit:
        raise ValueError(
            f"external pilot repository commit mismatch: expected {expected_commit}, got {head}"
        )
    if status:
        raise ValueError("external pilot repository has tracked or untracked changes")

    tracked = {
        posix_relative_path(item)
        for item in tracked_raw.split("\0")
        if item
    }
    result: list[tuple[str, Path]] = []
    for path in evidence_paths:
        normalized = posix_relative_path(path)
        if normalized not in tracked:
            raise ValueError(f"test evidence path is not tracked: {normalized}")
        source = root.joinpath(*normalized.split("/"))
        if not source.is_file():
            raise ValueError(f"test evidence path is not a file: {normalized}")
        result.append((normalized, source))
    return result


def _candidate_rank_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        -int(item["structural_score"]),
        -len(item["structural_features"]),
        -int(item["project_dependency_count"]),
        -int(item["static_test_reference_count"]),
        -int(item["line_count"]),
        str(item["path"]),
        int(item["start_byte"]),
        str(item["chunk_id"]),
    )


def _target_id(candidate: Mapping[str, Any]) -> str:
    raw = str(candidate["target_symbol"]).lower()
    slug = _SLUG_RE.sub("-", raw).strip("-") or "symbol"
    slug = slug[:48].rstrip("-") or "symbol"
    return f"tinyxml2-{slug}-{str(candidate['candidate_id'])[:12]}"


def discover_external_pilot_candidates(
    *,
    index: LoadedIndex,
    repository_root: Path,
    config: CandidateConfig,
) -> list[dict[str, Any]]:
    policy = external_policy(config)
    if index.repository_id != policy["repository_id"]:
        raise ValueError("external index repository id does not match candidate config")
    if index.repository_commit != policy["repository_commit"]:
        raise ValueError("external index commit does not match candidate config")

    test_files = validate_external_repository(
        repository_root,
        expected_commit=policy["repository_commit"],
        evidence_paths=policy["evidence_paths"],
    )
    indexed_paths = {str(chunk["path"]) for chunk in index.chunks}
    overlap = sorted(path for path, _ in test_files if path in indexed_paths)
    if overlap:
        raise ValueError(
            "test evidence leaked into production index: " + ", ".join(overlap)
        )

    version = str(config.raw["pilot"]["version"])
    symbol_paths = _project_symbol_paths(index)
    candidates: list[dict[str, Any]] = []
    for chunk in index.chunks:
        kind = str(chunk.get("kind", ""))
        granularity = _PILOT_KINDS.get(kind)
        if granularity not in policy["eligible_granularities"]:
            continue
        canonical_name = str(chunk.get("canonical_name", chunk.get("symbol", "")))
        short_name = str(chunk.get("short_symbol", canonical_name.rsplit("::", 1)[-1]))
        evidence = _test_evidence(
            canonical_name=canonical_name,
            short_name=short_name,
            kind=kind,
            parent_symbol=chunk.get("parent_symbol"),
            test_files=test_files,
        )
        if not evidence:
            continue
        features, dependency_count = _structural_features(
            chunk=chunk,
            symbol_paths=symbol_paths,
        )
        structural_score = sum(
            policy["feature_weights"].get(feature, 0) for feature in features
        )
        reference_count = sum(int(item["reference_count"]) for item in evidence)
        identity = "\n".join(
            [
                index.repository_id,
                index.repository_commit,
                str(chunk["chunk_id"]),
                version,
            ]
        )
        candidates.append(
            {
                "baseline_execution_status": str(
                    config.raw["pilot"]["baseline_execution_status"]
                ),
                "candidate_id": sha256_bytes(identity.encode("utf-8")),
                "chunk_id": str(chunk["chunk_id"]),
                "end_byte": int(chunk["end_byte"]),
                "end_line": int(chunk.get("end_line", 0)),
                "formal_overlap": False,
                "formal_target_member": False,
                "granularity": granularity,
                "kind": kind,
                "line_count": int(chunk.get("line_count", 0)),
                "path": str(chunk["path"]),
                "pilot_discovery_version": version,
                "project_dependency_count": dependency_count,
                "repository_commit": index.repository_commit,
                "repository_id": index.repository_id,
                "selection_status": "eligible",
                "source_restoration_status": str(
                    config.raw["pilot"]["source_restoration_status"]
                ),
                "start_byte": int(chunk["start_byte"]),
                "start_line": int(chunk.get("start_line", 0)),
                "static_test_evidence": evidence,
                "static_test_reference_count": reference_count,
                "structural_features": features,
                "structural_score": structural_score,
                "target_symbol": canonical_name,
            }
        )

    ranked = sorted(candidates, key=_candidate_rank_key)
    for rank, item in enumerate(ranked, start=1):
        item["candidate_rank"] = rank
    return ranked


def select_external_pilot_candidates(
    *,
    candidates: Sequence[Mapping[str, Any]],
    config: CandidateConfig,
) -> tuple[list[dict[str, Any]], list[str]]:
    policy = external_policy(config)
    selected_ids: list[str] = []
    selected_set: set[str] = set()
    reasons: list[str] = []

    if len(candidates) < policy["required_count"]:
        reasons.append(
            f"eligible candidate count {len(candidates)} is below required count {policy['required_count']}"
        )
        return [], reasons

    def add(candidate: Mapping[str, Any]) -> None:
        candidate_id = str(candidate["candidate_id"])
        if candidate_id not in selected_set:
            selected_set.add(candidate_id)
            selected_ids.append(candidate_id)

    for granularity in policy["eligible_granularities"]:
        needed = policy["minimum_per_granularity"][granularity]
        matches = [item for item in candidates if item["granularity"] == granularity]
        if len(matches) < needed:
            reasons.append(
                f"granularity {granularity} has {len(matches)} candidates but requires {needed}"
            )
        for item in matches[:needed]:
            add(item)

    distinct_paths = {
        str(item["path"])
        for item in candidates
        if str(item["candidate_id"]) in selected_set
    }
    for item in candidates:
        if len(distinct_paths) >= policy["minimum_distinct_source_files"]:
            break
        path = str(item["path"])
        if path not in distinct_paths:
            add(item)
            distinct_paths.add(path)
    if len(distinct_paths) < policy["minimum_distinct_source_files"]:
        reasons.append(
            "not enough distinct production source files for the frozen selection rule"
        )

    for item in candidates:
        if len(selected_ids) >= policy["required_count"]:
            break
        add(item)

    if reasons or len(selected_ids) != policy["required_count"]:
        if len(selected_ids) != policy["required_count"]:
            reasons.append(
                f"selection produced {len(selected_ids)} candidates instead of {policy['required_count']}"
            )
        return [], sorted(set(reasons))

    selected_set = set(selected_ids)
    selected = [dict(item) for item in candidates if str(item["candidate_id"]) in selected_set]
    selected.sort(key=lambda item: int(item["candidate_rank"]))
    for selection_rank, item in enumerate(selected, start=1):
        item["pilot_target_id"] = _target_id(item)
        item["selection_rank"] = selection_rank
        item["selection_status"] = "frozen"
    return selected, []


def external_candidate_documents(
    *,
    index: LoadedIndex,
    repository_root: Path,
    config: CandidateConfig,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = discover_external_pilot_candidates(
        index=index,
        repository_root=repository_root,
        config=config,
    )
    selected, reasons = select_external_pilot_candidates(
        candidates=candidates,
        config=config,
    )
    frozen = bool(selected) and not reasons
    selected_ids = {str(item["candidate_id"]) for item in selected}
    pool_candidates: list[dict[str, Any]] = []
    for item in candidates:
        record = dict(item)
        record["selection_status"] = (
            "frozen" if str(item["candidate_id"]) in selected_ids else "not_selected"
        )
        pool_candidates.append(record)

    policy = external_policy(config)
    counts = Counter(str(item["granularity"]) for item in candidates)
    pool = {
        "artifact_schema_version": "rag-external-pilot-candidate-pool-v1",
        "baseline_build_test_executed": False,
        "candidate_config_sha256": config.sha256,
        "candidate_count": len(candidates),
        "candidates": pool_candidates,
        "condition_id": str(config.raw["condition_id"]),
        "execution_scope": {
            "build_test": False,
            "candidate_extraction": True,
            "docker": False,
            "llm": False,
        },
        "formal_target_count_used_for_masking": 0,
        "formal_target_member": False,
        "granularity_candidate_counts": dict(sorted(counts.items())),
        "pilot_ids_frozen": frozen,
        "repository_commit": index.repository_commit,
        "repository_id": index.repository_id,
        "selection_count": len(selected),
        "selection_version": policy["selection_version"],
        "status": "selected" if frozen else "insufficient_candidates",
        "target_specific_manual_query": False,
    }
    selection = {
        "artifact_schema_version": "rag-external-pilot-selection-v1",
        "candidate_config_sha256": config.sha256,
        "condition_id": str(config.raw["condition_id"]),
        "insufficient_reasons": reasons,
        "pilot_ids_frozen": frozen,
        "repository_commit": index.repository_commit,
        "repository_id": index.repository_id,
        "required_count": policy["required_count"],
        "selected_candidates": selected,
        "selected_count": len(selected),
        "selection_version": policy["selection_version"],
        "status": "selected" if frozen else "insufficient_candidates",
    }
    return pool, selection
