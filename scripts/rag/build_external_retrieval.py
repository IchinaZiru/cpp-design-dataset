"""Build and independently verify external-pilot retrieval-only artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import posix_relative_path, sha256_file, write_canonical_json
from scripts.rag.external_retrieval import (
    ExternalRetrievalError,
    build_all_retrieval_artifacts,
)


@dataclass(frozen=True)
class ExternalRetrievalBuildResult:
    output_root: Path
    target_count: int
    deterministic: bool
    artifact_hashes: dict[str, str]
    validation_sha256: str


def _relative_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build_and_verify_external_retrieval(
    *,
    project_root: str | Path,
    config_path: str | Path,
    repository_root: str | Path,
    output_root: str | Path,
) -> ExternalRetrievalBuildResult:
    """Build twice, publish only exact matches, and preserve failure evidence."""

    root = Path(project_root).resolve()
    config = Path(config_path)
    if not config.is_absolute():
        config = root / config
    repository = Path(repository_root).resolve()
    output = Path(output_root)
    if not output.is_absolute():
        output = root / output
    work = output.with_name(output.name + ".rebuild-work")
    if output.exists():
        raise ExternalRetrievalError(
            f"retrieval output already exists; refusing to reuse or overwrite: {output}"
        )
    if work.exists():
        raise ExternalRetrievalError(
            f"stale retrieval rebuild evidence exists; inspect before removal: {work}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True)
    build_a = work / "build-a"
    build_b = work / "build-b"
    publish = work / "publish"
    try:
        first = build_all_retrieval_artifacts(
            project_root=root,
            config_path=config,
            repository_root=repository,
            output_root=build_a,
        )
        second = build_all_retrieval_artifacts(
            project_root=root,
            config_path=config,
            repository_root=repository,
            output_root=build_b,
        )
        first_hashes = _relative_hashes(build_a)
        second_hashes = _relative_hashes(build_b)
        if set(first_hashes) != set(second_hashes):
            only_a = sorted(set(first_hashes) - set(second_hashes))
            only_b = sorted(set(second_hashes) - set(first_hashes))
            raise ExternalRetrievalError(
                "independent retrieval artifact sets differ; evidence preserved at "
                f"{work}: only_build_a={only_a}, only_build_b={only_b}"
            )

        comparisons: dict[str, dict[str, Any]] = {}
        mismatches: list[str] = []
        for relative in sorted(first_hashes):
            match = first_hashes[relative] == second_hashes[relative]
            comparisons[relative] = {
                "build_a_sha256": first_hashes[relative],
                "build_b_sha256": second_hashes[relative],
                "match": match,
            }
            if not match:
                mismatches.append(relative)
        if mismatches:
            raise ExternalRetrievalError(
                "independent retrieval artifact hash mismatch; evidence preserved at "
                f"{work}: " + ", ".join(mismatches)
            )

        validation = {
            "artifact_hashes": dict(sorted(first_hashes.items())),
            "artifact_schema_version": "rag-external-retrieval-validation-v1",
            "build_hash_comparison": comparisons,
            "deterministic": True,
            "independent_build_count": 2,
            "llm_calls": {
                "code_regeneration": 0,
                "design_generation": 0,
            },
            "output_root": posix_relative_path(output.relative_to(root)),
            "status": "pass",
            "target_count": int(first["target_count"]),
            "validation_errors": [],
            "validation_version": "rag-external-retrieval-validation-v1",
        }
        validation_a = write_canonical_json(
            build_a / "retrieval_validation.json", validation
        )
        validation_b = write_canonical_json(
            build_b / "retrieval_validation.json", validation
        )
        if validation_a != validation_b:
            raise ExternalRetrievalError(
                "independent retrieval validation hash mismatch; evidence preserved at "
                f"{work}"
            )

        shutil.copytree(build_a, publish)
        publish.replace(output)
        shutil.rmtree(work)
        published_hashes = _relative_hashes(output)
        if published_hashes["retrieval_validation.json"] != validation_a:
            raise ExternalRetrievalError("published retrieval validation hash mismatch")
        if first["target_count"] != second["target_count"]:
            raise ExternalRetrievalError("independent retrieval target counts differ")
        return ExternalRetrievalBuildResult(
            output_root=output,
            target_count=int(first["target_count"]),
            deterministic=True,
            artifact_hashes=published_hashes,
            validation_sha256=validation_a,
        )
    except Exception:
        # The work directory deliberately remains as inspectable failure evidence.
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate retrieval-only external-pilot artifacts twice and publish "
            "only if every canonical SHA-256 matches."
        )
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--config",
        default="configs/rag/pilot/yaml_cpp_retrieval_pipeline_v2.json",
    )
    parser.add_argument("--repository-root", required=True)
    parser.add_argument(
        "--output-root",
        default="rag/retrieval/external-pilot/yaml-cpp/retrieval-v2",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = build_and_verify_external_retrieval(
            project_root=args.project_root,
            config_path=args.config,
            repository_root=args.repository_root,
            output_root=args.output_root,
        )
    except (ExternalRetrievalError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "artifact_hashes": result.artifact_hashes,
                "deterministic": result.deterministic,
                "output_root": str(result.output_root),
                "target_count": result.target_count,
                "validation_sha256": result.validation_sha256,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
