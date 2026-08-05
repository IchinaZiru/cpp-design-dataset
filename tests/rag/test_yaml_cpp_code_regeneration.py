from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.rag.canonical import sha256_bytes
from scripts.rag.run_yaml_cpp_code_regeneration import (
    EVALUATION_PLAN_FILE,
    PLAN_FILE,
    PROMPT_FILE,
    REQUEST_FILE,
    SCAFFOLD_FILE,
    CodeRegenerationError,
    FrozenInputs,
    RepositoryState,
    SourceReplacementTransaction,
    build_fixed_scaffold,
    compose_code_regeneration_prompt,
    ensure_execution_not_attempted,
    extract_verbatim_section,
    load_config,
    raw_offsets_for_normalized_range,
    run_execute_once,
    run_plan_only,
    validate_generated_class_span,
    verify_design_evidence,
    verify_frozen_selection_and_direct_tests,
    verify_prompt_isolation,
    verify_target_source,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = (
    ROOT / "configs" / "rag" / "pilot" / "yaml_cpp_yaml_node_code_regeneration_v1.json"
)
YAML_CPP_ROOT = (ROOT / ".." / "cpp-rag-pilot-yaml-cpp").resolve()


def _real_frozen(config: dict[str, object]) -> FrozenInputs:
    design, design_hash = verify_design_evidence(config, ROOT)
    raw, raw_hash, normalized_hash, target_source = verify_target_source(
        config, YAML_CPP_ROOT
    )
    return FrozenInputs(
        design_document=design,
        design_document_sha256=design_hash,
        original_source_bytes=raw,
        original_source_sha256=raw_hash,
        normalized_source_sha256=normalized_hash,
        target_source=target_source,
        target_source_sha256=sha256_bytes(target_source.encode("utf-8")),
        project_state=RepositoryState(
            head="a" * 40,
            branch="agent/rag-protocol-v0-9",
            clean=True,
        ),
        pilot_state=RepositoryState(head="b" * 40, branch=None, clean=True),
    )


class FrozenEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_design_document_hash_and_completed_one_call_are_validated(self) -> None:
        design, design_hash = verify_design_evidence(self.config, ROOT)
        self.assertTrue(design.strip())
        self.assertEqual(
            design_hash,
            "692d4328639916f425137b9254b8ee21db2a9d00b34d7f95cffbf330f1e3f796",
        )

        bad = copy.deepcopy(self.config)
        bad["design_evidence"]["design_document_sha256"] = "0" * 64
        with self.assertRaisesRegex(CodeRegenerationError, "design document SHA-256"):
            verify_design_evidence(bad, ROOT)

    def test_fixed_scaffold_is_deterministic_and_matches_frozen_hash(self) -> None:
        _raw, _raw_hash, _normalized_hash, target_source = verify_target_source(
            self.config, YAML_CPP_ROOT
        )
        first = build_fixed_scaffold(self.config, ROOT, target_source)
        second = build_fixed_scaffold(self.config, ROOT, target_source)
        self.assertEqual(first, second)
        self.assertEqual(
            sha256_bytes(first.encode("utf-8")),
            "78dc57fb4f8b5a6d909236426d0a61ac2811aec12759836640d557f33af2759c",
        )
        self.assertNotIn("return Type()", first)
        self.assertTrue(first.startswith("class YAML_CPP_API Node {"))
        self.assertTrue(first.endswith("}\n"))

    def test_direct_test_filter_is_derived_from_frozen_selection_evidence(self) -> None:
        selection_hash = verify_frozen_selection_and_direct_tests(
            self.config, ROOT, YAML_CPP_ROOT
        )
        self.assertEqual(
            selection_hash,
            "660eafc27072e4d04df321abe2c509ce063c61d154e625c214016cdbf3ef4170",
        )


class PromptIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)
        self.frozen = _real_frozen(self.config)
        self.scaffold = build_fixed_scaffold(
            self.config, ROOT, self.frozen.target_source
        )
        self.prompt = compose_code_regeneration_prompt(
            self.config, self.frozen.design_document, self.scaffold
        )

    def test_prompt_sections_are_exactly_design_and_scaffold(self) -> None:
        verify_prompt_isolation(
            self.config,
            self.prompt,
            self.frozen.design_document,
            self.scaffold,
            self.frozen.target_source,
        )
        prompt_config = self.config["prompt"]
        design_section = extract_verbatim_section(
            self.prompt, prompt_config["design_heading"]
        )
        scaffold_section = extract_verbatim_section(
            self.prompt, prompt_config["scaffold_heading"]
        )
        self.assertEqual(
            design_section,
            self.frozen.design_document
            + ("" if self.frozen.design_document.endswith("\n") else "\n"),
        )
        self.assertEqual(scaffold_section, self.scaffold)

    def test_forbidden_repository_and_rag_artifacts_are_not_embedded(self) -> None:
        design_root = ROOT / self.config["design_evidence"]["root_path"]
        forbidden_paths = [
            ROOT
            / "rag/retrieval/external-pilot/yaml-cpp/retrieval-v2/"
            "yaml-cpp-yaml-node-d2929956c2cd/context.txt",
            ROOT
            / "rag/retrieval/external-pilot/yaml-cpp/retrieval-v2/"
            "yaml-cpp-yaml-node-d2929956c2cd/selected_chunks.jsonl",
            design_root / "plan" / "design_prompt.txt",
            design_root / "plan" / "ollama_request.json",
            YAML_CPP_ROOT / "include/yaml-cpp/node/impl.h",
        ]
        self.assertNotIn(self.frozen.target_source, self.prompt)
        for path in forbidden_paths:
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertNotIn(content, self.prompt)

        forbidden = set(self.config["prompt_input_policy"]["forbidden_inputs"])
        self.assertEqual(len(forbidden), 7)
        self.assertIn("design_document_audit_findings", forbidden)
        self.assertIn(
            "yaml_cpp_implementation_files_including_node_impl_h", forbidden
        )


class ReplacementAndRestorationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_normalized_range_maps_to_only_the_crlf_target_bytes(self) -> None:
        raw = b"prefix\r\nTARGET\r\nsuffix\r\n"
        normalized = raw.replace(b"\r\n", b"\n")
        start = normalized.index(b"TARGET")
        end = start + len(b"TARGET")
        raw_start, raw_end = raw_offsets_for_normalized_range(raw, start, end)
        self.assertEqual(raw[raw_start:raw_end], b"TARGET")
        replaced = raw[:raw_start] + b"NEW" + raw[raw_end:]
        self.assertEqual(replaced[:raw_start], raw[:raw_start])
        self.assertEqual(replaced[raw_start + 3 :], raw[raw_end:])

    def test_generated_replacement_must_be_exact_class_span_without_semicolon(self) -> None:
        valid = "class YAML_CPP_API Node {\n public:\n  Node();\n}"
        self.assertEqual(
            validate_generated_class_span(self.config, valid), valid.encode("utf-8")
        )
        with self.assertRaisesRegex(CodeRegenerationError, "exclude the semicolon"):
            validate_generated_class_span(self.config, valid + ";")
        with self.assertRaisesRegex(CodeRegenerationError, "content after"):
            validate_generated_class_span(self.config, valid + "\nextra")

    def test_source_transaction_restores_exact_bytes_after_failure(self) -> None:
        original = b"prefix\r\nTARGET\r\nsuffix\r\n"
        normalized = original.replace(b"\r\n", b"\n")
        start = normalized.index(b"TARGET")
        end = start + len(b"TARGET")
        with tempfile.TemporaryDirectory() as raw_directory:
            path = Path(raw_directory) / "node.h"
            path.write_bytes(original)
            transaction = SourceReplacementTransaction(
                source_path=path,
                original_bytes=original,
                start=start,
                end=end,
                replacement_bytes=b"GENERATED",
                expected_original_sha256=sha256_bytes(original),
            )
            with self.assertRaisesRegex(RuntimeError, "simulated evaluation failure"):
                with transaction:
                    self.assertIn(b"GENERATED", path.read_bytes())
                    raise RuntimeError("simulated evaluation failure")
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(transaction.replaced)
            self.assertTrue(transaction.restored)
            self.assertEqual(transaction.restored_sha256, sha256_bytes(original))


class PlanAndOneShotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)
        self.frozen = _real_frozen(self.config)

    def _temporary_config(self, temporary: Path) -> dict[str, object]:
        config = copy.deepcopy(self.config)
        config["output_path"] = temporary.relative_to(ROOT).as_posix()
        return config

    def test_attempt_failure_or_result_marker_blocks_execution(self) -> None:
        policy = self.config["one_shot_policy"]
        with tempfile.TemporaryDirectory() as raw:
            run_root = Path(raw)
            for field in ("attempt_marker", "failure_marker", "result_marker"):
                marker = run_root / policy[field]
                with self.subTest(field=field):
                    marker.write_text("{}\n", encoding="utf-8")
                    with self.assertRaisesRegex(
                        CodeRegenerationError,
                        "already attempted, failed, or complete",
                    ):
                        ensure_execution_not_attempted(self.config, run_root)
                    marker.unlink()

    def test_plan_only_writes_five_artifacts_and_makes_zero_calls(self) -> None:
        source_path = YAML_CPP_ROOT / self.config["target"]["path"]
        source_before = source_path.read_bytes()
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            temporary = Path(raw)
            config = self._temporary_config(temporary)
            with (
                mock.patch(
                    "scripts.rag.run_yaml_cpp_code_regeneration.validate_frozen_inputs",
                    return_value=self.frozen,
                ),
                mock.patch(
                    "scripts.rag.run_yaml_cpp_code_regeneration.contact_generation_server"
                ) as contact,
            ):
                manifest = run_plan_only(
                    config, CONFIG_PATH, ROOT, YAML_CPP_ROOT
                )
            contact.assert_not_called()
            plan_root = temporary / "plan"
            self.assertEqual(
                {path.name for path in plan_root.iterdir()},
                {
                    SCAFFOLD_FILE,
                    PROMPT_FILE,
                    REQUEST_FILE,
                    EVALUATION_PLAN_FILE,
                    PLAN_FILE,
                },
            )
            self.assertFalse(manifest["llm_called"])
            self.assertEqual(manifest["llm_call_count"], 0)
            self.assertFalse(manifest["generation_server_contacted"])
            self.assertFalse(manifest["source_replaced"])
            self.assertFalse(manifest["build_started"])
            self.assertFalse(manifest["tests_started"])
            saved = json.loads((plan_root / PLAN_FILE).read_text(encoding="utf-8"))
            self.assertEqual(saved, manifest)
        self.assertEqual(source_path.read_bytes(), source_before)

    def test_failed_mock_request_is_durable_and_never_retried(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as raw:
            temporary = Path(raw)
            config = self._temporary_config(temporary)
            with mock.patch(
                "scripts.rag.run_yaml_cpp_code_regeneration.validate_frozen_inputs",
                return_value=self.frozen,
            ):
                run_plan_only(config, CONFIG_PATH, ROOT, YAML_CPP_ROOT)
                with (
                    mock.patch(
                        "scripts.rag.run_yaml_cpp_code_regeneration._verify_docker_image"
                    ),
                    mock.patch(
                        "scripts.rag.run_yaml_cpp_code_regeneration.contact_generation_server",
                        side_effect=OSError("offline test failure"),
                    ) as contact,
                ):
                    with self.assertRaisesRegex(OSError, "offline test failure"):
                        run_execute_once(config, ROOT, YAML_CPP_ROOT)
                    with self.assertRaisesRegex(
                        CodeRegenerationError,
                        "already attempted, failed, or complete",
                    ):
                        run_execute_once(config, ROOT, YAML_CPP_ROOT)
            self.assertEqual(contact.call_count, 1)
            failure_path = temporary / config["one_shot_policy"]["failure_marker"]
            failure = json.loads(failure_path.read_text(encoding="utf-8"))
            self.assertEqual(failure["llm_call_count"], 1)
            self.assertFalse(failure["retry_performed"])
            self.assertFalse(failure["source_replaced"])


if __name__ == "__main__":
    unittest.main()
