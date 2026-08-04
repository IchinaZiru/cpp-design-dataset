"""Collect a deterministic production C/C++ corpus from tracked Git files."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .canonical import posix_relative_path, sha256_bytes
from .config import CorpusSpec


class CorpusError(RuntimeError):
    """Raised when a pinned repository cannot be collected safely."""


@dataclass(frozen=True)
class TrackedEntry:
    path: str
    mode: str
    object_id: str


@dataclass(frozen=True)
class SourceFile:
    path: str
    absolute_path: Path
    data: bytes
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class ExcludedFile:
    path: str
    reason: str


@dataclass(frozen=True)
class CorpusCollection:
    repository_root: Path
    repository_commit: str
    files: tuple[SourceFile, ...]
    excluded_files: tuple[ExcludedFile, ...]


def _run_git(root: Path, *args: str, binary: bool = False) -> bytes | str:
    command = ["git", "-C", str(root), *args]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise CorpusError("git executable was not found") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace").strip()
        raise CorpusError(f"git command failed: {' '.join(command)}: {stderr}") from exc
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").strip()


def repository_head(root: Path) -> str:
    head = str(_run_git(root, "rev-parse", "HEAD")).lower()
    if len(head) != 40:
        raise CorpusError(f"unexpected repository HEAD: {head!r}")
    return head


def ensure_clean_tracked_files(root: Path) -> None:
    """Reject staged or tracked working-tree modifications.

    Untracked and ignored build outputs are intentionally ignored here. Corpus
    bytes are read from the exact Git tree at HEAD, never from those files.
    """

    status = str(
        _run_git(
            root,
            "status",
            "--porcelain=v1",
            "--untracked-files=no",
            "--ignore-submodules=all",
        )
    )
    if status:
        raise CorpusError(
            "tracked files are modified; refusing to mix working-tree changes into the index:\n"
            + status
        )


def tracked_entries(root: Path) -> tuple[TrackedEntry, ...]:
    """Enumerate the exact tree at HEAD, independent of checkout line endings."""

    raw = bytes(
        _run_git(
            root,
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            "HEAD",
            binary=True,
        )
    )
    entries: list[TrackedEntry] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, encoded_path = record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            path = encoded_path.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError) as exc:
            raise CorpusError("cannot parse git ls-tree output") from exc
        if object_type not in {"blob", "commit"}:
            raise CorpusError(
                f"unsupported Git tree object type {object_type!r}: {path}"
            )
        entries.append(
            TrackedEntry(
                path=posix_relative_path(path),
                mode=mode,
                object_id=object_id.lower(),
            )
        )
    return tuple(sorted(entries, key=lambda item: item.path))


def read_tracked_blob(root: Path, entry: TrackedEntry) -> bytes:
    """Read committed bytes directly from Git instead of the working tree."""

    return bytes(_run_git(root, "cat-file", "blob", entry.object_id, binary=True))


def collect_production_corpus(
    repository_root: str | Path,
    expected_commit: str,
    corpus_spec: CorpusSpec,
) -> CorpusCollection:
    root = Path(repository_root).resolve()
    if not (root / ".git").exists() and not (root / ".git").is_file():
        raise CorpusError(f"repository root is not a Git working tree: {root}")

    actual_commit = repository_head(root)
    if actual_commit != expected_commit.lower():
        raise CorpusError(
            f"repository commit mismatch: expected {expected_commit}, got {actual_commit}"
        )
    ensure_clean_tracked_files(root)

    included: list[SourceFile] = []
    excluded: list[ExcludedFile] = []
    for entry in tracked_entries(root):
        if entry.mode == "160000":
            excluded.append(ExcludedFile(path=entry.path, reason="nested_submodule"))
            continue
        if entry.mode == "120000":
            excluded.append(ExcludedFile(path=entry.path, reason="symlink"))
            continue

        reason = corpus_spec.classify_path(entry.path)
        if reason is not None:
            excluded.append(ExcludedFile(path=entry.path, reason=reason))
            continue

        absolute_path = root.joinpath(*entry.path.split("/"))
        data = read_tracked_blob(root, entry)
        included.append(
            SourceFile(
                path=entry.path,
                absolute_path=absolute_path,
                data=data,
                sha256=sha256_bytes(data),
                size_bytes=len(data),
            )
        )

    return CorpusCollection(
        repository_root=root,
        repository_commit=actual_commit,
        files=tuple(sorted(included, key=lambda item: item.path)),
        excluded_files=tuple(sorted(excluded, key=lambda item: (item.path, item.reason))),
    )
