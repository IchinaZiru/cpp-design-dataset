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
    render_audit_markdown,
    write_audit_report,
)
from scripts.rag.canonical import (
    canonical_json_bytes,
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


AUDIT_JSON_PATH = "reports/rag/formal/preparation/formal-context-audit-v1.json"
AUDIT_MARKDOWN_PATH = "reports/rag/formal/preparation/formal-context-audit-v1.md"


def _write_context(path: Path, value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.endswith("\n"):
        normalized += "\n"
    data = normalized.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)



def _ranges_overlap(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> bool:
    """Return whether two chunks overlap in the same committed source file."""

    if str(left.get("path", "")) != str(right.get("path", "")):
        return False
    if str(left.get("source_sha256", "")) != str(
        right.get("source_sha256", "")
    ):
        return False

    left_start = int(left["start_byte"])
    left_end = int(left["end_byte"])
    right_start = int(right["start_byte"])
    right_end = int(right["end_byte"])

    return left_start < right_end and right_start < left_end


def _deduplicate_overlapping_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Keep the highest-ranked candidate from every overlapping source range."""

    retained: list[dict[str, Any]] = []

    for candidate in candidates:
        if not bool(candidate.get("eligible")):
            continue

        retained_candidate = next(
            (
                item
                for item in retained
                if _ranges_overlap(candidate, item)
            ),
            None,
        )

        if retained_candidate is None:
            retained.append(candidate)
            continue

        candidate["eligible"] = False
        candidate["eligible_rank"] = None
        candidate["selection_status"] = "filtered"
        candidate["exclusion_reasons"] = sorted(
            set(candidate.get("exclusion_reasons", []))
            | {"overlapping_source_range"}
        )
        candidate["deduplicated_to_chunk_id"] = str(
            retained_candidate["chunk_id"]
        )

    eligible_rank = 0
    for candidate in candidates:
        if bool(candidate.get("eligible")):
            eligible_rank += 1
            candidate["eligible_rank"] = eligible_rank
        else:
            candidate["eligible_rank"] = None

    return candidates

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
    _deduplicate_overlapping_candidates(candidates)
    selected, context, context_tokens = select_context_candidates(
        candidates=candidates,
        chunks_by_id=target.index.chunks_by_id,
        query=target.query,
        config=config,
    )

    corpus_bytes = canonical_json_bytes(target.index.corpus_manifest)
    corpus_sha256 = sha256_bytes(corpus_bytes)
    if corpus_sha256 != target.index.artifact_hashes["corpus_manifest.json"]:
        raise FormalContextBuildError(
            f"canonical corpus manifest differs from frozen index: {target.target_id}"
        )
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
            "corpus_manifest.json": corpus_sha256,
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


def _write_mismatch_evidence(
    work: Path,
    message: str,
    *,
    canonical_output_exists: bool,
    partial_state: Mapping[str, Any],
    rollback: Mapping[str, Any],
) -> None:
    write_canonical_json(
        work / "mismatch_evidence.json",
        {
            "artifact_schema_version": "rag-formal-context-transaction-failure-v1",
            "canonical_output_published": canonical_output_exists,
            "canonical_success_artifact": False,
            "error": message,
            "partial_state": dict(partial_state),
            "retry_permitted": False,
            "rollback": dict(rollback),
            "status": "failed_transaction",
        },
    )


def _backup_target_configs(preparation: FormalPreparation, work: Path) -> Path:
    backups = work / "target-config-backups"
    backups.mkdir()
    for target in preparation.targets:
        shutil.copy2(target.path, backups / target.path.name)
    return backups


def _restore_target_configs(preparation: FormalPreparation, work: Path) -> int:
    backups = work / "target-config-backups"
    restored = 0
    for target in preparation.targets:
        backup = backups / target.path.name
        if backup.is_file():
            shutil.copy2(backup, target.path)
            restored += 1
    return restored


def _update_target_configs_after_audit(
    preparation: FormalPreparation,
    canonical_output: Path,
    work: Path,
) -> None:
    staged = work / "staged-target-configs"
    backups = work / "target-config-backups"
    staged.mkdir()
    if not backups.is_dir():
        _backup_target_configs(preparation, work)
    for target in preparation.targets:
        raw = json.loads(target.path.read_text(encoding="utf-8"))
        context_path = canonical_output / target.target_id / "context.txt"
        raw["context_status"] = "generated_and_audited"
        raw["context_sha256"] = sha256_file(context_path)
        write_canonical_json(staged / target.path.name, raw)

    for target in preparation.targets:
        (staged / target.path.name).replace(target.path)


def _resolve_project_output(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root.joinpath(*posix_relative_path(path).split("/"))


def _preserve_partial_file(path: Path, work: Path, name: str) -> bool:
    if not path.exists():
        return False
    partial = work / "partial-canonical-artifacts"
    partial.mkdir(exist_ok=True)
    path.replace(partial / name)
    return True


def execute_formal_contexts(
    *,
    project_root: str | Path,
    output_root: str | Path = "rag/retrieval/formal",
    work_root: str | Path | None = None,
    audit_json_path: str | Path = AUDIT_JSON_PATH,
    audit_markdown_path: str | Path = AUDIT_MARKDOWN_PATH,
    preparation: FormalPreparation | None = None,
    build_fn: Callable[[FormalPreparation, Path], Mapping[str, Any]] = build_formal_artifact_set,
    audit_fn: Callable[[FormalPreparation, Path], Mapping[str, Any]] = audit_formal_context_set,
    update_fn: Callable[[FormalPreparation, Path, Path], None] = _update_target_configs_after_audit,
    report_writer: Callable[..., Mapping[str, str]] = write_audit_report,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    prepared = preparation or prepare_formal_contexts(
        root, context_state="pre_generation"
    )
    output = _resolve_project_output(root, output_root)
    work = Path(work_root) if work_root is not None else output.with_name(output.name + ".rebuild-work")
    if not work.is_absolute():
        work = root.joinpath(*posix_relative_path(work).split("/"))
    audit_json = _resolve_project_output(root, audit_json_path)
    audit_markdown = _resolve_project_output(root, audit_markdown_path)
    if output.exists():
        raise FormalContextBuildError(
            f"canonical formal output exists; overwrite prohibited: {output}"
        )
    if work.exists():
        raise FormalContextBuildError(
            f"stale formal work evidence exists; retry prohibited: {work}"
        )
    if audit_json.exists() or audit_markdown.exists():
        raise FormalContextBuildError(
            "aggregate audit report exists; overwrite prohibited"
        )
    if len(prepared.targets) != 17 or any(
        target.raw.get("enabled") is not False
        or target.raw.get("context_status") != "not_generated"
        or target.raw.get("context_sha256") is not None
        for target in prepared.targets
    ):
        raise FormalContextBuildError(
            "execution requires exactly 17 disabled pre-generation targets"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True)
    build_a = work / "build-a"
    build_b = work / "build-b"
    publish = work / "publish"
    partial_state = {
        "aggregate_audit_reports_written": False,
        "canonical_context_published": False,
        "target_config_update_started": False,
        "post_generation_revalidation_completed": False,
    }
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
        if canonical_json_bytes(audit_a) != canonical_json_bytes(audit_b):
            raise FormalContextBuildError("independent aggregate audit reports differ")
        _backup_target_configs(prepared, work)
        shutil.copytree(build_a, publish)
        publish.replace(output)
        partial_state["canonical_context_published"] = True
        reported_audit_hashes = report_writer(
            audit_a,
            json_path=audit_json,
            markdown_path=audit_markdown,
        )
        partial_state["aggregate_audit_reports_written"] = True
        if not audit_json.is_file() or not audit_markdown.is_file():
            raise FormalContextBuildError("aggregate audit report was not persisted")
        if audit_json.read_bytes() != canonical_json_bytes(audit_a):
            raise FormalContextBuildError("aggregate audit JSON content differs")
        expected_markdown = render_audit_markdown(audit_a).encode("utf-8")
        if audit_markdown.read_bytes() != expected_markdown:
            raise FormalContextBuildError("aggregate audit Markdown content differs")
        audit_hashes = {
            "json_sha256": sha256_file(audit_json),
            "markdown_sha256": sha256_file(audit_markdown),
        }
        if reported_audit_hashes.get("json_sha256") != audit_hashes["json_sha256"]:
            raise FormalContextBuildError("aggregate audit JSON hash differs after persistence")
        if reported_audit_hashes.get("markdown_sha256") != audit_hashes["markdown_sha256"]:
            raise FormalContextBuildError("aggregate audit Markdown hash differs after persistence")
        partial_state["target_config_update_started"] = True
        update_fn(prepared, output, work)
        post_preparation = prepare_formal_contexts(
            root, context_state="post_generation"
        )
        post_audit = audit_fn(post_preparation, output)
        if post_audit.get("status") != "pass":
            raise FormalContextBuildError("post-generation aggregate audit did not pass")
        if canonical_json_bytes(post_audit) != canonical_json_bytes(audit_a):
            raise FormalContextBuildError("post-generation aggregate audit differs")
        partial_state["post_generation_revalidation_completed"] = True
        shutil.rmtree(work)
        return {
            "artifact_comparison": comparisons,
            "audit_json": audit_json,
            "audit_json_sha256": audit_hashes["json_sha256"],
            "audit_markdown": audit_markdown,
            "audit_markdown_sha256": audit_hashes["markdown_sha256"],
            "canonical_output": output,
            "deterministic": True,
            "status": "pass",
            "target_count": 17,
        }
    except Exception as exc:
        if work.exists():
            rollback: dict[str, Any] = {
                "audit_json_preserved": False,
                "audit_markdown_preserved": False,
                "canonical_context_preserved": False,
                "target_configs_restored": 0,
            }
            rollback_errors: list[str] = []
            try:
                rollback["target_configs_restored"] = _restore_target_configs(
                    prepared, work
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"target_config_restore:{rollback_exc}")
            try:
                rollback["audit_json_preserved"] = _preserve_partial_file(
                    audit_json, work, "formal-context-audit-v1.json"
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"audit_json_preserve:{rollback_exc}")
            try:
                rollback["audit_markdown_preserved"] = _preserve_partial_file(
                    audit_markdown, work, "formal-context-audit-v1.md"
                )
            except Exception as rollback_exc:
                rollback_errors.append(f"audit_markdown_preserve:{rollback_exc}")
            try:
                if output.exists():
                    output.replace(work / "partial-canonical-output")
                    rollback["canonical_context_preserved"] = True
            except Exception as rollback_exc:
                rollback_errors.append(f"canonical_context_preserve:{rollback_exc}")
            rollback["errors"] = rollback_errors
            _write_mismatch_evidence(
                work,
                str(exc),
                canonical_output_exists=output.exists(),
                partial_state=partial_state,
                rollback=rollback,
            )
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
    preparation = prepare_formal_contexts(
        project_root, context_state="pre_generation"
    )
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
