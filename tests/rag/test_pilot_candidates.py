from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.rag.artifacts import CandidateConfig, load_index_artifacts, load_query_artifact
from scripts.rag.build_pilot_candidates import build_and_verify_pilot_pool
from scripts.rag.pilot_candidates import (
    _test_evidence,
    discover_pilot_candidates,
)
from tests.rag.fixture_factory import make_chunk, query_record, write_index, write_query


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "rag" / "candidates_v1.json"
FIXTURE = ROOT / "tests" / "rag" / "fixtures" / "pilot_candidates"
EXPECTED = json.loads(
    (ROOT / "tests" / "rag" / "expected" / "pilot_candidates" / "pool.json").read_text(
        encoding="utf-8"
    )
)


class PilotCandidateTests(unittest.TestCase):
    def _fixture(self, root: Path):
        repository_root = root / "repo"
        shutil.copytree(FIXTURE, repository_root)

        chunks = [
            make_chunk(
                repository="repo",
                path="src/formal.hpp",
                start_byte=0,
                content="class Formal {};",
                canonical_name="Formal",
                kind="class_interface",
            ),
            make_chunk(
                repository="repo",
                path="src/pilot.hpp",
                start_byte=0,
                content="namespace n { class Pilot { void run(); Helper helper; }; }",
                canonical_name="n::Pilot",
                short_symbol="Pilot",
                kind="class_interface",
                namespace="n",
            ),
            make_chunk(
                repository="repo",
                path="src/helper.hpp",
                start_byte=0,
                content="struct Helper {};",
                canonical_name="Helper",
                kind="struct_interface",
            ),
        ]
        index_dir = write_index(root, repository="repo", chunks=chunks)
        formal_query = write_query(
            root,
            repository="repo",
            target_id="formal",
            records=[query_record(category="target_symbols", text="Formal")],
            source_ranges=[
                {"path": "src/formal.hpp", "start_byte": 0, "end_byte": 100}
            ],
            granularity="module_files",
        )
        return repository_root, index_dir, formal_query

    def test_discovers_only_static_test_referenced_formal_outside_targets(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            root = Path(raw)
            repository_root, index_dir, formal_query = self._fixture(root)
            candidates = discover_pilot_candidates(
                indexes=[load_index_artifacts(index_dir)],
                formal_queries=[load_query_artifact(formal_query)],
                repository_roots={"repo": repository_root},
                config=CandidateConfig.load(CONFIG),
            )
            self.assertEqual(
                [item["target_symbol"] for item in candidates],
                EXPECTED["target_symbols"],
            )
            candidate = candidates[0]
            self.assertFalse(candidate["formal_overlap"])
            self.assertEqual(candidate["baseline_execution_status"], "not_run")
            self.assertEqual(candidate["source_restoration_status"], "not_run")
            self.assertEqual(candidate["selection_status"], "provisional")
            self.assertEqual(candidate["static_test_evidence"][0]["path"], "tests/pilot_test.cpp")
            self.assertNotIn("content", candidate["static_test_evidence"][0])

    def test_method_evidence_requires_owner_and_code_call(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            false_owner = root / "false_owner_test.cpp"
            false_owner.write_text(
                "ThreadPool pool;\npool.Start();\n",
                encoding="utf-8",
            )
            comment_only = root / "comment_only_test.cpp"
            comment_only.write_text(
                "// WebServer server; server.Start();\n"
                'const char* message = "WebServer::Start()";\n',
                encoding="utf-8",
            )
            direct = root / "direct_test.cpp"
            direct.write_text(
                "WebServer server;\nserver.Start();\n",
                encoding="utf-8",
            )

            evidence = _test_evidence(
                canonical_name="ws::WebServer::Start",
                short_name="Start",
                kind="method_definition",
                parent_symbol="ws::WebServer",
                test_files=[
                    ("tests/comment_only_test.cpp", comment_only),
                    ("tests/direct_test.cpp", direct),
                    ("tests/false_owner_test.cpp", false_owner),
                ],
            )

            self.assertEqual(
                [item["path"] for item in evidence],
                ["tests/direct_test.cpp"],
            )
            self.assertEqual(
                evidence[0]["match_type"],
                "owner_and_short_call",
            )

    def test_main_is_not_selected_from_lexical_test_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "main_test.cpp"
            source.write_text("int main();\n", encoding="utf-8")
            evidence = _test_evidence(
                canonical_name="main",
                short_name="main",
                kind="function_definition",
                parent_symbol=None,
                test_files=[("tests/main_test.cpp", source)],
            )
            self.assertEqual(evidence, [])

    def test_independent_pilot_pool_hashes_match_without_freezing_ids(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            repository_root, index_dir, formal_query = self._fixture(root)
            output = root / "reports" / "rag" / "pilot"
            hashes = build_and_verify_pilot_pool(
                index_dirs={"repo": index_dir},
                formal_query_paths=[formal_query],
                repository_roots={"repo": repository_root},
                config_path=CONFIG,
                output_dir=output,
            )
            document = json.loads(
                (output / "pilot_candidate_pool.json").read_text(encoding="utf-8")
            )
            validation = json.loads(
                (output / "pilot_candidate_pool_validation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(document["formal_target_count_used_for_masking"], 1)
            self.assertEqual(document["pilot_ids_frozen"], EXPECTED["pilot_ids_frozen"])
            self.assertEqual(document["selection_count"], EXPECTED["selection_count"])
            self.assertFalse(document["baseline_build_test_executed"])
            self.assertTrue(validation["deterministic"])
            self.assertIn("pilot_candidate_pool.json", hashes)


if __name__ == "__main__":
    unittest.main()
