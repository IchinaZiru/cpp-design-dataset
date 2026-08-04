"""CLI for one deterministic Phase 1 index build."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.index_builder import build_repository_index


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build production C/C++ corpus, symbol chunks, and exact symbol index."
    )
    parser.add_argument("--config", default="configs/rag/retrieval_v1.json")
    parser.add_argument("--repository-id", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--allow-recorded-parse-errors",
        action="store_true",
        help="Write diagnostics without failing; fixture diagnostics only, not production.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = build_repository_index(
        config_path=args.config,
        repository_id=args.repository_id,
        repository_root=args.repository_root,
        output_dir=args.output_dir,
        strict=not args.allow_recorded_parse_errors,
    )
    print(
        json.dumps(
            {
                "artifact_hashes": result.artifact_hashes,
                "chunk_count": result.chunk_count,
                "file_count": result.file_count,
                "repository": result.repository_id,
                "repository_commit": result.repository_commit,
                "symbol_count": result.symbol_count,
                "valid": result.valid,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
