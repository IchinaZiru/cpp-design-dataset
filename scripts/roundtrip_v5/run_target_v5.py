from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


V4_RUNNER = Path(__file__).resolve().parents[1] / "roundtrip_v4" / "run_target_v4.py"
spec = importlib.util.spec_from_file_location("roundtrip_v4_runner_for_v5", V4_RUNNER)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load v4 runner: {V4_RUNNER}")
v4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v4)

from direct_include_retrieval import build_bundle, write_artifacts  # noqa: E402


v3 = v4.v3
PROTOCOL_ID = "source-faithful-detailed-design-direct-include-rag-v5-eval-001"
PROMPT_PROFILE = "source-faithful-detailed-design-direct-include-v5"
RAG_CONDITION = "full_source_source_faithful_direct_include_rag_v5"
KNOWLEDGE_FILE = "knowledge/detailed-design/general-v4.md"
PREFLIGHT_SUMMARY = "analysis/retrieval_v5/preflight_summary.json"

# Preserve v4 prompt/validator behavior and change only the condition identity and
# repository-context retrieval stage.
v3.PROTOCOL_ID = PROTOCOL_ID
v3.PROMPT_PROFILE = PROMPT_PROFILE
v3.RAG_CONDITION = RAG_CONDITION
v3.KNOWLEDGE_FILE = KNOWLEDGE_FILE
v4.PROTOCOL_ID = PROTOCOL_ID
v4.PROMPT_PROFILE = PROMPT_PROFILE
v4.RAG_CONDITION = RAG_CONDITION

_base_validate = v3.validate_v3_config


def validate_v5_config(
    config: dict[str, Any],
    *,
    project_root: Path | None = None,
    check_files: bool = False,
) -> dict[str, Any]:
    summary = _base_validate(config, project_root=project_root, check_files=check_files)
    retrieval = config.get("repository_retrieval") or {}
    expected = {
        "mode": "direct_include_whole_file_one_hop",
        "quoted_includes_only": True,
        "tracked_files_only": True,
        "whole_file": True,
        "depth": 1,
        "exclude_target_source_files": True,
        "target_specific_tuning": False,
    }
    for key, value in expected.items():
        if retrieval.get(key) != value:
            raise ValueError(f"repository_retrieval.{key} must be {value!r}")
    if retrieval.get("preflight_summary") != PREFLIGHT_SUMMARY:
        raise ValueError(f"repository_retrieval.preflight_summary must be {PREFLIGHT_SUMMARY!r}")
    return summary


def _expected_preflight_hash(config: dict[str, Any], project_root: Path) -> str:
    path = project_root / PREFLIGHT_SUMMARY
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing v5 retrieval preflight summary: {path}. "
            "Run audit_direct_include_retrieval_v5.py before formal execution."
        )
    data = v3.v2.load_json(path)
    if data.get("go_for_formal") is not True:
        raise RuntimeError("v5 retrieval preflight did not satisfy GO criteria")
    pair_id = str(config["pair_id"])
    records = data.get("records") or []
    matches = [row for row in records if str(row.get("pair_id")) == pair_id]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one preflight record for {pair_id}, got {len(matches)}")
    value = matches[0].get("combined_context_sha256")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Preflight context hash is missing for {pair_id}")
    return value


def resolve_detailed_design_knowledge_v5(
    config: dict[str, Any], project_root: Path, experiment_root: Path
) -> str:
    knowledge = config.get("design_knowledge") or {}
    if not knowledge.get("enabled", False):
        return ""

    source_files = v3.v2.source_files_for(config)
    repository = project_root / str(config["repository_path"])
    generic_knowledge_path = project_root / KNOWLEDGE_FILE
    bundle = build_bundle(
        repository=repository,
        repository_commit=str(config["repository_commit"]),
        source_files=source_files,
        generic_knowledge_path=generic_knowledge_path,
        pair_id=str(config["pair_id"]),
    )
    if bundle["unresolved"] or bundle["ambiguous"]:
        raise RuntimeError(
            "Direct-include retrieval is incomplete: "
            f"unresolved={len(bundle['unresolved'])}, ambiguous={len(bundle['ambiguous'])}"
        )

    expected_hash = _expected_preflight_hash(config, project_root)
    if bundle["combined_context_sha256"] != expected_hash:
        raise RuntimeError(
            "Direct-include context differs from frozen preflight: "
            f"{bundle['combined_context_sha256']} != {expected_hash}"
        )

    write_artifacts(bundle, experiment_root / "retrieval")
    return str(bundle["combined_context"]).strip()


v3.validate_v3_config = validate_v5_config
v3.resolve_detailed_design_knowledge = resolve_detailed_design_knowledge_v5
v3.validate_generated_design = v4.validate_generated_design_v4
v3.fixed_output_contract = v4.flexible_output_contract
v3.rag_append_section = v4.flexible_rag_append_section


def main() -> int:
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
