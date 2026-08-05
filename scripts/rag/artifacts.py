"""Validated loaders for deterministic RAG index and query artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .canonical import (
    canonical_json_bytes,
    posix_relative_path,
    sha256_bytes,
    sha256_file,
)


class ArtifactLoadError(RuntimeError):
    """Raised when a frozen artifact set is incomplete or internally inconsistent."""


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class LoadedIndex:
    root: Path
    repository_id: str
    repository_commit: str
    corpus_manifest: dict[str, Any]
    index_validation: dict[str, Any]
    chunks: tuple[dict[str, Any], ...]
    chunks_by_id: dict[str, dict[str, Any]]
    symbol_records: tuple[dict[str, Any], ...]
    symbols_by_lookup_key: dict[str, tuple[dict[str, Any], ...]]
    artifact_hashes: dict[str, str]


@dataclass(frozen=True)
class LoadedQuery:
    path: Path
    document: dict[str, Any]
    target_id: str
    repository_id: str
    repository_commit: str
    granularity: str
    source_ranges: tuple[dict[str, Any], ...]
    records: tuple[dict[str, Any], ...]
    includes: tuple[str, ...]
    sha256: str


@dataclass(frozen=True)
class CandidateConfig:
    path: Path
    sha256: str
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "CandidateConfig":
        source = Path(path)
        raw = _load_json_object(source)
        if raw.get("artifact_schema_version") != "rag-candidate-config-v1":
            raise ArtifactLoadError("unsupported candidate config schema")
        stages = raw.get("stages")
        if not isinstance(stages, Mapping):
            raise ArtifactLoadError("candidate config stages must be an object")
        required_true = {"exact_symbol_retrieval", "candidate_filtering"}
        if any(stages.get(name) is not True for name in required_true):
            raise ArtifactLoadError("exact retrieval and filtering must be enabled")
        prohibited = {
            "bm25",
            "one_hop_expansion",
            "context_selection",
            "llm",
            "docker",
            "build_test",
            "formal_run",
        }
        enabled = sorted(name for name in prohibited if bool(stages.get(name)))
        if enabled:
            raise ArtifactLoadError(
                "pre-pilot candidate config enables prohibited stages: "
                + ", ".join(enabled)
            )
        if raw.get("target_specific_manual_query") is not False:
            raise ArtifactLoadError("target-specific manual query must remain disabled")
        return cls(path=source, sha256=sha256_file(source), raw=raw)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactLoadError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ArtifactLoadError(f"JSON root must be an object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ArtifactLoadError(f"cannot load JSONL {path}: {exc}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line:
            raise ArtifactLoadError(f"blank JSONL record at {path}:{line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ArtifactLoadError(
                f"invalid JSONL record at {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise ArtifactLoadError(
                f"JSONL record must be an object at {path}:{line_number}"
            )
        records.append(value)
    return records


def _validated_path(value: Any, *, field: str) -> str:
    try:
        return posix_relative_path(str(value))
    except ValueError as exc:
        raise ArtifactLoadError(f"invalid {field}: {value!r}") from exc


def _require_sha256(value: Any, *, field: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ArtifactLoadError(f"{field} is not a full SHA-256")
    return text


def _require_commit(value: Any, *, field: str) -> str:
    text = str(value).lower()
    if len(text) != 40 or any(character not in "0123456789abcdef" for character in text):
        raise ArtifactLoadError(f"{field} is not a full SHA-1")
    return text


def _verify_query_payload(document: Mapping[str, Any]) -> None:
    expected = _require_sha256(
        document.get("query_payload_sha256"), field="query_payload_sha256"
    )
    payload = dict(document)
    payload.pop("query_payload_sha256", None)
    actual = sha256_bytes(canonical_json_bytes(payload))
    if actual != expected:
        raise ArtifactLoadError(
            f"query payload hash mismatch: expected {expected}, got {actual}"
        )


def _iter_query_records(document: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    queries = document.get("queries")
    if not isinstance(queries, Mapping):
        raise ArtifactLoadError("query document lacks queries object")
    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for category, values in queries.items():
        if not isinstance(values, list):
            raise ArtifactLoadError(f"query category {category} must be an array")
        for value in values:
            if not isinstance(value, dict):
                raise ArtifactLoadError(f"query record in {category} must be an object")
            query_id = _require_sha256(value.get("query_id"), field="query_id")
            if query_id in seen:
                raise ArtifactLoadError(f"duplicate query_id: {query_id}")
            seen.add(query_id)
            record = dict(value)
            record.setdefault("category", str(category))
            if record["category"] != category:
                raise ArtifactLoadError(
                    f"query category mismatch for {query_id}: {record['category']} != {category}"
                )
            record["canonical_text"] = str(
                record.get("canonical_text", record.get("text", ""))
            )
            if not record["canonical_text"]:
                raise ArtifactLoadError(f"empty canonical_text for query {query_id}")
            priority = str(record.get("priority", "low"))
            if priority not in _PRIORITY_ORDER:
                raise ArtifactLoadError(f"invalid query priority: {priority}")
            records.append(record)
    return sorted(
        records,
        key=lambda item: (
            _PRIORITY_ORDER[str(item.get("priority", "low"))],
            str(item["category"]),
            str(item["canonical_text"]),
            str(item["query_id"]),
        ),
    )


def load_query_artifact(path: str | Path) -> LoadedQuery:
    source = Path(path)
    document = _load_json_object(source)
    _verify_query_payload(document)
    target = document.get("target")
    if not isinstance(target, Mapping):
        raise ArtifactLoadError("query document lacks target object")
    target_id = str(target.get("target_id", ""))
    repository_id = str(target.get("repository_id", ""))
    if not target_id or not repository_id:
        raise ArtifactLoadError("query target identity is incomplete")
    repository_commit = _require_commit(
        target.get("repository_commit"), field="target.repository_commit"
    )
    granularity = str(target.get("granularity", ""))
    if granularity not in {"module_files", "function", "class_span"}:
        raise ArtifactLoadError(f"unsupported target granularity: {granularity}")

    raw_ranges = document.get("source_ranges")
    if not isinstance(raw_ranges, list) or not raw_ranges:
        raise ArtifactLoadError("query document has no source ranges")
    ranges: list[dict[str, Any]] = []
    for item in raw_ranges:
        if not isinstance(item, dict):
            raise ArtifactLoadError("source range must be an object")
        path_value = _validated_path(item.get("path"), field="source range path")
        start = int(item.get("start_byte", -1))
        end = int(item.get("end_byte", -1))
        if start < 0 or end <= start:
            raise ArtifactLoadError(
                f"invalid source range for {path_value}: [{start}, {end})"
            )
        normalized = dict(item)
        normalized["path"] = path_value
        normalized["start_byte"] = start
        normalized["end_byte"] = end
        ranges.append(normalized)
    ranges.sort(key=lambda item: (item["path"], item["start_byte"], item["end_byte"]))

    records = tuple(_iter_query_records(document))
    includes = tuple(
        sorted(
            {
                str(record["canonical_text"])
                for record in records
                if record["category"] == "includes"
            }
        )
    )
    return LoadedQuery(
        path=source,
        document=document,
        target_id=target_id,
        repository_id=repository_id,
        repository_commit=repository_commit,
        granularity=granularity,
        source_ranges=tuple(ranges),
        records=records,
        includes=includes,
        sha256=sha256_file(source),
    )


def load_index_artifacts(index_dir: str | Path) -> LoadedIndex:
    root = Path(index_dir)
    required = {
        "corpus_manifest.json",
        "chunks.jsonl",
        "symbol_index.jsonl",
        "index_validation.json",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise ArtifactLoadError("missing index artifacts: " + ", ".join(missing))

    manifest = _load_json_object(root / "corpus_manifest.json")
    validation = _load_json_object(root / "index_validation.json")
    if validation.get("status") != "pass":
        raise ArtifactLoadError("index validation status is not pass")
    if validation.get("deterministic") is not True:
        raise ArtifactLoadError("index is not independently deterministic")
    if int(validation.get("unhandled_parser_error_count", -1)) != 0:
        raise ArtifactLoadError("index contains unhandled parser errors")

    repository_id = str(manifest.get("repository", ""))
    repository_commit = _require_commit(
        manifest.get("repository_commit"), field="corpus repository_commit"
    )
    if str(validation.get("repository", "")) != repository_id:
        raise ArtifactLoadError("manifest/validation repository mismatch")
    if str(validation.get("repository_commit", "")).lower() != repository_commit:
        raise ArtifactLoadError("manifest/validation commit mismatch")

    actual_hashes = {
        name: sha256_file(root / name)
        for name in ("corpus_manifest.json", "chunks.jsonl", "symbol_index.jsonl")
    }
    declared_hashes = validation.get("artifact_hashes")
    if not isinstance(declared_hashes, Mapping):
        raise ArtifactLoadError("index validation lacks artifact_hashes")
    for name, actual in actual_hashes.items():
        expected = _require_sha256(declared_hashes.get(name), field=f"hash {name}")
        if actual != expected:
            raise ArtifactLoadError(
                f"index artifact hash mismatch for {name}: expected {expected}, got {actual}"
            )

    chunks = _load_jsonl(root / "chunks.jsonl")
    chunks_by_id: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        chunk_id = _require_sha256(chunk.get("chunk_id"), field="chunk_id")
        if chunk_id in chunks_by_id:
            raise ArtifactLoadError(f"duplicate chunk_id: {chunk_id}")
        path_value = _validated_path(chunk.get("path"), field="chunk path")
        start = int(chunk.get("start_byte", -1))
        end = int(chunk.get("end_byte", -1))
        if start < 0 or end <= start:
            raise ArtifactLoadError(
                f"invalid chunk range for {path_value}: [{start}, {end})"
            )
        normalized = dict(chunk)
        normalized["path"] = path_value
        normalized["start_byte"] = start
        normalized["end_byte"] = end
        normalized["content_sha256"] = _require_sha256(
            chunk.get("content_sha256"), field="chunk content_sha256"
        )
        content = str(chunk.get("content", ""))
        if sha256_bytes(content.encode("utf-8")) != normalized["content_sha256"]:
            raise ArtifactLoadError(f"chunk content hash mismatch: {chunk_id}")
        if str(chunk.get("repository", "")) != repository_id:
            raise ArtifactLoadError(f"chunk repository mismatch: {chunk_id}")
        if str(chunk.get("repository_commit", "")).lower() != repository_commit:
            raise ArtifactLoadError(f"chunk commit mismatch: {chunk_id}")
        chunks_by_id[chunk_id] = normalized
    expected_chunk_order = sorted(
        chunks_by_id.values(),
        key=lambda item: (
            item["path"],
            item["start_byte"],
            item["end_byte"],
            str(item.get("kind", "")),
            item["chunk_id"],
        ),
    )
    if list(chunks_by_id.values()) != expected_chunk_order:
        raise ArtifactLoadError("chunks.jsonl is not in canonical order")

    symbols = _load_jsonl(root / "symbol_index.jsonl")
    symbols_by_lookup: dict[str, list[dict[str, Any]]] = {}
    normalized_symbols: list[dict[str, Any]] = []
    for symbol in symbols:
        chunk_id = _require_sha256(symbol.get("chunk_id"), field="symbol chunk_id")
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            raise ArtifactLoadError(f"symbol references unknown chunk: {chunk_id}")
        path_value = _validated_path(symbol.get("path"), field="symbol path")
        if path_value != chunk["path"]:
            raise ArtifactLoadError(f"symbol/chunk path mismatch: {chunk_id}")
        if str(symbol.get("kind", "")) != str(chunk.get("kind", "")):
            raise ArtifactLoadError(f"symbol/chunk kind mismatch: {chunk_id}")
        record = dict(symbol)
        record["path"] = path_value
        record["canonical_name"] = str(symbol.get("canonical_name", ""))
        record["short_name"] = str(symbol.get("short_name", ""))
        if not record["canonical_name"] or not record["short_name"]:
            raise ArtifactLoadError(f"symbol identity is incomplete: {chunk_id}")
        lookup_values = symbol.get("lookup_keys", [])
        if not isinstance(lookup_values, list):
            raise ArtifactLoadError(f"lookup_keys must be an array: {chunk_id}")
        lookup_keys = sorted(
            {
                str(value)
                for value in [
                    record["canonical_name"],
                    record["short_name"],
                    *lookup_values,
                ]
                if str(value)
            }
        )
        record["lookup_keys"] = lookup_keys
        normalized_symbols.append(record)
        for key in lookup_keys:
            symbols_by_lookup.setdefault(key, []).append(record)

    normalized_symbols.sort(
        key=lambda item: (
            item["canonical_name"],
            str(item.get("index_role", "")),
            item["path"],
            int(item.get("start_line", 0)),
            item["chunk_id"],
        )
    )
    if symbols != normalized_symbols:
        raise ArtifactLoadError("symbol_index.jsonl is not in canonical order")

    frozen_lookup = {
        key: tuple(
            sorted(
                values,
                key=lambda item: (
                    item["canonical_name"],
                    str(item.get("index_role", "")),
                    item["path"],
                    int(item.get("start_line", 0)),
                    item["chunk_id"],
                ),
            )
        )
        for key, values in sorted(symbols_by_lookup.items())
    }
    return LoadedIndex(
        root=root,
        repository_id=repository_id,
        repository_commit=repository_commit,
        corpus_manifest=manifest,
        index_validation=validation,
        chunks=tuple(expected_chunk_order),
        chunks_by_id=chunks_by_id,
        symbol_records=tuple(normalized_symbols),
        symbols_by_lookup_key=frozen_lookup,
        artifact_hashes=actual_hashes,
    )
