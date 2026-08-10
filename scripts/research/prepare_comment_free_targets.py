from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    out: list[str] = []
    n = len(text)
    i = 0
    state = "normal"
    raw_terminator = None
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


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create comment-free copies of the 17 formal target-owned inputs "
            "without modifying the Git submodules."
        )
    )
    parser.add_argument("--project-root", default=".", type=Path)
    parser.add_argument(
        "--manifest",
        default=Path("configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json"),
        type=Path,
    )
    parser.add_argument(
        "--output-root",
        default=Path("derived/comment-ablation-v1/target-inputs"),
        type=Path,
    )
    args = parser.parse_args()

    root = args.project_root.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else root / args.manifest
    output_root = args.output_root if args.output_root.is_absolute() else root / args.output_root

    if not manifest_path.is_file():
        raise RuntimeError(f"Formal manifest does not exist: {manifest_path}")
    if output_root.exists():
        raise RuntimeError(
            f"Output already exists: {output_root}\n"
            "Refusing to overwrite an existing comment-ablation input set."
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("formal_target_count") != 17:
        raise RuntimeError(
            f"Expected formal_target_count=17, got {manifest.get('formal_target_count')}"
        )

    result_manifest = {
        "artifact_schema_version": "comment-ablation-target-inputs-v1",
        "source_manifest": str(manifest_path.relative_to(root)).replace("\\", "/"),
        "target_count": 17,
        "targets": [],
    }

    for entry in manifest["targets"]:
        config_path = root / entry["target_config_path"]
        cfg = json.loads(config_path.read_text(encoding="utf-8-sig"))
        target_id = cfg["target_id"]
        repo_root = root / cfg["repository"]["path"]

        target_out = output_root / target_id
        target_out.mkdir(parents=True, exist_ok=False)

        target_record = {
            "target_id": target_id,
            "repository": cfg["repository"]["id"],
            "repository_commit": cfg["repository"]["commit"],
            "units": [],
        }

        for unit in cfg["target_owned_inputs"]:
            if not unit.get("replacement_required", False):
                continue

            source_path = repo_root / unit["path"]
            source_bytes = source_path.read_bytes()
            scope = unit["scope"]

            if scope == "full_file":
                selected = source_bytes
            elif scope == "byte_span":
                selected = source_bytes[unit["start_byte"]:unit["end_byte"]]
            else:
                raise RuntimeError(f"Unsupported scope for {target_id}: {scope}")

            text = selected.decode("utf-8", errors="surrogateescape")
            stripped, line_count, block_count = strip_cpp_comments(text)
            stripped_again, lc2, bc2 = strip_cpp_comments(stripped)

            if stripped_again != stripped or lc2 != 0 or bc2 != 0:
                raise RuntimeError(
                    "Comments remain or stripping is not idempotent: "
                    f"{target_id}/{unit['file_id']}/{unit['unit_id']}"
                )
            if text.count("\n") != stripped.count("\n"):
                raise RuntimeError(
                    f"Line count changed: {target_id}/{unit['file_id']}/{unit['unit_id']}"
                )

            suffix = Path(unit["path"]).suffix or ".txt"
            output_name = f"{unit['file_id']}_{unit['unit_id']}{suffix}"
            output_path = target_out / output_name
            output_bytes = stripped.encode("utf-8", errors="surrogateescape")
            output_path.write_bytes(output_bytes)

            target_record["units"].append({
                "file_id": unit["file_id"],
                "unit_id": unit["unit_id"],
                "original_path": unit["path"],
                "scope": scope,
                "source_sha256": sha256(selected),
                "comment_free_sha256": sha256(output_bytes),
                "line_comments_removed": line_count,
                "block_comments_removed": block_count,
                "total_comments_removed": line_count + block_count,
                "output_path": str(output_path.relative_to(root)).replace("\\", "/"),
            })

        result_manifest["targets"].append(target_record)

    out_manifest = output_root / "comment_free_manifest.json"
    out_manifest.write_text(
        json.dumps(result_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    total_comments = sum(
        unit["total_comments_removed"]
        for target in result_manifest["targets"]
        for unit in target["units"]
    )

    print("COMMENT-FREE TARGET INPUTS CREATED")
    print(f"targets={len(result_manifest['targets'])}")
    print(f"comments_removed={total_comments}")
    print(f"output={output_root}")
    print(f"manifest={out_manifest}")


if __name__ == "__main__":
    main()
