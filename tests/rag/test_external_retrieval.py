from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.rag.artifacts import LoadedQuery
from scripts.rag.build_external_retrieval import (
    build_and_verify_external_retrieval,
)
from scripts.rag.canonical import write_canonical_json
from scripts.rag.external_retrieval import (
    ExternalRetrievalConfig,
    ExternalRetrievalError,
    bm25_scores_scaled,
    classify_usage,
    dependency_relation,
    lexical_token_count,
    select_context_candidates,
    tokenize_cpp,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "rag" / "pilot" / "yaml_cpp_retrieval_pipeline_v1.json"


def _query() -> LoadedQuery:
    return LoadedQuery(
        path=Path("query.json"),
        document={},
        target_id="target-1",
        repository_id="repo",
        repository_commit="a" * 40,
        granularity="function",
        source_ranges=(
            {
                "end_byte": 20,
                "normalized_source_sha256": "b" * 64,
                "path": "src/target.cpp",
                "start_byte": 10,
            },
        ),
        records=(),
        includes=(),
        sha256="c" * 64,
    )


def _config(*, budget: int = 1000) -> ExternalRetrievalConfig:
    return ExternalRetrievalConfig(
        path=Path("retrieval.json"),
        sha256="d" * 64,
        raw={
            "context": {
                "budget_tokens": budget,
                "format": "combined-path-role-v1",
                "token_counter_version": "cpp-lexical-token-count-v1",
            },
            "selection": {
                "fixed_quotas": {"0": 1, "1": 1, "2": 1, "3": 1},
                "retrieval_top_k": 4,
            },
        },
    )


def _candidate(chunk_id: str, tier: int, rank: int) -> dict[str, object]:
    return {
        "bm25_score_scaled": 0,
        "candidate_rank": rank,
        "canonical_name": f"repo::{chunk_id}",
        "chunk_id": chunk_id,
        "content_sha256": str(rank) * 64,
        "direct_relation": tier == 1,
        "directory_distance": 0,
        "eligible": True,
        "eligible_rank": rank,
        "end_byte": rank * 10 + 5,
        "end_line": rank + 1,
        "exact_match_rank": 0,
        "exclusion_reasons": [],
        "kind": "function_definition",
        "original_case_match": True,
        "overlap_evidence": [],
        "parent_symbol": None,
        "path": f"src/{chunk_id}.cpp",
        "repository_commit": "a" * 40,
        "repository_id": "repo",
        "retrieval_evidence": [],
        "retrieval_version": "test-v1",
        "selection_status": "not_selected",
        "signature": f"void {chunk_id}()",
        "source_sha256": "e" * 64,
        "start_byte": rank * 10,
        "start_line": rank,
        "target_id": "target-1",
        "tier": tier,
        "usage_classification": "none",
        "usage_classification_rank": 9,
    }


class RetrievalPrimitiveTests(unittest.TestCase):
    def test_tokenizer_preserves_case_and_splits_identifiers(self) -> None:
        tokens = tokenize_cpp("src/YAMLNode.cpp YAML::LoadFile")
        self.assertIn("YAMLNode", tokens)
        self.assertIn("yamlnode", tokens)
        self.assertIn("YAML", tokens)
        self.assertIn("Node", tokens)
        self.assertIn("Load", tokens)
        self.assertIn("File", tokens)

    def test_bm25_scores_are_integer_scaled_and_rank_relevant_document(self) -> None:
        scores = bm25_scores_scaled(
            [tokenize_cpp("LoadFile Parser"), tokenize_cpp("Emitter Stream")],
            tokenize_cpp("LoadFile"),
            k1_scaled=1_200_000,
            b_scaled=750_000,
            score_scale=1_000_000,
        )
        self.assertGreater(scores[0], scores[1])
        self.assertTrue(all(isinstance(item, int) for item in scores))

    def test_usage_classification_priority(self) -> None:
        self.assertEqual(classify_usage("LoadFile(path);", ["YAML::LoadFile"]), "direct_call_site")
        self.assertEqual(classify_usage("auto p = &LoadFile;", ["YAML::LoadFile"]), "symbol_reference")
        self.assertEqual(classify_usage("// use LoadFile here", ["YAML::LoadFile"]), "explicit_comment_reference")

    def test_direct_dependency_relations(self) -> None:
        dependency = {
            "canonical_name": "YAML::Node",
            "parent_symbol": None,
            "short_name": "Node",
        }
        source = {
            "base_symbols": [],
            "canonical_name": "YAML::Load",
            "content": "Node Load(const Node& input);",
            "kind": "function_definition",
            "signature": "Node Load(const Node& input)",
        }
        self.assertEqual(dependency_relation(source, dependency), "parameter_type")

    def test_fixed_quotas_and_budget_are_applied_in_rank_order(self) -> None:
        candidates = [
            _candidate("tier0-first", 0, 1),
            _candidate("tier0-second", 0, 2),
            _candidate("tier1", 1, 3),
            _candidate("tier2", 2, 4),
            _candidate("tier3", 3, 5),
        ]
        chunks = {
            str(item["chunk_id"]): {
                "content": f"void {item['chunk_id']}() {{}}",
            }
            for item in candidates
        }
        selected, context, count = select_context_candidates(
            candidates=candidates,
            chunks_by_id=chunks,
            query=_query(),
            config=_config(),
        )
        self.assertEqual(
            [item["chunk_id"] for item in selected],
            ["tier0-first", "tier1", "tier2", "tier3"],
        )
        self.assertNotIn("tier0-second", context)
        self.assertEqual(count, lexical_token_count(context))

    def test_frozen_real_config_and_dependency_hashes_load(self) -> None:
        config = ExternalRetrievalConfig.load(ROOT, CONFIG)
        self.assertEqual(config.raw["selection"]["retrieval_top_k"], 12)
        self.assertEqual(config.raw["context"]["budget_tokens"], 6000)


class RetrievalRebuildTests(unittest.TestCase):
    @staticmethod
    def _fake_build(**kwargs):
        output = Path(kwargs["output_root"])
        target = output / "target-1"
        target.mkdir(parents=True)
        (target / "context.txt").write_text("stable\n", encoding="utf-8", newline="\n")
        write_canonical_json(
            output / "retrieval_generation_manifest.json",
            {"status": "pass", "target_count": 1},
        )
        return {"target_count": 1}

    def test_two_matching_builds_publish_with_validation(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            temporary = Path(raw)
            output = temporary / "retrieval-v1"
            with mock.patch(
                "scripts.rag.build_external_retrieval.build_all_retrieval_artifacts",
                side_effect=self._fake_build,
            ):
                result = build_and_verify_external_retrieval(
                    project_root=ROOT,
                    config_path=CONFIG,
                    repository_root=temporary,
                    output_root=output,
                )
            validation = json.loads(
                (output / "retrieval_validation.json").read_text(encoding="utf-8")
            )
            self.assertTrue(result.deterministic)
            self.assertEqual(validation["independent_build_count"], 2)
            self.assertTrue(
                all(item["match"] for item in validation["build_hash_comparison"].values())
            )
            self.assertFalse(output.with_name("retrieval-v1.rebuild-work").exists())

    def test_hash_mismatch_preserves_both_builds(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            temporary = Path(raw)
            output = temporary / "retrieval-v1"
            calls = 0

            def changing_build(**kwargs):
                nonlocal calls
                calls += 1
                result = self._fake_build(**kwargs)
                (Path(kwargs["output_root"]) / "target-1" / "context.txt").write_text(
                    f"build-{calls}\n", encoding="utf-8", newline="\n"
                )
                return result

            with mock.patch(
                "scripts.rag.build_external_retrieval.build_all_retrieval_artifacts",
                side_effect=changing_build,
            ):
                with self.assertRaisesRegex(ExternalRetrievalError, "hash mismatch"):
                    build_and_verify_external_retrieval(
                        project_root=ROOT,
                        config_path=CONFIG,
                        repository_root=temporary,
                        output_root=output,
                    )
            evidence = output.with_name("retrieval-v1.rebuild-work")
            self.assertTrue((evidence / "build-a" / "target-1" / "context.txt").is_file())
            self.assertTrue((evidence / "build-b" / "target-1" / "context.txt").is_file())


if __name__ == "__main__":
    unittest.main()
