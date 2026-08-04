"""Configuration loading and validation for deterministic RAG indexing."""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .canonical import posix_relative_path, sha256_file


class ConfigError(ValueError):
    """Raised when retrieval_v1.json violates the Phase 1 schema."""


@dataclass(frozen=True)
class RepositorySpec:
    repository_id: str
    path: str
    expected_commit: str


@dataclass(frozen=True)
class ParserSpec:
    package: str
    package_version: str
    grammar_package: str
    grammar_version: str
    strict_unrecorded_errors: bool


@dataclass(frozen=True)
class ChunkingSpec:
    version: str
    macro_fallback_version: str
    stable_chunk_id_version: str
    large_chunk_soft_limit_lines: int
    attach_preceding_doxygen: bool


@dataclass(frozen=True)
class CorpusSpec:
    version: str
    include_extensions: tuple[str, ...]
    exclude_path_components: tuple[str, ...]
    exclude_path_prefixes: tuple[str, ...]
    exclude_filename_patterns: tuple[str, ...]
    tracked_files_only: bool

    def classify_path(self, path: str) -> str | None:
        """Return an exclusion reason or None for an eligible path."""

        normalized = posix_relative_path(path)
        pure = PurePosixPath(normalized)
        suffix = pure.suffix.lower()
        if suffix not in self.include_extensions:
            return "unsupported_extension"

        components = tuple(part.lower() for part in pure.parts[:-1])
        excluded_components = set(self.exclude_path_components)
        for component in components:
            if component in excluded_components:
                return "forbidden_path"
            if any(component.startswith(prefix) for prefix in self.exclude_path_prefixes):
                return "forbidden_path"

        filename = pure.name.lower()
        for pattern in self.exclude_filename_patterns:
            if fnmatch.fnmatchcase(filename, pattern.lower()):
                return "forbidden_filename"
        return None


@dataclass(frozen=True)
class IndexConfig:
    path: Path
    sha256: str
    version: str
    protocol_version: str
    condition_id: str
    artifact_schema_version: str
    retrieval_method: str
    corpus: CorpusSpec
    parser: ParserSpec
    chunking: ChunkingSpec
    repositories: dict[str, RepositorySpec]
    exact_symbol_index_version: str

    @classmethod
    def load(cls, path: str | Path) -> "IndexConfig":
        config_path = Path(path)
        try:
            raw: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"cannot load config {config_path}: {exc}") from exc

        required = {
            "artifact_schema_version",
            "chunking",
            "condition_id",
            "corpus",
            "exact_symbol_index",
            "out_of_scope",
            "parser",
            "protocol_version",
            "repositories",
            "retrieval_method",
            "version",
        }
        missing = sorted(required - raw.keys())
        if missing:
            raise ConfigError(f"missing config keys: {missing}")

        out_of_scope = raw["out_of_scope"]
        prohibited_enabled = sorted(key for key, value in out_of_scope.items() if value)
        if prohibited_enabled:
            raise ConfigError(
                "Phase 1 config must keep later stages disabled: "
                + ", ".join(prohibited_enabled)
            )

        corpus_raw = raw["corpus"]
        parser_raw = raw["parser"]
        chunking_raw = raw["chunking"]
        repositories_raw = raw["repositories"]

        include_extensions = tuple(
            sorted({str(item).lower() for item in corpus_raw["include_extensions"]})
        )
        if not include_extensions or any(not item.startswith(".") for item in include_extensions):
            raise ConfigError("include_extensions must contain dot-prefixed extensions")

        repositories: dict[str, RepositorySpec] = {}
        for repository_id, spec in sorted(repositories_raw.items()):
            expected_commit = str(spec["expected_commit"]).lower()
            if len(expected_commit) != 40 or any(
                character not in "0123456789abcdef" for character in expected_commit
            ):
                raise ConfigError(
                    f"repository {repository_id} expected_commit is not a full SHA-1"
                )
            repositories[repository_id] = RepositorySpec(
                repository_id=repository_id,
                path=posix_relative_path(spec["path"]),
                expected_commit=expected_commit,
            )

        soft_limit = int(chunking_raw["large_chunk_soft_limit_lines"])
        if soft_limit < 1:
            raise ConfigError("large_chunk_soft_limit_lines must be positive")

        return cls(
            path=config_path,
            sha256=sha256_file(config_path),
            version=str(raw["version"]),
            protocol_version=str(raw["protocol_version"]),
            condition_id=str(raw["condition_id"]),
            artifact_schema_version=str(raw["artifact_schema_version"]),
            retrieval_method=str(raw["retrieval_method"]),
            corpus=CorpusSpec(
                version=str(corpus_raw["version"]),
                include_extensions=include_extensions,
                exclude_path_components=tuple(
                    sorted({str(item).lower() for item in corpus_raw["exclude_path_components"]})
                ),
                exclude_path_prefixes=tuple(
                    sorted({str(item).lower() for item in corpus_raw["exclude_path_prefixes"]})
                ),
                exclude_filename_patterns=tuple(
                    sorted({str(item) for item in corpus_raw["exclude_filename_patterns"]})
                ),
                tracked_files_only=bool(corpus_raw["tracked_files_only"]),
            ),
            parser=ParserSpec(
                package=str(parser_raw["package"]),
                package_version=str(parser_raw["package_version"]),
                grammar_package=str(parser_raw["grammar_package"]),
                grammar_version=str(parser_raw["grammar_version"]),
                strict_unrecorded_errors=bool(parser_raw["strict_unrecorded_errors"]),
            ),
            chunking=ChunkingSpec(
                version=str(chunking_raw["version"]),
                macro_fallback_version=str(chunking_raw["macro_fallback_version"]),
                stable_chunk_id_version=str(chunking_raw["stable_chunk_id_version"]),
                large_chunk_soft_limit_lines=soft_limit,
                attach_preceding_doxygen=bool(
                    chunking_raw["attach_preceding_doxygen"]
                ),
            ),
            repositories=repositories,
            exact_symbol_index_version=str(raw["exact_symbol_index"]["version"]),
        )
