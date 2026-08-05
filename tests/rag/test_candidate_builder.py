from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.rag.build_candidates import build_and_verify_candidates
from scripts.rag.candidate_builder import CandidateBuildError
from scripts.rag.canonical import sha256_file
from tests.rag.fixture_factory import make_chunk, query_record, write_index, write_query


CONFIG = Path(__file__).resolve().parents[2] / "configs" / "rag" / "candidates_v1.json"


class CandidateBuilderTests(unittest.TestCase):
    def _inputs(self, root: Path) -> tuple[Path, Path]:
        chunks = [
            make_chunk(
                repository="repo",
                path="include/a/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="a::Widget",
                short_symbol="Widget",
                kind="class_interface",
            ),
            make_chunk(
                repository="repo",
                path="include/b/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="b::Widget",
                short_symbol="Widget",
                kind="class_interface",
            ),
        ]
        index_dir = write_index(root, repository="repo", chunks=chunks)
        query_path = write_query(
            root,
            repository="repo",
            target_id="formal",
            records=[query_record(category="user_defined_types", text="Widget")],
            source_ranges=[
                {"path": "src/formal.cpp", "start_byte": 0, "end_byte": 20}
            ],
        )
        return index_dir, query_path

    def test_independent_builds_publish_identical_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index_dir, query_path = self._inputs(root)
            output = root / "candidate-output"
            result = build_and_verify_candidates(
                index_dir=index_dir,
                query_path=query_path,
                config_path=CONFIG,
                output_dir=output,
            )
            self.assertTrue(result.deterministic)
            validation = json.loads(
                (output / "candidate_validation.json").read_text(encoding="utf-8")
            )
            manifest = json.loads(
                (output / "candidate_manifest.json").read_text(encoding="utf-8")
            )
            candidates = [
                json.loads(line)
                for line in (output / "candidates.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(validation["status"], "pass")
            self.assertTrue(validation["deterministic"])
            self.assertTrue(manifest["deterministic"])
            self.assertFalse(manifest["top_k_applied"])
            self.assertFalse(manifest["context_budget_applied"])
            self.assertEqual(len(candidates), 2)
            self.assertTrue(all(item["ambiguous"] for item in candidates))
            self.assertEqual(
                [item["ranking_basis"]["eligible_rank"] for item in candidates],
                [1, 2],
            )

            first_hash = sha256_file(output / "candidates.jsonl")
            second = build_and_verify_candidates(
                index_dir=index_dir,
                query_path=query_path,
                config_path=CONFIG,
                output_dir=output,
            )
            self.assertEqual(first_hash, second.artifact_hashes["candidates.jsonl"])

    def test_refuses_to_overwrite_different_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index_dir, query_path = self._inputs(root)
            output = root / "candidate-output"
            build_and_verify_candidates(
                index_dir=index_dir,
                query_path=query_path,
                config_path=CONFIG,
                output_dir=output,
            )
            (output / "candidates.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(CandidateBuildError, "refusing to overwrite"):
                build_and_verify_candidates(
                    index_dir=index_dir,
                    query_path=query_path,
                    config_path=CONFIG,
                    output_dir=output,
                )


if __name__ == "__main__":
    unittest.main()
