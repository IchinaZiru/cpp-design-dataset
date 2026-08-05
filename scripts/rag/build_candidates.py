"""Build and independently verify deterministic exact candidate artifacts."""

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

from scripts.rag.candidate_builder import CandidateBuildError, write_candidate_artifacts
from scripts.rag.canonical import sha256_file, write_canonical_json


@dataclass(frozen=True)
class CandidateBuildResult:
    output_dir: Path
    deterministic: bool
    artifact_hashes: dict[str, str]
    validation_sha256: str


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build_and_verify_candidates(
    *,
    index_dir: str | Path,
    query_path: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
) -> CandidateBuildResult:
    output = Path(output_dir)
    work = output.with_name(output.name + ".rebuild-work")
    if work.exists():
        raise CandidateBuildError(
            f"stale candidate rebuild evidence exists; inspect before removal: {work}"
        )
    build_a = work / "build-a"
    build_b = work / "build-b"
    publish = work / "publish"
    work.mkdir(parents=True)

    try:
        first = write_candidate_artifacts(
            index_dir=index_dir,
            query_path=query_path,
            config_path=config_path,
            output_dir=build_a,
        )
        second = write_candidate_artifacts(
            index_dir=index_dir,
            query_path=query_path,
            config_path=config_path,
            output_dir=build_b,
        )
        comparisons: dict[str, dict[str, Any]] = {}
        for name in sorted(first):
            first_hash = sha256_file(build_a / name)
            second_hash = sha256_file(build_b / name)
            match = first_hash == second_hash
            comparisons[name] = {
                "build_a_sha256": first_hash,
                "build_b_sha256": second_hash,
                "match": match,
            }
            if not match:
                raise CandidateBuildError(
                    f"independent candidate artifact hash mismatch: {name}"
                )
            publish.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(build_a / name, publish / name)

        manifest = json.loads(
            (publish / "candidate_manifest.json").read_text(encoding="utf-8")
        )
        manifest["deterministic"] = True
        write_canonical_json(publish / "candidate_manifest.json", manifest)
        # Rebuild B's manifest with the same post-verification marker solely for
        # final published-hash comparison; no input-dependent data changes.
        second_manifest = json.loads(
            (build_b / "candidate_manifest.json").read_text(encoding="utf-8")
        )
        second_manifest["deterministic"] = True
        write_canonical_json(build_b / "candidate_manifest.json", second_manifest)
        if sha256_file(publish / "candidate_manifest.json") != sha256_file(
            build_b / "candidate_manifest.json"
        ):
            raise CandidateBuildError("verified manifest hash mismatch")

        published_hashes = {
            name: sha256_file(publish / name)
            for name in ("candidate_manifest.json", "candidates.jsonl")
        }
        validation = {
            "artifact_hashes": dict(sorted(published_hashes.items())),
            "artifact_schema_version": "rag-candidate-validation-v1",
            "build_hash_comparison": comparisons,
            "deterministic": True,
            "independent_build_count": 2,
            "status": "pass",
            "validation_errors": [],
            "validation_version": "rag-candidate-validation-v1",
        }
        validation_sha = write_canonical_json(
            publish / "candidate_validation.json", validation
        )

        if output.exists():
            if _file_hashes(output) != _file_hashes(publish):
                raise CandidateBuildError(
                    "candidate output already exists with different hashes; refusing to overwrite"
                )
            shutil.rmtree(work)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            publish.rename(output)
            shutil.rmtree(work)

        return CandidateBuildResult(
            output_dir=output,
            deterministic=True,
            artifact_hashes=published_hashes,
            validation_sha256=validation_sha,
        )
    except Exception:
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate exact candidates.jsonl twice and publish only when every "
            "canonical SHA-256 matches."
        )
    )
    parser.add_argument("--index-dir", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--config", default="configs/rag/candidates_v1.json")
    parser.add_argument("--output-dir", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = build_and_verify_candidates(
            index_dir=args.index_dir,
            query_path=args.query,
            config_path=args.config,
            output_dir=args.output_dir,
        )
    except CandidateBuildError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "artifact_hashes": result.artifact_hashes,
                "deterministic": result.deterministic,
                "output_dir": str(result.output_dir),
                "validation_sha256": result.validation_sha256,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
