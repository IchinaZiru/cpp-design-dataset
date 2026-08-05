from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.rag.artifacts import CandidateConfig, load_index_artifacts, load_query_artifact
from scripts.rag.exact_retriever import exact_retrieve
from tests.rag.fixture_factory import make_chunk, query_record, write_index, write_query


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "rag" / "candidates_v1.json"
EXPECTED = json.loads(
    (ROOT / "tests" / "rag" / "expected" / "exact_retrieval" / "candidates.json").read_text(
        encoding="utf-8"
    )
)


class ExactRetrievalTests(unittest.TestCase):
    def _fixture(self, root: Path):
        chunks = [
            make_chunk(
                repository="repo",
                path="include/ns/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="ns::Widget",
                short_symbol="Widget",
                kind="class_interface",
            ),
            make_chunk(
                repository="repo",
                path="include/other/widget.hpp",
                start_byte=0,
                content="class Widget {};",
                canonical_name="other::Widget",
                short_symbol="Widget",
                kind="class_interface",
            ),
            make_chunk(
                repository="repo",
                path="src/widget.cpp",
                start_byte=50,
                content="void Widget::run() noexcept {}",
                canonical_name="ns::Widget::run",
                short_symbol="run",
                parent_symbol="ns::Widget",
                kind="method_definition",
                signature="void ns::Widget::run() noexcept",
            ),
            make_chunk(
                repository="repo",
                path="src/factory.cpp",
                start_byte=0,
                content="WidgetFactory make();",
                canonical_name="WidgetFactory",
                short_symbol="WidgetFactory",
                kind="function_declaration",
            ),
        ]
        return load_index_artifacts(write_index(root, repository="repo", chunks=chunks))

    def test_unqualified_short_name_retains_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index = self._fixture(root)
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[query_record(category="user_defined_types", text="Widget")],
                )
            )
            candidates = exact_retrieve(
                index=index,
                query=query,
                config=CandidateConfig.load(CONFIG),
            )
            self.assertEqual(
                [item["canonical_name"] for item in candidates],
                EXPECTED["unqualified_ambiguous"],
            )
            self.assertTrue(all(item["ambiguous"] for item in candidates))
            self.assertTrue(
                all(item["best_match_type"] == "exact_short_name" for item in candidates)
            )

    def test_include_relation_resolves_short_name_without_manual_choice(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index = self._fixture(root)
            records = [
                query_record(
                    category="includes",
                    text="include/ns/widget.hpp",
                    kind="project_include",
                    relation="include",
                ),
                query_record(category="user_defined_types", text="Widget"),
            ]
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=records,
                )
            )
            candidates = exact_retrieve(
                index=index,
                query=query,
                config=CandidateConfig.load(CONFIG),
            )
            self.assertEqual(len(candidates), 1)
            self.assertEqual([candidates[0]["canonical_name"]], EXPECTED["include_resolved"])
            self.assertEqual(
                candidates[0]["best_match_type"],
                "resolved_include_path_and_short_name",
            )
            self.assertFalse(candidates[0]["ambiguous"])

    def test_qualified_method_prefers_exact_canonical_name(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index = self._fixture(root)
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[
                        query_record(
                            category="function_calls",
                            text="ns::Widget::run",
                            kind="qualified_call",
                            relation="call_target",
                        )
                    ],
                )
            )
            candidates = exact_retrieve(
                index=index,
                query=query,
                config=CandidateConfig.load(CONFIG),
            )
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["best_match_type"], "exact_qualified_name")
            self.assertEqual([candidates[0]["canonical_name"]], EXPECTED["qualified_method"])

    def test_substring_matching_is_not_used(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index = self._fixture(root)
            query = load_query_artifact(
                write_query(
                    root,
                    repository="repo",
                    target_id="formal",
                    records=[query_record(category="user_defined_types", text="Factory")],
                )
            )
            self.assertEqual(
                exact_retrieve(
                    index=index,
                    query=query,
                    config=CandidateConfig.load(CONFIG),
                ),
                [],
            )


if __name__ == "__main__":
    unittest.main()
