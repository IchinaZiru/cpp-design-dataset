from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def raw_string_start(text: str, pos: int):
    prefixes = ("u8R\"", "uR\"", "UR\"", "LR\"", "R\"")

    if pos > 0:
        prev = text[pos - 1]
        if prev.isalnum() or prev == "_":
            return None

    for prefix in prefixes:
        if not text.startswith(prefix, pos):
            continue

        delimiter_start = pos + len(prefix)
        paren = text.find("(", delimiter_start)
        if paren == -1:
            continue

        delimiter = text[delimiter_start:paren]
        if len(delimiter) > 16:
            continue
        if any(ch.isspace() or ch in "\\()" for ch in delimiter):
            continue

        return paren + 1, ")" + delimiter + "\""

    return None


def strip_cpp_comments(text: str) -> tuple[str, int, int]:
    """Remove C/C++ comments while preserving literals and physical newlines."""
    out: list[str] = []
    n = len(text)
    i = 0
    state = "normal"
    raw_terminator: str | None = None
    line_comments = 0
    block_comments = 0

    while i < n:
        if state == "normal":
            raw = raw_string_start(text, i)
            if raw is not None:
                raw_content_start, raw_terminator = raw
                out.append(text[i:raw_content_start])
                i = raw_content_start
                state = "raw"
                continue

            if text.startswith("//", i):
                line_comments += 1
                out.append("  ")
                i += 2
                state = "line_comment"
                continue

            if text.startswith("/*", i):
                block_comments += 1
                out.append("  ")
                i += 2
                state = "block_comment"
                continue

            ch = text[i]
            if ch == '"':
                out.append(ch)
                i += 1
                state = "string"
                continue
            if ch == "'":
                out.append(ch)
                i += 1
                state = "char"
                continue

            out.append(ch)
            i += 1
            continue

        if state == "string":
            ch = text[i]
            out.append(ch)
            i += 1
            if ch == "\\" and i < n:
                out.append(text[i])
                if text[i] == "\r" and i + 1 < n and text[i + 1] == "\n":
                    i += 1
                    out.append(text[i])
                i += 1
                continue
            if ch == '"':
                state = "normal"
            continue

        if state == "char":
            ch = text[i]
            out.append(ch)
            i += 1
            if ch == "\\" and i < n:
                out.append(text[i])
                if text[i] == "\r" and i + 1 < n and text[i + 1] == "\n":
                    i += 1
                    out.append(text[i])
                i += 1
                continue
            if ch == "'":
                state = "normal"
            continue

        if state == "raw":
            assert raw_terminator is not None
            end = text.find(raw_terminator, i)
            if end == -1:
                out.append(text[i:])
                i = n
                continue
            out.append(text[i:end + len(raw_terminator)])
            i = end + len(raw_terminator)
            raw_terminator = None
            state = "normal"
            continue

        if state == "line_comment":
            ch = text[i]
            if ch == "\\":
                if i + 1 < n and text[i + 1] == "\n":
                    out.append(" ")
                    out.append("\n")
                    i += 2
                    continue
                if i + 2 < n and text[i + 1] == "\r" and text[i + 2] == "\n":
                    out.append(" ")
                    out.append("\r\n")
                    i += 3
                    continue
            if ch == "\n":
                out.append("\n")
                i += 1
                state = "normal"
                continue
            if ch == "\r":
                out.append("\r")
                i += 1
                if i < n and text[i] == "\n":
                    out.append("\n")
                    i += 1
                state = "normal"
                continue
            out.append(" ")
            i += 1
            continue

        if state == "block_comment":
            if text.startswith("*/", i):
                out.append("  ")
                i += 2
                state = "normal"
                continue
            ch = text[i]
            out.append(ch if ch in "\r\n" else " ")
            i += 1
            continue

    return "".join(out), line_comments, block_comments


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        raise RuntimeError(f"Missing retrieval artifact: {path}")
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSONL {path}:{line_no}: {exc}") from exc
    return rows


def render_context(rows: list[dict]) -> str:
    parts = ["RAG_CONTEXT repository-dependencies-v1\n"]
    for row in rows:
        path = row["path"]
        content = row["content"]
        if content and not content.endswith("\n"):
            content += "\n"
        parts.append(
            "\n"
            f"### PATH: {path}\n"
            f"SOURCE_SHA256: {row['source_sha256']}\n"
            f"CONTENT_SHA256: {row['content_sha256']}\n"
            f"----- BEGIN DEPENDENCY HEADER CONTENT: {path} -----\n"
            f"{content}"
            f"----- END DEPENDENCY HEADER CONTENT: {path} -----\n"
        )
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the exact dependency selections used by comment-present formal-r2, "
            "remove C/C++ comments only from the selected dependency code, and create "
            "comment-free RAG contexts for the 17-target comment-ablation experiment."
        )
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--target-manifest",
        type=Path,
        default=Path("derived/comment-ablation-v1/target-inputs/comment_free_manifest.json"),
    )
    parser.add_argument(
        "--formal-r2-root",
        type=Path,
        default=Path("experiments/rag/roundtrip-ab-v1/formal-r2"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("derived/comment-ablation-v1/rag-context"),
    )
    args = parser.parse_args()

    root = args.project_root.resolve()
    target_manifest_path = args.target_manifest if args.target_manifest.is_absolute() else root / args.target_manifest
    formal_r2_root = args.formal_r2_root if args.formal_r2_root.is_absolute() else root / args.formal_r2_root
    output_root = args.output_root if args.output_root.is_absolute() else root / args.output_root

    if not target_manifest_path.is_file():
        raise RuntimeError(f"Missing target manifest: {target_manifest_path}")
    if not formal_r2_root.is_dir():
        raise RuntimeError(f"Missing formal-r2 root: {formal_r2_root}")
    if output_root.exists():
        raise RuntimeError(
            f"Output already exists: {output_root}\n"
            "Refusing to overwrite a frozen comment-free RAG context set."
        )

    target_manifest = json.loads(target_manifest_path.read_text(encoding="utf-8-sig"))
    target_ids = [t["target_id"] for t in target_manifest.get("targets", [])]
    if target_manifest.get("target_count") != 17 or len(target_ids) != 17 or len(set(target_ids)) != 17:
        raise RuntimeError("Expected exactly 17 unique targets in comment-free target manifest")

    output_root.mkdir(parents=True, exist_ok=False)

    overall = {
        "artifact_schema_version": "comment-ablation-rag-context-v1",
        "purpose": "same formal-r2 RAG dependency selection with C/C++ comments removed from selected dependency code",
        "selection_policy": "frozen-from-comment-present-formal-r2-condition-b",
        "source_formal_r2_root": str(formal_r2_root.relative_to(root)).replace("\\", "/"),
        "source_target_manifest": str(target_manifest_path.relative_to(root)).replace("\\", "/"),
        "target_count": 17,
        "targets": [],
    }

    total_dependencies = 0
    total_comments = 0
    targets_with_dependencies = 0
    targets_with_dependency_comments = 0

    for target_id in target_ids:
        old_retrieval = formal_r2_root / target_id / "condition-b" / "retrieval"
        old_candidates = old_retrieval / "candidates_selected.jsonl"
        old_query = old_retrieval / "query.json"
        old_manifest = old_retrieval / "retrieval_manifest.json"
        old_context = old_retrieval / "actual_rag_context.txt"

        for required in (old_candidates, old_query, old_manifest, old_context):
            if not required.is_file():
                raise RuntimeError(f"Missing formal-r2 retrieval artifact for {target_id}: {required}")

        source_manifest = json.loads(old_manifest.read_text(encoding="utf-8-sig"))
        rows = read_jsonl(old_candidates)
        expected_count = source_manifest.get("dependency_header_count")
        if expected_count != len(rows):
            raise RuntimeError(
                f"Dependency count mismatch for {target_id}: manifest={expected_count}, candidates={len(rows)}"
            )

        target_out = output_root / target_id
        target_out.mkdir(parents=True, exist_ok=False)
        shutil.copy2(old_query, target_out / "query.json")

        new_rows: list[dict] = []
        target_comments = 0
        dependency_records: list[dict] = []

        for row in rows:
            original_content = row["content"]
            stripped, line_comments, block_comments = strip_cpp_comments(original_content)
            stripped2, lc2, bc2 = strip_cpp_comments(stripped)
            if stripped2 != stripped or lc2 != 0 or bc2 != 0:
                raise RuntimeError(f"Comments remain after stripping dependency {target_id}:{row['path']}")
            if original_content.count("\n") != stripped.count("\n"):
                raise RuntimeError(f"Line count changed for dependency {target_id}:{row['path']}")

            new_row = dict(row)
            new_content_bytes = stripped.encode("utf-8")
            new_row["content"] = stripped
            new_row["content_bytes"] = len(new_content_bytes)
            new_row["content_sha256"] = sha256_bytes(new_content_bytes)
            new_row["comment_ablation"] = {
                "source_formal_r2_content_sha256": row["content_sha256"],
                "line_comments_removed": line_comments,
                "block_comments_removed": block_comments,
                "total_comments_removed": line_comments + block_comments,
            }
            new_rows.append(new_row)

            removed = line_comments + block_comments
            target_comments += removed
            dependency_records.append(
                {
                    "path": row["path"],
                    "source_sha256": row["source_sha256"],
                    "source_formal_r2_content_sha256": row["content_sha256"],
                    "comment_free_content_sha256": new_row["content_sha256"],
                    "line_comments_removed": line_comments,
                    "block_comments_removed": block_comments,
                    "total_comments_removed": removed,
                }
            )

        candidates_text = "".join(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            for row in new_rows
        )
        candidates_path = target_out / "candidates_selected_comment_free.jsonl"
        candidates_path.write_text(candidates_text, encoding="utf-8", newline="\n")

        context_text = render_context(new_rows)
        context_path = target_out / "actual_rag_context_comment_free.txt"
        context_path.write_text(context_text, encoding="utf-8", newline="\n")

        query_bytes = (target_out / "query.json").read_bytes()
        new_manifest = {
            "artifact_schema_version": "comment-ablation-rag-retrieval-manifest-v1",
            "target_id": target_id,
            "condition": "B-comment-free",
            "status": "pass",
            "selection_frozen_from_formal_r2": True,
            "source_formal_r2_retrieval_manifest_sha256": sha256_bytes(old_manifest.read_bytes()),
            "source_formal_r2_actual_rag_context_sha256": sha256_bytes(old_context.read_bytes()),
            "dependency_header_mode": source_manifest.get("dependency_header_mode"),
            "dependency_header_count": len(new_rows),
            "comments_removed": target_comments,
            "query_unchanged_from_formal_r2": True,
            "artifact_hashes": {
                "query.json": sha256_bytes(query_bytes),
                "candidates_selected_comment_free.jsonl": sha256_bytes(candidates_path.read_bytes()),
                "actual_rag_context_comment_free.txt": sha256_bytes(context_path.read_bytes()),
            },
            "context_bytes": len(context_path.read_bytes()),
            "context_sha256": sha256_bytes(context_path.read_bytes()),
            "dependencies": dependency_records,
        }
        (target_out / "retrieval_manifest_comment_free.json").write_text(
            json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

        if rows:
            targets_with_dependencies += 1
        if target_comments:
            targets_with_dependency_comments += 1
        total_dependencies += len(rows)
        total_comments += target_comments

        overall["targets"].append(
            {
                "target_id": target_id,
                "dependency_header_count": len(rows),
                "comments_removed": target_comments,
                "source_retrieval_path": str(old_retrieval.relative_to(root)).replace("\\", "/"),
                "output_path": str(target_out.relative_to(root)).replace("\\", "/"),
                "context_sha256": new_manifest["context_sha256"],
            }
        )

    overall.update(
        {
            "total_dependency_headers": total_dependencies,
            "total_dependency_comments_removed": total_comments,
            "targets_with_dependencies": targets_with_dependencies,
            "targets_with_dependency_comments": targets_with_dependency_comments,
        }
    )

    top_manifest = output_root / "comment_free_rag_context_manifest.json"
    top_manifest.write_text(
        json.dumps(overall, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("COMMENT-FREE RAG CONTEXTS CREATED")
    print(f"targets={len(target_ids)}")
    print(f"dependency_headers={total_dependencies}")
    print(f"dependency_comments_removed={total_comments}")
    print(f"targets_with_dependencies={targets_with_dependencies}")
    print(f"targets_with_dependency_comments={targets_with_dependency_comments}")
    print(f"output={output_root}")
    print(f"manifest={top_manifest}")


if __name__ == "__main__":
    main()
