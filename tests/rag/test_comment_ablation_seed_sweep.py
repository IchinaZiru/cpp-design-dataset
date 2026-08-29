from __future__ import annotations

from pathlib import Path

import pytest

from scripts.rag.roundtrip_ab import RoundtripABError
from scripts.research.run_comment_ablation_seed_sweep import preflight


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs/rag/comment_ablation_seed_sweep_v1/seed_sweep.json"


def test_seed_sweep_preflight_is_no_contact_and_checks_all_pairs() -> None:
    result = preflight(ROOT, CONFIG, 42)

    assert result["status"] == "pass"
    assert result["formal_result"] is False
    assert result["target_count"] == 17
    assert result["condition_count"] == 34
    assert result["design_prompts_checked"] == 34
    assert result["llm_call_count"] == 0
    assert result["generation_server_contacted"] is False
    assert result["temperature"] == 0.1


def test_seed_sweep_rejects_undeclared_seed() -> None:
    with pytest.raises(RoundtripABError, match="not predeclared"):
        preflight(ROOT, CONFIG, 999)
