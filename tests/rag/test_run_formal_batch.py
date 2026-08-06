from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.rag.formal_run_policy import FormalRunPolicyError
from scripts.rag.formal_run_runtime import read_json
from scripts.rag.run_formal_batch import (
    _canonical_plan_bytes,
    execute_batch,
    write_batch_plan,
)


def test_batch_plan_is_written_only_to_rag_specific_directory(tmp_path: Path) -> None:
    plan = {
        "artifact_schema_version": "rag-formal-batch-plan-v1",
        "condition_id": "rag-design-context-v1",
        "target_count": 17,
        "counts": {"disabled": 17},
        "targets": [],
        "batch_report_root": "reports/rag/formal/batch",
        "formal_run_manifest": "manifests/rag/formal_runs.csv",
        "shared_non_rag_batch_report_used": False,
        "shared_non_rag_run_manifest_used": False,
        "force_supported": False,
        "reprocess_existing_supported": False,
    }

    json_path, markdown_path = write_batch_plan(tmp_path, plan)

    assert json_path == tmp_path / "reports/rag/formal/batch/batch_plan_disabled.json"
    assert markdown_path == tmp_path / "reports/rag/formal/batch/batch_plan_disabled.md"
    assert not (tmp_path / "reports/batch/batch_plan.json").exists()
    assert not (tmp_path / "manifests/runs.csv").exists()


def test_existing_different_plan_is_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "reports/rag/formal/batch/batch_plan_disabled.json"
    path.parent.mkdir(parents=True)
    path.write_text("different\n", encoding="utf-8")
    plan = {
        "condition_id": "rag-design-context-v1",
        "target_count": 17,
        "counts": {"disabled": 17},
        "targets": [],
    }

    with pytest.raises(Exception, match="will not be overwritten"):
        write_batch_plan(tmp_path, plan)


def test_execute_batch_rejects_any_enabled_count_other_than_17(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.rag.run_formal_batch as module

    monkeypatch.setattr(
        module,
        "build_formal_batch_plan",
        lambda root: {
            "condition_id": "rag-design-context-v1",
            "target_count": 17,
            "counts": {"ready": 16, "disabled": 1},
            "targets": [],
        },
    )

    with pytest.raises(Exception, match="requires exactly 17 ready targets"):
        execute_batch(tmp_path)


def test_batch_cli_source_has_no_force_or_reprocess_option() -> None:
    import scripts.rag.run_formal_batch as batch_module
    import scripts.rag.run_formal_target as target_module

    batch_source = Path(batch_module.__file__).read_text(encoding="utf-8")
    target_source = Path(target_module.__file__).read_text(encoding="utf-8")
    assert '"--force"' not in batch_source
    assert '"--reprocess-existing"' not in batch_source
    assert '"--force"' not in target_source
    assert '"--reprocess-existing"' not in target_source
