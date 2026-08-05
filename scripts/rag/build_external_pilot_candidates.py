"""Build and independently verify external pilot candidate selection."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.artifacts import CandidateConfig, load_index_artifacts
from scripts.rag.canonical import sha256_file, write_canonical_json
from scripts.rag.external_pilot_candidates import external_candidate_documents


_POOL_NAME = "external_pilot_candidate_pool.json"
_SELECTION_NAME = "external_pilot_selection.json"
_VALIDATION_NAME = "external_pilot_candidate_validation.json"


def _write_once(
    *,
    index_dir: Path,
    repository_root: Path,
    config_path: Path,
    output_dir: Path,
) -> dict[str, str]:
    config = CandidateConfig.load(config_path)
    index = load_index_artifacts(index_dir)
    pool, selection = external_candidate_documents(
        index=index,
        repository_root=repository_root,
        config=config,
    )
    return {
        _POOL_NAME: write_canonical_json(output_dir / _POOL_NAME, pool),
        _SELECTION_NAME: write_canonical_json(
            output_dir / _SELECTION_NAME, selection
        ),
    }


def build_and_verify_external_pilot_selection(
    *,
    index_dir: Path,
    repository_root: Path,
    config_path: Path,
    output_dir: Path,
) -> dict[str, str]:
    work = output_dir.with_name(output_dir.name + ".rebuild-work")
    if work.exists():
        raise RuntimeError(f"stale external pilot rebuild evidence exists: {work}")
    build_a = work / "build-a"
    build_b = work / "build-b"
    publish = work / "publish"
    build_a.mkdir(parents=True)
    build_b.mkdir(parents=True)
    publish.mkdir(parents=True)
    try:
        first = _write_once(
            index_dir=index_dir,
            repository_root=repository_root,
            config_path=config_path,
            output_dir=build_a,
        )
        second = _write_once(
            index_dir=index_dir,
            repository_root=repository_root,
            config_path=config_path,
            output_dir=build_b,
        )
        comparison: dict[str, dict[str, object]] = {}
        for name in (_POOL_NAME, _SELECTION_NAME):
            first_hash = first[name]
            second_hash = second[name]
            comparison[name] = {
                "build_a_sha256": first_hash,
                "build_b_sha256": second_hash,
                "match": first_hash == second_hash,
            }
            if first_hash != second_hash:
                raise RuntimeError(
                    f"independent external pilot artifact hash mismatch: {name}"
                )
            shutil.copyfile(build_a / name, publish / name)

        validation = {
            "artifact_hashes": {
                name: sha256_file(publish / name)
                for name in (_POOL_NAME, _SELECTION_NAME)
            },
            "artifact_schema_version": "rag-external-pilot-candidate-validation-v1",
            "build_hash_comparison": comparison,
            "candidate_config_sha256": sha256_file(config_path),
            "deterministic": True,
            "independent_build_count": 2,
            "status": "pass",
            "validation_errors": [],
        }
        validation_hash = write_canonical_json(
            publish / _VALIDATION_NAME,
            validation,
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
                    "external pilot candidate output already exists with different hashes"
                )
            shutil.rmtree(work)
        else:
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            publish.rename(output_dir)
            shutil.rmtree(work)

        return {
            _POOL_NAME: comparison[_POOL_NAME]["build_a_sha256"],
            _SELECTION_NAME: comparison[_SELECTION_NAME]["build_a_sha256"],
            _VALIDATION_NAME: validation_hash,
        }
    except Exception:
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic external pilot candidates."
    )
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument(
        "--config",
        default="configs/rag/pilot/tinyxml2_candidates_v1.json",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/rag/pilot/external/tinyxml2/candidate-selection-v1",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = build_and_verify_external_pilot_selection(
            index_dir=Path(args.index_dir),
            repository_root=Path(args.repository_root),
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
