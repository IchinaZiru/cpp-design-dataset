"""Aggregate validation for deterministic formal retrieval context artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.artifacts import LoadedQuery, load_query_artifact
from scripts.rag.candidate_filters import apply_candidate_filters, path_byte_overlap_v1
from scripts.rag.canonical import (
    posix_relative_path,
    sha256_bytes,
    sha256_file,
    write_canonical_json,
)
from scripts.rag.external_retrieval import (
    ExternalRetrievalConfig,
    _context_block,
    _context_header,
    lexical_token_count,
)
from scripts.rag.formal_preparation import (
    FormalCommonConfig,
    FormalPreparation,
    FormalPreparationError,
    FormalTarget,
    prepare_formal_contexts,
)


class FormalAuditError(RuntimeError):
    """Raised when any formal context artifact violates the frozen protocol."""


EXPECTED_TARGET_FILES = {
    "candidates.jsonl",
    "context.txt",
    "corpus_manifest.json",
    "query.json",
    "retrieval_manifest.json",
    "selected_chunks.jsonl",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FormalAuditError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FormalAuditError(f"JSON root must be an object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FormalAuditError(f"cannot load JSONL {path}: {exc}") from exc
    records: list[dict[str, Any]] = []
    for number, line in enumerate(lines, start=1):
        if not line:
            raise FormalAuditError(f"blank JSONL line: {path}:{number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FormalAuditError(f"invalid JSONL line: {path}:{number}") from exc
        if not isinstance(value, dict):
            raise FormalAuditError(f"JSONL value is not an object: {path}:{number}")
        records.append(value)
    return records


def _external_config(common: FormalCommonConfig) -> ExternalRetrievalConfig:
    return ExternalRetrievalConfig(path=common.path, sha256=common.sha256, raw=common.raw)


def render_context(
    *,
    common: FormalCommonConfig,
    query: LoadedQuery,
    selected: Iterable[Mapping[str, Any]],
) -> str:
    config = _external_config(common)
    items = list(selected)
    return _context_header(query, config) + "".join(
        _context_block(item, item, rank)
        for rank, item in enumerate(items, start=1)
    )


def _timestamp_keys(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered = str(key).lower()
            if "timestamp" in lowered or lowered.endswith("_at") or lowered.endswith("_at_utc"):
                found.append(str(key))
            found.extend(_timestamp_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_timestamp_keys(nested))
    return found


def audit_selection(
    *,
    common: FormalCommonConfig,
    query: LoadedQuery,
    candidate_config: Any,
    selected: list[dict[str, Any]],
    context: str,
    expected_context_sha256: str,
    manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    top_k = int(common.raw["selection"]["retrieval_top_k"])
    budget = int(common.raw["context"]["budget_tokens"])
    quotas = {
        int(tier): int(value)
        for tier, value in common.raw["selection"]["fixed_quotas"].items()
    }
    if len(selected) > top_k:
        errors.append(f"selected_count_exceeds_top_k:{len(selected)}>{top_k}")
    context_tokens = lexical_token_count(context)
    if context_tokens > budget:
        errors.append(f"context_budget_exceeded:{context_tokens}>{budget}")
    tier_counts = Counter(int(item.get("tier", -1)) for item in selected)
    for tier, count in sorted(tier_counts.items()):
        if tier not in quotas:
            errors.append(f"invalid_tier:{tier}")
        elif count > quotas[tier]:
            errors.append(f"tier_quota_exceeded:{tier}:{count}>{quotas[tier]}")

    chunk_ids = [str(item.get("chunk_id", "")) for item in selected]
    content_hashes = [str(item.get("content_sha256", "")) for item in selected]
    if len(set(chunk_ids)) != len(chunk_ids):
        errors.append("duplicate_chunk_id")
    if len(set(content_hashes)) != len(content_hashes):
        errors.append("duplicate_content_sha256")
    if [int(item.get("selection_rank", -1)) for item in selected] != list(
        range(1, len(selected) + 1)
    ):
        errors.append("selected_chunk_order")

    for item in selected:
        chunk_id = str(item.get("chunk_id", ""))
        content = str(item.get("content", ""))
        if sha256_bytes(content.encode("utf-8")) != str(item.get("content_sha256", "")):
            errors.append(f"content_hash_mismatch:{chunk_id}")
        raw_path = str(item.get("path", ""))
        try:
            if re.match(r"^[A-Za-z]:/", raw_path) or raw_path.startswith(("//", "\\\\")):
                raise ValueError("platform-absolute path")
            normalized = posix_relative_path(raw_path)
            if normalized != str(item.get("path", "")):
                errors.append(f"noncanonical_path:{chunk_id}")
        except ValueError:
            errors.append(f"absolute_or_invalid_path:{chunk_id}")
        try:
            overlap = path_byte_overlap_v1(
                candidate_path=str(item["path"]),
                candidate_start=int(item["start_byte"]),
                candidate_end=int(item["end_byte"]),
                source_ranges=query.source_ranges,
                candidate_source_sha256=str(item.get("source_sha256", "")) or None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"overlap_validation_error:{chunk_id}:{exc}")
            overlap = []
        if overlap:
            errors.append(f"target_source_overlap:{chunk_id}")
        try:
            filtered = apply_candidate_filters(
                {**item, "_content": content},
                query=query,
                config=candidate_config,
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"filter_validation_error:{chunk_id}:{exc}")
        else:
            if filtered["exclusion_reasons"]:
                errors.append(
                    f"forbidden_or_leaking_content:{chunk_id}:"
                    + ",".join(filtered["exclusion_reasons"])
                )

    for left_index, left in enumerate(selected):
        for right in selected[left_index + 1 :]:
            if str(left.get("path")) != str(right.get("path")):
                continue
            if int(left.get("start_byte", -1)) < int(right.get("end_byte", -1)) and int(
                right.get("start_byte", -1)
            ) < int(left.get("end_byte", -1)):
                errors.append(
                    "equivalent_range_overlap:"
                    f"{left.get('chunk_id')}:{right.get('chunk_id')}"
                )

    actual_context_sha = sha256_bytes(context.encode("utf-8"))
    if actual_context_sha != expected_context_sha256:
        errors.append("context_sha256_mismatch")
    expected_context = render_context(common=common, query=query, selected=selected)
    if context != expected_context:
        errors.append("context_serialization_mismatch")

    if manifest is not None:
        if manifest.get("selected_chunk_count") != len(selected):
            errors.append("manifest_selected_count_mismatch")
        if manifest.get("selected_chunk_ids") != chunk_ids:
            errors.append("manifest_selected_order_mismatch")
        if manifest.get("context_token_count") != context_tokens:
            errors.append("manifest_token_count_mismatch")
        if len(selected) < top_k and not str(manifest.get("shortfall_reason", "")):
            errors.append("missing_shortfall_reason")
        if _timestamp_keys(manifest):
            errors.append("timestamp_in_content_hashed_manifest")

    if errors:
        raise FormalAuditError("; ".join(errors))
    return {
        "context_sha256": actual_context_sha,
        "context_token_count": context_tokens,
        "duplicate_chunk_id_count": 0,
        "duplicate_content_sha256_count": 0,
        "equivalent_range_overlap_count": 0,
        "forbidden_selected_count": 0,
        "selected_chunk_count": len(selected),
        "selected_tier_counts": {str(key): value for key, value in sorted(tier_counts.items())},
        "status": "pass",
        "target_source_overlap_count": 0,
    }


def audit_target_directory(
    preparation: FormalPreparation,
    target: FormalTarget,
    directory: Path,
) -> dict[str, Any]:
    if not directory.is_dir():
        raise FormalAuditError(f"target output directory is missing: {target.target_id}")
    names = {path.name for path in directory.iterdir() if path.is_file()}
    if names != EXPECTED_TARGET_FILES:
        raise FormalAuditError(
            f"target artifact set differs for {target.target_id}: {sorted(names)}"
        )
    if any(path.is_dir() for path in directory.iterdir()):
        raise FormalAuditError(f"nested artifact directory is prohibited: {target.target_id}")

    manifest = _load_json(directory / "retrieval_manifest.json")
    if manifest.get("artifact_schema_version") != "rag-formal-retrieval-manifest-v1":
        raise FormalAuditError(f"manifest schema differs: {target.target_id}")
    if manifest.get("status") != "pass" or manifest.get("deterministic") is not True:
        raise FormalAuditError(f"manifest status differs: {target.target_id}")
    expected_links = {
        "common_config_path": preparation.common.relative_path,
        "common_config_sha256": preparation.common.sha256,
        "index_validation_path": target.index_validation_relative_path,
        "index_validation_sha256": target.index_validation_sha256,
        "query_sha256": target.query.sha256,
        "repository_commit": target.query.repository_commit,
        "repository_id": target.query.repository_id,
        "target_id": target.target_id,
    }
    for key, expected in expected_links.items():
        if manifest.get(key) != expected:
            raise FormalAuditError(f"manifest {key} differs: {target.target_id}")

    hashes = manifest.get("artifact_hashes")
    if not isinstance(hashes, Mapping):
        raise FormalAuditError(f"manifest artifact hashes missing: {target.target_id}")
    for name in sorted(EXPECTED_TARGET_FILES - {"retrieval_manifest.json"}):
        actual = sha256_file(directory / name)
        if hashes.get(name) != actual:
            raise FormalAuditError(f"artifact hash differs: {target.target_id}/{name}")
    if (directory / "query.json").read_bytes() != target.query.path.read_bytes():
        raise FormalAuditError(f"frozen query bytes changed: {target.target_id}")
    query = load_query_artifact(directory / "query.json")
    candidates = _load_jsonl(directory / "candidates.jsonl")
    selected = _load_jsonl(directory / "selected_chunks.jsonl")
    context_bytes = (directory / "context.txt").read_bytes()
    if not context_bytes.endswith(b"\n") or b"\r" in context_bytes:
        raise FormalAuditError(f"context line endings differ: {target.target_id}")
    context = context_bytes.decode("utf-8")

    candidate_ids = [str(item.get("chunk_id", "")) for item in candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise FormalAuditError(f"duplicate candidate chunk ID: {target.target_id}")
    for item in selected:
        chunk = target.index.chunks_by_id.get(str(item.get("chunk_id", "")))
        if chunk is None:
            raise FormalAuditError(f"selected unknown index chunk: {target.target_id}")
        for field in ("path", "start_byte", "end_byte", "content_sha256"):
            if item.get(field) != chunk.get(field):
                raise FormalAuditError(
                    f"selected/index {field} differs: {target.target_id}/{item.get('chunk_id')}"
                )
    result = audit_selection(
        common=preparation.common,
        query=query,
        candidate_config=preparation.candidate_config,
        selected=selected,
        context=context,
        expected_context_sha256=str(manifest.get("context_sha256", "")),
        manifest=manifest,
    )
    if manifest.get("index_artifact_hashes") != target.index.artifact_hashes:
        raise FormalAuditError(f"index artifact hashes differ: {target.target_id}")
    return {"target_id": target.target_id, **result}


def relative_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def compare_artifact_trees(build_a: Path, build_b: Path) -> dict[str, dict[str, Any]]:
    first = relative_hashes(build_a)
    second = relative_hashes(build_b)
    if set(first) != set(second):
        raise FormalAuditError(
            "independent artifact path sets differ: "
            f"only_a={sorted(set(first) - set(second))}, "
            f"only_b={sorted(set(second) - set(first))}"
        )
    comparisons = {
        path: {
            "build_a_sha256": first[path],
            "build_b_sha256": second[path],
            "match": first[path] == second[path],
        }
        for path in sorted(first)
    }
    mismatches = [path for path, value in comparisons.items() if not value["match"]]
    if mismatches:
        raise FormalAuditError(
            "independent artifact byte hashes differ: " + ", ".join(mismatches)
        )
    return comparisons


def audit_formal_context_set(
    preparation: FormalPreparation,
    output_root: str | Path,
) -> dict[str, Any]:
    root = Path(output_root)
    if not root.is_absolute():
        root = preparation.project_root / root
    expected_ids = [target.target_id for target in preparation.targets]
    actual_ids = sorted(path.name for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
    if actual_ids != expected_ids:
        raise FormalAuditError("formal target directory set differs")
    if any(target.raw.get("enabled") is not False for target in preparation.targets):
        raise FormalAuditError("an enabled formal target was found")
    results = [
        audit_target_directory(preparation, target, root / target.target_id)
        for target in preparation.targets
    ]
    return {
        "artifact_schema_version": "rag-formal-context-audit-v1",
        "common_config_path": preparation.common.relative_path,
        "common_config_sha256": preparation.common.sha256,
        "enabled_target_count": 0,
        "status": "pass",
        "target_count": len(results),
        "targets": results,
    }


def render_audit_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Formal RAG context audit v1",
        "",
        f"- Status: `{report['status']}`",
        f"- Target count: `{report['target_count']}`",
        f"- Enabled target count: `{report['enabled_target_count']}`",
        f"- Common config SHA-256: `{report['common_config_sha256']}`",
        "",
        "| Target | Selected | Tokens | Context SHA-256 |",
        "|---|---:|---:|---|",
    ]
    for target in report["targets"]:
        lines.append(
            f"| `{target['target_id']}` | {target['selected_chunk_count']} | "
            f"{target['context_token_count']} | `{target['context_sha256']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def write_audit_report(
    report: Mapping[str, Any],
    *,
    json_path: Path,
    markdown_path: Path,
) -> None:
    if json_path.exists() or markdown_path.exists():
        raise FormalAuditError("audit report already exists; refusing overwrite")
    write_canonical_json(json_path, report)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_audit_markdown(report), encoding="utf-8", newline="\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit frozen formal RAG context artifacts.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output-root", default="rag/retrieval/formal")
    parser.add_argument(
        "--audit-json",
        default="reports/rag/formal/preparation/formal-context-audit-v1.json",
    )
    parser.add_argument(
        "--audit-md",
        default="reports/rag/formal/preparation/formal-context-audit-v1.md",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        preparation = prepare_formal_contexts(
            args.project_root, require_absent_outputs=False
        )
        report = audit_formal_context_set(preparation, args.output_root)
        root = preparation.project_root
        write_audit_report(
            report,
            json_path=root / posix_relative_path(args.audit_json),
            markdown_path=root / posix_relative_path(args.audit_md),
        )
    except (FormalAuditError, FormalPreparationError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
