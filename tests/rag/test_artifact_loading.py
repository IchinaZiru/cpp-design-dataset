from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.rag.artifacts import ArtifactLoadError, load_index_artifacts, load_query_artifact
from scripts.rag.canonical import write_canonical_jsonl
from tests.rag.fixture_factory import (
    make_chunk,
    query_record,
    refresh_index_validation,
    symbol_for_chunk,
    write_index,
    write_query,
)


class ArtifactLoadingTests(unittest.TestCase):
    def test_loads_consistent_index_and_query(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            chunk = make_chunk(
                repository="repo",
                path="src/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="ns::Widget",
                short_symbol="Widget",
                kind="class_interface",
            )
            index = load_index_artifacts(write_index(root, repository="repo", chunks=[chunk]))
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[query_record(category="user_defined_types", text="Widget")],
                )
            )
            self.assertEqual(index.repository_id, "repo")
            self.assertEqual(len(index.chunks), 1)
            self.assertEqual(query.target_id, "formal")
            self.assertEqual(len(query.records), 1)

    def test_rejects_duplicate_chunk_id_after_hash_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            chunk = make_chunk(
                repository="repo",
                path="src/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="ns::Widget",
                kind="class_interface",
            )
            index_dir = write_index(root, repository="repo", chunks=[chunk])
            write_canonical_jsonl(index_dir / "chunks.jsonl", [chunk, chunk])
            refresh_index_validation(index_dir)
            with self.assertRaisesRegex(ArtifactLoadError, "duplicate chunk_id"):
                load_index_artifacts(index_dir)

    def test_rejects_symbol_reference_to_unknown_chunk(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            chunk = make_chunk(
                repository="repo",
                path="src/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="ns::Widget",
                kind="class_interface",
            )
            symbol = symbol_for_chunk(chunk)
            symbol["chunk_id"] = "f" * 64
            index_dir = write_index(
                root, repository="repo", chunks=[chunk], symbols=[symbol]
            )
            with self.assertRaisesRegex(ArtifactLoadError, "unknown chunk"):
                load_index_artifacts(index_dir)

    def test_rejects_query_payload_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            query_path = write_query(
                root,
                repository="repo",
                target_id="formal",
                records=[query_record(category="user_defined_types", text="Widget")],
            )
            document = json.loads(query_path.read_text(encoding="utf-8"))
            document["target"]["target_name"] = "changed"
            query_path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ArtifactLoadError, "payload hash mismatch"):
                load_query_artifact(query_path)

    def test_rejects_absolute_chunk_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            chunk = make_chunk(
                repository="repo",
                path="src/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="ns::Widget",
                kind="class_interface",
            )
            index_dir = write_index(root, repository="repo", chunks=[chunk])
            bad = dict(chunk)
            bad["path"] = "/tmp/widget.hpp"
            write_canonical_jsonl(index_dir / "chunks.jsonl", [bad])
            refresh_index_validation(index_dir)
            with self.assertRaisesRegex(ArtifactLoadError, "invalid chunk path"):
                load_index_artifacts(index_dir)


if __name__ == "__main__":
    unittest.main()
