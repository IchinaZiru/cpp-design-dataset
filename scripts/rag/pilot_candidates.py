"""Automatically discover formal-outside pilot target candidates."""

from __future__ import annotations

import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .artifacts import CandidateConfig, LoadedIndex, LoadedQuery
from .candidate_filters import path_byte_overlap_v1
from .canonical import posix_relative_path, sha256_bytes


_PILOT_KINDS = {
    "class_interface": "class_span",
    "struct_interface": "class_span",
    "function_definition": "function",
    "method_definition": "function",
}
_TEST_PATH_PARTS = {"test", "tests", "testing"}
_IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
_CALL_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_:<>]*\s*\(")


def _is_test_path(path: str) -> bool:
    pure = PurePosixPath(posix_relative_path(path))
    lower_parts = tuple(part.lower() for part in pure.parts)
    filename = pure.name.lower()
    return (
        any(part in _TEST_PATH_PARTS for part in lower_parts[:-1])
        or filename.startswith("test_")
        or any(
            filename.endswith(suffix)
            for suffix in (
                "_test.c",
                "_test.cc",
                "_test.cpp",
                "_test.cxx",
                "_tests.c",
                "_tests.cc",
                "_tests.cpp",
                "_tests.cxx",
            )
        )
    )


def _git_tracked_paths(repository_root: Path) -> list[str] | None:
    """Return tracked paths only when the supplied root is the Git worktree root."""

    try:
        root = repository_root.resolve()
        top_level = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        ).stdout.strip()
        if Path(top_level).resolve() != root:
            return None
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return [
            item.decode("utf-8", errors="strict")
            for item in completed.stdout.split(b"\0")
            if item
        ]
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return None


def _tracked_test_files(repository_root: Path) -> list[tuple[str, Path]]:
    root = repository_root.resolve()
    paths = _git_tracked_paths(root)
    if paths is None:
        paths = [
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        ]
    result = []
    for value in sorted(set(paths)):
        try:
            normalized = posix_relative_path(value)
        except ValueError:
            continue
        if _is_test_path(normalized):
            full = repository_root.joinpath(*normalized.split("/"))
            if full.is_file():
                result.append((normalized, full))
    return result


def _test_evidence(
    *,
    canonical_name: str,
    short_name: str,
    test_files: Sequence[tuple[str, Path]],
) -> list[dict[str, Any]]:
    names = sorted({canonical_name, short_name}, key=lambda item: (-len(item), item))
    evidence: list[dict[str, Any]] = []
    for path, source in test_files:
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        best_name = ""
        count = 0
        for name in names:
            if not name:
                continue
            pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")
            current = len(pattern.findall(text))
            if current > count or (current == count and current > 0 and name < best_name):
                best_name = name
                count = current
        if count:
            evidence.append(
                {
                    "match_type": (
                        "exact_canonical_symbol"
                        if best_name == canonical_name
                        else "exact_short_symbol"
                    ),
                    "path": path,
                    "reference_count": count,
                }
            )
    return evidence


def _formal_ranges_by_repository(
    formal_queries: Sequence[LoadedQuery],
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for query in formal_queries:
        for source_range in query.source_ranges:
            item = dict(source_range)
            item["target_id"] = query.target_id
            result[query.repository_id].append(item)
    return {
        repository_id: sorted(
            values,
            key=lambda item: (
                item["path"],
                item["start_byte"],
                item["end_byte"],
                item["target_id"],
            ),
        )
        for repository_id, values in sorted(result.items())
    }


def _project_symbol_paths(index: LoadedIndex) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for symbol in index.symbol_records:
        result[str(symbol["short_name"])].add(str(symbol["path"]))
    return result


def _structural_features(
    *,
    chunk: Mapping[str, Any],
    symbol_paths: Mapping[str, set[str]],
) -> tuple[list[str], int]:
    content = str(chunk.get("content", ""))
    identifiers = set(_IDENTIFIER_RE.findall(content))
    project_dependencies = {
        identifier
        for identifier in identifiers
        if identifier in symbol_paths
        and any(path != chunk["path"] for path in symbol_paths[identifier])
    }
    features: list[str] = []
    if re.search(r"\b(?:using|typedef|enum)\b", content):
        features.append("alias_or_enum_relation")
    if project_dependencies:
        features.append("cross_file_relation")
    if chunk.get("base_symbols") or re.search(
        r"\b(?:class|struct)\b[^\{;]*:\s*(?:public|protected|private)?",
        content,
    ):
        features.append("inheritance")
    if len(_CALL_RE.findall(content)) >= 2:
        features.append("call_site")
    if len(project_dependencies) >= 2:
        features.append("multiple_dependencies")
    if chunk.get("is_template") or chunk.get("namespace"):
        features.append("template_or_namespace")
    return sorted(set(features)), len(project_dependencies)


def discover_pilot_candidates(
    *,
    indexes: Sequence[LoadedIndex],
    formal_queries: Sequence[LoadedQuery],
    repository_roots: Mapping[str, Path],
    config: CandidateConfig,
) -> list[dict[str, Any]]:
    """Build a deterministic candidate pool without selecting or executing pilots."""

    formal_ranges = _formal_ranges_by_repository(formal_queries)
    version = str(config.raw["pilot"]["version"])
    output: list[dict[str, Any]] = []
    for index in sorted(indexes, key=lambda item: item.repository_id):
        repository_root = repository_roots.get(index.repository_id)
        if repository_root is None:
            raise ValueError(f"missing repository root: {index.repository_id}")
        test_files = _tracked_test_files(Path(repository_root))
        symbol_paths = _project_symbol_paths(index)
        repository_formal = formal_ranges.get(index.repository_id, [])
        for chunk in index.chunks:
            kind = str(chunk.get("kind", ""))
            granularity = _PILOT_KINDS.get(kind)
            if granularity is None:
                continue
            overlaps = path_byte_overlap_v1(
                candidate_path=str(chunk["path"]),
                candidate_start=int(chunk["start_byte"]),
                candidate_end=int(chunk["end_byte"]),
                source_ranges=repository_formal,
            )
            if overlaps:
                continue
            canonical_name = str(chunk.get("canonical_name", chunk.get("symbol", "")))
            short_name = str(chunk.get("short_symbol", canonical_name.rsplit("::", 1)[-1]))
            evidence = _test_evidence(
                canonical_name=canonical_name,
                short_name=short_name,
                test_files=test_files,
            )
            if not evidence:
                continue
            features, dependency_count = _structural_features(
                chunk=chunk, symbol_paths=symbol_paths
            )
            identity = "\n".join(
                [
                    index.repository_id,
                    index.repository_commit,
                    str(chunk["chunk_id"]),
                    version,
                ]
            )
            output.append(
                {
                    "baseline_execution_status": str(
                        config.raw["pilot"]["baseline_execution_status"]
                    ),
                    "candidate_id": sha256_bytes(identity.encode("utf-8")),
                    "chunk_id": str(chunk["chunk_id"]),
                    "end_byte": int(chunk["end_byte"]),
                    "end_line": int(chunk.get("end_line", 0)),
                    "formal_overlap": False,
                    "granularity": granularity,
                    "kind": kind,
                    "line_count": int(chunk.get("line_count", 0)),
                    "path": str(chunk["path"]),
                    "pilot_discovery_version": version,
                    "project_dependency_count": dependency_count,
                    "repository_commit": index.repository_commit,
                    "repository_id": index.repository_id,
                    "selection_status": str(config.raw["pilot"]["selection_status"]),
                    "source_restoration_status": str(
                        config.raw["pilot"]["source_restoration_status"]
                    ),
                    "start_byte": int(chunk["start_byte"]),
                    "start_line": int(chunk.get("start_line", 0)),
                    "static_test_evidence": evidence,
                    "structural_features": features,
                    "target_symbol": canonical_name,
                }
            )
    return sorted(
        output,
        key=lambda item: (
            item["repository_id"],
            item["path"],
            item["start_byte"],
            item["chunk_id"],
        ),
    )


def pilot_pool_document(
    *,
    candidates: Sequence[Mapping[str, Any]],
    config: CandidateConfig,
    repository_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    repository_counts = Counter(str(item["repository_id"]) for item in candidates)
    all_repositories = sorted(set(repository_ids or repository_counts))
    missing_repositories = [
        repository_id
        for repository_id in all_repositories
        if repository_counts.get(repository_id, 0) == 0
    ]
    return {
        "artifact_schema_version": "rag-pilot-candidate-pool-v1",
        "baseline_build_test_executed": False,
        "candidate_config_sha256": config.sha256,
        "candidate_count": len(candidates),
        "candidates": list(candidates),
        "condition_id": str(config.raw["condition_id"]),
        "formal_target_count_used_for_masking": None,
        "pilot_ids_frozen": False,
        "repositories_without_candidates": missing_repositories,
        "repository_candidate_counts": {
            repository_id: repository_counts.get(repository_id, 0)
            for repository_id in all_repositories
        },
        "selection_count": 0,
        "status": (
            "insufficient_candidates" if missing_repositories else "provisional"
        ),
        "target_specific_manual_query": False,
    }
