"""Deterministic, non-LLM C/C++ query extraction for RAG Phase 2."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .canonical import (
    canonical_json_bytes,
    posix_relative_path,
    sha256_bytes,
    sha256_file,
    write_canonical_json,
)


class QueryExtractionError(RuntimeError):
    """Raised when a frozen target cannot be reproduced safely."""


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
    "bool", "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t",
    "class", "compl", "concept", "const", "consteval", "constexpr", "constinit",
    "const_cast", "continue", "co_await", "co_return", "co_yield", "decltype",
    "default", "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit",
    "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline",
    "int", "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq",
    "nullptr", "operator", "or", "or_eq", "private", "protected", "public",
    "register", "reinterpret_cast", "requires", "return", "short", "signed", "sizeof",
    "static", "static_assert", "static_cast", "struct", "switch", "template", "this",
    "thread_local", "throw", "true", "try", "typedef", "typeid", "typename", "union",
    "unsigned", "using", "virtual", "void", "volatile", "wchar_t", "while", "xor",
    "xor_eq",
}
_BUILTIN_TYPES = {
    "bool", "char", "char8_t", "char16_t", "char32_t", "double", "float", "int",
    "long", "short", "signed", "unsigned", "void", "wchar_t", "size_t", "ssize_t",
    "ptrdiff_t", "intptr_t", "uintptr_t", "int8_t", "int16_t", "int32_t", "int64_t",
    "uint8_t", "uint16_t", "uint32_t", "uint64_t",
}
_TYPE_NODE_TYPES = {
    "type_identifier", "qualified_identifier", "scoped_type_identifier", "template_type",
    "dependent_type", "decltype", "placeholder_type_specifier",
}
_TYPE_CONTEXTS = {
    "alias_declaration", "base_class_clause", "cast_expression", "condition_clause",
    "declaration", "field_declaration", "function_definition", "new_expression",
    "optional_parameter_declaration", "parameter_declaration", "template_argument_list",
    "type_definition", "type_descriptor",
}
_CLASS_NODE_TYPES = {"class_specifier", "struct_specifier", "union_specifier"}
_NESTED_TYPE_NODE_TYPES = _CLASS_NODE_TYPES | {
    "enum_specifier", "alias_declaration", "type_definition",
}
_COMMENT_NODE_TYPES = {"comment"}
_IDENTIFIER_NODE_TYPES = {
    "identifier", "field_identifier", "namespace_identifier", "type_identifier",
}
_INCLUDE_RE = re.compile(
    rb"(?m)^[ \t]*#[ \t]*include[ \t]*(?P<delim>[<\"])(?P<path>[^>\"\r\n]+)[>\"]"
)
_MACRO_RE = re.compile(
    rb"(?m)^[ \t]*#[ \t]*define[ \t]+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)
_DOXYGEN_SEE_RE = re.compile(r"(?:@see|\\see)\s+([A-Za-z_][A-Za-z0-9_:<>]*)")
_DOXYGEN_PARAM_RE = re.compile(r"(?:@p|\\p)\s+([A-Za-z_][A-Za-z0-9_:<>]*)")
_DOXYGEN_THROW_RE = re.compile(
    r"(?:@throws|@exception|\\throws|\\exception)\s+([A-Za-z_][A-Za-z0-9_:<>]*)"
)
_BACKTICK_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_:<>]*)`")


@dataclass(frozen=True)
class QueryConfig:
    path: Path
    sha256: str
    raw: dict[str, Any]

    @property
    def generic_unqualified_calls(self) -> frozenset[str]:
        return frozenset(str(item) for item in self.raw["filters"]["generic_unqualified_calls"])

    @property
    def minimum_identifier_length(self) -> int:
        return int(self.raw["filters"]["minimum_identifier_length"])

    @property
    def standard_namespace_prefixes(self) -> tuple[str, ...]:
        return tuple(str(item) for item in self.raw["filters"]["standard_namespace_prefixes"])

    @property
    def uppercase_constant_pattern(self) -> re.Pattern[str]:
        return re.compile(str(self.raw["filters"]["uppercase_constant_pattern"]))

    @classmethod
    def load(cls, path: str | Path) -> "QueryConfig":
        source = Path(path)
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise QueryExtractionError(f"cannot load query config {source}: {exc}") from exc
        if not isinstance(raw, dict):
            raise QueryExtractionError("query config root must be an object")
        if raw.get("method") != "deterministic-cpp-query-v1":
            raise QueryExtractionError("unsupported query method")
        if raw.get("llm_used") is not False:
            raise QueryExtractionError("Phase 2 query extraction must keep llm_used=false")
        stages = raw.get("stages", {})
        if stages.get("query_extraction") is not True:
            raise QueryExtractionError("query_extraction stage is not enabled")
        prohibited = sorted(
            key for key, value in stages.items() if key != "query_extraction" and bool(value)
        )
        if prohibited:
            raise QueryExtractionError(
                "later stages must remain disabled: " + ", ".join(prohibited)
            )
        return cls(path=source, sha256=sha256_file(source), raw=raw)


@dataclass(frozen=True)
class TargetRegistry:
    path: Path
    sha256: str
    entries: dict[str, dict[str, Any]]

    @classmethod
    def load(cls, path: str | Path) -> "TargetRegistry":
        source = Path(path)
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise QueryExtractionError(f"cannot load target registry {source}: {exc}") from exc
        if not isinstance(raw, dict) or not isinstance(raw.get("targets"), list):
            raise QueryExtractionError("target registry must contain a targets array")
        entries: dict[str, dict[str, Any]] = {}
        for item in raw["targets"]:
            if not isinstance(item, dict):
                raise QueryExtractionError("target registry entry must be an object")
            target_id = str(item.get("target_id", ""))
            if not target_id or target_id in entries:
                raise QueryExtractionError(f"invalid or duplicate target_id: {target_id!r}")
            entries[target_id] = item
        expected = int(raw.get("expected_target_count", len(entries)))
        if len(entries) != expected:
            raise QueryExtractionError(
                f"target registry count mismatch: expected {expected}, got {len(entries)}"
            )
        return cls(path=source, sha256=sha256_file(source), entries=entries)


@dataclass(frozen=True)
class SymbolCatalog:
    lookup_keys: frozenset[str]

    @classmethod
    def empty(cls) -> "SymbolCatalog":
        return cls(lookup_keys=frozenset())

    @classmethod
    def load(cls, path: str | Path) -> "SymbolCatalog":
        source = Path(path)
        keys: set[str] = set()
        try:
            lines = source.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise QueryExtractionError(f"cannot load Phase 1 symbol index {source}: {exc}") from exc
        for line_number, line in enumerate(lines, start=1):
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise QueryExtractionError(
                    f"invalid symbol index JSONL at {source}:{line_number}"
                ) from exc
            for field in ("canonical_name", "short_name"):
                value = record.get(field)
                if isinstance(value, str) and value:
                    keys.add(_canonical_text(value))
            for value in record.get("lookup_keys", []):
                if isinstance(value, str) and value:
                    keys.add(_canonical_text(value))
        return cls(lookup_keys=frozenset(keys))

    def contains(self, text: str) -> bool:
        canonical = _canonical_text(text)
        without_templates = re.sub(r"<.*>$", "", canonical)
        return canonical in self.lookup_keys or without_templates in self.lookup_keys


@dataclass(frozen=True)
class SourceRange:
    path: str
    data: bytes
    start_byte: int
    end_byte: int
    git_blob_sha256: str
    normalized_source_sha256: str
    normalized_range_sha256: str
    locator_kind: str
    locator_start_offset: int | None = None
    locator_end_offset: int | None = None

    def metadata(self) -> dict[str, Any]:
        start_line, start_column = _line_column(self.data, self.start_byte)
        end_probe = self.end_byte - 1 if self.end_byte > self.start_byte else self.end_byte
        end_line, end_column = _line_column(self.data, end_probe)
        result = {
            "end_byte": self.end_byte,
            "end_column": end_column,
            "end_line": end_line,
            "git_blob_sha256": self.git_blob_sha256,
            "locator_kind": self.locator_kind,
            "normalized_range_sha256": self.normalized_range_sha256,
            "normalized_source_sha256": self.normalized_source_sha256,
            "path": self.path,
            "start_byte": self.start_byte,
            "start_column": start_column,
            "start_line": start_line,
        }
        if self.locator_start_offset is not None:
            result["frozen_character_start_offset"] = self.locator_start_offset
        if self.locator_end_offset is not None:
            result["frozen_character_end_offset"] = self.locator_end_offset
        return result


@dataclass(frozen=True)
class FrozenTarget:
    target_id: str
    target_name: str
    repository_id: str
    repository_commit: str
    repository_root: Path
    granularity: str
    source_ranges: tuple[SourceRange, ...]
    target_symbols: tuple[str, ...]
    frozen_target_config_path: str | None
    source_metadata_path: str
    phase1_index_validation_path: str
    phase1_index_validation_sha256: str


def normalize_source_bytes(raw: bytes) -> bytes:
    """Match the frozen design-input coordinate space.

    The non-RAG harness read UTF-8 with BOM removal and universal-newline
    translation before slicing class spans. Reproducing that normalization makes
    byte offsets independent of Windows CRLF checkout behavior.
    """

    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise QueryExtractionError("target source is not valid UTF-8") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QueryExtractionError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QueryExtractionError(f"JSON root must be an object: {path}")
    return value


def _line_column(data: bytes, offset: int) -> tuple[int, int]:
    bounded = max(0, min(offset, len(data)))
    previous = data.rfind(b"\n", 0, bounded)
    line = data.count(b"\n", 0, bounded) + 1
    column = bounded if previous < 0 else bounded - previous - 1
    return line, column


def _character_span_to_bytes(
    data: bytes, start_character: int, end_character: int
) -> tuple[int, int]:
    text = data.decode("utf-8", errors="strict")
    if not (0 <= start_character <= end_character <= len(text)):
        raise QueryExtractionError(
            f"invalid zero-based character span: [{start_character}, {end_character})"
        )
    return (
        len(text[:start_character].encode("utf-8")),
        len(text[:end_character].encode("utf-8")),
    )


def _line_span_to_bytes(data: bytes, start_line: int, end_line: int) -> tuple[int, int]:
    if start_line < 1 or end_line < start_line:
        raise QueryExtractionError(
            f"invalid one-based line span: {start_line}-{end_line}"
        )
    offsets = [0]
    offsets.extend(match.end() for match in re.finditer(b"\n", data))
    if start_line > len(offsets):
        raise QueryExtractionError(f"start line is outside source: {start_line}")
    start = offsets[start_line - 1]
    end = offsets[end_line] if end_line < len(offsets) else len(data)
    return start, end


def _run_git(root: Path, *args: str, binary: bool = False) -> bytes | str:
    from .corpus import _run_git as run_git

    return run_git(root, *args, binary=binary)


def _read_commit_blob(repository_root: Path, path: str) -> bytes:
    normalized = posix_relative_path(path)
    try:
        return bytes(
            _run_git(
                repository_root,
                "show",
                f"HEAD:{normalized}",
                binary=True,
            )
        )
    except Exception as exc:
        raise QueryExtractionError(
            f"cannot read committed target source {normalized}: {exc}"
        ) from exc


def _verify_phase1_index(project_root: Path, repository_id: str, commit: str) -> tuple[str, str]:
    relative = posix_relative_path(
        f"rag/index/{repository_id}/{commit}/index_validation.json"
    )
    path = project_root.joinpath(*relative.split("/"))
    validation = _load_json(path)
    if validation.get("status") != "pass":
        raise QueryExtractionError(f"Phase 1 index is not valid: {relative}")
    if validation.get("deterministic") is not True:
        raise QueryExtractionError(f"Phase 1 index is not deterministic: {relative}")
    if int(validation.get("unhandled_parser_error_count", -1)) != 0:
        raise QueryExtractionError(f"Phase 1 index has unhandled parser errors: {relative}")
    return relative, sha256_file(path)


def _metadata_original_file(metadata: Mapping[str, Any], path: str) -> Mapping[str, Any] | None:
    for item in metadata.get("original_files", []):
        if isinstance(item, Mapping) and str(item.get("path")) == path:
            return item
    return None


def load_frozen_target(
    *,
    project_root: str | Path,
    query_config: QueryConfig,
    registry: TargetRegistry,
    target_id: str,
) -> FrozenTarget:
    root = Path(project_root).resolve()
    entry = registry.entries.get(target_id)
    if entry is None:
        raise QueryExtractionError(f"unknown target_id: {target_id}")

    dependency = query_config.raw["dependencies"]
    retrieval_path = root.joinpath(*str(dependency["retrieval_config_path"]).split("/"))
    if sha256_file(retrieval_path) != str(dependency["retrieval_config_sha256"]):
        raise QueryExtractionError("Phase 1 retrieval config SHA-256 mismatch")

    from .config import IndexConfig
    from .corpus import ensure_clean_tracked_files, repository_head

    index_config = IndexConfig.load(retrieval_path)
    metadata_relative = posix_relative_path(str(entry["source_metadata_path"]))
    metadata = _load_json(root.joinpath(*metadata_relative.split("/")))

    target_kind = str(entry["target_kind"])
    frozen_config_relative: str | None = None
    if target_kind == "standard":
        frozen_config_relative = posix_relative_path(
            str(entry["frozen_target_config_path"])
        )
        frozen_config = _load_json(root.joinpath(*frozen_config_relative.split("/")))
        repository_id = str(frozen_config["repository_id"])
        repository_commit = str(frozen_config["repository_commit"]).lower()
        target_name = str(frozen_config["target_name"])
        granularity = str(frozen_config["granularity"])
        source_files = [posix_relative_path(str(item)) for item in frozen_config["source_files"]]
        locator = frozen_config.get("locator", {})
        target_symbols = (
            (str(locator["symbol"]),)
            if isinstance(locator, dict) and locator.get("symbol")
            else ()
        )
        if str(frozen_config["target_id"]) != target_id:
            raise QueryExtractionError(f"frozen config target_id mismatch: {target_id}")
        if str(metadata.get("target_id", "")) != target_id:
            raise QueryExtractionError(f"source metadata target_id mismatch: {target_id}")
        if str(metadata.get("repository_id", "")) != repository_id:
            raise QueryExtractionError(f"source metadata repository_id mismatch: {target_id}")
        if str(metadata.get("granularity", "")) != granularity:
            raise QueryExtractionError(f"source metadata granularity mismatch: {target_id}")
        metadata_sources = [
            posix_relative_path(str(item)) for item in metadata.get("source_files", [])
        ]
        if metadata_sources != source_files:
            raise QueryExtractionError(f"source metadata file list mismatch: {target_id}")
    elif target_kind == "legacy_function":
        repository_id = str(entry.get("repository_id", "ini-cpp"))
        repository_commit = str(metadata["repository_commit"]).lower()
        target_name = str(metadata["target_function"])
        granularity = "function"
        source_files = [posix_relative_path(str(metadata["source_file"]))]
        target_symbols = (str(metadata["target_function"]),)
    else:
        raise QueryExtractionError(f"unsupported target kind: {target_kind}")

    if repository_id not in index_config.repositories:
        raise QueryExtractionError(f"repository missing from retrieval config: {repository_id}")
    repository_spec = index_config.repositories[repository_id]
    if repository_commit != repository_spec.expected_commit:
        raise QueryExtractionError(
            f"target repository commit mismatch: {repository_commit} != {repository_spec.expected_commit}"
        )
    if str(metadata.get("repository_commit", "")).lower() != repository_commit:
        raise QueryExtractionError("source metadata repository commit mismatch")

    repository_root = root.joinpath(*repository_spec.path.split("/"))
    actual_head = repository_head(repository_root)
    if actual_head != repository_commit:
        raise QueryExtractionError(
            f"repository HEAD mismatch for {repository_id}: {actual_head}"
        )
    ensure_clean_tracked_files(repository_root)
    index_path, index_sha = _verify_phase1_index(root, repository_id, repository_commit)

    ranges: list[SourceRange] = []
    for source_path in source_files:
        raw = _read_commit_blob(repository_root, source_path)
        normalized = normalize_source_bytes(raw)
        raw_hash = sha256_bytes(raw)
        normalized_hash = sha256_bytes(normalized)

        working_path = repository_root.joinpath(*source_path.split("/"))
        if working_path.is_file():
            working_normalized = normalize_source_bytes(working_path.read_bytes())
            if working_normalized != normalized:
                raise QueryExtractionError(
                    f"working tree normalization differs from committed source: {source_path}"
                )

        start_character: int | None = None
        end_character: int | None = None
        if target_kind == "legacy_function":
            legacy = entry["legacy_range"]
            start_line = int(metadata[str(legacy["start_line_field"])])
            end_line = int(metadata[str(legacy["end_line_field"])])
            start, end = _line_span_to_bytes(normalized, start_line, end_line)
            locator_kind = "legacy_design_input_line_span"
        elif granularity == "module_files":
            start, end = 0, len(normalized)
            locator_kind = "module_file"
        elif granularity == "class_span":
            locator = metadata.get("locator")
            if not isinstance(locator, dict):
                raise QueryExtractionError("class_span source metadata lacks locator")
            start_character = int(locator["start_offset"])
            end_character = int(locator["end_offset"])
            start, end = _character_span_to_bytes(
                normalized, start_character, end_character
            )
            locator_kind = "frozen_normalized_class_character_offset"
            expected_span_hash = str(locator["original_span_sha256"])
            actual_span_hash = sha256_bytes(normalized[start:end])
            if actual_span_hash != expected_span_hash:
                raise QueryExtractionError(
                    f"frozen class span hash mismatch for {target_id}: "
                    f"expected {expected_span_hash}, got {actual_span_hash}"
                )
        else:
            raise QueryExtractionError(f"unsupported granularity: {granularity}")

        if not (0 <= start <= end <= len(normalized)):
            raise QueryExtractionError(
                f"invalid normalized source range for {source_path}: [{start}, {end})"
            )
        ranges.append(
            SourceRange(
                path=source_path,
                data=normalized,
                start_byte=start,
                end_byte=end,
                git_blob_sha256=raw_hash,
                normalized_source_sha256=normalized_hash,
                normalized_range_sha256=sha256_bytes(normalized[start:end]),
                locator_kind=locator_kind,
                locator_start_offset=(
                    start_character if granularity == "class_span" else None
                ),
                locator_end_offset=(
                    end_character if granularity == "class_span" else None
                ),
            )
        )

    return FrozenTarget(
        target_id=target_id,
        target_name=target_name,
        repository_id=repository_id,
        repository_commit=repository_commit,
        repository_root=repository_root,
        granularity=granularity,
        source_ranges=tuple(sorted(ranges, key=lambda item: item.path)),
        target_symbols=tuple(sorted(set(target_symbols))),
        frozen_target_config_path=frozen_config_relative,
        source_metadata_path=metadata_relative,
        phase1_index_validation_path=index_path,
        phase1_index_validation_sha256=index_sha,
    )


def _node_text(node: Any, data: bytes) -> str:
    return data[int(node.start_byte):int(node.end_byte)].decode("utf-8", errors="strict")


def _named_children(node: Any) -> tuple[Any, ...]:
    children = getattr(node, "named_children", ())
    return tuple(children)


def _child_by_field(node: Any, name: str) -> Any | None:
    method = getattr(node, "child_by_field_name", None)
    if method is None:
        return None
    return method(name)


def _point(point: Any) -> tuple[int, int]:
    if hasattr(point, "row") and hasattr(point, "column"):
        return int(point.row), int(point.column)
    return int(point[0]), int(point[1])


def _location_for_span(data: bytes, path: str, start: int, end: int) -> dict[str, Any]:
    start_line, start_column = _line_column(data, start)
    probe = end - 1 if end > start else end
    end_line, end_column = _line_column(data, probe)
    return {
        "end_byte": end,
        "end_column": end_column,
        "end_line": end_line,
        "path": path,
        "start_byte": start,
        "start_column": start_column,
        "start_line": start_line,
    }


def _location_for_node(
    node: Any,
    path: str,
    data: bytes,
) -> dict[str, Any]:
    return _location_for_span(
        data,
        path,
        int(node.start_byte),
        int(node.end_byte),
    )


def _canonical_text(text: str) -> str:
    compact = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    compact = re.sub(r"\s*::\s*", "::", compact)
    compact = re.sub(r"\s*->\s*", "->", compact)
    compact = re.sub(r"\s*\.\s*", ".", compact)
    return compact.lstrip(":")


def _short_identifier(text: str) -> str:
    value = text.rsplit("::", 1)[-1]
    value = value.rsplit("->", 1)[-1].rsplit(".", 1)[-1]
    value = re.sub(r"<.*>$", "", value)
    return value.strip()


def _is_standard_only(text: str, config: QueryConfig) -> bool:
    canonical = _canonical_text(text)
    return any(canonical.startswith(prefix) for prefix in config.standard_namespace_prefixes)


def _valid_identifier_candidate(text: str, config: QueryConfig) -> bool:
    short = _short_identifier(_canonical_text(text))
    if len(short) < config.minimum_identifier_length:
        return False
    if short in _CPP_KEYWORDS or short in _BUILTIN_TYPES:
        return False
    if _is_standard_only(text, config):
        return False
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_~]*$", short))


def _record(
    *,
    category: str,
    text: str,
    kind: str,
    priority: str,
    relation: str,
    location: Mapping[str, Any],
    qualified: bool,
    evidence_node_type: str,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = _canonical_text(text)
    identity = {
        "canonical_text": canonical,
        "category": category,
        "kind": kind,
        "relation": relation,
    }
    query_id = sha256_bytes(canonical_json_bytes(identity))
    result: dict[str, Any] = {
        "canonical_text": canonical,
        "category": category,
        "evidence_node_type": evidence_node_type,
        "kind": kind,
        "location": dict(location),
        "priority": priority,
        "qualified": qualified,
        "query_id": query_id,
        "relation": relation,
        "text": text.strip(),
    }
    if details:
        result["details"] = dict(details)
    return result


def _record_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(record["category"]),
        str(record["canonical_text"]),
        str(record["kind"]),
        str(record["relation"]),
    )


def _record_sort_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    location = record["location"]
    return (
        _PRIORITY_ORDER[str(record["priority"])],
        str(record["canonical_text"]),
        str(location["path"]),
        int(location["start_byte"]),
        str(record["kind"]),
        str(record["query_id"]),
    )


def _location_key(location: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(location["path"]),
        int(location["start_byte"]),
        int(location["end_byte"]),
        int(location["start_line"]),
        int(location["start_column"]),
    )


def _deduplicate(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for item in records:
        grouped.setdefault(_record_key(item), []).append(item)

    merged: list[dict[str, Any]] = []
    for items in grouped.values():
        preferred = min(items, key=_record_sort_key)
        result = dict(preferred)
        locations = {
            _location_key(item["location"]): dict(item["location"])
            for item in items
        }
        result["evidence_locations"] = [
            locations[key] for key in sorted(locations)
        ]
        result["evidence_count"] = len(result["evidence_locations"])
        result["evidence_node_types"] = sorted(
            {str(item["evidence_node_type"]) for item in items}
        )
        details = {
            canonical_json_bytes(item["details"]): dict(item["details"])
            for item in items
            if isinstance(item.get("details"), Mapping)
        }
        if details:
            result["evidence_details"] = [details[key] for key in sorted(details)]
        merged.append(result)
    return sorted(merged, key=_record_sort_key)


def _intersects(node: Any, source_range: SourceRange) -> bool:
    return int(node.end_byte) > source_range.start_byte and int(node.start_byte) < source_range.end_byte


def _inside(node: Any, source_range: SourceRange) -> bool:
    return int(node.start_byte) >= source_range.start_byte and int(node.end_byte) <= source_range.end_byte


def _ancestor(node: Any, node_types: set[str]) -> Any | None:
    current = getattr(node, "parent", None)
    while current is not None:
        if str(current.type) in node_types:
            return current
        current = getattr(current, "parent", None)
    return None


def _top_type_expression(node: Any) -> Any:
    current = node
    parent = getattr(current, "parent", None)
    while parent is not None and str(parent.type) in _TYPE_NODE_TYPES | {
        "template_argument_list", "qualified_identifier", "scoped_identifier"
    }:
        if str(parent.type) == "template_argument_list":
            break
        current = parent
        parent = getattr(current, "parent", None)
    return current


def _type_context(node: Any) -> bool:
    current = getattr(node, "parent", None)
    for _ in range(5):
        if current is None:
            return False
        node_type = str(current.type)
        if node_type == "field_declaration":
            declarator = _child_by_field(current, "declarator")
            if declarator is None:
                return True
            return int(node.end_byte) <= int(declarator.start_byte)
        if node_type in _TYPE_CONTEXTS:
            return True
        if node_type in {"call_expression", "argument_list", "compound_statement", "init_declarator"}:
            return False
        current = getattr(current, "parent", None)
    return False


def _find_name_node(node: Any) -> Any | None:
    if node is None:
        return None
    if str(node.type) in _IDENTIFIER_NODE_TYPES:
        return node
    for field in ("name", "declarator", "field"):
        child = _child_by_field(node, field)
        if child is not None:
            found = _find_name_node(child)
            if found is not None:
                return found
    for child in _named_children(node):
        found = _find_name_node(child)
        if found is not None:
            return found
    return None


def _class_ancestor(node: Any) -> Any | None:
    return _ancestor(node, _CLASS_NODE_TYPES)


def _function_expression_parts(function: Any, data: bytes) -> tuple[str, str, bool, str]:
    expression = _canonical_text(_node_text(function, data))
    node_type = str(function.type)
    if node_type in {"field_expression", "pointer_expression"} or "." in expression or "->" in expression:
        field = _child_by_field(function, "field")
        name = _canonical_text(_node_text(field, data)) if field is not None else _short_identifier(expression)
        return name, expression, False, "member"
    qualified = "::" in expression
    return _short_identifier(expression), expression, qualified, "qualified" if qualified else "unqualified"


def _scan_includes(source_range: SourceRange) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    data = source_range.data
    for match in _INCLUDE_RE.finditer(data, source_range.start_byte, source_range.end_byte):
        if match.group("delim") != b'"':
            continue
        path = match.group("path").decode("utf-8", errors="strict")
        location = _location_for_span(data, source_range.path, match.start("path"), match.end("path"))
        records.append(
            _record(
                category="includes", text=path, kind="project_include", priority="high",
                relation="include", location=location, qualified="/" in path,
                evidence_node_type="preprocessor_include_regex",
            )
        )
    return records


def _scan_macro_definitions(source_range: SourceRange) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    data = source_range.data
    for match in _MACRO_RE.finditer(data, source_range.start_byte, source_range.end_byte):
        name = match.group("name").decode("ascii")
        location = _location_for_span(data, source_range.path, match.start("name"), match.end("name"))
        records.append(
            _record(
                category="constants_and_macros", text=name, kind="macro_definition",
                priority="high", relation="macro_definition", location=location,
                qualified=False, evidence_node_type="preprocessor_define_regex",
            )
        )
    return records


def _extract_documentation_references(
    node: Any, source_range: SourceRange, config: QueryConfig, catalog: "SymbolCatalog"
) -> list[dict[str, Any]]:
    text = _node_text(node, source_range.data)
    results: list[dict[str, Any]] = []
    patterns = (
        ("doxygen_see", _DOXYGEN_SEE_RE),
        ("doxygen_parameter_reference", _DOXYGEN_PARAM_RE),
        ("doxygen_exception_type", _DOXYGEN_THROW_RE),
        ("backtick_code_reference", _BACKTICK_RE),
    )
    for kind, pattern in patterns:
        for match in pattern.finditer(text):
            value = match.group(1)
            if not _valid_identifier_candidate(value, config) or not catalog.contains(value):
                continue
            prefix = text[:match.start(1)].encode("utf-8")
            raw = value.encode("utf-8")
            start = int(node.start_byte) + len(prefix)
            end = start + len(raw)
            results.append(
                _record(
                    category="documentation_references", text=value, kind=kind,
                    priority="medium", relation="documentation_reference",
                    location=_location_for_span(source_range.data, source_range.path, start, end),
                    qualified="::" in value, evidence_node_type=str(node.type),
                )
            )
    return results


class _AstExtractor:
    def __init__(
        self, source_range: SourceRange, config: QueryConfig, catalog: "SymbolCatalog"
    ):
        self.source_range = source_range
        self.config = config
        self.catalog = catalog
        self.records: dict[str, list[dict[str, Any]]] = {
            "user_defined_types": [], "function_calls": [], "base_classes": [],
            "nested_types": [], "enums": [], "constants_and_macros": [],
            "documentation_references": [],
        }

    def emit(self, category: str, **kwargs: Any) -> None:
        self.records[category].append(_record(category=category, **kwargs))

    def visit(self, node: Any) -> None:
        if not _intersects(node, self.source_range):
            return
        node_type = str(node.type)
        fully_inside = _inside(node, self.source_range)

        if fully_inside:
            if node_type == "call_expression":
                self._call(node)
            elif node_type == "new_expression":
                self._new_expression(node)
            elif node_type == "base_class_clause":
                self._base_clause(node)
            elif node_type in _NESTED_TYPE_NODE_TYPES:
                self._nested_type(node)
            if node_type == "enum_specifier":
                self._enum(node)
            if node_type in {"declaration", "field_declaration"}:
                self._constant_definition(node)
            if node_type == "type_identifier":
                self._type_identifier(node)
            if node_type in {"qualified_identifier", "scoped_identifier"}:
                self._scoped_value_reference(node)
            if node_type in _IDENTIFIER_NODE_TYPES:
                self._uppercase_reference(node)
            if node_type in _COMMENT_NODE_TYPES:
                self.records["documentation_references"].extend(
                    _extract_documentation_references(
                        node, self.source_range, self.config, self.catalog
                    )
                )

        for child in _named_children(node):
            self.visit(child)

    def _call(self, node: Any) -> None:
        function = _child_by_field(node, "function")
        if function is None:
            return
        name, expression, qualified, call_form = _function_expression_parts(
            function, self.source_range.data
        )
        if not _valid_identifier_candidate(name, self.config):
            return
        if _is_standard_only(expression, self.config):
            return
        if call_form == "unqualified" and name in self.config.generic_unqualified_calls:
            return
        kind = "constructor_candidate" if name[:1].isupper() else f"{call_form}_call"
        priority = "high" if qualified else "medium"
        if call_form == "member":
            priority = "medium"
        self.emit(
            "function_calls", text=name, kind=kind, priority=priority,
            relation="call_target", location=_location_for_node(function, self.source_range.path, self.source_range.data),
            qualified=qualified,
            evidence_node_type=str(function.type),
            details={"call_expression": expression, "call_form": call_form},
        )

    def _new_expression(self, node: Any) -> None:
        type_node = _child_by_field(node, "type")
        if type_node is None:
            type_node = next(
                (
                    child
                    for child in _named_children(node)
                    if str(child.type) in _TYPE_NODE_TYPES
                ),
                None,
            )
        if type_node is None:
            return
        top = _top_type_expression(type_node)
        text = _canonical_text(_node_text(top, self.source_range.data))
        if not _valid_identifier_candidate(text, self.config):
            return
        qualified = "::" in text
        self.emit(
            "function_calls", text=text, kind="constructor_candidate",
            priority="high" if qualified else "medium",
            relation="constructor_call",
            location=_location_for_node(top, self.source_range.path, self.source_range.data),
            qualified=qualified, evidence_node_type=str(node.type),
            details={"call_form": "new_expression"},
        )

    def _base_clause(self, node: Any) -> None:
        seen: set[tuple[int, int]] = set()
        stack = list(_named_children(node))
        while stack:
            current = stack.pop()
            if str(current.type) in _TYPE_NODE_TYPES | {"identifier"}:
                top = _top_type_expression(current)
                key = (int(top.start_byte), int(top.end_byte))
                text = _canonical_text(_node_text(top, self.source_range.data))
                if key not in seen and _valid_identifier_candidate(text, self.config):
                    seen.add(key)
                    self.emit(
                        "base_classes", text=text, kind="base_class", priority="high",
                        relation="base_type", location=_location_for_node(top, self.source_range.path, self.source_range.data),
                        qualified="::" in text, evidence_node_type=str(top.type),
                    )
            else:
                stack.extend(_named_children(current))

    def _nested_type(self, node: Any) -> None:
        owner = _class_ancestor(node)
        if owner is None:
            return
        name_node = _child_by_field(node, "name") or _find_name_node(node)
        if name_node is None:
            return
        text = _canonical_text(_node_text(name_node, self.source_range.data))
        if not _valid_identifier_candidate(text, self.config):
            return
        owner_name_node = _child_by_field(owner, "name") or _find_name_node(owner)
        owner_text = (
            _canonical_text(_node_text(owner_name_node, self.source_range.data))
            if owner_name_node is not None else "<anonymous>"
        )
        self.emit(
            "nested_types", text=text, kind=f"nested_{str(node.type)}", priority="high",
            relation="nested_type", location=_location_for_node(name_node, self.source_range.path, self.source_range.data),
            qualified=False, evidence_node_type=str(node.type), details={"owner": owner_text},
        )

    def _enum(self, node: Any) -> None:
        name_node = _child_by_field(node, "name") or _find_name_node(node)
        if name_node is not None:
            text = _canonical_text(_node_text(name_node, self.source_range.data))
            if _valid_identifier_candidate(text, self.config):
                self.emit(
                    "enums", text=text, kind="enum_definition", priority="high",
                    relation="enum_definition", location=_location_for_node(name_node, self.source_range.path, self.source_range.data),
                    qualified="::" in text, evidence_node_type=str(node.type),
                )
        stack = list(_named_children(node))
        while stack:
            current = stack.pop()
            if str(current.type) == "enumerator":
                enum_name = _child_by_field(current, "name") or _find_name_node(current)
                if enum_name is not None:
                    text = _canonical_text(_node_text(enum_name, self.source_range.data))
                    if _valid_identifier_candidate(text, self.config):
                        self.emit(
                            "constants_and_macros", text=text, kind="enumerator",
                            priority="high", relation="enum_constant",
                            location=_location_for_node(enum_name, self.source_range.path, self.source_range.data),
                            qualified=False, evidence_node_type="enumerator",
                        )
            else:
                stack.extend(_named_children(current))

    def _constant_definition(self, node: Any) -> None:
        text = _node_text(node, self.source_range.data)
        if not re.search(r"\b(?:constexpr|constinit|const)\b", text):
            return
        if _ancestor(node, {"function_definition", "lambda_expression"}) is not None:
            return
        declarator = _child_by_field(node, "declarator")
        name_node = _find_name_node(declarator or node)
        if name_node is None:
            return
        name = _canonical_text(_node_text(name_node, self.source_range.data))
        if not _valid_identifier_candidate(name, self.config):
            return
        self.emit(
            "constants_and_macros", text=name, kind="constant_definition", priority="high",
            relation="namespace_or_class_constant", location=_location_for_node(name_node, self.source_range.path, self.source_range.data),
            qualified="::" in name, evidence_node_type=str(node.type),
        )

    def _type_identifier(self, node: Any) -> None:
        if not _type_context(node):
            return
        top = _top_type_expression(node)
        text = _canonical_text(_node_text(top, self.source_range.data))
        if not _valid_identifier_candidate(text, self.config):
            return
        qualified = "::" in text
        location = _location_for_node(top, self.source_range.path, self.source_range.data)
        self.emit(
            "user_defined_types", text=text,
            kind="qualified_type" if qualified else "user_defined_type",
            priority="high" if qualified else "medium", relation="type_reference",
            location=location, qualified=qualified,
            evidence_node_type=str(top.type),
        )
        if qualified:
            self.emit(
                "nested_types", text=text, kind="nested_type_reference_candidate",
                priority="high", relation="nested_type_reference",
                location=location, qualified=True,
                evidence_node_type=str(top.type),
            )

    def _scoped_value_reference(self, node: Any) -> None:
        parent = getattr(node, "parent", None)
        if parent is not None and str(parent.type) in {
            "qualified_identifier", "scoped_identifier"
        }:
            return
        if _type_context(node) or _ancestor(node, _COMMENT_NODE_TYPES) is not None:
            return
        text = _canonical_text(_node_text(node, self.source_range.data))
        if "::" not in text or _is_standard_only(text, self.config):
            return
        parts = [part for part in text.split("::") if part]
        if len(parts) < 2:
            return
        final = _short_identifier(parts[-1])
        if not final[:1].isupper():
            return
        owner = "::".join(parts[:-1])
        if not _valid_identifier_candidate(owner, self.config):
            return
        location = _location_for_node(node, self.source_range.path, self.source_range.data)
        self.emit(
            "enums", text=owner, kind="enum_reference_candidate",
            priority="medium", relation="enum_reference", location=location,
            qualified="::" in owner, evidence_node_type=str(node.type),
            details={"scoped_value": text},
        )
        self.emit(
            "constants_and_macros", text=text,
            kind="scoped_enum_or_constant_reference", priority="medium",
            relation="constant_or_macro_reference", location=location,
            qualified=True, evidence_node_type=str(node.type),
        )

    def _uppercase_reference(self, node: Any) -> None:
        if _ancestor(node, _COMMENT_NODE_TYPES | {"string_literal", "system_lib_string"}) is not None:
            return
        text = _canonical_text(_node_text(node, self.source_range.data))
        if not self.config.uppercase_constant_pattern.fullmatch(text):
            return
        if text in _CPP_KEYWORDS:
            return
        self.emit(
            "constants_and_macros", text=text, kind="constant_or_macro_reference",
            priority="medium", relation="constant_or_macro_reference",
            location=_location_for_node(node, self.source_range.path, self.source_range.data), qualified=False,
            evidence_node_type=str(node.type),
        )


def _error_count(root: Any, source_range: SourceRange) -> int:
    if not _intersects(root, source_range):
        return 0
    count = (
        1
        if bool(getattr(root, "is_error", False))
        or str(getattr(root, "type", "")) == "ERROR"
        else 0
    )
    for child in _named_children(root):
        count += _error_count(child, source_range)
    return count


def extract_queries_from_tree(
    *,
    root: Any,
    source_range: SourceRange,
    config: QueryConfig,
    catalog: "SymbolCatalog | None" = None,
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    extractor = _AstExtractor(source_range, config, catalog or SymbolCatalog.empty())
    extractor.visit(root)
    result = {key: _deduplicate(value) for key, value in extractor.records.items()}
    result["includes"] = _deduplicate(_scan_includes(source_range))
    result["constants_and_macros"] = _deduplicate(
        [*result["constants_and_macros"], *_scan_macro_definitions(source_range)]
    )
    result["dependency_candidates"] = _dependency_records(result)
    return result, _error_count(root, source_range)


def _target_symbol_records(target: FrozenTarget) -> list[dict[str, Any]]:
    if not target.target_symbols:
        return []
    first_range = target.source_ranges[0]
    location = _location_for_span(
        first_range.data, first_range.path, first_range.start_byte, first_range.start_byte
    )
    return [
        _record(
            category="target_symbols", text=symbol, kind="target_symbol", priority="high",
            relation="target_symbol", location=location, qualified="::" in symbol,
            evidence_node_type="frozen_target_metadata",
        )
        for symbol in target.target_symbols
    ]


def _dependency_records(
    categories: Mapping[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    mapping = {
        "includes": "include",
        "user_defined_types": "type_reference",
        "function_calls": "call_target",
        "base_classes": "base_type",
        "nested_types": "nested_type",
        "enums": "enum_reference",
        "constants_and_macros": "constant_or_macro",
        "documentation_references": "documentation_reference",
    }
    records: list[dict[str, Any]] = []
    for category, relation in mapping.items():
        for source in categories.get(category, []):
            locations = source.get("evidence_locations", [source["location"]])
            for location in locations:
                records.append(
                    _record(
                        category="dependency_candidates",
                        text=str(source["text"]),
                        kind="dependency_candidate",
                        priority=str(source["priority"]),
                        relation=relation,
                        location=location,
                        qualified=bool(source["qualified"]),
                        evidence_node_type="derived_from_query",
                        details={
                            "source_category": category,
                            "source_query_id": source["query_id"],
                        },
                    )
                )
    return _deduplicate(records)


def build_query_document(
    *,
    project_root: str | Path,
    query_config_path: str | Path,
    target_registry_path: str | Path,
    target_id: str,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    config = QueryConfig.load(query_config_path)
    registry = TargetRegistry.load(target_registry_path)
    target = load_frozen_target(
        project_root=root, query_config=config, registry=registry, target_id=target_id
    )

    dependency = config.raw["dependencies"]
    retrieval_path = posix_relative_path(str(dependency["retrieval_config_path"]))
    retrieval_config = _load_json(root.joinpath(*retrieval_path.split("/")))
    parser_spec = retrieval_config["parser"]

    from .config import IndexConfig
    from .cpp_symbols import create_cpp_parser

    index_config = IndexConfig.load(root.joinpath(*retrieval_path.split("/")))
    parser = create_cpp_parser(index_config.parser)
    symbol_index_relative = posix_relative_path(
        f"rag/index/{target.repository_id}/{target.repository_commit}/symbol_index.jsonl"
    )
    symbol_index_path = root.joinpath(*symbol_index_relative.split("/"))
    symbol_catalog = SymbolCatalog.load(symbol_index_path)

    category_names = [str(item) for item in config.raw["query_categories"]]
    categories: dict[str, list[dict[str, Any]]] = {name: [] for name in category_names}
    categories["target_symbols"] = _target_symbol_records(target)
    parse_diagnostics: list[dict[str, Any]] = []

    parsed_by_hash: dict[str, Any] = {}
    for source_range in target.source_ranges:
        tree = parsed_by_hash.get(source_range.normalized_source_sha256)
        if tree is None:
            tree = parser.parse(source_range.data)
            parsed_by_hash[source_range.normalized_source_sha256] = tree
        extracted, errors = extract_queries_from_tree(
            root=tree.root_node,
            source_range=source_range,
            config=config,
            catalog=symbol_catalog,
        )
        for category, records in extracted.items():
            categories.setdefault(category, []).extend(records)
        parse_diagnostics.append(
            {
                "error_node_count": errors,
                "path": source_range.path,
                "phase1_unhandled_parser_errors": 0,
            }
        )

    for category in list(categories):
        if category != "dependency_candidates":
            categories[category] = _deduplicate(categories[category])
    categories["dependency_candidates"] = _dependency_records(categories)

    counts = {category: len(categories.get(category, [])) for category in category_names}
    counts["total_without_dependency_duplicates"] = sum(
        value for key, value in counts.items() if key != "dependency_candidates"
    )
    counts["total_records"] = sum(len(value) for value in categories.values())

    document: dict[str, Any] = {
        "artifact_schema_version": str(config.raw["artifact_schema_version"]),
        "canonicalization": config.raw["canonical_serialization"],
        "condition_id": str(config.raw["condition_id"]),
        "coordinate_space": config.raw["coordinate_space"],
        "counts": counts,
        "llm_used": False,
        "non_rag_baseline": config.raw["non_rag_baseline"],
        "parse_diagnostics": sorted(parse_diagnostics, key=lambda item: item["path"]),
        "parser": {
            "grammar_package": str(parser_spec["grammar_package"]),
            "grammar_version": str(parser_spec["grammar_version"]),
            "package": str(parser_spec["package"]),
            "package_version": str(parser_spec["package_version"]),
        },
        "phase1_index_validation_path": target.phase1_index_validation_path,
        "phase1_index_validation_sha256": target.phase1_index_validation_sha256,
        "phase1_symbol_index_path": symbol_index_relative,
        "phase1_symbol_index_sha256": sha256_file(symbol_index_path),
        "queries": {key: categories.get(key, []) for key in category_names},
        "query_config_path": posix_relative_path(config.path.resolve().relative_to(root)),
        "query_config_sha256": config.sha256,
        "query_method": str(config.raw["method"]),
        "query_version": str(config.raw["query_version"]),
        "retrieval_config_path": retrieval_path,
        "retrieval_config_sha256": str(dependency["retrieval_config_sha256"]),
        "source_ranges": [item.metadata() for item in target.source_ranges],
        "target": {
            "frozen_target_config_path": target.frozen_target_config_path,
            "granularity": target.granularity,
            "repository_commit": target.repository_commit,
            "repository_id": target.repository_id,
            "source_metadata_path": target.source_metadata_path,
            "target_id": target.target_id,
            "target_name": target.target_name,
            "target_symbol_policy": (
                "retain_frozen_locator_symbol"
                if target.target_symbols else "not_applicable_module_files"
            ),
        },
        "target_registry_path": posix_relative_path(registry.path.resolve().relative_to(root)),
        "target_registry_sha256": registry.sha256,
        "target_specific_manual_additions": False,
    }
    payload_hash = sha256_bytes(canonical_json_bytes(document))
    document["query_payload_sha256"] = payload_hash
    return document


def verify_query_payload(document: Mapping[str, Any]) -> bool:
    expected = str(document.get("query_payload_sha256", ""))
    payload = dict(document)
    payload.pop("query_payload_sha256", None)
    return bool(expected) and sha256_bytes(canonical_json_bytes(payload)) == expected


def write_query_document(path: str | Path, document: Mapping[str, Any]) -> str:
    if not verify_query_payload(document):
        raise QueryExtractionError("query payload SHA-256 verification failed")
    return write_canonical_json(path, document)
