from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from scripts.rag.canonical import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    write_canonical_json,
)
from scripts.rag.formal_preparation import (
    EXPECTED_INPUT_ISOLATION,
    EXTERNAL_RETRIEVAL_SHA256,
    FormalPreparationError,
    build_plan,
    prepare_formal_contexts,
)
from tests.rag.fixture_factory import (
    COMMIT,
    make_chunk,
    query_record,
    write_index,
    write_query,
)


ROOT = Path(__file__).resolve().parents[2]
TARGET_IDS = tuple(f"formal-target-{number:02d}" for number in range(17))
REPOSITORY = "fixture-repo"


def _git_metadata(path: Path, *, branch: str | None, commit: str = COMMIT) -> None:
    git = path / ".git"
    git.mkdir(parents=True)
    if branch is None:
        (git / "HEAD").write_text(commit + "\n", encoding="utf-8", newline="\n")
    else:
        reference = git / "refs" / "heads" / branch
        reference.parent.mkdir(parents=True)
        reference.write_text(commit + "\n", encoding="utf-8", newline="\n")
        (git / "HEAD").write_text(
            f"ref: refs/heads/{branch}\n", encoding="utf-8", newline="\n"
        )


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rewrite(path: Path, change) -> dict:
    value = _read(path)
    change(value)
    write_canonical_json(path, value)
    return value


def _protected_target(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "repository_id": REPOSITORY,
        "repository_path": "repos/fixture-repo",
        "repository_commit": COMMIT,
        "target_name": target_id,
        "granularity": "class_span",
        "source_files": ["src/formal.cpp"],
        "locator": {"start_byte": 0, "end_byte": 20},
        "test_files": ["tests/formal_test.cpp"],
        "model": {
            "name": "fixture-model",
            "temperature": 0,
            "seed": 42,
            "num_ctx": 8192,
            "num_predict": 2048,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "stream": False,
            "generations": 1,
            "retry": False,
            "automatic_repair": False,
        },
        "evaluation": {
            "docker_image": "fixture:locked",
            "docker_image_id": "sha256:" + "2" * 64,
            "configure_command": "configure",
            "build_command": "build",
            "direct_test_command": "direct",
            "full_test_command": "full",
            "full_test_kind": "ctest",
            "direct_test_filter": "Formal.*",
            "direct_test_names": ["Formal.Pass"],
            "expected_direct_tests": 1,
            "expected_full_tests": 1,
            "stage_timeouts_seconds": {
                "configure": 1,
                "build": 1,
                "direct_test": 1,
                "full_test": 1,
            },
        },
        "readiness": {
            "configured": True,
            "reasons": [],
            "baseline_probed": True,
            "baseline_passed": True,
        },
    }


def make_formal_project(root: Path) -> Path:
    _git_metadata(root, branch="agent/rag-protocol-v0-9")
    repository_root = root / "repos" / REPOSITORY
    repository_root.mkdir(parents=True)
    _git_metadata(repository_root, branch=None)
    source_content = "class FormalTarget {};\n"
    source_path = repository_root / "src" / "formal.cpp"
    source_path.parent.mkdir()
    source_path.write_text(source_content, encoding="utf-8", newline="\n")
    source_hash = sha256_bytes(source_content.encode("utf-8"))

    protocol = root / "docs" / "rag_experiment_protocol.md"
    protocol.parent.mkdir(parents=True)
    protocol.write_text(
        "# Fixture protocol\n\n"
        "- Protocol version: `1.0`\n"
        "- Protocol status: post-pilot formal freeze\n"
        "- Formal execution status: not started\n",
        encoding="utf-8",
        newline="\n",
    )
    query_config = root / "configs" / "rag" / "query_v1.json"
    retrieval_config = root / "configs" / "rag" / "retrieval_v1.json"
    query_config.parent.mkdir(parents=True)
    write_canonical_json(query_config, {"fixture": "query-v1"})
    write_canonical_json(retrieval_config, {"fixture": "retrieval-v1"})
    external = root / "scripts" / "rag" / "external_retrieval.py"
    external.parent.mkdir(parents=True)
    external.write_bytes((ROOT / "scripts" / "rag" / "external_retrieval.py").read_bytes())
    candidate = root / "configs" / "rag" / "candidates_v1.json"
    candidate.write_bytes((ROOT / "configs" / "rag" / "candidates_v1.json").read_bytes())

    target_chunk = make_chunk(
        repository=REPOSITORY,
        path="src/formal.cpp",
        start_byte=0,
        content=source_content,
        canonical_name="FormalTarget",
        kind="class_interface",
    )
    target_chunk["source_sha256"] = source_hash
    helper_chunk = make_chunk(
        repository=REPOSITORY,
        path="src/helper.hpp",
        start_byte=0,
        content="class Helper {};\n",
        canonical_name="Helper",
        kind="class_interface",
    )
    source_index = write_index(
        root / "index-source",
        repository=REPOSITORY,
        chunks=[target_chunk, helper_chunk],
    )
    index_dir = root / "rag" / "index" / REPOSITORY / COMMIT
    index_dir.parent.mkdir(parents=True)
    shutil.copytree(source_index, index_dir)
    shutil.rmtree(root / "index-source")
    index_validation = index_dir / "index_validation.json"
    symbol_index = index_dir / "symbol_index.jsonl"

    evidence_root = root / "evidence"
    entries = []
    evidence_paths: dict[str, tuple[Path, Path]] = {}
    for target_id in TARGET_IDS:
        directory = evidence_root / target_id
        directory.mkdir(parents=True)
        non_rag = directory / "target_config.json"
        metadata = directory / "source_metadata.json"
        write_canonical_json(non_rag, _protected_target(target_id))
        write_canonical_json(
            metadata,
            {
                "repository": REPOSITORY,
                "repository_commit": COMMIT,
                "source_file": "src/formal.cpp",
                "target_id": target_id,
            },
        )
        non_rag_rel = non_rag.relative_to(root).as_posix()
        metadata_rel = metadata.relative_to(root).as_posix()
        entries.append(
            {
                "frozen_target_config_path": non_rag_rel,
                "source_metadata_path": metadata_rel,
                "target_id": target_id,
                "target_kind": "standard",
            }
        )
        evidence_paths[target_id] = (non_rag, metadata)
    registry = root / "configs" / "rag" / "query_targets_v1.json"
    write_canonical_json(
        registry,
        {
            "artifact_schema_version": "rag-query-target-registry-v1",
            "condition_id": "rag-design-context-v1",
            "expected_target_count": 17,
            "targets": entries,
            "version": "query-targets-v1",
        },
    )

    common_source = ROOT / "configs" / "rag" / "formal_retrieval_pipeline_v1.json"
    common = _read(common_source)
    common["dependencies"] = {
        "formal_protocol_path": protocol.relative_to(root).as_posix(),
        "formal_protocol_sha256": sha256_file(protocol),
        "query_config_path": query_config.relative_to(root).as_posix(),
        "query_config_sha256": sha256_file(query_config),
        "retrieval_implementation_path": external.relative_to(root).as_posix(),
        "retrieval_implementation_sha256": sha256_file(external),
        "retrieval_index_config_path": retrieval_config.relative_to(root).as_posix(),
        "retrieval_index_config_sha256": sha256_file(retrieval_config),
        "target_registry_path": registry.relative_to(root).as_posix(),
        "target_registry_sha256": sha256_file(registry),
    }
    common_path = root / "configs" / "rag" / "formal_retrieval_pipeline_v1.json"
    write_canonical_json(common_path, common)
    common_hash = sha256_file(common_path)

    target_directory = root / "configs" / "rag" / "targets"
    target_directory.mkdir()
    for target_id in TARGET_IDS:
        query_temp = write_query(
            root / "query-temp",
            repository=REPOSITORY,
            target_id=target_id,
            records=[query_record(category="user_defined_types", text="Helper")],
            source_ranges=[
                {
                    "end_byte": len(source_content.encode("utf-8")),
                    "end_column": 0,
                    "end_line": 1,
                    "git_blob_sha256": source_hash,
                    "locator_kind": "fixture",
                    "normalized_range_sha256": source_hash,
                    "normalized_source_sha256": source_hash,
                    "path": "src/formal.cpp",
                    "start_byte": 0,
                    "start_column": 0,
                    "start_line": 1,
                }
            ],
        )
        document = _read(query_temp)
        evidence_path, metadata_path = evidence_paths[target_id]
        document.update(
            {
                "phase1_index_validation_path": index_validation.relative_to(root).as_posix(),
                "phase1_index_validation_sha256": sha256_file(index_validation),
                "phase1_symbol_index_path": symbol_index.relative_to(root).as_posix(),
                "phase1_symbol_index_sha256": sha256_file(symbol_index),
                "query_config_path": query_config.relative_to(root).as_posix(),
                "query_config_sha256": sha256_file(query_config),
                "retrieval_config_path": retrieval_config.relative_to(root).as_posix(),
                "retrieval_config_sha256": sha256_file(retrieval_config),
                "target_registry_path": registry.relative_to(root).as_posix(),
                "target_registry_sha256": sha256_file(registry),
            }
        )
        document["target"]["frozen_target_config_path"] = evidence_path.relative_to(root).as_posix()
        document["target"]["source_metadata_path"] = metadata_path.relative_to(root).as_posix()
        document.pop("query_payload_sha256", None)
        document["query_payload_sha256"] = sha256_bytes(canonical_json_bytes(document))
        query_dir = root / "rag" / "query" / target_id
        query_dir.mkdir(parents=True)
        query_path = query_dir / "query.json"
        write_canonical_json(query_path, document)
        query_hash = sha256_file(query_path)
        write_canonical_json(
            query_dir / "query_validation.json",
            {
                "artifact_hashes": {"query.json": query_hash},
                "build_hash_comparison": {
                    "query.json": {
                        "build_a_sha256": query_hash,
                        "build_b_sha256": query_hash,
                        "match": True,
                    }
                },
                "deterministic": True,
                "independent_build_count": 2,
                "status": "pass",
                "target_id": target_id,
            },
        )
        protected = _protected_target(target_id)
        formal = {
            "artifact_schema_version": "rag-formal-target-config-v1",
            "enabled": False,
            "condition_id": "rag-design-context-v1",
            "experiment_id": f"rag-v1-formal-{target_id}",
            "run_id": f"rag-v1-formal-{target_id}",
            "output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
            "formal_run_id": f"rag-v1-formal-{target_id}",
            "formal_output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
            "target_kind": "standard",
            "non_rag_evidence": {
                "config_path": evidence_path.relative_to(root).as_posix(),
                "config_sha256": sha256_file(evidence_path),
                "source_metadata_path": metadata_path.relative_to(root).as_posix(),
                "source_metadata_sha256": sha256_file(metadata_path),
            },
            "common_formal_config": {
                "path": common_path.relative_to(root).as_posix(),
                "sha256": common_hash,
            },
            "frozen_query": {
                "path": query_path.relative_to(root).as_posix(),
                "sha256": query_hash,
            },
            "retrieval_settings": {
                "retrieval_top_k": 12,
                "context_budget_tokens": 6000,
                "category_quotas": {"0": 4, "1": 4, "2": 3, "3": 1},
                "top_k_and_quotas_are_caps": True,
                "per_target_override": False,
                "target_specific_manual_query": False,
            },
            "context_status": "not_generated",
            "context_path": f"rag/retrieval/formal/{target_id}/context.txt",
            "context_sha256": None,
            "one_shot_generation_policy": {
                "design_generation_count": 1,
                "code_generation_count": 1,
                "retry": False,
                "automatic_repair": False,
                "manual_patch": False,
                "overwrite": False,
            },
            "input_isolation": EXPECTED_INPUT_ISOLATION,
            **protected,
        }
        write_canonical_json(target_directory / f"{target_id}.json", formal)
    shutil.rmtree(root / "query-temp")
    return root


@pytest.fixture
def formal_project(tmp_path: Path) -> Path:
    return make_formal_project(tmp_path)


def _target_path(root: Path, number: int = 0) -> Path:
    return root / "configs" / "rag" / "targets" / f"{TARGET_IDS[number]}.json"


def mark_context_configs_generated(root: Path) -> None:
    for target_id in TARGET_IDS:
        target_path = root / "configs" / "rag" / "targets" / f"{target_id}.json"
        target = _read(target_path)
        context_path = root / target["context_path"]
        if not context_path.is_file():
            context_path.parent.mkdir(parents=True, exist_ok=True)
            context_path.write_text(
                f"frozen context for {target_id}\n", encoding="utf-8", newline="\n"
            )
        target["context_status"] = "generated_and_audited"
        target["context_sha256"] = sha256_file(context_path)
        write_canonical_json(target_path, target)


def test_valid_17_target_preparation(formal_project: Path) -> None:
    preparation = prepare_formal_contexts(
        formal_project, context_state="pre_generation"
    )
    assert len(preparation.targets) == 17
    assert preparation.branch == "agent/rag-protocol-v0-9"
    assert preparation.project_head == COMMIT


def test_post_generation_accepts_17_generated_and_audited_configs(
    formal_project: Path,
) -> None:
    mark_context_configs_generated(formal_project)
    preparation = prepare_formal_contexts(
        formal_project, context_state="post_generation"
    )
    assert len(preparation.targets) == 17
    assert all(
        target.raw["context_status"] == "generated_and_audited"
        for target in preparation.targets
    )


def test_post_generation_rejects_context_sha256_mismatch(
    formal_project: Path,
) -> None:
    mark_context_configs_generated(formal_project)
    context_path = formal_project / _read(_target_path(formal_project))["context_path"]
    context_path.write_text("changed context\n", encoding="utf-8", newline="\n")
    with pytest.raises(FormalPreparationError, match="context SHA-256 mismatch"):
        prepare_formal_contexts(formal_project, context_state="post_generation")


def test_pre_and_post_generation_states_are_not_ambiguous(
    formal_project: Path,
) -> None:
    with pytest.raises(FormalPreparationError, match="not post-generation"):
        prepare_formal_contexts(formal_project, context_state="post_generation")
    mark_context_configs_generated(formal_project)
    with pytest.raises(FormalPreparationError, match="not pre-generation"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_target_count_mismatch_is_rejected(formal_project: Path) -> None:
    _target_path(formal_project).unlink()
    with pytest.raises(FormalPreparationError, match="target config count mismatch"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_duplicate_target_id_is_rejected(formal_project: Path) -> None:
    _rewrite(_target_path(formal_project, 1), lambda value: value.update(target_id=TARGET_IDS[0]))
    with pytest.raises(FormalPreparationError, match="duplicate target ID"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_duplicate_run_id_is_rejected(formal_project: Path) -> None:
    first = _read(_target_path(formal_project))["run_id"]
    _rewrite(_target_path(formal_project, 1), lambda value: value.update(run_id=first))
    with pytest.raises(FormalPreparationError, match="duplicate or empty formal run ID"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_enabled_target_is_rejected(formal_project: Path) -> None:
    _rewrite(_target_path(formal_project), lambda value: value.update(enabled=True))
    with pytest.raises(FormalPreparationError, match="formal target is enabled"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_common_config_hash_mismatch_is_rejected(formal_project: Path) -> None:
    _rewrite(
        _target_path(formal_project),
        lambda value: value["common_formal_config"].update(sha256="0" * 64),
    )
    with pytest.raises(FormalPreparationError, match="common config hash mismatch"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_query_hash_mismatch_is_rejected(formal_project: Path) -> None:
    _rewrite(
        _target_path(formal_project),
        lambda value: value["frozen_query"].update(sha256="0" * 64),
    )
    with pytest.raises(FormalPreparationError, match="frozen query.*hash mismatch"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_non_rag_evidence_hash_mismatch_is_rejected(formal_project: Path) -> None:
    _rewrite(
        _target_path(formal_project),
        lambda value: value["non_rag_evidence"].update(config_sha256="0" * 64),
    )
    with pytest.raises(FormalPreparationError, match="non-RAG config.*hash mismatch"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("per_target_override", "per-target override is enabled"),
        ("target_specific_manual_query", "manual query is enabled"),
    ],
)
def test_target_specific_retrieval_changes_are_rejected(
    formal_project: Path, field: str, message: str
) -> None:
    _rewrite(
        _target_path(formal_project),
        lambda value: value["retrieval_settings"].update({field: True}),
    )
    with pytest.raises(FormalPreparationError, match=message):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_context_sha256_prepopulation_is_rejected(formal_project: Path) -> None:
    _rewrite(_target_path(formal_project), lambda value: value.update(context_sha256="0" * 64))
    with pytest.raises(FormalPreparationError, match="context SHA-256 is pre-populated"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


@pytest.mark.parametrize("kind", ["context", "output", "marker"])
def test_preexisting_context_output_or_marker_is_rejected(
    formal_project: Path, kind: str
) -> None:
    target = _read(_target_path(formal_project))
    if kind == "context":
        path = formal_project / target["context_path"]
        path.parent.mkdir(parents=True)
        path.write_text("unexpected\n", encoding="utf-8")
    else:
        directory = formal_project / target["output_directory"]
        directory.mkdir(parents=True)
        if kind == "marker":
            (directory / "attempt.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(FormalPreparationError, match="formal context already exists|formal output directory already exists|formal marker already exists"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_protected_field_change_is_rejected(formal_project: Path) -> None:
    _rewrite(_target_path(formal_project), lambda value: value.update(target_name="changed"))
    with pytest.raises(FormalPreparationError, match="protected field changed"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_generation_and_retrieval_top_k_conflation_is_rejected(
    formal_project: Path,
) -> None:
    target_path = _target_path(formal_project)
    target = _read(target_path)
    evidence_path = formal_project / target["non_rag_evidence"]["config_path"]
    _rewrite(evidence_path, lambda value: value["model"].update(top_k=12))
    target["model"]["top_k"] = 12
    target["non_rag_evidence"]["config_sha256"] = sha256_file(evidence_path)
    write_canonical_json(target_path, target)
    with pytest.raises(FormalPreparationError, match="model.top_k and retrieval_top_k are conflated"):
        prepare_formal_contexts(formal_project, context_state="pre_generation")


def test_plan_construction_is_read_only_and_uses_no_subprocess(
    formal_project: Path,
) -> None:
    before = {
        path.relative_to(formal_project).as_posix(): sha256_file(path)
        for path in formal_project.rglob("*")
        if path.is_file()
    }
    with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess called")):
        plan = build_plan(
            prepare_formal_contexts(formal_project, context_state="pre_generation")
        )
    after = {
        path.relative_to(formal_project).as_posix(): sha256_file(path)
        for path in formal_project.rglob("*")
        if path.is_file()
    }
    assert before == after
    assert plan["mode"] == "plan-only"
    assert plan["target_count"] == 17
    assert plan["retrieval_executed"] is False


def test_index_hashes_use_canonical_lf_bytes_on_windows(formal_project: Path) -> None:
    index = formal_project / "rag" / "index" / REPOSITORY / COMMIT
    for name in ("chunks.jsonl", "symbol_index.jsonl"):
        path = index / name
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    preparation = prepare_formal_contexts(
        formal_project, context_state="pre_generation"
    )
    assert len(preparation.targets) == 17


def test_external_retrieval_fixed_sha256_is_unchanged() -> None:
    assert sha256_file(ROOT / "scripts" / "rag" / "external_retrieval.py") == EXTERNAL_RETRIEVAL_SHA256
