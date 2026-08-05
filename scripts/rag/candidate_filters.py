"""Deterministic leakage and target-overlap filters for retrieval candidates."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

from .artifacts import CandidateConfig, LoadedQuery
from .canonical import posix_relative_path


_TEST_MACRO_RE = re.compile(
    r"\b(?:TEST|TEST_F|TEST_P|TYPED_TEST|SCENARIO|GIVEN|WHEN|THEN)\s*\(|"
    r"\b(?:EXPECT|ASSERT)_[A-Z0-9_]+\s*\("
)
_GENERATED_CONTENT_RE = re.compile(
    r"(?:generated\s+by|auto[- ]generated|do\s+not\s+edit)", re.IGNORECASE
)


def path_byte_overlap_v1(
    *,
    candidate_path: str,
    candidate_start: int,
    candidate_end: int,
    source_ranges: Sequence[Mapping[str, Any]],
    candidate_source_sha256: str | None = None,
) -> list[dict[str, Any]]:
    """Return evidence for half-open byte overlaps on the same POSIX path."""

    path = posix_relative_path(candidate_path)
    evidence: list[dict[str, Any]] = []
    for source_range in source_ranges:
        target_path = posix_relative_path(str(source_range["path"]))
        target_start = int(source_range["start_byte"])
        target_end = int(source_range["end_byte"])
        if path != target_path:
            continue
        normalized_hash = source_range.get("normalized_source_sha256")
        git_blob_hash = source_range.get("git_blob_sha256")
        if candidate_source_sha256 and normalized_hash:
            accepted = {str(normalized_hash)}
            if git_blob_hash and str(git_blob_hash) == str(normalized_hash):
                accepted.add(str(git_blob_hash))
            if candidate_source_sha256 not in accepted:
                raise ValueError(
                    "candidate/source-range coordinate hash mismatch for "
                    f"{path}: candidate={candidate_source_sha256}, "
                    f"normalized={normalized_hash}, git_blob={git_blob_hash}"
                )
        if candidate_start < target_end and target_start < candidate_end:
            evidence.append(
                {
                    "candidate_end_byte": candidate_end,
                    "candidate_start_byte": candidate_start,
                    "method": "path_byte_overlap_v1",
                    "path": path,
                    "target_end_byte": target_end,
                    "target_start_byte": target_start,
                }
            )
    return sorted(
        evidence,
        key=lambda item: (
            item["path"],
            item["target_start_byte"],
            item["target_end_byte"],
            item["candidate_start_byte"],
            item["candidate_end_byte"],
        ),
    )


def _path_components(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(posix_relative_path(path)).parts)


def _path_reason_set(path: str) -> set[str]:
    components = _path_components(path)
    filename = components[-1]
    reasons: set[str] = set()

    if any(part in {"test", "tests", "testing"} for part in components[:-1]):
        reasons.add("test_content_detected")
    if filename.startswith("test_") or any(
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
    ):
        reasons.add("test_content_detected")

    if any(part in {"experiment", "experiments"} for part in components):
        reasons.add("experiment_artifact")
    if any(part in {"generated", "autogen", "codegen"} for part in components):
        reasons.add("generated_content")
    if ".generated." in filename or filename.startswith("generated_"):
        reasons.add("generated_content")
    if any(
        part in {"vendor", "vendors", "third-party", "third_party", "external"}
        for part in components
    ):
        reasons.add("third_party")
    if any(
        part in {
            "build",
            "benchmark",
            "benchmarks",
            "docs",
            "documentation",
            "logs",
            "report",
            "reports",
        }
        or part.startswith("cmake-build-")
        for part in components
    ):
        reasons.add("forbidden_path")
    if any(
        part in {"raw_output", "llm_output", "generated_code", "regenerated_code"}
        for part in components
    ) or filename in {
        "design_document.md",
        "generated_design.md",
        "regenerated.cpp",
        "generated.cpp",
    }:
        reasons.add("previous_llm_output")
    return reasons


def apply_candidate_filters(
    candidate: Mapping[str, Any],
    *,
    query: LoadedQuery,
    config: CandidateConfig,
) -> dict[str, Any]:
    result = dict(candidate)
    content = str(result.pop("_content", ""))
    reasons = _path_reason_set(str(result["path"]))
    if _TEST_MACRO_RE.search(content):
        reasons.add("test_content_detected")
    if _GENERATED_CONTENT_RE.search(content):
        reasons.add("generated_content")

    overlap = path_byte_overlap_v1(
        candidate_path=str(result["path"]),
        candidate_start=int(result["start_byte"]),
        candidate_end=int(result["end_byte"]),
        source_ranges=query.source_ranges,
        candidate_source_sha256=(
            str(result.get("source_sha256"))
            if result.get("source_sha256")
            else None
        ),
    )
    if overlap:
        reasons.add("target_source_overlap")

    configured_order = list(config.raw["filtering"]["exclusion_reason_order"])
    order = {reason: index for index, reason in enumerate(configured_order)}
    ordered_reasons = sorted(reasons, key=lambda reason: (order.get(reason, 999), reason))
    result["eligible"] = not ordered_reasons
    result["exclusion_reasons"] = ordered_reasons
    result["overlap_evidence"] = overlap
    return result
