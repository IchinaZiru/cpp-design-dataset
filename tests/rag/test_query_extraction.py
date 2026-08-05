from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from types import SimpleNamespace

from scripts.rag.canonical import canonical_json_bytes, sha256_bytes, sha256_file
from scripts.rag.build_queries import build_and_verify_queries
from scripts.rag.query_extractor import (
    QueryConfig,
    SourceRange,
    _character_span_to_bytes,
    _deduplicate,
    _record,
    SymbolCatalog,
    TargetRegistry,
    extract_queries_from_tree,
    normalize_source_bytes,
    verify_query_payload,
    write_query_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERY_CONFIG = PROJECT_ROOT / "configs" / "rag" / "query_v1.json"
TARGET_REGISTRY = PROJECT_ROOT / "configs" / "rag" / "query_targets_v1.json"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "query_symbols.cpp"
EXPECTED = json.loads(
    (Path(__file__).resolve().parent / "expected" / "queries.json").read_text(
        encoding="utf-8"
    )
)
TREE_SITTER_AVAILABLE = (
    importlib.util.find_spec("tree_sitter") is not None
    and importlib.util.find_spec("tree_sitter_cpp") is not None
)


class _EmptyRoot:
    type = "translation_unit"
    start_byte = 0
    parent = None
    named_children: tuple[object, ...] = ()
    is_error = False

    def __init__(self, data: bytes):
        self.end_byte = len(data)
        self.start_point = SimpleNamespace(row=0, column=0)
        self.end_point = SimpleNamespace(
            row=data.count(b"\n"),
            column=len(data.rsplit(b"\n", 1)[-1]),
        )


class QueryConfigTests(unittest.TestCase):
    def test_phase2_enables_only_query_extraction(self) -> None:
        config = QueryConfig.load(QUERY_CONFIG)
        stages = config.raw["stages"]
        self.assertTrue(stages["query_extraction"])
        self.assertFalse(
            any(value for key, value in stages.items() if key != "query_extraction")
        )
        self.assertFalse(config.raw["llm_used"])
        self.assertFalse(config.raw["target_specific_manual_additions"])
        self.assertTrue(
            config.raw["deduplication"]["query_id_location_independent"]
        )
        self.assertEqual(
            config.raw["dependency_candidate_priority_policy"],
            "inherit-source-query-priority",
        )
        self.assertEqual(config.raw["non_rag_baseline"]["target_count"], 17)
        self.assertEqual(config.raw["non_rag_baseline"]["pass_count"], 6)
        self.assertEqual(config.raw["non_rag_baseline"]["fail_count"], 11)
        self.assertEqual(config.raw["non_rag_baseline"]["write_policy"], "read_only")
        retrieval = PROJECT_ROOT / "configs" / "rag" / "retrieval_v1.json"
        if retrieval.is_file():
            self.assertEqual(
                config.raw["dependencies"]["retrieval_config_sha256"],
                sha256_file(retrieval),
            )
        else:
            self.assertEqual(
                config.raw["dependencies"]["retrieval_config_sha256"],
                "6723c18d1239c2ba588cc016852d3fd16a1878425bfef04f331430ba1a807fa1",
            )

    def test_registry_contains_exactly_the_frozen_17_targets(self) -> None:
        registry = TargetRegistry.load(TARGET_REGISTRY)
        self.assertEqual(len(registry.entries), 17)
        self.assertIn("ini-cpp-ini-writer", registry.entries)
        self.assertIn("echo-web-server-log", registry.entries)
        self.assertIn("riscv-simulator-registerfile", registry.entries)

    def test_registry_references_existing_frozen_inputs(self) -> None:
        registry = TargetRegistry.load(TARGET_REGISTRY)

        for target_id, entry in registry.entries.items():
            metadata = PROJECT_ROOT.joinpath(
                *str(entry["source_metadata_path"]).split("/")
            )
            self.assertTrue(
                metadata.is_file(),
                f"missing source metadata for {target_id}: {metadata}",
            )

            if entry["target_kind"] == "standard":
                frozen_config = PROJECT_ROOT.joinpath(
                    *str(entry["frozen_target_config_path"]).split("/")
                )
                self.assertTrue(
                    frozen_config.is_file(),
                    f"missing frozen target config for {target_id}: {frozen_config}",
                )


class CanonicalQueryTests(unittest.TestCase):
    def test_source_normalization_matches_frozen_design_input_rules(self) -> None:
        raw = b"\xef\xbb\xbfline1\r\nline2\rline3\n"
        self.assertEqual(normalize_source_bytes(raw), b"line1\nline2\nline3\n")

    def test_character_offsets_convert_to_utf8_byte_offsets(self) -> None:
        data = "前置き\nclass Widget {};\n".encode("utf-8")
        text = data.decode("utf-8")
        start_character = text.index("class")
        end_character = text.index("\n", start_character)
        start, end = _character_span_to_bytes(
            data, start_character, end_character
        )
        self.assertEqual(data[start:end], b"class Widget {};")

    def test_payload_hash_excludes_only_its_own_field(self) -> None:
        payload = {"query_method": "deterministic-cpp-query-v1", "queries": {}}
        payload_hash = sha256_bytes(canonical_json_bytes(payload))
        document = {**payload, "query_payload_sha256": payload_hash}
        self.assertTrue(verify_query_payload(document))
        changed = {**document, "query_method": "changed"}
        self.assertFalse(verify_query_payload(changed))

    def test_quoted_include_and_macro_fallback_are_deterministic(self) -> None:
        data = b'#include "local/project.hpp"\n#include <vector>\n#define LIMIT_VALUE 4\n'
        source = SourceRange(
            path="fixture.cpp",
            data=data,
            start_byte=0,
            end_byte=len(data),
            git_blob_sha256=sha256_bytes(data),
            normalized_source_sha256=sha256_bytes(data),
            normalized_range_sha256=sha256_bytes(data),
            locator_kind="module_file",
        )
        config = QueryConfig.load(QUERY_CONFIG)
        first, first_errors = extract_queries_from_tree(
            root=_EmptyRoot(data), source_range=source, config=config
        )
        second, second_errors = extract_queries_from_tree(
            root=_EmptyRoot(data), source_range=source, config=config
        )
        self.assertEqual(first_errors, 0)
        self.assertEqual(second_errors, 0)
        self.assertEqual(first, second)
        self.assertEqual(
            [item["text"] for item in first["includes"]],
            ["local/project.hpp"],
        )
        self.assertEqual(
            [item["text"] for item in first["constants_and_macros"]],
            ["LIMIT_VALUE"],
        )

    def test_canonical_dedup_aggregates_source_locations(self) -> None:
        first_location = {
            "path": "fixture.cpp", "start_byte": 10, "end_byte": 14,
            "start_line": 2, "end_line": 2,
            "start_column": 1, "end_column": 4,
        }
        second_location = {
            "path": "fixture.cpp", "start_byte": 30, "end_byte": 34,
            "start_line": 4, "end_line": 4,
            "start_column": 2, "end_column": 5,
        }
        first = _record(
            category="function_calls", text="Run", kind="unqualified_call",
            priority="medium", relation="call_target", location=first_location,
            qualified=False, evidence_node_type="identifier",
        )
        second = _record(
            category="function_calls", text="Run", kind="unqualified_call",
            priority="medium", relation="call_target", location=second_location,
            qualified=False, evidence_node_type="identifier",
        )
        self.assertEqual(first["query_id"], second["query_id"])
        merged = _deduplicate([second, first])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["evidence_count"], 2)
        self.assertEqual(
            [item["start_byte"] for item in merged[0]["evidence_locations"]],
            [10, 30],
        )

    def test_canonical_file_hash_matches_across_independent_writes(self) -> None:
        payload = {"query_method": "deterministic-cpp-query-v1", "queries": {}}
        document = {
            **payload,
            "query_payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
        }
        with tempfile.TemporaryDirectory(prefix="rag-query-canonical-") as raw:
            root = Path(raw)
            first = write_query_document(root / "a.json", document)
            second = write_query_document(root / "b.json", document)
            self.assertEqual(first, second)
            self.assertEqual((root / "a.json").read_bytes(), (root / "b.json").read_bytes())


class IndependentBuildTests(unittest.TestCase):
    @staticmethod
    def _document(target_id: str, marker: str = "stable") -> dict[str, object]:
        payload: dict[str, object] = {
            "artifact_schema_version": "rag-query-v1",
            "marker": marker,
            "queries": {},
            "query_method": "deterministic-cpp-query-v1",
            "target": {"target_id": target_id},
        }
        return {
            **payload,
            "query_payload_sha256": sha256_bytes(canonical_json_bytes(payload)),
        }

    def test_two_independent_builds_publish_matching_hashes(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="rag-query-build-", dir=PROJECT_ROOT
        ) as raw:
            output = Path(raw) / "query"
            with mock.patch(
                "scripts.rag.build_queries.build_query_document",
                side_effect=lambda **kwargs: self._document(kwargs["target_id"]),
            ):
                result = build_and_verify_queries(
                    project_root=PROJECT_ROOT,
                    config_path=QUERY_CONFIG,
                    target_registry_path=TARGET_REGISTRY,
                    output_root=output,
                    target_ids=["ini-cpp-inireader"],
                )
            self.assertTrue(result.deterministic)
            self.assertEqual(result.target_count, 1)
            validation = json.loads(
                (output / "ini-cpp-inireader" / "query_validation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(validation["independent_build_count"], 2)
            self.assertTrue(
                validation["build_hash_comparison"]["query.json"]["match"]
            )
            self.assertTrue(
                (output / "query_generation_manifest.json").is_file()
            )

    def test_existing_different_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="rag-query-overwrite-", dir=PROJECT_ROOT
        ) as raw:
            output = Path(raw) / "query"
            with mock.patch(
                "scripts.rag.build_queries.build_query_document",
                side_effect=lambda **kwargs: self._document(kwargs["target_id"]),
            ):
                build_and_verify_queries(
                    project_root=PROJECT_ROOT,
                    config_path=QUERY_CONFIG,
                    target_registry_path=TARGET_REGISTRY,
                    output_root=output,
                    target_ids=["ini-cpp-inireader"],
                )
            original = (
                output / "ini-cpp-inireader" / "query.json"
            ).read_bytes()
            with mock.patch(
                "scripts.rag.build_queries.build_query_document",
                side_effect=lambda **kwargs: self._document(
                    kwargs["target_id"], marker="changed"
                ),
            ):
                with self.assertRaises(Exception):
                    build_and_verify_queries(
                        project_root=PROJECT_ROOT,
                        config_path=QUERY_CONFIG,
                        target_registry_path=TARGET_REGISTRY,
                        output_root=output,
                        target_ids=["ini-cpp-inireader"],
                    )
            self.assertEqual(
                original,
                (output / "ini-cpp-inireader" / "query.json").read_bytes(),
            )
            self.assertTrue(
                output.with_name(output.name + ".rebuild-work").exists()
            )


@unittest.skipUnless(TREE_SITTER_AVAILABLE, "fixed Tree-sitter environment is not installed")
class QueryFixtureTests(unittest.TestCase):
    def test_fixture_covers_all_phase2_query_categories(self) -> None:
        from scripts.rag.config import IndexConfig
        from scripts.rag.cpp_symbols import create_cpp_parser

        index_config = IndexConfig.load(
            PROJECT_ROOT / "configs" / "rag" / "retrieval_v1.json"
        )
        parser = create_cpp_parser(index_config.parser)
        data = normalize_source_bytes(FIXTURE.read_bytes())
        source = SourceRange(
            path="query_symbols.cpp",
            data=data,
            start_byte=0,
            end_byte=len(data),
            git_blob_sha256=sha256_bytes(data),
            normalized_source_sha256=sha256_bytes(data),
            normalized_range_sha256=sha256_bytes(data),
            locator_kind="module_file",
        )
        queries, error_count = extract_queries_from_tree(
            root=parser.parse(data).root_node,
            source_range=source,
            config=QueryConfig.load(QUERY_CONFIG),
            catalog=SymbolCatalog.empty(),
        )
        self.assertEqual(error_count, 0)
        for category, required in EXPECTED["required"].items():
            actual = {item["text"] for item in queries[category]}
            for text in required:
                self.assertIn(text, actual, f"missing {category}: {text}")
        for category, excluded in EXPECTED["excluded"].items():
            actual = {item["text"] for item in queries[category]}
            for text in excluded:
                self.assertNotIn(text, actual, f"unexpected {category}: {text}")

        qualified = next(
            item for item in queries["function_calls"] if item["text"] == "qualified"
        )
        self.assertEqual(qualified["priority"], "high")
        self.assertTrue(qualified["qualified"])
        self.assertTrue(qualified["evidence_locations"])
        self.assertTrue(queries["dependency_candidates"])


if __name__ == "__main__":
    unittest.main()
