"""Build and independently verify formal-outside pilot candidate pools."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.artifacts import CandidateConfig, load_index_artifacts, load_query_artifact
from scripts.rag.canonical import sha256_file, write_canonical_json
from scripts.rag.pilot_candidates import discover_pilot_candidates, pilot_pool_document


def _parse_mapping(values: list[str], *, option: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"{option} requires REPOSITORY=PATH: {value}")
        repository_id, raw_path = value.split("=", 1)
        if not repository_id or repository_id in result:
            raise ValueError(f"invalid or duplicate repository id: {repository_id!r}")
        result[repository_id] = Path(raw_path)
    return result


def _write_once(
    *,
    index_dirs: dict[str, Path],
    formal_query_paths: list[Path],
    repository_roots: dict[str, Path],
    config_path: Path,
    output_path: Path,
) -> str:
    config = CandidateConfig.load(config_path)
    indexes = [
        load_index_artifacts(path)
        for _, path in sorted(index_dirs.items())
    ]
    formal_queries = [load_query_artifact(path) for path in sorted(formal_query_paths)]
    candidates = discover_pilot_candidates(
        indexes=indexes,
        formal_queries=formal_queries,
        repository_roots=repository_roots,
        config=config,
    )
    document = pilot_pool_document(
        candidates=candidates,
        config=config,
        repository_ids=[index.repository_id for index in indexes],
    )
    document["formal_target_count_used_for_masking"] = len(formal_queries)
    return write_canonical_json(output_path, document)


def build_and_verify_pilot_pool(
    *,
    index_dirs: dict[str, Path],
    formal_query_paths: list[Path],
    repository_roots: dict[str, Path],
    config_path: Path,
    output_dir: Path,
) -> dict[str, str]:
    work = output_dir.with_name(output_dir.name + ".rebuild-work")
    if work.exists():
        raise RuntimeError(f"stale pilot rebuild evidence exists: {work}")
    build_a = work / "build-a"
    build_b = work / "build-b"
    publish = work / "publish"
    build_a.mkdir(parents=True)
    build_b.mkdir(parents=True)
    publish.mkdir(parents=True)
    try:
        first = build_a / "pilot_candidate_pool.json"
        second = build_b / "pilot_candidate_pool.json"
        _write_once(
            index_dirs=index_dirs,
            formal_query_paths=formal_query_paths,
            repository_roots=repository_roots,
            config_path=config_path,
            output_path=first,
        )
        _write_once(
            index_dirs=index_dirs,
            formal_query_paths=formal_query_paths,
            repository_roots=repository_roots,
            config_path=config_path,
            output_path=second,
        )
        first_hash = sha256_file(first)
        second_hash = sha256_file(second)
        if first_hash != second_hash:
            raise RuntimeError("independent pilot candidate pool hash mismatch")
        shutil.copyfile(first, publish / first.name)
        validation = {
            "artifact_hashes": {first.name: first_hash},
            "artifact_schema_version": "rag-pilot-candidate-validation-v1",
            "build_hash_comparison": {
                first.name: {
                    "build_a_sha256": first_hash,
                    "build_b_sha256": second_hash,
                    "match": True,
                }
            },
            "deterministic": True,
            "independent_build_count": 2,
            "status": "pass",
            "validation_errors": [],
        }
        validation_hash = write_canonical_json(
            publish / "pilot_candidate_pool_validation.json", validation
        )
        if output_dir.exists():
            existing = {
                path.name: sha256_file(path)
                for path in output_dir.iterdir()
                if path.is_file()
            }
            proposed = {
                path.name: sha256_file(path)
                for path in publish.iterdir()
                if path.is_file()
            }
            if existing != proposed:
                raise RuntimeError(
                    "pilot candidate output already exists with different hashes"
                )
            shutil.rmtree(work)
        else:
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            publish.rename(output_dir)
            shutil.rmtree(work)
        return {
            first.name: first_hash,
            "pilot_candidate_pool_validation.json": validation_hash,
        }
    except Exception:
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic formal-outside pilot candidate pool."
    )
    parser.add_argument("--index", action="append", required=True)
    parser.add_argument("--repository-root", action="append", required=True)
    parser.add_argument("--formal-query", action="append", required=True)
    parser.add_argument("--config", default="configs/rag/candidates_v1.json")
    parser.add_argument("--output-dir", default="reports/rag/pilot")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = build_and_verify_pilot_pool(
            index_dirs=_parse_mapping(args.index, option="--index"),
            formal_query_paths=[Path(path) for path in args.formal_query],
            repository_roots=_parse_mapping(
                args.repository_root, option="--repository-root"
            ),
            config_path=Path(args.config),
            output_dir=Path(args.output_dir),
        )
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
