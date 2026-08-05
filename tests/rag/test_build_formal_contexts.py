from __future__ import annotations

import subprocess
import urllib.request
from pathlib import Path
from unittest import mock

import pytest

from scripts.rag.audit_formal_contexts import FormalAuditError
from scripts.rag.build_formal_contexts import (
    FormalContextBuildError,
    execute_formal_contexts,
    main,
    run_plan_only,
)
from scripts.rag.canonical import sha256_file
from scripts.rag.formal_preparation import prepare_formal_contexts
from tests.rag.test_formal_preparation import make_formal_project


@pytest.fixture
def prepared_project(tmp_path: Path):
    root = make_formal_project(tmp_path)
    return root, prepare_formal_contexts(root)


def _stable_build(preparation, output: Path):
    output.mkdir(parents=True)
    (output / "stable.txt").write_text("stable\n", encoding="utf-8", newline="\n")
    return {"target_count": len(preparation.targets)}


def _passing_audit(preparation, output: Path):
    assert (output / "stable.txt").is_file()
    return {"status": "pass", "target_count": len(preparation.targets)}


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


def test_two_matching_builds_publish_then_update(prepared_project) -> None:
    root, preparation = prepared_project
    output = root / "canonical"
    updates: list[Path] = []

    def update(prepared, canonical: Path, work: Path) -> None:
        assert prepared is preparation
        assert canonical == output
        assert (canonical / "stable.txt").read_text(encoding="utf-8") == "stable\n"
        assert work.is_dir()
        updates.append(canonical)

    result = execute_formal_contexts(
        project_root=root,
        output_root=output,
        preparation=preparation,
        build_fn=_stable_build,
        audit_fn=_passing_audit,
        update_fn=update,
    )
    assert result["deterministic"] is True
    assert (output / "stable.txt").is_file()
    assert updates == [output]
    assert not output.with_name("canonical.rebuild-work").exists()


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
