from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.rag.canonical import canonical_json_bytes, sha256_bytes
from scripts.rag.run_yaml_cpp_design_generation import (
    DESIGN_FILE,
    FAILURE_FILE,
    PLAN_FILE,
    PROMPT_FILE,
    REQUEST_FILE,
    DesignGenerationError,
    FrozenInputs,
    RepositoryState,
    _verify_retrieval_and_context,
    build_request_payload,
    compose_design_prompt,
    ensure_execution_not_attempted,
    load_config,
    run_execute_once,
    run_plan_only,
    verify_source,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    ROOT / "configs" / "rag" / "pilot" / "yaml_cpp_yaml_node_design_generation_v1.json"
)
YAML_CPP_ROOT = (ROOT / ".." / "cpp-rag-pilot-yaml-cpp").resolve()


def _frozen_inputs(source: str = "class Node {};", context: str = "helper context") -> FrozenInputs:
    state = RepositoryState(head="a" * 40, branch="agent/rag-protocol-v0-9", clean=True)
    return FrozenInputs(
        target_source=source,
        retrieved_context=context,
        source_file_sha256=sha256_bytes(source.encode("utf-8")),
        source_range_sha256=sha256_bytes(source.encode("utf-8")),
        context_sha256=sha256_bytes(context.encode("utf-8")),
        selection_sha256="b" * 64,
        retrieval_manifest_sha256="c" * 64,
        project_state=state,
        pilot_state=RepositoryState(head="d" * 40, branch=None, clean=True),
    )


class PromptCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_prompt_has_separate_frozen_source_and_context_sections(self) -> None:
        source = "class Node {\n public:\n  bool ok() const;\n};"
        context = "path: src/node.cpp\nrole: direct_dependency\nvoid helper();"
        prompt = compose_design_prompt(self.config, source, context)
        source_heading = self.config["prompt"]["target_source_heading"]
        context_heading = self.config["prompt"]["retrieved_context_heading"]

        self.assertIn(f"# {source_heading}\n{source}\n# END {source_heading}", prompt)
        self.assertIn(f"# {context_heading}\n{context}\n# END {context_heading}", prompt)
        self.assertLess(prompt.index(source_heading), prompt.index(context_heading))
        self.assertIn(source, prompt)
        self.assertIn(context, prompt)

    def test_request_contains_exact_prompt_and_frozen_generation_options(self) -> None:
        prompt = compose_design_prompt(self.config, "source", "context")
        payload = build_request_payload(self.config, prompt)
        self.assertEqual(payload["prompt"], prompt)
        self.assertEqual(payload["model"], "qwen2.5-coder:32b")
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual(payload["options"]["seed"], 42)

    def test_future_regeneration_direct_inputs_exclude_raw_rag_evidence(self) -> None:
        policy = self.config["downstream_code_regeneration_policy"]
        allowed = set(policy["allowed_direct_inputs"])
        forbidden = set(policy["forbidden_direct_inputs"])
        self.assertFalse(policy["implemented_by_this_runner"])
        self.assertTrue(
            {
                "frozen_target_source",
                "frozen_retrieved_repository_context",
                "design_generation_prompt",
                "design_generation_request",
            }.issubset(forbidden)
        )
        self.assertTrue(allowed.isdisjoint(forbidden))


class FrozenHashTests(unittest.TestCase):
    def test_source_crlf_normalization_range_and_hash_are_verified(self) -> None:
        normalized = b"one\nTARGET\nthree\n"
        source_range = b"TARGET"
        config = {
            "target": {
                "path": "include/node.h",
                "start_byte": 4,
                "end_byte": 10,
                "start_line": 2,
                "end_line": 2,
                "normalized_source_sha256": sha256_bytes(normalized),
                "source_range_sha256": sha256_bytes(source_range),
            }
        }
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            path = root / "include" / "node.h"
            path.parent.mkdir(parents=True)
            path.write_bytes(normalized.replace(b"\n", b"\r\n"))
            text, source_hash, range_hash = verify_source(config, root)
            self.assertEqual(text, "TARGET")
            self.assertEqual(source_hash, sha256_bytes(normalized))
            self.assertEqual(range_hash, sha256_bytes(source_range))

            bad_config = copy.deepcopy(config)
            bad_config["target"]["source_range_sha256"] = "0" * 64
            with self.assertRaisesRegex(DesignGenerationError, "range hash mismatch"):
                verify_source(bad_config, root)

    def test_real_frozen_context_hash_is_verified_and_mismatch_refused(self) -> None:
        config = load_config(CONFIG_PATH)
        context, context_hash, _manifest_hash = _verify_retrieval_and_context(
            config, ROOT
        )
        self.assertIn("yaml-cpp-yaml-node-d2929956c2cd", context)
        self.assertEqual(
            context_hash,
            "9d4345e151390ae65df9d915046cdbfada1de1191c9278365c055b0bcff75dd9",
        )

        bad_config = copy.deepcopy(config)
        bad_config["frozen_artifacts"]["context_sha256"] = "0" * 64
        with self.assertRaisesRegex(DesignGenerationError, "context hash mismatch"):
            _verify_retrieval_and_context(bad_config, ROOT)


class PlanAndOneShotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def _temporary_config(self, root: Path) -> tuple[dict[str, object], Path]:
        config = copy.deepcopy(self.config)
        config["output_path"] = "run-output"
        config_path = root / "config.json"
        config_path.write_bytes(canonical_json_bytes(config))
        return config, config_path

    def test_plan_only_stores_exact_prompt_and_request_with_zero_calls(self) -> None:
        frozen = _frozen_inputs()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config, config_path = self._temporary_config(root)
            with (
                mock.patch(
                    "scripts.rag.run_yaml_cpp_design_generation.validate_frozen_inputs",
                    return_value=frozen,
                ),
                mock.patch(
                    "scripts.rag.run_yaml_cpp_design_generation.contact_generation_server"
                ) as contact,
            ):
                manifest = run_plan_only(config, config_path, root, root / "yaml-cpp")

            contact.assert_not_called()
            run_root = root / "run-output"
            prompt_bytes = (run_root / "plan" / PROMPT_FILE).read_bytes()
            request_bytes = (run_root / "plan" / REQUEST_FILE).read_bytes()
            saved_manifest = json.loads(
                (run_root / "plan" / PLAN_FILE).read_text(encoding="utf-8")
            )
            expected_prompt = compose_design_prompt(
                config, frozen.target_source, frozen.retrieved_context
            )
            self.assertEqual(prompt_bytes, expected_prompt.encode("utf-8"))
            self.assertEqual(
                request_bytes,
                canonical_json_bytes(build_request_payload(config, expected_prompt)),
            )
            self.assertFalse(manifest["llm_called"])
            self.assertEqual(manifest["llm_call_count"], 0)
            self.assertFalse(manifest["generation_server_contacted"])
            self.assertFalse(manifest["design_document_generated"])
            self.assertEqual(saved_manifest, manifest)
            self.assertFalse((run_root / DESIGN_FILE).exists())

    def test_attempt_or_result_marker_blocks_execution(self) -> None:
        policy = self.config["one_shot_policy"]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name in (policy["attempt_marker"], policy["result_marker"]):
                with self.subTest(name=name):
                    marker = root / name
                    marker.write_text("{}\n", encoding="utf-8")
                    with self.assertRaisesRegex(
                        DesignGenerationError, "already attempted or complete"
                    ):
                        ensure_execution_not_attempted(self.config, root)
                    marker.unlink()

    def test_failed_request_preserves_evidence_and_cannot_retry(self) -> None:
        frozen = _frozen_inputs()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config, config_path = self._temporary_config(root)
            with mock.patch(
                "scripts.rag.run_yaml_cpp_design_generation.validate_frozen_inputs",
                return_value=frozen,
            ):
                run_plan_only(config, config_path, root, root / "yaml-cpp")
                with mock.patch(
                    "scripts.rag.run_yaml_cpp_design_generation.contact_generation_server",
                    side_effect=OSError("offline test failure"),
                ) as contact:
                    with self.assertRaisesRegex(OSError, "offline test failure"):
                        run_execute_once(config, root, root / "yaml-cpp")
                    with self.assertRaisesRegex(
                        DesignGenerationError, "already attempted or complete"
                    ):
                        run_execute_once(config, root, root / "yaml-cpp")

            self.assertEqual(contact.call_count, 1)
            run_root = root / "run-output"
            self.assertTrue(
                (run_root / config["one_shot_policy"]["attempt_marker"]).is_file()
            )
            self.assertTrue((run_root / FAILURE_FILE).is_file())
            failure = json.loads(
                (run_root / FAILURE_FILE).read_text(encoding="utf-8")
            )
            self.assertTrue(failure["llm_called"])
            self.assertEqual(failure["llm_call_count"], 1)
            self.assertFalse(failure["retry_performed"])


if __name__ == "__main__":
    unittest.main()
