from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.rag.audit_formal_contexts import (
    FormalAuditError,
    audit_selection,
    audit_target_directory,
    render_context,
)
from scripts.rag.build_formal_contexts import build_formal_target_artifacts
from scripts.rag.canonical import sha256_bytes
from scripts.rag.external_retrieval import lexical_token_count
from scripts.rag.formal_preparation import FormalCommonConfig, prepare_formal_contexts
from tests.rag.test_formal_preparation import make_formal_project


@pytest.fixture
def audit_fixture(tmp_path: Path):
    root = make_formal_project(tmp_path)
    preparation = prepare_formal_contexts(root)
    return preparation, preparation.targets[0]


def _selected_item(target, *, rank: int = 1, tier: int = 0) -> dict:
    chunk = next(item for item in target.index.chunks if item["path"] == "src/helper.hpp")
    return {
        "artifact_schema_version": "rag-retrieval-candidate-v1",
        "bm25_score_scaled": 1,
        "candidate_id": "c" * 64,
        "candidate_rank": rank,
        "canonical_name": chunk["canonical_name"],
        "chunk_id": chunk["chunk_id"],
        "content": chunk["content"],
        "content_sha256": chunk["content_sha256"],
        "content_token_count": 4,
        "context_block_sha256": "d" * 64,
        "direct_relation": False,
        "directory_distance": 1,
        "eligible": True,
        "eligible_rank": rank,
        "end_byte": chunk["end_byte"],
        "end_line": chunk["end_line"],
        "exact_match_rank": 0,
        "exclusion_reasons": [],
        "kind": chunk["kind"],
        "original_case_match": True,
        "overlap_evidence": [],
        "parent_symbol": chunk.get("parent_symbol"),
        "path": chunk["path"],
        "repository_commit": chunk["repository_commit"],
        "repository_id": chunk["repository"],
        "retrieval_evidence": [],
        "retrieval_version": "formal-retrieval-pipeline-v1",
        "selection_rank": rank,
        "selection_status": "selected",
        "signature": chunk["signature"],
        "source_sha256": chunk["source_sha256"],
        "start_byte": chunk["start_byte"],
        "start_line": chunk["start_line"],
        "target_id": target.target_id,
        "tier": tier,
        "usage_classification": "none",
        "usage_classification_rank": 9,
    }


def _manifest(selected: list[dict], context: str) -> dict:
    return {
        "context_token_count": lexical_token_count(context),
        "selected_chunk_count": len(selected),
        "selected_chunk_ids": [item["chunk_id"] for item in selected],
        "shortfall_reason": "synthetic deterministic shortfall",
    }


def _audit(preparation, target, selected, *, common=None, context=None, sha=None):
    common = common or preparation.common
    context = context if context is not None else render_context(
        common=common, query=target.query, selected=selected
    )
    sha = sha or sha256_bytes(context.encode("utf-8"))
    return audit_selection(
        common=common,
        query=target.query,
        candidate_config=preparation.candidate_config,
        selected=selected,
        context=context,
        expected_context_sha256=sha,
        manifest=_manifest(selected, context),
    )


def _synthetic_item(target, *, rank: int, tier: int, path: str, start: int, content: str):
    item = _selected_item(target, rank=rank, tier=tier)
    item.update(
        {
            "candidate_id": sha256_bytes(f"candidate-{rank}".encode()),
            "chunk_id": sha256_bytes(f"chunk-{rank}".encode()),
            "content": content,
            "content_sha256": sha256_bytes(content.encode()),
            "end_byte": start + len(content.encode()),
            "end_line": rank,
            "path": path,
            "selection_rank": rank,
            "source_sha256": sha256_bytes(f"source-{path}".encode()),
            "start_byte": start,
            "start_line": rank,
        }
    )
    return item


def test_synthetic_target_build_passes_full_artifact_audit(audit_fixture, tmp_path: Path) -> None:
    preparation, target = audit_fixture
    output = tmp_path / "target-output"
    build_formal_target_artifacts(preparation, target, output)
    result = audit_target_directory(preparation, target, output)
    assert result["status"] == "pass"
    assert result["selected_chunk_count"] <= 12


def test_budget_excess_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    raw = copy.deepcopy(preparation.common.raw)
    raw["context"]["budget_tokens"] = 1
    common = replace(preparation.common, raw=raw)
    selected = [_selected_item(target)]
    with pytest.raises(FormalAuditError, match="context_budget_exceeded"):
        _audit(preparation, target, selected, common=common)


def test_tier_quota_excess_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    selected = [
        _synthetic_item(
            target,
            rank=index + 1,
            tier=0,
            path=f"src/helper-{index}.hpp",
            start=0,
            content=f"class Helper{index} {{}};\n",
        )
        for index in range(5)
    ]
    with pytest.raises(FormalAuditError, match="tier_quota_exceeded"):
        _audit(preparation, target, selected)


def test_target_source_overlap_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    selected = [_selected_item(target)]
    source_range = target.query.source_ranges[0]
    selected[0].update(
        {
            "path": source_range["path"],
            "start_byte": source_range["start_byte"],
            "end_byte": source_range["end_byte"],
            "source_sha256": source_range["normalized_source_sha256"],
        }
    )
    with pytest.raises(FormalAuditError, match="target_source_overlap"):
        _audit(preparation, target, selected)


def test_forbidden_path_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    selected = [_selected_item(target)]
    selected[0]["path"] = "tests/helper_test.cpp"
    with pytest.raises(FormalAuditError, match="forbidden_or_leaking_content"):
        _audit(preparation, target, selected)


def test_duplicate_content_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    first = _selected_item(target)
    second = copy.deepcopy(first)
    second.update(
        {
            "candidate_id": "e" * 64,
            "chunk_id": "f" * 64,
            "path": "src/helper-copy.hpp",
            "selection_rank": 2,
            "start_byte": 100,
            "end_byte": 100 + len(second["content"].encode()),
        }
    )
    with pytest.raises(FormalAuditError, match="duplicate_content_sha256"):
        _audit(preparation, target, [first, second])


def test_equivalent_range_overlap_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    first = _synthetic_item(
        target,
        rank=1,
        tier=0,
        path="src/helpers.hpp",
        start=0,
        content="class First {};\n",
    )
    second = _synthetic_item(
        target,
        rank=2,
        tier=1,
        path="src/helpers.hpp",
        start=5,
        content="class Second {};\n",
    )
    with pytest.raises(FormalAuditError, match="equivalent_range_overlap"):
        _audit(preparation, target, [first, second])


def test_context_hash_mismatch_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    selected = [_selected_item(target)]
    with pytest.raises(FormalAuditError, match="context_sha256_mismatch"):
        _audit(preparation, target, selected, sha="0" * 64)


def test_absolute_path_is_detected(audit_fixture) -> None:
    preparation, target = audit_fixture
    selected = [_selected_item(target)]
    selected[0]["path"] = "C:/private/helper.hpp"
    with pytest.raises(FormalAuditError, match="absolute_or_invalid_path"):
        _audit(preparation, target, selected)
