"""Build deterministic corpus, symbol chunks, and exact-symbol index artifacts."""

from __future__ import annotations

import importlib.metadata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import (
    posix_relative_path,
    sha256_bytes,
    write_canonical_json,
    write_canonical_jsonl,
)
from .config import IndexConfig
from .corpus import CorpusCollection, collect_production_corpus
from .cpp_symbols import (
    ParseDiagnostic,
    build_exact_symbol_index,
    create_cpp_parser,
    extract_symbol_chunks,
)


CORE_ARTIFACTS = ("corpus_manifest.json", "chunks.jsonl", "symbol_index.jsonl")
BUILD_COMPARISON_ARTIFACTS = CORE_ARTIFACTS + ("index_validation.json",)


class IndexValidationError(RuntimeError):
    """Raised when a Phase 1 index violates protocol v0.9."""


@dataclass(frozen=True)
class BuildResult:
    repository_id: str
    repository_commit: str
    output_dir: Path
    file_count: int
    chunk_count: int
    symbol_count: int
    diagnostics: tuple[ParseDiagnostic, ...]
    validation_errors: tuple[str, ...]
    artifact_hashes: dict[str, str]

    @property
    def valid(self) -> bool:
        return not self.validation_errors


def _artifact_config_path(path: Path) -> str:
    """Return a machine-independent config path for index artifacts."""

    candidate = path
    if candidate.is_absolute():
        try:
            candidate = candidate.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            candidate = Path(candidate.name)
    return posix_relative_path(candidate)


def _distribution_version(name: str) -> str:
    return importlib.metadata.version(name)


def _validate_chunks(
    corpus: CorpusCollection,
    chunks: list[dict[str, Any]],
    diagnostics: list[ParseDiagnostic],
    *,
    strict_parse_errors: bool,
) -> list[str]:
    errors: list[str] = []
    source_by_path = {source.path: source for source in corpus.files}

    ids = [str(chunk["chunk_id"]) for chunk in chunks]
    duplicate_ids = sorted(chunk_id for chunk_id, count in Counter(ids).items() if count > 1)
    if duplicate_ids:
        errors.append("duplicate_chunk_id:" + ",".join(duplicate_ids))

    expected_order = sorted(
        chunks,
        key=lambda item: (
            item["path"],
            item["start_byte"],
            item["end_byte"],
            item["kind"],
            item["chunk_id"],
        ),
    )
    if chunks != expected_order:
        errors.append("nondeterministic_chunk_order")

    for chunk in chunks:
        path = str(chunk["path"])
        source = source_by_path.get(path)
        if source is None:
            errors.append(f"unknown_source_path:{path}")
            continue
        start = int(chunk["start_byte"])
        end = int(chunk["end_byte"])
        if start < 0 or end <= start or end > len(source.data):
            errors.append(f"invalid_range:{path}:{start}:{end}")
            continue
        content = str(chunk["content"]).encode("utf-8")
        if not content:
            errors.append(f"empty_chunk:{path}:{start}:{end}")
        if content != source.data[start:end]:
            errors.append(f"content_slice_mismatch:{path}:{start}:{end}")
        if sha256_bytes(content) != chunk["content_sha256"]:
            errors.append(f"content_hash_mismatch:{path}:{start}:{end}")
        if chunk["source_sha256"] != source.sha256:
            errors.append(f"source_hash_mismatch:{path}")

    unhandled_diagnostics = [item for item in diagnostics if not item.handled]
    if strict_parse_errors and unhandled_diagnostics:
        errors.append(f"unhandled_parser_errors:{len(unhandled_diagnostics)}")
    return sorted(set(errors))


def _corpus_manifest(
    *,
    config: IndexConfig,
    repository_id: str,
    corpus: CorpusCollection,
    chunks: list[dict[str, Any]],
    diagnostics: list[ParseDiagnostic],
) -> dict[str, Any]:
    chunk_counts = Counter(str(chunk["path"]) for chunk in chunks)
    diagnostic_counts = Counter(item.path for item in diagnostics)
    handled_diagnostic_counts = Counter(
        item.path for item in diagnostics if item.handled
    )
    unhandled_diagnostic_counts = Counter(
        item.path for item in diagnostics if not item.handled
    )
    excluded_counts = Counter(item.reason for item in corpus.excluded_files)
    return {
        "artifact_schema_version": config.artifact_schema_version,
        "chunk_count": len(chunks),
        "chunking_version": config.chunking.version,
        "config_path": _artifact_config_path(config.path),
        "config_sha256": config.sha256,
        "corpus_version": config.corpus.version,
        "exclude_filename_patterns": list(config.corpus.exclude_filename_patterns),
        "exclude_path_components": list(config.corpus.exclude_path_components),
        "exclude_path_prefixes": list(config.corpus.exclude_path_prefixes),
        "excluded_file_count": len(corpus.excluded_files),
        "excluded_reason_counts": dict(sorted(excluded_counts.items())),
        "excluded_files": [
            {"path": item.path, "reason": item.reason}
            for item in corpus.excluded_files
        ],
        "file_count": len(corpus.files),
        "file_hashes": [
            {
                "chunk_count": chunk_counts.get(source.path, 0),
                "handled_parser_error_count": handled_diagnostic_counts.get(
                    source.path, 0
                ),
                "parser_error_count": diagnostic_counts.get(source.path, 0),
                "path": source.path,
                "sha256": source.sha256,
                "size_bytes": source.size_bytes,
                "unhandled_parser_error_count": unhandled_diagnostic_counts.get(
                    source.path, 0
                ),
            }
            for source in corpus.files
        ],
        "grammar_package": config.parser.grammar_package,
        "grammar_version": _distribution_version(config.parser.grammar_package),
        "include_extensions": list(config.corpus.include_extensions),
        "handled_parser_error_count": sum(item.handled for item in diagnostics),
        "macro_fallback_version": config.chunking.macro_fallback_version,
        "parser": "Tree-sitter C++",
        "parser_error_count": len(diagnostics),
        "preprocessor_error_fallback_version": (
            config.chunking.preprocessor_error_fallback_version
        ),
        "parser_package": config.parser.package,
        "parser_version": _distribution_version(config.parser.package),
        "protocol_version": config.protocol_version,
        "repository": repository_id,
        "repository_commit": corpus.repository_commit,
        "tracked_files_only": config.corpus.tracked_files_only,
        "unhandled_parser_error_count": sum(
            not item.handled for item in diagnostics
        ),
    }


def build_repository_index(
    *,
    config_path: str | Path,
    repository_id: str,
    repository_root: str | Path,
    output_dir: str | Path,
    strict: bool = True,
    parser: Any | None = None,
) -> BuildResult:
    """Build one deterministic Phase 1 index.

    This function does not perform query extraction, BM25 retrieval, expansion,
    context generation, LLM calls, Docker execution, pilot work, or formal runs.
    """

    config = IndexConfig.load(config_path)
    if repository_id not in config.repositories:
        raise KeyError(f"repository is not configured: {repository_id}")
    repository_spec = config.repositories[repository_id]
    corpus = collect_production_corpus(
        repository_root,
        repository_spec.expected_commit,
        config.corpus,
    )
    cpp_parser = parser if parser is not None else create_cpp_parser(config.parser)

    all_chunks: list[dict[str, Any]] = []
    diagnostics: list[ParseDiagnostic] = []
    for source in corpus.files:
        parsed = extract_symbol_chunks(
            parser=cpp_parser,
            repository_id=repository_id,
            repository_commit=corpus.repository_commit,
            source=source,
            chunking=config.chunking,
        )
        all_chunks.extend(parsed.chunks)
        diagnostics.extend(parsed.diagnostics)

    all_chunks.sort(
        key=lambda item: (
            item["path"],
            item["start_byte"],
            item["end_byte"],
            item["kind"],
            item["chunk_id"],
        )
    )
    symbol_index = build_exact_symbol_index(
        all_chunks,
        index_version=config.exact_symbol_index_version,
    )
    validation_errors = _validate_chunks(
        corpus,
        all_chunks,
        diagnostics,
        strict_parse_errors=config.parser.strict_unrecorded_errors,
    )

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest = _corpus_manifest(
        config=config,
        repository_id=repository_id,
        corpus=corpus,
        chunks=all_chunks,
        diagnostics=diagnostics,
    )
    artifact_hashes = {
        "corpus_manifest.json": write_canonical_json(
            output / "corpus_manifest.json", manifest
        ),
        "chunks.jsonl": write_canonical_jsonl(output / "chunks.jsonl", all_chunks),
        "symbol_index.jsonl": write_canonical_jsonl(
            output / "symbol_index.jsonl", symbol_index
        ),
    }
    validation = {
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
        "chunk_count": len(all_chunks),
        "deterministic": None,
        "duplicate_chunk_id_count": sum(
            1 for error in validation_errors if error.startswith("duplicate_chunk_id:")
        ),
        "file_count": len(corpus.files),
        "independent_build_count": 1,
        "parser_diagnostics": [
            {
                "end_byte": item.end_byte,
                "end_line": item.end_line,
                "fallback_method": item.fallback_method,
                "handled": item.handled,
                "node_type": item.node_type,
                "path": item.path,
                "reason": item.reason,
                "start_byte": item.start_byte,
                "start_line": item.start_line,
            }
            for item in sorted(
                diagnostics,
                key=lambda item: (item.path, item.start_byte, item.end_byte, item.node_type),
            )
        ],
        "handled_parser_error_count": sum(item.handled for item in diagnostics),
        "parser_error_count": len(diagnostics),
        "repository": repository_id,
        "repository_commit": corpus.repository_commit,
        "status": "pass" if not validation_errors else "fail",
        "symbol_count": len(symbol_index),
        "unhandled_parser_error_count": sum(
            not item.handled for item in diagnostics
        ),
        "validation_errors": validation_errors,
        "validation_version": "rag-index-validation-v1",
    }
    write_canonical_json(output / "index_validation.json", validation)

    result = BuildResult(
        repository_id=repository_id,
        repository_commit=corpus.repository_commit,
        output_dir=output,
        file_count=len(corpus.files),
        chunk_count=len(all_chunks),
        symbol_count=len(symbol_index),
        diagnostics=tuple(diagnostics),
        validation_errors=tuple(validation_errors),
        artifact_hashes=artifact_hashes,
    )
    if strict and not result.valid:
        raise IndexValidationError(
            "index validation failed: " + "; ".join(result.validation_errors)
        )
    return result
