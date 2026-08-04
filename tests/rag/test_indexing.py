from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from scripts.rag.canonical import (
    canonical_json_bytes,
    sha256_file,
    write_canonical_json,
    write_canonical_jsonl,
)
from scripts.rag.config import IndexConfig
from scripts.rag.corpus import CorpusError, collect_production_corpus
from scripts.rag.index_builder import BuildResult, IndexValidationError, build_repository_index
from scripts.rag.verify_rebuild import verify_independent_rebuilds


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TREE_SITTER_AVAILABLE = (
    importlib.util.find_spec("tree_sitter") is not None
    and importlib.util.find_spec("tree_sitter_cpp") is not None
)
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"
EXPECTED = json.loads(
    (Path(__file__).resolve().parent / "expected" / "symbols.json").read_text(
        encoding="utf-8"
    )
)
BASE_CONFIG = PROJECT_ROOT / "configs" / "rag" / "retrieval_v1.json"


def _run(root: Path, *args: str) -> str:
    completed = subprocess.run(
        [*args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _initialize_repository(root: Path, filenames: list[str]) -> str:
    root.mkdir(parents=True, exist_ok=True)
    _run(root, "git", "init", "-q")
    _run(root, "git", "config", "user.name", "RAG Fixture")
    _run(root, "git", "config", "user.email", "rag-fixture@example.invalid")
    _run(root, "git", "config", "core.autocrlf", "false")
    for filename in filenames:
        data = (FIXTURE_ROOT / filename).read_bytes()
        if filename == "crlf.hpp":
            data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        (root / filename).write_bytes(data)
    _run(root, "git", "add", "--", *filenames)
    _run(root, "git", "commit", "-q", "-m", "test: add deterministic fixtures")
    return _run(root, "git", "rev-parse", "HEAD")


def _write_fixture_config(path: Path, commit: str) -> None:
    raw = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    raw["repositories"] = {
        "fixture-repo": {
            "expected_commit": commit,
            "path": "fixture-repo",
        }
    }
    path.write_bytes(canonical_json_bytes(raw))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class EnvironmentAndConfigTests(unittest.TestCase):
    def test_environment_manifest_hashes_match_files(self) -> None:
        manifest_path = PROJECT_ROOT / "rag" / "environment" / "rag_environment_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["requirements_lock_sha256"],
            sha256_file(PROJECT_ROOT / manifest["requirements_lock_path"]),
        )
        self.assertEqual(
            manifest["retrieval_config_sha256"],
            sha256_file(PROJECT_ROOT / manifest["retrieval_config_path"]),
        )

    def test_later_phases_are_disabled(self) -> None:
        config = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
        self.assertTrue(config["out_of_scope"])
        self.assertFalse(any(config["out_of_scope"].values()))
        self.assertNotIn("bm25_index_metadata", config)

    def test_lockfile_uses_hashes_and_binary_only_setup(self) -> None:
        lock = (PROJECT_ROOT / "requirements" / "rag.lock.txt").read_text(
            encoding="utf-8"
        )
        setup = (PROJECT_ROOT / "scripts" / "rag" / "setup_environment.ps1").read_text(
            encoding="utf-8"
        )
        self.assertEqual(lock.count("--hash=sha256:"), 2)
        self.assertIn("--require-hashes", setup)
        self.assertIn("--only-binary=:all:", setup)


class CorpusCollectionTests(unittest.TestCase):
    def _config_for(self, root: Path, commit: str) -> Path:
        config = root / "retrieval_fixture.json"
        _write_fixture_config(config, commit)
        return config

    def test_collects_committed_production_blobs_and_ignores_untracked_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rag-corpus-test-") as raw:
            root = Path(raw)
            repository = root / "repository"
            repository.mkdir()
            _run(repository, "git", "init", "-q")
            _run(repository, "git", "config", "user.name", "RAG Fixture")
            _run(repository, "git", "config", "user.email", "rag-fixture@example.invalid")
            (repository / "src").mkdir()
            (repository / "tests").mkdir()
            (repository / "src" / "main.cpp").write_bytes(b"int committed_value = 1;\n")
            (repository / "tests" / "main_test.cpp").write_bytes(b"int test_only = 1;\n")
            _run(repository, "git", "add", "--", "src/main.cpp", "tests/main_test.cpp")
            _run(repository, "git", "commit", "-q", "-m", "test: add corpus fixture")
            commit = _run(repository, "git", "rev-parse", "HEAD")
            (repository / "src" / "untracked.cpp").write_bytes(b"int ignored = 1;\n")

            config = IndexConfig.load(self._config_for(root, commit))
            corpus = collect_production_corpus(
                repository, commit, config.corpus
            )
            self.assertEqual([item.path for item in corpus.files], ["src/main.cpp"])
            self.assertEqual(corpus.files[0].data, b"int committed_value = 1;\n")
            self.assertIn(
                ("tests/main_test.cpp", "forbidden_path"),
                {(item.path, item.reason) for item in corpus.excluded_files},
            )

    def test_tracked_working_tree_change_stops_collection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rag-corpus-dirty-test-") as raw:
            root = Path(raw)
            repository = root / "repository"
            commit = _initialize_repository(repository, ["symbols.cpp"])
            config = IndexConfig.load(self._config_for(root, commit))
            (repository / "symbols.cpp").write_text("int dirty = 1;\n", encoding="utf-8")
            with self.assertRaises(CorpusError):
                collect_production_corpus(repository, commit, config.corpus)

    def test_commit_mismatch_stops_collection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rag-corpus-commit-test-") as raw:
            root = Path(raw)
            repository = root / "repository"
            commit = _initialize_repository(repository, ["symbols.cpp"])
            config = IndexConfig.load(self._config_for(root, commit))
            with self.assertRaises(CorpusError):
                collect_production_corpus(repository, "0" * 40, config.corpus)


class RebuildEvidenceTests(unittest.TestCase):
    @staticmethod
    def _fake_builder(valid: bool):
        def build(**kwargs):
            output = Path(kwargs["output_dir"])
            output.mkdir(parents=True, exist_ok=True)
            hashes = {
                "corpus_manifest.json": write_canonical_json(
                    output / "corpus_manifest.json", {"repository": "fixture-repo"}
                ),
                "chunks.jsonl": write_canonical_jsonl(
                    output / "chunks.jsonl", [{"chunk_id": "a"}]
                ),
                "symbol_index.jsonl": write_canonical_jsonl(
                    output / "symbol_index.jsonl", [{"canonical_name": "fixture"}]
                ),
            }
            write_canonical_json(
                output / "index_validation.json",
                {"status": "pass" if valid else "fail"},
            )
            return BuildResult(
                repository_id="fixture-repo",
                repository_commit="1" * 40,
                output_dir=output,
                file_count=1,
                chunk_count=1,
                symbol_count=1,
                diagnostics=(),
                validation_errors=() if valid else ("recorded_parser_errors:1",),
                artifact_hashes=hashes,
            )

        return build

    def test_successful_rebuild_publishes_and_removes_work_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rag-rebuild-success-") as raw:
            output = Path(raw) / "index"
            with mock.patch(
                "scripts.rag.verify_rebuild.build_repository_index",
                side_effect=self._fake_builder(True),
            ):
                result = verify_independent_rebuilds(
                    config_path="unused.json",
                    repository_id="fixture-repo",
                    repository_root="unused",
                    output_dir=output,
                )
            self.assertTrue(result["deterministic"])
            self.assertTrue((output / "index_validation.json").is_file())
            self.assertFalse(output.with_name("index.rebuild-work").exists())

    def test_invalid_matching_rebuilds_preserve_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rag-rebuild-invalid-") as raw:
            output = Path(raw) / "index"
            with mock.patch(
                "scripts.rag.verify_rebuild.build_repository_index",
                side_effect=self._fake_builder(False),
            ):
                with self.assertRaises(IndexValidationError):
                    verify_independent_rebuilds(
                        config_path="unused.json",
                        repository_id="fixture-repo",
                        repository_root="unused",
                        output_dir=output,
                    )
            work = output.with_name("index.rebuild-work")
            self.assertTrue((work / "build-a" / "index_validation.json").is_file())
            self.assertTrue((work / "build-b" / "index_validation.json").is_file())
            self.assertFalse(output.exists())


@unittest.skipUnless(TREE_SITTER_AVAILABLE, "fixed Tree-sitter environment is not installed")
class SymbolIndexFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rag-fixture-test-")
        self.root = Path(self.temp.name)
        self.repository = self.root / "repository"
        self.commit = _initialize_repository(
            self.repository,
            ["symbols.hpp", "symbols.cpp", "oversized.cpp", "crlf.hpp"],
        )
        self.config = self.root / "retrieval_fixture.json"
        _write_fixture_config(self.config, self.commit)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_symbol_metadata_and_byte_slices(self) -> None:
        output = self.root / "index"
        result = build_repository_index(
            config_path=self.config,
            repository_id="fixture-repo",
            repository_root=self.repository,
            output_dir=output,
            strict=True,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.diagnostics, ())

        chunks = _read_jsonl(output / "chunks.jsonl")
        symbols = _read_jsonl(output / "symbol_index.jsonl")
        by_pair = {(item["canonical_name"], item["kind"]) for item in chunks}
        for expected in EXPECTED["required_symbols"]:
            self.assertIn(
                (expected["canonical_name"], expected["kind"]),
                by_pair,
            )

        self.assertTrue(
            any(
                item["canonical_name"] == EXPECTED["doxygen_symbol"]
                and item["doxygen_attached"]
                for item in chunks
            )
        )
        self.assertTrue(
            all(
                item["chunk_method"] == EXPECTED["macro_chunk_method"]
                for item in chunks
                if item["kind"] == "macro_definition"
            )
        )
        self.assertGreaterEqual(
            sum(
                item["canonical_name"] == "fixture::overloaded"
                and item["kind"] == "function_definition"
                for item in chunks
            ),
            EXPECTED["minimum_overload_count"],
        )
        self.assertTrue(
            any(
                item["canonical_name"] == EXPECTED["oversized_symbol"]
                and item["oversized_unsplit"]
                for item in chunks
            )
        )

        widget = next(
            item
            for item in chunks
            if item["canonical_name"] == "fixture::Widget"
            and item["kind"] == "class_interface"
        )
        self.assertIn("Base", widget["base_symbols"])
        nested = next(
            item
            for item in chunks
            if item["canonical_name"] == "fixture::Widget::Nested"
        )
        self.assertTrue(nested["is_nested_type"])

        self.assertTrue(any(item["kind"].startswith("constructor_") for item in chunks))
        self.assertTrue(any(item["kind"].startswith("destructor_") for item in chunks))
        self.assertTrue(any(item["kind"].startswith("operator_") for item in chunks))
        self.assertTrue(any(item["cv_qualifier"] == "const" for item in symbols))
        self.assertTrue(any(item["noexcept"] for item in symbols))
        self.assertTrue(any(item["template_arity"] > 0 for item in symbols))

        self.assertIn(b"\r\n", (self.repository / "crlf.hpp").read_bytes())

        for chunk in chunks:
            raw = (self.repository / str(chunk["path"])).read_bytes()
            start = int(chunk["start_byte"])
            end = int(chunk["end_byte"])
            encoded_content = str(chunk["content"]).encode("utf-8")
            self.assertEqual(raw[start:end], encoded_content)
            self.assertEqual(
                hashlib.sha256(encoded_content).hexdigest(),
                chunk["content_sha256"],
            )

        self.assertEqual(
            symbols,
            sorted(
                symbols,
                key=lambda item: (
                    item["canonical_name"],
                    item["index_role"],
                    item["path"],
                    item["start_line"],
                    item["chunk_id"],
                ),
            ),
        )

    def test_independent_rebuild_hashes_match(self) -> None:
        output = self.root / "verified-index"
        verification = verify_independent_rebuilds(
            config_path=self.config,
            repository_id="fixture-repo",
            repository_root=self.repository,
            output_dir=output,
        )
        self.assertTrue(verification["deterministic"])
        self.assertEqual(verification["independent_build_count"], 2)
        for comparison in verification["build_hash_comparison"].values():
            self.assertTrue(comparison["match"])
            self.assertEqual(
                comparison["build_a_sha256"], comparison["build_b_sha256"]
            )


@unittest.skipUnless(TREE_SITTER_AVAILABLE, "fixed Tree-sitter environment is not installed")
class ParseErrorFixtureTests(unittest.TestCase):
    def test_parse_error_is_recorded_and_strict_build_stops(self) -> None:
        with tempfile.TemporaryDirectory(prefix="rag-parse-error-test-") as raw:
            root = Path(raw)
            repository = root / "repository"
            commit = _initialize_repository(repository, ["parse_error.cpp"])
            config = root / "retrieval_fixture.json"
            _write_fixture_config(config, commit)

            diagnostic_output = root / "diagnostic-index"
            result = build_repository_index(
                config_path=config,
                repository_id="fixture-repo",
                repository_root=repository,
                output_dir=diagnostic_output,
                strict=False,
            )
            self.assertFalse(result.valid)
            self.assertGreater(len(result.diagnostics), 0)
            validation = json.loads(
                (diagnostic_output / "index_validation.json").read_text(encoding="utf-8")
            )
            self.assertGreater(validation["parser_error_count"], 0)
            self.assertEqual(validation["status"], "fail")

            with self.assertRaises(IndexValidationError):
                build_repository_index(
                    config_path=config,
                    repository_id="fixture-repo",
                    repository_root=repository,
                    output_dir=root / "strict-index",
                    strict=True,
                )


if __name__ == "__main__":
    unittest.main()
