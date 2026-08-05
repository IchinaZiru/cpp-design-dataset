from __future__ import annotations

import json
import subprocess
import urllib.request
from pathlib import Path
from unittest import mock

import pytest

from scripts.rag.audit_formal_contexts import FormalAuditError
from scripts.rag.build_formal_contexts import (
    FormalContextBuildError,
    _deduplicate_overlapping_candidates,
    execute_formal_contexts,
    main,
    run_plan_only,
)
from scripts.rag.canonical import sha256_file, write_canonical_json
from scripts.rag.formal_preparation import prepare_formal_contexts
from tests.rag.test_formal_preparation import TARGET_IDS, make_formal_project


@pytest.fixture
def prepared_project(tmp_path: Path):
    root = make_formal_project(tmp_path)
    return root, prepare_formal_contexts(root, context_state="pre_generation")


def _stable_build(preparation, output: Path):
    output.mkdir(parents=True)
    (output / "stable.txt").write_text("stable\n", encoding="utf-8", newline="\n")
    return {"target_count": len(preparation.targets)}


def _passing_audit(preparation, output: Path):
    assert (output / "stable.txt").is_file()
    return {
        "artifact_schema_version": "rag-formal-context-audit-v1",
        "common_config_path": preparation.common.relative_path,
        "common_config_sha256": preparation.common.sha256,
        "enabled_target_count": 0,
        "status": "pass",
        "target_count": len(preparation.targets),
        "targets": [],
    }


def test_no_mode_does_not_generate(prepared_project) -> None:
    root, _ = prepared_project
    before = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    with pytest.raises(SystemExit):
        main(["--project-root", str(root)])
    after = sorted(path.relative_to(root).as_posix() for path in root.rglob("*"))
    assert before == after


def test_plan_only_writes_only_requested_plan_files_and_calls_no_external_process(
    prepared_project,
) -> None:
    root, _ = prepared_project
    before = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    plan_json = root / "reports" / "plan.json"
    plan_md = root / "reports" / "plan.md"
    with (
        mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess called")),
        mock.patch.object(
            urllib.request, "urlopen", side_effect=AssertionError("network called")
        ),
    ):
        plan = run_plan_only(
            project_root=root,
            plan_json=plan_json,
            plan_markdown=plan_md,
        )
    after = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    assert set(after) - set(before) == {"reports/plan.json", "reports/plan.md"}
    assert all(after[path] == digest for path, digest in before.items())
    assert plan["llm_call_count"] == 0
    assert plan["generation_server_contacted"] is False
    assert not (root / "rag" / "retrieval" / "formal").exists()


def test_existing_canonical_output_is_rejected(prepared_project) -> None:
    root, preparation = prepared_project
    output = root / "canonical"
    output.mkdir()
    with pytest.raises(FormalContextBuildError, match="overwrite prohibited"):
        execute_formal_contexts(
            project_root=root,
            output_root=output,
            preparation=preparation,
            build_fn=_stable_build,
            audit_fn=_passing_audit,
        )


def test_stale_work_directory_is_rejected(prepared_project) -> None:
    root, preparation = prepared_project
    output = root / "canonical"
    work = root / "stale-work"
    work.mkdir()
    with pytest.raises(FormalContextBuildError, match="stale formal work evidence"):
        execute_formal_contexts(
            project_root=root,
            output_root=output,
            work_root=work,
            preparation=preparation,
            build_fn=_stable_build,
            audit_fn=_passing_audit,
        )


def test_success_transaction_persists_contexts_audit_and_target_configs(
    prepared_project,
) -> None:
    root, preparation = prepared_project
    result = execute_formal_contexts(
        project_root=root,
        preparation=preparation,
    )
    output = root / "rag" / "retrieval" / "formal"
    audit_json = root / "reports" / "rag" / "formal" / "preparation" / "formal-context-audit-v1.json"
    audit_markdown = audit_json.with_suffix(".md")
    assert result["deterministic"] is True
    assert sorted(path.name for path in output.iterdir()) == list(TARGET_IDS)
    assert audit_json.is_file()
    assert audit_markdown.is_file()
    assert result["audit_json_sha256"] == sha256_file(audit_json)
    assert result["audit_markdown_sha256"] == sha256_file(audit_markdown)
    post = prepare_formal_contexts(root, context_state="post_generation")
    assert len(post.targets) == 17
    assert all(
        target.raw["context_status"] == "generated_and_audited"
        and len(target.raw["context_sha256"]) == 64
        for target in post.targets
    )
    assert not output.with_name("formal.rebuild-work").exists()


def test_mismatching_builds_do_not_publish_and_preserve_evidence(
    prepared_project,
) -> None:
    root, preparation = prepared_project
    output = root / "canonical"
    calls = 0

    def changing_build(prepared, directory: Path):
        nonlocal calls
        calls += 1
        directory.mkdir(parents=True)
        (directory / "stable.txt").write_text(
            f"build-{calls}\n", encoding="utf-8", newline="\n"
        )
        return {"target_count": len(prepared.targets)}

    with pytest.raises(FormalAuditError, match="byte hashes differ"):
        execute_formal_contexts(
            project_root=root,
            output_root=output,
            preparation=preparation,
            build_fn=changing_build,
            audit_fn=_passing_audit,
        )
    work = output.with_name("canonical.rebuild-work")
    assert not output.exists()
    assert (work / "build-a" / "stable.txt").is_file()
    assert (work / "build-b" / "stable.txt").is_file()
    assert (work / "mismatch_evidence.json").is_file()


def test_target_configs_are_not_updated_until_all_audits_pass(
    prepared_project,
) -> None:
    root, preparation = prepared_project
    output = root / "canonical"
    update = mock.Mock()

    def failing_audit(prepared, directory: Path):
        raise FormalAuditError("synthetic aggregate audit failure")

    with pytest.raises(FormalAuditError, match="synthetic aggregate audit failure"):
        execute_formal_contexts(
            project_root=root,
            output_root=output,
            preparation=preparation,
            build_fn=_stable_build,
            audit_fn=failing_audit,
            update_fn=update,
        )
    update.assert_not_called()
    assert not output.exists()
    assert output.with_name("canonical.rebuild-work").is_dir()


def test_missing_audit_report_is_not_success(prepared_project) -> None:
    root, preparation = prepared_project
    output = root / "canonical"

    def missing_report(*args, **kwargs):
        return {"json_sha256": "0" * 64, "markdown_sha256": "0" * 64}

    with pytest.raises(FormalContextBuildError, match="was not persisted"):
        execute_formal_contexts(
            project_root=root,
            output_root=output,
            preparation=preparation,
            build_fn=_stable_build,
            audit_fn=_passing_audit,
            report_writer=missing_report,
        )
    work = output.with_name("canonical.rebuild-work")
    assert not output.exists()
    assert (work / "partial-canonical-output" / "stable.txt").is_file()
    evidence = json.loads((work / "mismatch_evidence.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "failed_transaction"
    assert evidence["retry_permitted"] is False


def test_partial_report_and_config_failure_preserves_evidence_and_restores_configs(
    prepared_project,
) -> None:
    root, preparation = prepared_project
    output = root / "canonical"
    audit_json = root / "reports" / "partial-audit.json"
    audit_markdown = root / "reports" / "partial-audit.md"
    before = {target.path: sha256_file(target.path) for target in preparation.targets}

    def partial_report(report, *, json_path: Path, markdown_path: Path):
        write_canonical_json(json_path, report)
        raise OSError("synthetic report interruption")

    with pytest.raises(OSError, match="synthetic report interruption"):
        execute_formal_contexts(
            project_root=root,
            output_root=output,
            audit_json_path=audit_json,
            audit_markdown_path=audit_markdown,
            preparation=preparation,
            build_fn=_stable_build,
            audit_fn=_passing_audit,
            report_writer=partial_report,
        )
    work = output.with_name("canonical.rebuild-work")
    assert not output.exists()
    assert not audit_json.exists()
    assert (work / "partial-canonical-artifacts" / "formal-context-audit-v1.json").is_file()
    assert (work / "mismatch_evidence.json").is_file()
    assert all(sha256_file(path) == digest for path, digest in before.items())

    second_root = make_formal_project(root.parent / "config-failure")
    second_preparation = prepare_formal_contexts(
        second_root, context_state="pre_generation"
    )
    second_output = second_root / "canonical"
    second_before = {
        target.path: sha256_file(target.path) for target in second_preparation.targets
    }

    def partial_config_update(prepared, canonical: Path, work_directory: Path) -> None:
        target = prepared.targets[0]
        raw = json.loads(target.path.read_text(encoding="utf-8"))
        raw["context_status"] = "generated_and_audited"
        write_canonical_json(target.path, raw)
        raise OSError("synthetic config interruption")

    with pytest.raises(OSError, match="synthetic config interruption"):
        execute_formal_contexts(
            project_root=second_root,
            output_root=second_output,
            audit_json_path=second_root / "reports" / "audit.json",
            audit_markdown_path=second_root / "reports" / "audit.md",
            preparation=second_preparation,
            build_fn=_stable_build,
            audit_fn=_passing_audit,
            update_fn=partial_config_update,
        )
    second_work = second_output.with_name("canonical.rebuild-work")
    assert not second_output.exists()
    assert all(sha256_file(path) == digest for path, digest in second_before.items())
    evidence = json.loads(
        (second_work / "mismatch_evidence.json").read_text(encoding="utf-8")
    )
    assert evidence["rollback"]["target_configs_restored"] == 17


def test_existing_aggregate_audit_report_is_rejected(prepared_project) -> None:
    root, preparation = prepared_project
    audit_json = root / "reports" / "rag" / "formal" / "preparation" / "formal-context-audit-v1.json"
    write_canonical_json(audit_json, {"status": "stale"})
    with pytest.raises(FormalContextBuildError, match="audit report exists"):
        execute_formal_contexts(
            project_root=root,
            preparation=preparation,
            build_fn=_stable_build,
            audit_fn=_passing_audit,
        )



def test_overlapping_candidate_dedup_keeps_highest_ranked_range() -> None:
    def candidate(
        chunk_id: str,
        *,
        path: str,
        start: int,
        end: int,
        rank: int,
    ) -> dict:
        return {
            "candidate_rank": rank,
            "chunk_id": chunk_id,
            "deduplicated_to_chunk_id": None,
            "eligible": True,
            "eligible_rank": rank,
            "end_byte": end,
            "exclusion_reasons": [],
            "path": path,
            "selection_status": "not_selected",
            "source_sha256": "a" * 64,
            "start_byte": start,
        }

    candidates = [
        candidate("parent", path="include/value.h", start=0, end=100, rank=1),
        candidate("child", path="include/value.h", start=20, end=30, rank=2),
        candidate("adjacent", path="include/value.h", start=100, end=120, rank=3),
        candidate("other-path", path="src/value.cpp", start=20, end=30, rank=4),
    ]

    result = _deduplicate_overlapping_candidates(candidates)

    assert result is candidates
    assert candidates[0]["eligible"] is True
    assert candidates[1]["eligible"] is False
    assert candidates[1]["selection_status"] == "filtered"
    assert candidates[1]["eligible_rank"] is None
    assert candidates[1]["deduplicated_to_chunk_id"] == "parent"
    assert candidates[1]["exclusion_reasons"] == ["overlapping_source_range"]
    assert candidates[2]["eligible"] is True
    assert candidates[3]["eligible"] is True
    assert [
        item["eligible_rank"] for item in candidates
    ] == [1, None, 2, 3]
