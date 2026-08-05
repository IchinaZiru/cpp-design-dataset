from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.rag.artifacts import CandidateConfig, load_query_artifact
from scripts.rag.candidate_filters import apply_candidate_filters, path_byte_overlap_v1
from tests.rag.fixture_factory import query_record, write_query


CONFIG = Path(__file__).resolve().parents[2] / "configs" / "rag" / "candidates_v1.json"


class CandidateFilterTests(unittest.TestCase):
    def test_half_open_ranges_touch_without_overlapping(self) -> None:
        ranges = [{"path": "src/a.cpp", "start_byte": 10, "end_byte": 20}]
        self.assertEqual(
            path_byte_overlap_v1(
                candidate_path="src/a.cpp",
                candidate_start=0,
                candidate_end=10,
                source_ranges=ranges,
            ),
            [],
        )
        self.assertEqual(
            len(
                path_byte_overlap_v1(
                    candidate_path="src/a.cpp",
                    candidate_start=9,
                    candidate_end=11,
                    source_ranges=ranges,
                )
            ),
            1,
        )

    def test_rejects_incompatible_coordinate_hashes(self) -> None:
        with self.assertRaisesRegex(ValueError, "coordinate hash mismatch"):
            path_byte_overlap_v1(
                candidate_path="src/a.cpp",
                candidate_start=0,
                candidate_end=10,
                candidate_source_sha256="a" * 64,
                source_ranges=[
                    {
                        "path": "src/a.cpp",
                        "start_byte": 0,
                        "end_byte": 20,
                        "git_blob_sha256": "a" * 64,
                        "normalized_source_sha256": "b" * 64,
                    }
                ],
            )

    def test_module_file_range_excludes_entire_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[query_record(category="user_defined_types", text="Widget")],
                    source_ranges=[
                        {
                            "path": "src/a.cpp",
                            "start_byte": 0,
                            "end_byte": 100,
                        }
                    ],
                    granularity="module_files",
                )
            )
            candidate = {
                "path": "src/a.cpp",
                "start_byte": 20,
                "end_byte": 30,
                "_content": "void f() {}",
            }
            result = apply_candidate_filters(
                candidate,
                query=query,
                config=CandidateConfig.load(CONFIG),
            )
            self.assertFalse(result["eligible"])
            self.assertIn("target_source_overlap", result["exclusion_reasons"])

    def test_class_span_keeps_nonoverlapping_symbol_in_same_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[query_record(category="user_defined_types", text="Widget")],
                    source_ranges=[
                        {
                            "path": "src/a.cpp",
                            "start_byte": 20,
                            "end_byte": 40,
                        }
                    ],
                    granularity="class_span",
                )
            )
            result = apply_candidate_filters(
                {
                    "path": "src/a.cpp",
                    "start_byte": 50,
                    "end_byte": 70,
                    "_content": "void helper() {}",
                },
                query=query,
                config=CandidateConfig.load(CONFIG),
            )
            self.assertTrue(result["eligible"])
            self.assertEqual(result["overlap_evidence"], [])

    def test_test_generated_and_experiment_filters_record_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[query_record(category="user_defined_types", text="Widget")],
                )
            )
            result = apply_candidate_filters(
                {
                    "path": "experiments/generated/tests/widget_test.cpp",
                    "start_byte": 0,
                    "end_byte": 20,
                    "_content": "// Generated by tool\nTEST(Widget, Works) {}",
                },
                query=query,
                config=CandidateConfig.load(CONFIG),
            )
            self.assertEqual(
                result["exclusion_reasons"],
                [
                    "test_content_detected",
                    "experiment_artifact",
                    "generated_content",
                ],
            )

    def test_plain_assert_does_not_trigger_test_filter(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[query_record(category="user_defined_types", text="Widget")],
                )
            )
            result = apply_candidate_filters(
                {
                    "path": "src/check.cpp",
                    "start_byte": 100,
                    "end_byte": 130,
                    "_content": "assert(value > 0);",
                },
                query=query,
                config=CandidateConfig.load(CONFIG),
            )
            self.assertNotIn("test_content_detected", result["exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
