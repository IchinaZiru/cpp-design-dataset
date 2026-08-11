from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import pytest

from scripts.rag.roundtrip_ab import RoundtripABError, load_json
from scripts.research import run_devstral_replication_2x2 as replication


ROOT = Path(__file__).resolve().parents[2]
COMMON_PATH = ROOT / replication.DEFAULT_COMMON
MANIFEST_PATH = ROOT / replication.DEFAULT_MANIFEST
AUTH_PATH = ROOT / replication.DEFAULT_AUTHORIZATION


def test_preflight_covers_all_68_conditions_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_network(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("preflight attempted network access")

    monkeypatch.setattr(urllib.request, "urlopen", reject_network)
    result = replication.preflight(
        ROOT, MANIFEST_PATH, COMMON_PATH, AUTH_PATH
    )

    assert result["status"] == "pass"
    assert result["target_count"] == 17
    assert result["condition_count"] == 68
    assert result["comments_present_condition_count"] == 34
    assert result["comments_absent_condition_count"] == 34
    assert result["qwen_common_diff_paths"] == ["generation.model"]
    assert result["present_rag_contexts_match_frozen_qwen"] is True
    assert result["absent_inputs_match_frozen_comment_ablation"] is True
    assert result["all_output_roots_unused"] is True
    assert result["llm_call_count"] == 0
    assert result["generation_server_contacted"] is False
    assert len(result["target_checks"]) == 17


def test_prepared_common_changes_only_model() -> None:
    qwen = load_json(ROOT / replication.DEFAULT_QWEN_COMMON)
    devstral = load_json(COMMON_PATH)

    assert replication._deep_diff_paths(qwen, devstral) == ["generation.model"]
    assert devstral["generation"]["model"] == replication.MODEL_TAG
    assert devstral["generation"]["design_options"] == (
        replication.EXPECTED_DESIGN_OPTIONS
    )
    assert devstral["generation"]["code_options"] == (
        replication.EXPECTED_CODE_OPTIONS
    )


def test_authorization_is_devstral_specific_and_bound() -> None:
    auth = replication._verify_authorization_bindings(
        ROOT, MANIFEST_PATH, COMMON_PATH, AUTH_PATH
    )

    assert auth["model"] == replication.MODEL_TAG
    assert auth["model_id"] == replication.MODEL_ID
    assert auth["baseline_commit"] == replication.BASELINE_COMMIT
    assert auth["target_count"] == 17
    assert auth["condition_count"] == 68

    if auth["authorized"] is True:
        verified = replication._verify_authorized(
            ROOT, MANIFEST_PATH, COMMON_PATH, AUTH_PATH
        )
        assert verified["authorized"] is True
    else:
        with pytest.raises(RoundtripABError, match="not authorized"):
            replication._verify_authorized(
                ROOT, MANIFEST_PATH, COMMON_PATH, AUTH_PATH
            )

def test_runtime_present_config_changes_only_dedicated_namespaces() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    first = manifest["targets"][0]
    source = load_json(ROOT / first["source_target_config_path"])
    runtime = replication._runtime_present_config(source, first["target_id"])

    assert replication._deep_diff_paths(source, runtime) == [
        "execution.output_root",
        "execution.plan_root",
    ]
    assert runtime["execution"]["output_root"] == (
        "experiments/rag/model-replication-v1/devstral-small-2-24b/formal/"
        f"{first['target_id']}/comments-present"
    )
    assert runtime["execution"]["plan_root"] == (
        "reports/rag/model-replication-v1/devstral-small-2-24b/formal/"
        f"{first['target_id']}/comments-present/plan"
    )


def test_dirty_source_restoration_is_a_global_failure(tmp_path: Path) -> None:
    restoration = tmp_path / "evaluation/source_restoration.json"
    restoration.parent.mkdir(parents=True)
    restoration.write_text(
        json.dumps(
            {
                "status": "pass",
                "repository_clean": True,
                "error": None,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RoundtripABError, match="global failure"):
        replication._ensure_condition_is_not_global_failure(
            tmp_path,
            {"repository_clean_after_restoration": False},
        )


def test_batch_uses_fixed_target_and_four_cell_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target_ids = [f"target-{index:02d}" for index in range(17)]
    source_formal = {
        "targets": [
            {
                "target_id": target_id,
                "target_config_path": f"unused/{target_id}.json",
                "target_config_sha256": "unused",
            }
            for target_id in target_ids
        ]
    }
    source_comment = {
        "targets": [
            {
                "target_id": target_id,
                "source_target_config_path": f"unused/{target_id}.json",
                "source_target_config_sha256": "unused",
            }
            for target_id in target_ids
        ]
    }
    calls: list[tuple[str, str, str]] = []

    monkeypatch.setattr(replication, "preflight", lambda *_args: {"status": "pass"})
    monkeypatch.setattr(replication, "_verify_authorized", lambda *_args: {})
    monkeypatch.setattr(
        replication,
        "_load_replication_inputs",
        lambda *_args: ({}, {}, {}, source_formal, source_comment, {}),
    )
    monkeypatch.setattr(replication, "git_output", lambda *_args: "")
    monkeypatch.setattr(
        replication,
        "_execute_present",
        lambda _root, target_id, _entry, _common, condition: (
            calls.append((target_id, "comments-present", condition))
            or {
                "overall_pass": True,
                "llm_call_count": 2,
                "repository_clean_after_restoration": True,
            }
        ),
    )
    monkeypatch.setattr(
        replication,
        "_execute_absent",
        lambda _root, _manifest, target_id, _entry, _common, condition: (
            calls.append((target_id, "comments-absent", condition))
            or {
                "overall_pass": True,
                "llm_call_count": 2,
                "repository_clean_after_restoration": True,
            }
        ),
    )

    result = replication.execute_batch(
        tmp_path,
        tmp_path / "manifest.json",
        tmp_path / "common.json",
        tmp_path / "auth.json",
        tmp_path / "reports",
    )

    assert len(calls) == 68
    assert calls[:4] == [
        ("target-00", "comments-present", "A"),
        ("target-00", "comments-present", "B"),
        ("target-00", "comments-absent", "A"),
        ("target-00", "comments-absent", "B"),
    ]
    assert calls[-1] == ("target-16", "comments-absent", "B")
    assert result["llm_call_count"] == 136
    assert all(cell == {"pass": 17, "fail": 0} for cell in result["cells"].values())
    assert (tmp_path / "reports/batch_execution.json").is_file()


@pytest.mark.parametrize(
    "flag,attribute",
    [
        ("--prepare", "prepare"),
        ("--preflight", "preflight"),
        ("--authorize", "authorize"),
        ("--execute-batch", "execute_batch"),
    ],
)
def test_cli_exposes_required_modes(flag: str, attribute: str) -> None:
    args = replication.parse_args([flag])
    assert getattr(args, attribute) is True
