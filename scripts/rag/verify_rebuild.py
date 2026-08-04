"""Verify two independent index builds and publish only matching artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import sha256_file, write_canonical_json
from scripts.rag.index_builder import (
    BUILD_COMPARISON_ARTIFACTS,
    CORE_ARTIFACTS,
    IndexValidationError,
    build_repository_index,
)


class RebuildMismatchError(RuntimeError):
    """Raised when independently built artifacts differ."""


def verify_independent_rebuilds(
    *,
    config_path: str | Path,
    repository_id: str,
    repository_root: str | Path,
    output_dir: str | Path,
) -> dict[str, object]:
    """Build twice, preserve failed evidence, and publish only validated matches."""

    output = Path(output_dir)
    output_parent = output.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    working_root = output.with_name(output.name + ".rebuild-work")

    if output.exists():
        raise FileExistsError(
            f"output already exists; remove it explicitly before rebuilding: {output}"
        )
    if working_root.exists():
        raise FileExistsError(
            "prior rebuild evidence exists; inspect or remove it explicitly before retrying: "
            f"{working_root}"
        )

    first = working_root / "build-a"
    second = working_root / "build-b"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    # strict=False is deliberate: invalid artifacts must remain inspectable under
    # .rebuild-work instead of disappearing with a temporary directory.
    first_result = build_repository_index(
        config_path=config_path,
        repository_id=repository_id,
        repository_root=repository_root,
        output_dir=first,
        strict=False,
    )
    second_result = build_repository_index(
        config_path=config_path,
        repository_id=repository_id,
        repository_root=repository_root,
        output_dir=second,
        strict=False,
    )

    first_hashes = {
        name: sha256_file(first / name) for name in BUILD_COMPARISON_ARTIFACTS
    }
    second_hashes = {
        name: sha256_file(second / name) for name in BUILD_COMPARISON_ARTIFACTS
    }
    mismatches = [
        name
        for name in BUILD_COMPARISON_ARTIFACTS
        if first_hashes[name] != second_hashes[name]
    ]
    if mismatches:
        raise RebuildMismatchError(
            "independent rebuild hash mismatch; evidence preserved at "
            f"{working_root}: " + ", ".join(mismatches)
        )

    invalid_builds: list[str] = []
    if not first_result.valid:
        invalid_builds.append("build-a: " + "; ".join(first_result.validation_errors))
    if not second_result.valid:
        invalid_builds.append("build-b: " + "; ".join(second_result.validation_errors))
    if invalid_builds:
        raise IndexValidationError(
            "independent builds matched but validation failed; evidence preserved at "
            f"{working_root}: " + " | ".join(invalid_builds)
        )

    temporary_publish = output.with_name(output.name + ".tmp-publish")
    if temporary_publish.exists():
        raise FileExistsError(
            f"temporary publish path already exists: {temporary_publish}"
        )
    temporary_publish.mkdir(parents=True)
    for name in CORE_ARTIFACTS:
        shutil.copyfile(first / name, temporary_publish / name)

    verification: dict[str, object] = {
        "artifact_hashes": dict(sorted(first_hashes.items())),
        "build_hash_comparison": {
            name: {
                "build_a_sha256": first_hashes[name],
                "build_b_sha256": second_hashes[name],
                "match": True,
            }
            for name in BUILD_COMPARISON_ARTIFACTS
        },
        "chunk_count": first_result.chunk_count,
        "deterministic": True,
        "file_count": first_result.file_count,
        "handled_parser_error_count": sum(
            item.handled for item in first_result.diagnostics
        ),
        "independent_build_count": 2,
        "parser_error_count": len(first_result.diagnostics),
        "repository": repository_id,
        "repository_commit": first_result.repository_commit,
        "status": "pass",
        "symbol_count": first_result.symbol_count,
        "unhandled_parser_error_count": sum(
            not item.handled for item in first_result.diagnostics
        ),
        "validation_errors": [],
        "validation_version": "rag-index-validation-v1",
    }
    write_canonical_json(temporary_publish / "index_validation.json", verification)
    temporary_publish.replace(output)
    shutil.rmtree(working_root)
    return verification


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the same Phase 1 index twice and require identical hashes."
    )
    parser.add_argument("--config", default="configs/rag/retrieval_v1.json")
    parser.add_argument("--repository-id", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    verification = verify_independent_rebuilds(
        config_path=args.config,
        repository_id=args.repository_id,
        repository_root=args.repository_root,
        output_dir=args.output_dir,
    )
    print(json.dumps(verification, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
