from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


CONTROL_CONDITION = "full_source_prompt_preserving_non_rag"
RAG_CONDITION = "full_source_prompt_preserving_detailed_design_rag"
PROMPT_PROFILE = "prompt-preserving-detailed-design-v3"
KNOWLEDGE_FILE = "knowledge/detailed-design/general-v3.md"
NUM_CTX = 32768
NUM_PREDICT = 16384


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def normalized(config: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(config, ensure_ascii=False))
    for key in ("condition", "experiment_id", "run_id", "design_knowledge"):
        value.pop(key, None)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()
    non = read_json(
        root / "configs/roundtrip_v3/pilot/non-rag/riscv-simulator-session.json"
    )
    rag = read_json(
        root / "configs/roundtrip_v3/pilot/rag/riscv-simulator-session.json"
    )

    if non.get("condition") != CONTROL_CONDITION:
        raise RuntimeError("Pilot control condition mismatch")
    if rag.get("condition") != RAG_CONDITION:
        raise RuntimeError("Pilot RAG condition mismatch")
    if non.get("design_prompt_profile") != PROMPT_PROFILE:
        raise RuntimeError("Pilot control prompt profile mismatch")
    if rag.get("design_prompt_profile") != PROMPT_PROFILE:
        raise RuntimeError("Pilot RAG prompt profile mismatch")
    if (non.get("design_knowledge") or {}).get("enabled") is not False:
        raise RuntimeError("Pilot control knowledge must be disabled")
    rk = rag.get("design_knowledge") or {}
    if rk.get("enabled") is not True or rk.get("context_file") != KNOWLEDGE_FILE:
        raise RuntimeError("Pilot RAG knowledge mismatch")
    if normalized(non) != normalized(rag):
        raise RuntimeError("Pilot pair differs outside allowed treatment fields")

    for config in (non, rag):
        if config.get("enabled") is not False:
            raise RuntimeError("Pilot configs must remain disabled")
        if config.get("formal_result_eligible") is not False:
            raise RuntimeError("Pilot configs must not be formal eligible")
        model = config.get("model") or {}
        if model.get("num_ctx") != NUM_CTX or model.get("num_predict") != NUM_PREDICT:
            raise RuntimeError("Pilot context/output settings mismatch")
        if model.get("generations") != 1:
            raise RuntimeError("Pilot generations must be 1")
        if model.get("retry") is not False or model.get("automatic_repair") is not False:
            raise RuntimeError("Pilot retry/repair policy mismatch")

    print(json.dumps({"valid": True, "pair_id": non.get("pair_id")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())