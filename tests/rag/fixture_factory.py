from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable

from scripts.rag.canonical import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    write_canonical_json,
    write_canonical_jsonl,
)


COMMIT = "1" * 40


def stable_id(*parts: str) -> str:
    return sha256_bytes("\n".join(parts).encode("utf-8"))


def make_chunk(
    *,
    repository: str,
    path: str,
    start_byte: int,
    content: str,
    canonical_name: str,
    kind: str,
    short_symbol: str | None = None,
    parent_symbol: str | None = None,
    signature: str | None = None,
    start_line: int = 1,
    namespace: str | None = None,
    base_symbols: list[str] | None = None,
    is_template: bool = False,
) -> dict[str, Any]:
    encoded = content.encode("utf-8")
    end_byte = start_byte + len(encoded)
    line_count = content.count("\n") + 1
    return {
        "base_symbols": base_symbols or [],
        "canonical_name": canonical_name,
        "chunk_id": stable_id(repository, path, str(start_byte), canonical_name, kind, content),
        "chunk_method": "tree-sitter-symbol-v1",
        "content": content,
        "content_sha256": sha256_bytes(encoded),
        "end_byte": end_byte,
        "end_column": 0,
        "end_line": start_line + line_count - 1,
        "is_template": is_template,
        "kind": kind,
        "line_count": line_count,
        "namespace": namespace,
        "parent_symbol": parent_symbol,
        "path": path,
        "repository": repository,
        "repository_commit": COMMIT,
        "short_symbol": short_symbol or canonical_name.rsplit("::", 1)[-1],
        "signature": signature or canonical_name,
        "source_sha256": stable_id(repository, path, "source"),
        "start_byte": start_byte,
        "start_column": 0,
        "start_line": start_line,
        "symbol": canonical_name,
        "symbol_end_byte": end_byte,
        "symbol_start_byte": start_byte,
    }


def symbol_for_chunk(chunk: dict[str, Any], *, role: str = "definition") -> dict[str, Any]:
    canonical = str(chunk["canonical_name"])
    short = str(chunk["short_symbol"])
    parent = chunk.get("parent_symbol")
    lookup = {canonical, short}
    if parent:
        lookup.add(f"{parent}::{short}")
    return {
        "canonical_name": canonical,
        "chunk_id": chunk["chunk_id"],
        "cv_qualifier": None,
        "index_role": role,
        "index_version": "exact-symbol-index-v1",
        "kind": chunk["kind"],
        "lookup_keys": sorted(lookup),
        "noexcept": "noexcept" in str(chunk["signature"]),
        "parameter_count": 0 if "(" in str(chunk["signature"]) else None,
        "parent_symbol": parent,
        "path": chunk["path"],
        "ref_qualifier": None,
        "short_name": short,
        "signature": chunk["signature"],
        "start_line": chunk["start_line"],
        "template_arity": 1 if chunk.get("is_template") else 0,
    }


def write_index(
    root: Path,
    *,
    repository: str,
    chunks: Iterable[dict[str, Any]],
    symbols: Iterable[dict[str, Any]] | None = None,
) -> Path:
    output = root / "index"
    output.mkdir(parents=True, exist_ok=True)
    chunk_list = sorted(
        [copy.deepcopy(item) for item in chunks],
        key=lambda item: (
            item["path"],
            item["start_byte"],
            item["end_byte"],
            item["kind"],
            item["chunk_id"],
        ),
    )
    symbol_list = (
        list(symbols)
        if symbols is not None
        else [symbol_for_chunk(item) for item in chunk_list]
    )
    symbol_list = sorted(
        [copy.deepcopy(item) for item in symbol_list],
        key=lambda item: (
            item["canonical_name"],
            item["index_role"],
            item["path"],
            item["start_line"],
            item["chunk_id"],
        ),
    )
    manifest = {
        "artifact_schema_version": "rag-index-v1",
        "chunk_count": len(chunk_list),
        "file_count": len({item["path"] for item in chunk_list}),
        "repository": repository,
        "repository_commit": COMMIT,
    }
    manifest_hash = write_canonical_json(output / "corpus_manifest.json", manifest)
    chunks_hash = write_canonical_jsonl(output / "chunks.jsonl", chunk_list)
    symbols_hash = write_canonical_jsonl(output / "symbol_index.jsonl", symbol_list)
    validation = {
        "artifact_hashes": {
            "chunks.jsonl": chunks_hash,
            "corpus_manifest.json": manifest_hash,
            "symbol_index.jsonl": symbols_hash,
        },
        "deterministic": True,
        "repository": repository,
        "repository_commit": COMMIT,
        "status": "pass",
        "unhandled_parser_error_count": 0,
    }
    write_canonical_json(output / "index_validation.json", validation)
    return output


def query_record(
    *,
    category: str,
    text: str,
    priority: str = "high",
    kind: str = "user_defined_type",
    relation: str = "type_reference",
    path: str = "src/formal.cpp",
    start_byte: int = 0,
) -> dict[str, Any]:
    query_id = stable_id(category, text, kind, relation)
    return {
        "canonical_text": text,
        "category": category,
        "evidence_count": 1,
        "evidence_locations": [
            {
                "end_byte": start_byte + len(text.encode("utf-8")),
                "end_column": len(text),
                "end_line": 1,
                "path": path,
                "start_byte": start_byte,
                "start_column": 0,
                "start_line": 1,
            }
        ],
        "evidence_node_type": "fixture",
        "evidence_node_types": ["fixture"],
        "kind": kind,
        "location": {
            "end_byte": start_byte + len(text.encode("utf-8")),
            "end_column": len(text),
            "end_line": 1,
            "path": path,
            "start_byte": start_byte,
            "start_column": 0,
            "start_line": 1,
        },
        "priority": priority,
        "qualified": "::" in text,
        "query_id": query_id,
        "relation": relation,
        "text": text,
    }


def write_query(
    root: Path,
    *,
    repository: str,
    target_id: str,
    records: Iterable[dict[str, Any]],
    source_ranges: list[dict[str, Any]] | None = None,
    granularity: str = "class_span",
) -> Path:
    categories = {
        "base_classes": [],
        "constants_and_macros": [],
        "dependency_candidates": [],
        "documentation_references": [],
        "enums": [],
        "function_calls": [],
        "includes": [],
        "nested_types": [],
        "target_symbols": [],
        "user_defined_types": [],
    }
    for record in records:
        categories[str(record["category"])].append(copy.deepcopy(record))
    for values in categories.values():
        values.sort(key=lambda item: (item["canonical_text"], item["query_id"]))
    ranges = source_ranges or [
        {
            "end_byte": 20,
            "end_column": 0,
            "end_line": 2,
            "git_blob_sha256": stable_id(repository, "src/formal.cpp", "source"),
            "locator_kind": "fixture",
            "normalized_range_sha256": stable_id("range"),
            "normalized_source_sha256": stable_id(repository, "src/formal.cpp", "source"),
            "path": "src/formal.cpp",
            "start_byte": 0,
            "start_column": 0,
            "start_line": 1,
        }
    ]
    payload = {
        "artifact_schema_version": "rag-query-v1",
        "condition_id": "rag-design-context-v1",
        "queries": categories,
        "query_method": "deterministic-cpp-query-v1",
        "query_version": "deterministic-cpp-query-v1",
        "source_ranges": ranges,
        "target": {
            "granularity": granularity,
            "repository_commit": COMMIT,
            "repository_id": repository,
            "target_id": target_id,
            "target_name": target_id,
        },
        "target_specific_manual_additions": False,
    }
    document = {
        **payload,
        "query_payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
    }
    path = root / f"{target_id}.query.json"
    write_canonical_json(path, document)
    return path


def refresh_index_validation(index_dir: Path) -> None:
    validation_path = index_dir / "index_validation.json"
    import json

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    for name in ("corpus_manifest.json", "chunks.jsonl", "symbol_index.jsonl"):
        validation["artifact_hashes"][name] = sha256_file(index_dir / name)
    write_canonical_json(validation_path, validation)
