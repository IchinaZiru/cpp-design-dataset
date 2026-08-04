"""Canonical JSON/JSONL serialization and SHA-256 helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


JSONValue = (
    None
    | bool
    | int
    | float
    | str
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)


def posix_relative_path(path: str | Path) -> str:
    """Return a normalized repository-relative POSIX path.

    Absolute paths and parent traversal are rejected because local machine paths
    must never enter reproducibility artifacts.
    """

    raw = str(path).replace("\\", "/")
    normalized = PurePosixPath(raw)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"path must be repository-relative: {path!s}")
    result = normalized.as_posix()
    if result in {"", "."}:
        raise ValueError("empty repository-relative path")
    return result


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically as UTF-8 with one final LF."""

    text = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (text + "\n").encode("utf-8")


def canonical_jsonl_bytes(records: Iterable[Mapping[str, Any]]) -> bytes:
    """Serialize records as canonical JSON Lines with one LF per record."""

    chunks: list[bytes] = []
    for record in records:
        line = json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        chunks.append((line + "\n").encode("utf-8"))
    return b"".join(chunks)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_canonical_json(path: str | Path, value: Any) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json_bytes(value)
    output.write_bytes(data)
    return sha256_bytes(data)


def write_canonical_jsonl(
    path: str | Path, records: Iterable[Mapping[str, Any]]
) -> str:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_jsonl_bytes(records)
    output.write_bytes(data)
    return sha256_bytes(data)
