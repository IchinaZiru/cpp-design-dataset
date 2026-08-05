"""Plan or atomically build the frozen 17-target formal retrieval contexts."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.audit_formal_contexts import (
    FormalAuditError,
    audit_formal_context_set,
    compare_artifact_trees,
)
from scripts.rag.canonical import (
    posix_relative_path,
    sha256_bytes,
    sha256_file,
    write_canonical_json,
    write_canonical_jsonl,
)
from scripts.rag.external_retrieval import (
    ExternalRetrievalConfig,
    build_candidates,
    lexical_token_count,
    select_context_candidates,
)
from scripts.rag.formal_preparation import (
    FormalPreparation,
    FormalPreparationError,
    FormalTarget,
    build_plan,
    prepare_formal_contexts,
    render_plan_markdown,
)


class FormalContextBuildError(RuntimeError):
    """Raised when a formal context build cannot safely continue."""


def _write_context(path: Path, value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    data = normalized.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def _shortfall_reason(
    *,
    candidates: list[dict[str, Any]],
    selected_count: int,
    top_k: int,
) -> str | None:
    if selected_count >= top_k:
        return None
    eligible_by_tier = Counter(
        str(item["tier"]) for item in candidates if bool(item.get("eligible"))
    )
    budget_excluded = sum(
        1 for item in candidates if item.get("selection_status") == "budget_excluded"
    )
    tier_text = ",".join(
        f"{tier}:{eligible_by_tier.get(str(tier), 0)}" for tier in range(4)
    )
    return (
        "frozen caps are not fill requirements; "
        f"selected={selected_count},top_k_cap={top_k},"
        f"eligible_by_tier={tier_text},budget_excluded={budget_excluded}"
    )


def build_formal_target_artifacts(
    preparation: FormalPreparation,
    target: FormalTarget,
    output_directory: Path,
) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=False)
    config = ExternalRetrievalConfig(
        path=preparation.common.path,
        sha256=preparation.common.sha256,
        raw=preparation.common.raw,
    )
    # build_candidates only consumes these pure, already-validated fields.  It
    # never invokes the external-pilot loader or regenerates the frozen query.
    inputs = SimpleNamespace(
        config=config,
        index=target.index,
        exact_config=preparation.candidate_config,
    )
    candidates = build_candidates(inputs=inputs, query=target.query)
    selected, context, context_tokens = select_context_candidates(
        candidates=candidates,
        chunks_by_id=target.index.chunks_by_id,
        query=target.query,
        config=config,
    )

    corpus_bytes = (target.index.root / "corpus_manifest.json").read_bytes()
    (output_directory / "corpus_manifest.json").write_bytes(corpus_bytes)
    query_bytes = target.query.path.read_bytes()
    (output_directory / "query.json").write_bytes(query_bytes)
    candidates_sha = write_canonical_jsonl(
        output_directory / "candidates.jsonl", candidates
    )
    selected_sha = write_canonical_jsonl(
        output_directory / "selected_chunks.jsonl", selected
    )
    context_sha = _write_context(output_directory / "context.txt", context)
    if lexical_token_count(context) != context_tokens:
        raise FormalContextBuildError(
            f"context token count is inconsistent: {target.target_id}"
        )

    tier_counts = Counter(str(item["tier"]) for item in selected)
    top_k = int(preparation.common.raw["selection"]["retrieval_top_k"])
    shortfall_reason = _shortfall_reason(
        candidates=candidates,
        selected_count=len(selected),
        top_k=top_k,
    )
    manifest = {
        "artifact_hashes": {
            "candidates.jsonl": candidates_sha,
            "context.txt": context_sha,
            "corpus_manifest.json": sha256_bytes(corpus_bytes),
            "query.json": sha256_bytes(query_bytes),
            "selected_chunks.jsonl": selected_sha,
        },
        "artifact_schema_version": "rag-formal-retrieval-manifest-v1",
        "bm25": preparation.common.raw["bm25"],
        "candidate_count": len(candidates),
        "common_config_path": preparation.common.relative_path,
        "common_config_sha256": preparation.common.sha256,
        "condition_id": preparation.common.raw["condition_id"],
        "context_budget_tokens": preparation.common.raw["context"]["budget_tokens"],
        "context_format": preparation.common.raw["context"]["format"],
        "context_sha256": context_sha,
        "context_token_count": context_tokens,
        "deterministic": True,
        "index_artifact_hashes": target.index.artifact_hashes,
        "index_validation_path": target.index_validation_relative_path,
        "index_validation_sha256": target.index_validation_sha256,
        "llm_calls": {"code_regeneration": 0, "design_generation": 0},
        "one_hop": preparation.common.raw["one_hop"],
        "query_sha256": target.query.sha256,
        "query_validation_path": target.query_validation_relative_path,
        "query_validation_sha256": target.query_validation_sha256,
        "ranking": preparation.common.raw["ranking"],
        "repository_commit": target.query.repository_commit,
        "repository_id": target.query.repository_id,
        "retrieval_executed": True,
        "retrieval_top_k": top_k,
        "selected_chunk_count": len(selected),
        "selected_chunk_ids": [str(item["chunk_id"]) for item in selected],
        "selected_tier_counts": dict(sorted(tier_counts.items())),
        "selection_quotas": preparation.common.raw["selection"]["fixed_quotas"],
        "shortfall_reason": shortfall_reason,
        "status": "pass",
        "target_id": target.target_id,
        "target_source_ranges": list(target.query.source_ranges),
        "token_counter_version": preparation.common.raw["context"][
            "token_counter_version"
        ],
    }
    manifest_sha = write_canonical_json(
        output_directory / "retrieval_manifest.json", manifest
    )
    return {
        "context_sha256": context_sha,
        "retrieval_manifest_sha256": manifest_sha,
        "selected_chunk_count": len(selected),
        "target_id": target.target_id,
    }


def build_formal_artifact_set(
    preparation: FormalPreparation,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=False)
    results = [
        build_formal_target_artifacts(
            preparation,
            target,
            output_root / target.target_id,
        )
        for target in preparation.targets
    ]
    return {
        "target_count": len(results),
        "targets": results,
    }


def _write_mismatch_evidence(work: Path, message: str) -> None:
    write_canonical_json(
        work / "mismatch_evidence.json",
        {
            "artifact_schema_version": "rag-formal-context-mismatch-v1",
            "canonical_output_published": False,
            "error": message,
            "retry_permitted": False,
            "status": "failed_determinism_or_audit",
        },
    )


def _update_target_configs_after_audit(
    preparation: FormalPreparation,
    canonical_output: Path,
    work: Path,
) -> None:
    staged = work / "staged-target-configs"
    backups = work / "target-config-backups"
    staged.mkdir()
    backups.mkdir()
    for target in preparation.targets:
        raw = json.loads(target.path.read_text(encoding="utf-8"))
        context_path = canonical_output / target.target_id / "context.txt"
        raw["context_status"] = "generated_and_audited"
        raw["context_sha256"] = sha256_file(context_path)
        write_canonical_json(staged / target.path.name, raw)
        shutil.copy2(target.path, backups / target.path.name)

    replaced: list[FormalTarget] = []
    try:
        for target in preparation.targets:
            (staged / target.path.name).replace(target.path)
            replaced.append(target)
    except Exception:
        for target in replaced:
            shutil.copy2(backups / target.path.name, target.path)
        raise


def execute_formal_contexts(
    *,
    project_root: str | Path,
    output_root: str | Path = "rag/retrieval/formal",
    work_root: str | Path | None = None,
    preparation: FormalPreparation | None = None,
    build_fn: Callable[[FormalPreparation, Path], Mapping[str, Any]] = build_formal_artifact_set,
    audit_fn: Callable[[FormalPreparation, Path], Mapping[str, Any]] = audit_formal_context_set,
    update_fn: Callable[[FormalPreparation, Path, Path], None] = _update_target_configs_after_audit,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    prepared = preparation or prepare_formal_contexts(root)
    output = Path(output_root)
    if not output.is_absolute():
        output = root.joinpath(*posix_relative_path(output).split("/"))
    work = Path(work_root) if work_root is not None else output.with_name(output.name + ".rebuild-work")
    if not work.is_absolute():
        work = root.joinpath(*posix_relative_path(work).split("/"))
    if output.exists():
        raise FormalContextBuildError(
            f"canonical formal output exists; overwrite prohibited: {output}"
        )
    if work.exists():
        raise FormalContextBuildError(
            f"stale formal work evidence exists; retry prohibited: {work}"
        )
    if len(prepared.targets) != 17 or any(
        target.raw.get("enabled") is not False for target in prepared.targets
    ):
        raise FormalContextBuildError("execution requires exactly 17 disabled targets")

    output.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True)
    build_a = work / "build-a"
    build_b = work / "build-b"
    publish = work / "publish"
    try:
        first = build_fn(prepared, build_a)
        second = build_fn(prepared, build_b)
        if int(first.get("target_count", -1)) != 17 or int(second.get("target_count", -1)) != 17:
            raise FormalContextBuildError("independent build target count differs from 17")
        comparisons = compare_artifact_trees(build_a, build_b)
        audit_a = audit_fn(prepared, build_a)
        audit_b = audit_fn(prepared, build_b)
        if audit_a.get("status") != "pass" or audit_b.get("status") != "pass":
            raise FormalContextBuildError("aggregate audit did not pass twice")
        shutil.copytree(build_a, publish)
        publish.replace(output)
        update_fn(prepared, output, work)
        shutil.rmtree(work)
        return {
            "artifact_comparison": comparisons,
            "canonical_output": output,
            "deterministic": True,
            "status": "pass",
            "target_count": 17,
        }
    except Exception as exc:
        if work.exists():
            _write_mismatch_evidence(work, str(exc))
        raise


def write_plan_artifacts(
    plan: Mapping[str, Any],
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    if json_path.exists() or markdown_path.exists():
        raise FormalContextBuildError("plan artifact already exists; overwrite prohibited")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_temp = json_path.with_name(json_path.name + ".tmp")
    markdown_temp = markdown_path.with_name(markdown_path.name + ".tmp")
    if json_temp.exists() or markdown_temp.exists():
        raise FormalContextBuildError("stale plan temporary artifact exists")
    try:
        write_canonical_json(json_temp, plan)
        markdown_temp.write_text(
            render_plan_markdown(plan), encoding="utf-8", newline="\n"
        )
        json_temp.replace(json_path)
        markdown_temp.replace(markdown_path)
    except Exception:
        json_temp.unlink(missing_ok=True)
        markdown_temp.unlink(missing_ok=True)
        raise


def run_plan_only(
    *,
    project_root: str | Path,
    plan_json: str | Path,
    plan_markdown: str | Path,
) -> dict[str, Any]:
    preparation = prepare_formal_contexts(project_root)
    plan = build_plan(preparation)
    root = preparation.project_root
    json_path = Path(plan_json)
    markdown_path = Path(plan_markdown)
    if not json_path.is_absolute():
        json_path = root.joinpath(*posix_relative_path(json_path).split("/"))
    if not markdown_path.is_absolute():
        markdown_path = root.joinpath(*posix_relative_path(markdown_path).split("/"))
    write_plan_artifacts(plan, json_path=json_path, markdown_path=markdown_path)
    return plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or execute deterministic formal RAG context generation."
    )
    parser.add_argument("--project-root", default=".")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan-only", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--plan-json",
        default="reports/rag/formal/preparation/formal-context-build-plan-v1.json",
    )
    parser.add_argument(
        "--plan-md",
        default="reports/rag/formal/preparation/formal-context-build-plan-v1.md",
    )
    parser.add_argument("--output-root", default="rag/retrieval/formal")
    parser.add_argument("--work-root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.plan_only:
            result = run_plan_only(
                project_root=args.project_root,
                plan_json=args.plan_json,
                plan_markdown=args.plan_md,
            )
        else:
            result = execute_formal_contexts(
                project_root=args.project_root,
                output_root=args.output_root,
                work_root=args.work_root,
            )
    except (
        FormalAuditError,
        FormalContextBuildError,
        FormalPreparationError,
        OSError,
        ValueError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    printable = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in result.items()
        if key not in {"targets", "artifact_comparison"}
    }
    print(json.dumps(printable, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
