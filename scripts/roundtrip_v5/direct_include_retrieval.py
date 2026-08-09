from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


QUOTED_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
RETRIEVAL_MODE = "direct_include_whole_file_one_hop"


@dataclass(frozen=True)
class IncludeOccurrence:
    source_file: str
    line: int
    include: str


@dataclass(frozen=True)
class Resolution:
    occurrence: IncludeOccurrence
    status: str
    resolved_path: str | None
    candidate_paths: tuple[str, ...]
    resolution_rule: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _normalize_rel(value: str) -> str:
    return PurePosixPath(value.replace("\\", "/")).as_posix()


def tracked_files(repository: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git ls-files failed for {repository}: {stderr.strip()}")
    values = [item for item in result.stdout.decode("utf-8", errors="strict").split("\0") if item]
    return sorted(_normalize_rel(item) for item in values)


def extract_quoted_includes(repository: Path, source_files: list[str]) -> list[IncludeOccurrence]:
    result: list[IncludeOccurrence] = []
    for source_file in source_files:
        path = repository / source_file
        text = _read_text(path)
        for line_number, line in enumerate(text.splitlines(), start=1):
            match = QUOTED_INCLUDE_RE.match(line)
            if match:
                result.append(
                    IncludeOccurrence(
                        source_file=_normalize_rel(source_file),
                        line=line_number,
                        include=_normalize_rel(match.group(1)),
                    )
                )
    return result


def _candidate_paths(
    occurrence: IncludeOccurrence,
    tracked: set[str],
) -> tuple[list[str], str]:
    include_name = occurrence.include
    source_parent = PurePosixPath(occurrence.source_file).parent

    same_dir = _normalize_rel((source_parent / include_name).as_posix())
    if same_dir in tracked:
        return [same_dir], "including_file_directory"

    root_relative = _normalize_rel(include_name)
    if root_relative in tracked:
        return [root_relative], "repository_root"

    suffix = "/" + root_relative
    suffix_matches = sorted(path for path in tracked if path.endswith(suffix))
    if suffix_matches:
        return suffix_matches, "unique_repository_suffix" if len(suffix_matches) == 1 else "ambiguous_repository_suffix"

    basename = PurePosixPath(root_relative).name
    basename_matches = sorted(path for path in tracked if PurePosixPath(path).name == basename)
    if basename_matches:
        return basename_matches, "unique_repository_basename" if len(basename_matches) == 1 else "ambiguous_repository_basename"

    return [], "not_found_in_tracked_repository"


def resolve_occurrences(
    occurrences: list[IncludeOccurrence],
    tracked_files_list: list[str],
    source_files: list[str],
) -> list[Resolution]:
    tracked = set(tracked_files_list)
    target_sources = {_normalize_rel(path) for path in source_files}
    results: list[Resolution] = []

    for occurrence in occurrences:
        candidates, rule = _candidate_paths(occurrence, tracked)
        if len(candidates) == 1:
            resolved = candidates[0]
            status = "target_source" if resolved in target_sources else "resolved_external"
            results.append(
                Resolution(
                    occurrence=occurrence,
                    status=status,
                    resolved_path=resolved,
                    candidate_paths=(resolved,),
                    resolution_rule=rule,
                )
            )
        elif len(candidates) > 1:
            results.append(
                Resolution(
                    occurrence=occurrence,
                    status="ambiguous",
                    resolved_path=None,
                    candidate_paths=tuple(candidates),
                    resolution_rule=rule,
                )
            )
        else:
            results.append(
                Resolution(
                    occurrence=occurrence,
                    status="unresolved",
                    resolved_path=None,
                    candidate_paths=(),
                    resolution_rule=rule,
                )
            )
    return results


def selected_paths(resolutions: list[Resolution]) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for resolution in resolutions:
        if resolution.status != "resolved_external" or resolution.resolved_path is None:
            continue
        if resolution.resolved_path not in seen:
            seen.add(resolution.resolved_path)
            selected.append(resolution.resolved_path)
    return selected


def render_repository_context(repository: Path, paths: list[str]) -> str:
    lines = [
        "# Repository-local direct-include context",
        "",
        "以下は対象source_filesが直接 #include \"...\" しているリポジトリ内ファイルの全文である。",
        "これらは対象コードを理解するための参照情報であり、再実装対象そのものではない。",
        "対象source_files自身は重複を避けるためここには含めない。",
        "取得したファイルからさらにinclude先を辿らない（1-hop限定）。",
        "",
    ]
    if not paths:
        lines.extend(["該当する対象外のrepository-local direct includeはない。", ""])
        return "\n".join(lines)

    for relative in paths:
        text = _read_text(repository / relative).rstrip()
        lines.extend(
            [
                f"===== BEGIN REPOSITORY CONTEXT FILE: {relative} =====",
                text,
                f"===== END REPOSITORY CONTEXT FILE: {relative} =====",
                "",
            ]
        )
    return "\n".join(lines)


def build_bundle(
    *,
    repository: Path,
    repository_commit: str,
    source_files: list[str],
    generic_knowledge_path: Path,
    pair_id: str,
) -> dict[str, Any]:
    normalized_sources = [_normalize_rel(path) for path in source_files]
    tracked = tracked_files(repository)
    occurrences = extract_quoted_includes(repository, normalized_sources)
    resolutions = resolve_occurrences(occurrences, tracked, normalized_sources)
    paths = selected_paths(resolutions)

    generic_text = _read_text(generic_knowledge_path).strip()
    if not generic_text:
        raise ValueError(f"Generic design knowledge is empty: {generic_knowledge_path}")

    repository_context = render_repository_context(repository, paths).rstrip()
    combined_context = (
        "# Generic detailed-design guidance\n\n"
        + generic_text
        + "\n\n"
        + repository_context
        + "\n"
    )

    selected = []
    for rank, relative in enumerate(paths, start=1):
        raw = (repository / relative).read_bytes()
        selected.append(
            {
                "rank": rank,
                "path": relative,
                "selection_reason": "direct quoted include from target source",
                "chunk_type": "whole_file_direct_include",
                "whole_file": True,
                "sha256": _sha256_bytes(raw),
                "bytes": len(raw),
            }
        )

    resolution_rows = []
    for resolution in resolutions:
        resolution_rows.append(
            {
                "source_file": resolution.occurrence.source_file,
                "line": resolution.occurrence.line,
                "include": resolution.occurrence.include,
                "status": resolution.status,
                "resolved_path": resolution.resolved_path,
                "candidate_paths": list(resolution.candidate_paths),
                "resolution_rule": resolution.resolution_rule,
            }
        )

    unresolved = [row for row in resolution_rows if row["status"] == "unresolved"]
    ambiguous = [row for row in resolution_rows if row["status"] == "ambiguous"]

    return {
        "pair_id": pair_id,
        "repository_commit": repository_commit,
        "source_files": normalized_sources,
        "tracked_file_count": len(tracked),
        "quoted_include_count": len(occurrences),
        "resolutions": resolution_rows,
        "selected": selected,
        "selected_paths": paths,
        "unresolved": unresolved,
        "ambiguous": ambiguous,
        "repository_context": repository_context + "\n",
        "combined_context": combined_context,
        "combined_context_sha256": _sha256_bytes(combined_context.encode("utf-8")),
        "combined_context_bytes": len(combined_context.encode("utf-8")),
        "generic_knowledge_sha256": _sha256_bytes((generic_text + "\n").encode("utf-8")),
    }


def write_artifacts(bundle: dict[str, Any], retrieval_dir: Path) -> None:
    retrieval_dir.mkdir(parents=True, exist_ok=True)

    query = {
        "schema_version": "1.0",
        "pair_id": bundle["pair_id"],
        "retrieval_mode": RETRIEVAL_MODE,
        "source_files": bundle["source_files"],
        "quoted_includes": [
            {
                "source_file": row["source_file"],
                "line": row["line"],
                "include": row["include"],
            }
            for row in bundle["resolutions"]
        ],
        "query_generation": "deterministic_non_llm",
        "target_specific_tuning": False,
    }
    _write_json(retrieval_dir / "query.json", query)

    _write_json(
        retrieval_dir / "corpus_manifest.json",
        {
            "schema_version": "1.0",
            "repository_commit": bundle["repository_commit"],
            "tracked_files_only": True,
            "tracked_file_count": bundle["tracked_file_count"],
            "retrieval_depth": 1,
            "recursive_include_expansion": False,
        },
    )

    _write_jsonl(retrieval_dir / "candidates.jsonl", bundle["resolutions"])
    _write_jsonl(retrieval_dir / "selected_chunks.jsonl", bundle["selected"])
    _write_text(retrieval_dir / "context.txt", bundle["combined_context"])
    _write_json(
        retrieval_dir / "retrieval_manifest.json",
        {
            "schema_version": "1.0",
            "pair_id": bundle["pair_id"],
            "retrieval_mode": RETRIEVAL_MODE,
            "repository_commit": bundle["repository_commit"],
            "quoted_includes_only": True,
            "tracked_files_only": True,
            "whole_file": True,
            "one_hop": True,
            "exclude_target_source_files": True,
            "target_specific_tuning": False,
            "selected_file_count": len(bundle["selected"]),
            "selected_paths": bundle["selected_paths"],
            "unresolved_count": len(bundle["unresolved"]),
            "ambiguous_count": len(bundle["ambiguous"]),
            "combined_context_sha256": bundle["combined_context_sha256"],
            "combined_context_bytes": bundle["combined_context_bytes"],
            "generic_knowledge_sha256": bundle["generic_knowledge_sha256"],
        },
    )
