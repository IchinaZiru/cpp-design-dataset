from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = PACKAGE_ROOT / "scripts" / "roundtrip_v2" / "generate_formal_configs_v2.py"
VALIDATOR_PATH = PACKAGE_ROOT / "scripts" / "roundtrip_v2" / "validate_formal_pairs_v2.py"
BATCH_PATH = PACKAGE_ROOT / "scripts" / "roundtrip_v2" / "run_formal_batch_v2.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FormalGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generator = load_module(GENERATOR_PATH, "formal_generator")
        cls.validator = load_module(VALIDATOR_PATH, "formal_validator")
        cls.batch = load_module(BATCH_PATH, "formal_batch")

    def make_legacy(self, target_id: str, granularity: str) -> dict:
        repository_id = "ini-cpp" if target_id.startswith("ini-cpp") else "repo"
        source_files = ["include/example.h"]
        locator = {"kind": "class", "symbol": "Example"}
        if granularity == "module_files":
            source_files = ["include/example.h", "src/example.cpp"]
            locator = {}
        return {
            "schema_version": "3.0",
            "enabled": False,
            "target_id": target_id,
            "experiment_id": f"legacy/{target_id}",
            "run_id": f"legacy-{target_id}",
            "repository_id": repository_id,
            "repository_path": f"repos/{repository_id}",
            "repository_commit": "a" * 40,
            "target_name": "Example",
            "adoption_status": "採用",
            "granularity": granularity,
            "source_files": source_files,
            "locator": locator,
            "model": {
                "name": "qwen2.5-coder:32b",
                "temperature": 0,
                "seed": 42,
                "num_ctx": 8192,
                "num_predict": 2048,
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "stream": False,
                "generations": 1,
                "retry": False,
                "automatic_repair": False,
            },
            "evaluation": {
                "docker_image": "image",
                "docker_image_id": "sha256:" + "b" * 64,
                "configure_command": "configure",
                "build_command": "build",
                "direct_test_command": "direct",
                "full_test_command": "full",
                "full_test_kind": "gtest",
                "expected_direct_tests": 1,
                "expected_full_tests": 2,
            },
            "_formal_source_config": "source.json",
        }

    def test_inventory_is_exactly_17(self) -> None:
        self.assertEqual(len(self.generator.FORMAL_TARGETS), 17)
        self.assertEqual(len(set(self.generator.FORMAL_TARGET_IDS)), 17)
        self.assertEqual(
            self.generator.FORMAL_TARGET_IDS,
            self.validator.EXPECTED_TARGET_IDS,
        )

    def test_pair_diff_is_only_condition_specific(self) -> None:
        legacy = self.make_legacy("echo-web-server-buffer", "module_files")
        non_rag = self.generator.make_condition_config(
            legacy,
            target_id="echo-web-server-buffer",
            granularity="module_files",
            condition_key="non_rag",
            sequence=2,
        )
        rag = self.generator.make_condition_config(
            legacy,
            target_id="echo-web-server-buffer",
            granularity="module_files",
            condition_key="rag",
            sequence=2,
        )
        self.assertEqual(
            self.validator.normalized_pair(non_rag),
            self.validator.normalized_pair(rag),
        )
        self.assertFalse(non_rag["design_knowledge"]["enabled"])
        self.assertTrue(rag["design_knowledge"]["enabled"])
        self.assertEqual(rag["design_knowledge"]["context_file"], "knowledge/detailed-design/general-v2.md")
        self.assertEqual(rag["design_knowledge"]["instruction_mode"], "required_additional_artifacts")

    def test_echo_class_legacy_can_be_promoted_to_module_files(self) -> None:
        legacy = self.make_legacy("echo-web-server-block-deque", "class_span")
        legacy["source_files"] = ["include/containers/block_deque.h"]
        config = self.generator.make_condition_config(
            legacy,
            target_id="echo-web-server-block-deque",
            granularity="module_files",
            condition_key="non_rag",
            sequence=1,
        )
        self.assertEqual(config["granularity"], "module_files")
        self.assertEqual(config["locator"], {})
        self.assertNotIn("target_source_file", config)

    def test_function_config_preserves_signature_locator(self) -> None:
        legacy = self.make_legacy("ini-cpp-iniwriter", "function")
        legacy["source_files"] = ["ini/ini.h"]
        legacy["locator"] = {
            "kind": "function",
            "symbol": "INIWriter::write",
            "signature_regex": self.generator.INIWRITER_SIGNATURE_REGEX,
        }
        config = self.generator.make_condition_config(
            legacy,
            target_id="ini-cpp-iniwriter",
            granularity="function",
            condition_key="rag",
            sequence=12,
        )
        self.assertEqual(config["target_source_file"], "ini/ini.h")
        self.assertEqual(config["locator"]["kind"], "function")
        self.assertIn("signature_regex", config["locator"])

    def test_model_settings_are_frozen_for_pair(self) -> None:
        legacy = self.make_legacy("riscv-simulator-register", "class_span")
        config = self.generator.make_condition_config(
            legacy,
            target_id="riscv-simulator-register",
            granularity="class_span",
            condition_key="non_rag",
            sequence=16,
        )
        model = config["model"]
        self.assertEqual(model["num_ctx"], 16384)
        self.assertEqual(model["num_predict"], 8192)
        self.assertEqual(model["generations"], 1)
        self.assertFalse(model["retry"])
        self.assertFalse(model["automatic_repair"])

    def test_terminal_artifact_loader_rejects_incomplete_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(RuntimeError):
                self.batch.result_artifact(root)

    def test_terminal_artifact_loader_accepts_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "evaluation" / "evaluation_manifest.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"overall_pass": True}), encoding="utf-8")
            kind, loaded_path, value = self.batch.result_artifact(root)
            self.assertEqual(kind, "evaluation")
            self.assertEqual(loaded_path, path)
            self.assertTrue(value["overall_pass"])


if __name__ == "__main__":
    unittest.main()
