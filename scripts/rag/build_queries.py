"""Build and independently verify deterministic Phase 2 query artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.canonical import posix_relative_path, sha256_file, write_canonical_json
from scripts.rag.query_extractor import (
    QueryConfig,
    QueryExtractionError,
    TargetRegistry,
    build_query_document,
    verify_query_payload,
    write_query_document,
)


@dataclass(frozen=True)
class QueryBuildResult:
    output_root: Path
    target_count: int
    deterministic: bool
    manifest_sha256: str
    target_artifacts: tuple[dict[str, Any], ...]


def _relative_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_one(
    *,
    project_root: Path,
    config_path: Path,
    registry_path: Path,
    target_id: str,
    output_root: Path,
) -> str:
    document = build_query_document(
        project_root=project_root,
        query_config_path=config_path,
        target_registry_path=registry_path,
        target_id=target_id,
    )
    if not verify_query_payload(document):
        raise QueryExtractionError(f"payload verification failed: {target_id}")
    return write_query_document(output_root / target_id / "query.json", document)


def _target_ids(registry: TargetRegistry, requested: Iterable[str] | None) -> list[str]:
    if requested is None:
        return sorted(registry.entries)
    unique = sorted(set(str(item) for item in requested))
    unknown = [item for item in unique if item not in registry.entries]
    if unknown:
        raise QueryExtractionError("unknown target ids: " + ", ".join(unknown))
    if not unique:
        raise QueryExtractionError("at least one target id is required")
    return unique


def build_and_verify_queries(
    *,
    project_root: str | Path,
    config_path: str | Path,
    target_registry_path: str | Path,
    output_root: str | Path,
    target_ids: Iterable[str] | None = None,
) -> QueryBuildResult:
    root = Path(project_root).resolve()
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = root / config_file
    registry_file = Path(target_registry_path)
    if not registry_file.is_absolute():
        registry_file = root / registry_file
    output = Path(output_root)
    if not output.is_absolute():
        output = root / output

    config = QueryConfig.load(config_file)
    registry = TargetRegistry.load(registry_file)
    selected = _target_ids(registry, target_ids)

    work = output.with_name(output.name + ".rebuild-work")
    if work.exists():
        raise QueryExtractionError(
            f"stale query rebuild evidence exists; inspect before removal: {work}"
        )
    build_a = work / "build-a"
    build_b = work / "build-b"
    publish = work / "publish"
    work.mkdir(parents=True)

    try:
        for target_id in selected:
            _write_one(
                project_root=root,
                config_path=config_file,
                registry_path=registry_file,
                target_id=target_id,
                output_root=build_a,
            )
            _write_one(
                project_root=root,
                config_path=config_file,
                registry_path=registry_file,
                target_id=target_id,
                output_root=build_b,
            )

        comparisons: dict[str, dict[str, Any]] = {}
        target_artifacts: list[dict[str, Any]] = []
        for target_id in selected:
            relative = f"{target_id}/query.json"
            a_path = build_a / target_id / "query.json"
            b_path = build_b / target_id / "query.json"
            a_hash = sha256_file(a_path)
            b_hash = sha256_file(b_path)
            match = a_hash == b_hash
            comparisons[relative] = {
                "build_a_sha256": a_hash,
                "build_b_sha256": b_hash,
                "match": match,
            }
            if not match:
                raise QueryExtractionError(
                    f"independent query generation hash mismatch: {target_id}"
                )

            document = json.loads(a_path.read_text(encoding="utf-8"))
            if not verify_query_payload(document):
                raise QueryExtractionError(f"query payload hash mismatch: {target_id}")
            destination = publish / target_id / "query.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(a_path, destination)
            validation = {
                "artifact_hashes": {"query.json": a_hash},
                "build_hash_comparison": {"query.json": comparisons[relative]},
                "deterministic": True,
                "independent_build_count": 2,
                "query_payload_sha256": document["query_payload_sha256"],
                "status": "pass",
                "target_id": target_id,
                "validation_errors": [],
                "validation_version": "rag-query-validation-v1",
            }
            validation_path = publish / target_id / "query_validation.json"
            validation_hash = write_canonical_json(validation_path, validation)
            target_artifacts.append(
                {
                    "query_path": posix_relative_path(
                        Path(output).relative_to(root) / target_id / "query.json"
                    ),
                    "query_payload_sha256": document["query_payload_sha256"],
                    "query_sha256": a_hash,
                    "query_validation_path": posix_relative_path(
                        Path(output).relative_to(root) / target_id / "query_validation.json"
                    ),
                    "query_validation_sha256": validation_hash,
                    "target_id": target_id,
                }
            )

        manifest = {
            "artifact_schema_version": "rag-query-generation-manifest-v1",
            "condition_id": str(config.raw["condition_id"]),
            "deterministic": True,
            "independent_build_count": 2,
            "query_config_path": posix_relative_path(config_file.relative_to(root)),
            "query_config_sha256": config.sha256,
            "query_method": str(config.raw["method"]),
            "query_version": str(config.raw["query_version"]),
            "retrieval_config_path": str(config.raw["dependencies"]["retrieval_config_path"]),
            "retrieval_config_sha256": str(
                config.raw["dependencies"]["retrieval_config_sha256"]
            ),
            "status": "pass",
            "target_artifacts": sorted(target_artifacts, key=lambda item: item["target_id"]),
            "target_count": len(selected),
            "target_registry_path": posix_relative_path(registry_file.relative_to(root)),
            "target_registry_sha256": registry.sha256,
            "validation_errors": [],
        }
        manifest_hash = write_canonical_json(
            publish / "query_generation_manifest.json", manifest
        )

        publish_hashes = _relative_hashes(publish)
        if output.exists():
            existing_hashes = _relative_hashes(output)
            if existing_hashes != publish_hashes:
                raise QueryExtractionError(
                    "query output already exists with different hashes; refusing to overwrite"
                )
            shutil.rmtree(work)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            publish.rename(output)
            shutil.rmtree(work)

        return QueryBuildResult(
            output_root=output,
            target_count=len(selected),
            deterministic=True,
            manifest_sha256=manifest_hash,
            target_artifacts=tuple(sorted(target_artifacts, key=lambda item: item["target_id"])),
        )
    except Exception:
        # Preserve both independent builds and any partial publish evidence.
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate canonical non-LLM C/C++ query.json artifacts twice and "
            "publish only when every SHA-256 matches."
        )
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--config", default="configs/rag/query_v1.json")
    parser.add_argument("--targets", default="configs/rag/query_targets_v1.json")
    parser.add_argument("--output-root", default="rag/query")
    parser.add_argument(
        "--target-id",
        action="append",
        dest="target_ids",
        help="Generate only this target; repeat for multiple targets.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = build_and_verify_queries(
            project_root=args.project_root,
            config_path=args.config,
            target_registry_path=args.targets,
            output_root=args.output_root,
            target_ids=args.target_ids,
        )
    except QueryExtractionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "deterministic": result.deterministic,
                "manifest_sha256": result.manifest_sha256,
                "output_root": str(result.output_root),
                "target_count": result.target_count,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
