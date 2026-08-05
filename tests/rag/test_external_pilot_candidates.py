from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.rag.artifacts import CandidateConfig, load_index_artifacts
from scripts.rag.build_external_pilot_candidates import (
    build_and_verify_external_pilot_selection,
)
from scripts.rag.canonical import canonical_json_bytes
from scripts.rag.external_pilot_candidates import (
    _target_id,
    discover_external_pilot_candidates,
    external_candidate_documents,
    external_policy,
    validate_external_repository,
)
from tests.rag.fixture_factory import COMMIT, make_chunk, write_index


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "rag" / "pilot" / "tinyxml2_candidates_v1.json"
YAML_CPP_CONFIG = (
    ROOT / "configs" / "rag" / "pilot" / "yaml_cpp_candidates_v1.json"
)
YAML_CPP_CONFIG_V2 = (
    ROOT / "configs" / "rag" / "pilot" / "yaml_cpp_candidates_v2.json"
)


def _run(root: Path, *args: str) -> str:
    completed = subprocess.run(
        [*args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _fixture_config(root: Path, *, required_count: int = 5) -> Path:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["pilot"]["repository_commit"] = COMMIT
    raw["selection"]["required_count"] = required_count
    path = root / "external-config.json"
    path.write_bytes(canonical_json_bytes(raw))
    return path


def _candidate_chunks() -> list[dict[str, object]]:
    return [
        make_chunk(
            repository="tinyxml2",
            path="tinyxml2.h",
            start_byte=0,
            content="class XMLDocument { public: void Parse(); void Print(); };",
            canonical_name="tinyxml2::XMLDocument",
            short_symbol="XMLDocument",
            kind="class_interface",
            namespace="tinyxml2",
        ),
        make_chunk(
            repository="tinyxml2",
            path="tinyxml2.h",
            start_byte=100,
            content="class XMLPrinter { public: void CloseElement(); };",
            canonical_name="tinyxml2::XMLPrinter",
            short_symbol="XMLPrinter",
            kind="class_interface",
            namespace="tinyxml2",
        ),
        make_chunk(
            repository="tinyxml2",
            path="tinyxml2.h",
            start_byte=200,
            content="struct XMLNode { XMLDocument* document; };",
            canonical_name="tinyxml2::XMLNode",
            short_symbol="XMLNode",
            kind="struct_interface",
            namespace="tinyxml2",
        ),
        make_chunk(
            repository="tinyxml2",
            path="tinyxml2.cpp",
            start_byte=0,
            content="void XMLDocument::Parse() { Print(); CloseElement(); }",
            canonical_name="tinyxml2::XMLDocument::Parse",
            short_symbol="Parse",
            parent_symbol="tinyxml2::XMLDocument",
            kind="method_definition",
        ),
        make_chunk(
            repository="tinyxml2",
            path="tinyxml2.cpp",
            start_byte=100,
            content="void XMLDocument::Print() { Parse(); CloseElement(); }",
            canonical_name="tinyxml2::XMLDocument::Print",
            short_symbol="Print",
            parent_symbol="tinyxml2::XMLDocument",
            kind="method_definition",
        ),
        make_chunk(
            repository="tinyxml2",
            path="tinyxml2.cpp",
            start_byte=200,
            content="void XMLPrinter::CloseElement() { Parse(); Print(); }",
            canonical_name="tinyxml2::XMLPrinter::CloseElement",
            short_symbol="CloseElement",
            parent_symbol="tinyxml2::XMLPrinter",
            kind="method_definition",
        ),
        make_chunk(
            repository="tinyxml2",
            path="tinyxml2.cpp",
            start_byte=300,
            content="void Other::Parse() {}",
            canonical_name="tinyxml2::Other::Parse",
            short_symbol="Parse",
            parent_symbol="tinyxml2::Other",
            kind="method_definition",
        ),
    ]


def _write_evidence(root: Path) -> Path:
    source = root / "xmltest.cpp"
    source.write_text(
        "XMLDocument document;\n"
        "document.Parse();\n"
        "document.Print();\n"
        "XMLPrinter printer;\n"
        "printer.CloseElement();\n"
        "XMLNode node;\n",
        encoding="utf-8",
    )
    return source


class ExternalPilotPolicyTests(unittest.TestCase):
    def test_target_id_uses_repository_identity(self) -> None:
        target_id = _target_id(
            {
                "candidate_id": "a" * 64,
                "repository_id": "yaml-cpp",
                "target_symbol": "YAML::LoadFile",
            }
        )
        self.assertEqual(target_id, "yaml-cpp-yaml-loadfile-aaaaaaaaaaaa")

    def test_yaml_cpp_config_keeps_the_frozen_selection_rules(self) -> None:
        policy = external_policy(CandidateConfig.load(YAML_CPP_CONFIG))
        self.assertEqual(policy["repository_id"], "yaml-cpp")
        self.assertEqual(
            policy["repository_commit"],
            "3eb39d5808c33aa93a113cb6c668fa2435ff3ecd",
        )
        self.assertEqual(policy["required_count"], 5)
        self.assertEqual(policy["minimum_distinct_source_files"], 2)
        self.assertEqual(
            policy["minimum_per_granularity"],
            {"class_span": 1, "function": 1},
        )
        self.assertEqual(len(policy["evidence_paths"]), 16)

    def test_yaml_cpp_v2_changes_provenance_not_selection_policy(self) -> None:
        first = CandidateConfig.load(YAML_CPP_CONFIG).raw
        second = CandidateConfig.load(YAML_CPP_CONFIG_V2).raw
        self.assertEqual(first["selection"], second["selection"])
        self.assertEqual(first["filtering"], second["filtering"])
        self.assertEqual(first["exact_retrieval"], second["exact_retrieval"])
        self.assertEqual(first["stages"], second["stages"])
        self.assertNotEqual(first["dependencies"], second["dependencies"])
        self.assertNotEqual(first["pilot"]["version"], second["pilot"]["version"])

    def test_config_freezes_external_selection_rules(self) -> None:
        policy = external_policy(CandidateConfig.load(CONFIG))
        self.assertEqual(policy["repository_id"], "tinyxml2")
        self.assertEqual(
            policy["repository_commit"],
            "8224e427b655b83dae5e2298f1e6919523a78737",
        )
        self.assertEqual(policy["evidence_paths"], ["xmltest.cpp"])
        self.assertEqual(policy["required_count"], 5)
        self.assertEqual(
            policy["minimum_per_granularity"],
            {"class_span": 1, "function": 1},
        )
        self.assertEqual(policy["minimum_distinct_source_files"], 2)

    def test_repository_validation_requires_fixed_clean_tracked_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _run(root, "git", "init", "-q")
            _run(root, "git", "config", "user.name", "External Pilot Fixture")
            _run(root, "git", "config", "user.email", "pilot@example.invalid")
            evidence = _write_evidence(root)
            _run(root, "git", "add", "--", evidence.name)
            _run(root, "git", "commit", "-q", "-m", "test: add evidence")
            commit = _run(root, "git", "rev-parse", "HEAD")
            files = validate_external_repository(
                root,
                expected_commit=commit,
                evidence_paths=["xmltest.cpp"],
            )
            self.assertEqual(files[0][0], "xmltest.cpp")
            evidence.write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "tracked or untracked changes"):
                validate_external_repository(
                    root,
                    expected_commit=commit,
                    evidence_paths=["xmltest.cpp"],
                )


class ExternalPilotCandidateTests(unittest.TestCase):
    def _fixture(self, root: Path, *, chunks=None, required_count: int = 5):
        repository_root = root / "repo"
        repository_root.mkdir()
        evidence = _write_evidence(repository_root)
        index_dir = write_index(
            root,
            repository="tinyxml2",
            chunks=chunks or _candidate_chunks(),
        )
        config_path = _fixture_config(root, required_count=required_count)
        return repository_root, evidence, index_dir, config_path

    def test_explicit_xmltest_evidence_is_owner_aware(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            root = Path(raw)
            repository_root, evidence, index_dir, config_path = self._fixture(root)
            with mock.patch(
                "scripts.rag.external_pilot_candidates.validate_external_repository",
                return_value=[("xmltest.cpp", evidence)],
            ):
                candidates = discover_external_pilot_candidates(
                    index=load_index_artifacts(index_dir),
                    repository_root=repository_root,
                    config=CandidateConfig.load(config_path),
                )
            symbols = [item["target_symbol"] for item in candidates]
            self.assertIn("tinyxml2::XMLDocument::Parse", symbols)
            self.assertNotIn("tinyxml2::Other::Parse", symbols)
            self.assertTrue(all(item["path"] != "xmltest.cpp" for item in candidates))
            parse = next(
                item
                for item in candidates
                if item["target_symbol"] == "tinyxml2::XMLDocument::Parse"
            )
            self.assertEqual(
                parse["static_test_evidence"][0]["match_type"],
                "owner_and_short_call",
            )

    def test_selection_freezes_five_targets_with_granularity_and_path_diversity(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            root = Path(raw)
            repository_root, evidence, index_dir, config_path = self._fixture(root)
            with mock.patch(
                "scripts.rag.external_pilot_candidates.validate_external_repository",
                return_value=[("xmltest.cpp", evidence)],
            ):
                pool, selection = external_candidate_documents(
                    index=load_index_artifacts(index_dir),
                    repository_root=repository_root,
                    config=CandidateConfig.load(config_path),
                )
            self.assertEqual(pool["status"], "selected")
            self.assertTrue(pool["pilot_ids_frozen"])
            self.assertEqual(selection["selected_count"], 5)
            selected = selection["selected_candidates"]
            self.assertEqual(
                {item["granularity"] for item in selected},
                {"class_span", "function"},
            )
            self.assertEqual(len({item["path"] for item in selected}), 2)
            self.assertEqual(len({item["pilot_target_id"] for item in selected}), 5)

    def test_insufficient_candidates_do_not_freeze_ids(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            root = Path(raw)
            chunks = _candidate_chunks()[:2]
            repository_root, evidence, index_dir, config_path = self._fixture(
                root,
                chunks=chunks,
            )
            with mock.patch(
                "scripts.rag.external_pilot_candidates.validate_external_repository",
                return_value=[("xmltest.cpp", evidence)],
            ):
                pool, selection = external_candidate_documents(
                    index=load_index_artifacts(index_dir),
                    repository_root=repository_root,
                    config=CandidateConfig.load(config_path),
                )
            self.assertEqual(pool["status"], "insufficient_candidates")
            self.assertFalse(pool["pilot_ids_frozen"])
            self.assertEqual(selection["selected_count"], 0)
            self.assertTrue(selection["insufficient_reasons"])

    def test_independent_builds_match_in_separate_external_output(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            root = Path(raw)
            repository_root, evidence, index_dir, config_path = self._fixture(root)
            output = root / "reports" / "rag" / "pilot" / "external" / "tinyxml2"
            with mock.patch(
                "scripts.rag.external_pilot_candidates.validate_external_repository",
                return_value=[("xmltest.cpp", evidence)],
            ):
                hashes = build_and_verify_external_pilot_selection(
                    index_dir=index_dir,
                    repository_root=repository_root,
                    config_path=config_path,
                    output_dir=output,
                )
            validation = json.loads(
                (output / "external_pilot_candidate_validation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(validation["deterministic"])
            self.assertEqual(validation["independent_build_count"], 2)
            self.assertIn("external_pilot_candidate_pool.json", hashes)
            self.assertIn("external_pilot_selection.json", hashes)
            self.assertFalse((root / "reports" / "rag" / "pilot" / "pilot_candidate_pool.json").exists())


if __name__ == "__main__":
    unittest.main()
