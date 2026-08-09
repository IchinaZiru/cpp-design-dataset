from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from direct_include_retrieval import build_bundle, write_artifacts


KNOWLEDGE_FILE = "knowledge/detailed-design/general-v4.md"
DEFAULT_MANIFEST = "configs/roundtrip_v5/evaluation/generation_manifest.json"
DEFAULT_OUTPUT = "analysis/retrieval_v5"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v5 direct-include retrieval only; no LLM/build/test calls.")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, default=Path(DEFAULT_MANIFEST))
    parser.add_argument("--output-root", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    root = args.project_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    output_root = args.output_root if args.output_root.is_absolute() else root / args.output_root
    manifest = read_json(manifest_path)
    targets = manifest.get("targets") or []
    if len(targets) != 17:
        raise RuntimeError(f"Expected 17 v5 targets, got {len(targets)}")

    if output_root.exists():
        if not args.overwrite:
            raise FileExistsError(f"Retrieval audit output already exists: {output_root}; use --overwrite only before formal execution")
        shutil.rmtree(output_root)

    records: list[dict[str, Any]] = []
    for target in targets:
        config = read_json(root / str(target["config_path"]))
        pair_id = str(config["pair_id"])
        repository = root / str(config["repository_path"])
        source_files = [str(value) for value in config["source_files"]]
        bundle = build_bundle(
            repository=repository,
            repository_commit=str(config["repository_commit"]),
            source_files=source_files,
            generic_knowledge_path=root / KNOWLEDGE_FILE,
            pair_id=pair_id,
        )
        retrieval_dir = output_root / pair_id / "retrieval"
        write_artifacts(bundle, retrieval_dir)

        unresolved = len(bundle["unresolved"])
        ambiguous = len(bundle["ambiguous"])
        record = {
            "pair_id": pair_id,
            "quoted_include_count": bundle["quoted_include_count"],
            "selected_file_count": len(bundle["selected"]),
            "selected_paths": bundle["selected_paths"],
            "unresolved_count": unresolved,
            "ambiguous_count": ambiguous,
            "combined_context_sha256": bundle["combined_context_sha256"],
            "combined_context_bytes": bundle["combined_context_bytes"],
            "retrieval_complete": unresolved == 0 and ambiguous == 0,
        }
        records.append(record)

    go_for_formal = all(record["retrieval_complete"] for record in records)
    summary = {
        "schema_version": "1.0",
        "llm_called": False,
        "build_called": False,
        "test_called": False,
        "target_count": len(records),
        "retrieval_mode": "direct_include_whole_file_one_hop",
        "go_for_formal": go_for_formal,
        "go_criteria": [
            "17 targets audited",
            "no unresolved quoted include",
            "no ambiguous repository-local include resolution",
            "target source files excluded from retrieved context",
            "selected repository files copied as whole files",
            "retrieval is deterministic and non-LLM",
        ],
        "records": records,
    }
    write_json(output_root / "preflight_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if go_for_formal else 2


if __name__ == "__main__":
    raise SystemExit(main())
