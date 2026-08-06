from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any


def _find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("no closing brace")


def _locate_class_span(text: str, symbol: str) -> tuple[int, int]:
    match = re.search(rf"\b(?:class|struct)\s+{re.escape(symbol)}\b", text)
    if match is None:
        raise ValueError(symbol)
    open_brace = text.find("{", match.end())
    close_brace = _find_matching_brace(text, open_brace)
    semicolon = text.find(";", close_brace)
    return match.start(), semicolon + 1


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _normalize_outer_fence(
    text: str,
    allowed_languages: set[str],
) -> tuple[str, dict[str, Any]]:
    match = re.fullmatch(r"\s*```([^\n]*)\n(.*)\n```\s*", text, re.DOTALL)
    if match is None:
        normalized = text
        language = None
        applied = False
    else:
        language = match.group(1).strip().lower()
        if language not in allowed_languages:
            raise RuntimeError(language)
        normalized = match.group(2)
        applied = True
    return normalized, {
        "schema_version": "1.0",
        "normalization_applied": applied,
        "normalization_type": "outer_markdown_fence" if applied else "none",
        "fence_language": language,
        "strict_format_pass": not applied,
        "raw_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "normalized_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "code_body_modified": False,
        "retry_performed": False,
        "automatic_repair_performed": False,
    }


def _load_runner() -> types.ModuleType:
    root = Path(__file__).resolve().parents[2]
    runner_path = root / "scripts" / "roundtrip_v2" / "run_target_v2.py"

    common = types.ModuleType("roundtrip_common")
    common.call_ollama = lambda payload: ({"response": ""}, 0.0)
    common.docker_image_id = lambda image: image
    common.docker_run = lambda **kwargs: {}
    common.extract_includes = lambda text: [
        line for line in text.splitlines() if line.lstrip().startswith("#include")
    ]
    common.find_matching_brace = _find_matching_brace
    common.git_output = lambda repository, *args: ""
    common.load_json = lambda path: json.loads(_read_text(path))
    common.locate_class_span = _locate_class_span
    common.parse_ctest_counts = lambda output: {"ran": 0, "passed": 0, "failed": 0}
    common.parse_gtest_counts = lambda output: {"ran": 0, "passed": 0, "failed": 0}
    common.read_text = _read_text
    common.sha256_bytes = lambda data: hashlib.sha256(data).hexdigest()
    common.sha256_file = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    common.strip_inline_callable_bodies = lambda text: "SCAFFOLD\n" + text
    common.utc_now = lambda: "2026-08-06T00:00:00+00:00"
    common.write_json = _write_json
    common.write_text = _write_text

    legacy = types.ModuleType("run_target")
    legacy.normalize_outer_markdown_fence = _normalize_outer_fence
    legacy.ollama_options = lambda config: {}

    previous_common = sys.modules.get("roundtrip_common")
    previous_legacy = sys.modules.get("run_target")
    sys.modules["roundtrip_common"] = common
    sys.modules["run_target"] = legacy
    try:
        spec = importlib.util.spec_from_file_location("run_target_v2_tested", runner_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load runner")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous_common is None:
            sys.modules.pop("roundtrip_common", None)
        else:
            sys.modules["roundtrip_common"] = previous_common
        if previous_legacy is None:
            sys.modules.pop("run_target", None)
        else:
            sys.modules["run_target"] = previous_legacy


RUNNER = _load_runner()


def _evaluation() -> dict[str, Any]:
    return {
        "docker_image": "image",
        "docker_image_id": "sha256:image",
        "configure_command": "configure",
        "build_command": "build",
        "direct_test_command": "direct",
        "full_test_command": "full",
        "full_test_kind": "gtest",
        "expected_direct_tests": 1,
        "expected_full_tests": 2,
    }


def _model() -> dict[str, Any]:
    return {
        "name": "model",
        "generations": 1,
        "retry": False,
        "automatic_repair": False,
    }


class GranularityTests(unittest.TestCase):
    def test_backward_compatible_target_span_without_granularity(self) -> None:
        config = {"locator": {"kind": "class", "symbol": "Register"}}
        self.assertEqual(RUNNER.normalized_granularity(config), "target_span")

    def test_module_files_granularity(self) -> None:
        self.assertEqual(
            RUNNER.normalized_granularity({"granularity": "module_files"}),
            "module_files",
        )

    def test_rejects_path_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsafe relative path"):
            RUNNER.validate_relative_paths(["../secret.cpp"], "source_files")


class ModuleOutputTests(unittest.TestCase):
    def test_schema_has_exact_item_count(self) -> None:
        schema = RUNNER.module_output_schema(["include/a.h", "src/a.cpp"])
        files = schema["properties"]["files"]
        self.assertEqual(files["minItems"], 2)
        self.assertEqual(files["maxItems"], 2)

    def test_parse_valid_output_in_expected_order(self) -> None:
        text = json.dumps(
            {
                "files": [
                    {"path": "src/a.cpp", "content": "int f() { return 1; }"},
                    {"path": "include/a.h", "content": "int f();"},
                ]
            }
        )
        result = RUNNER.parse_module_output(text, ["include/a.h", "src/a.cpp"])
        self.assertEqual(list(result), ["include/a.h", "src/a.cpp"])

    def test_rejects_duplicate_path(self) -> None:
        text = json.dumps(
            {
                "files": [
                    {"path": "a.h", "content": "x"},
                    {"path": "a.h", "content": "y"},
                ]
            }
        )
        with self.assertRaisesRegex(RuntimeError, "Duplicate generated file path"):
            RUNNER.parse_module_output(text, ["a.h", "a.cpp"])

    def test_rejects_unknown_path(self) -> None:
        text = json.dumps(
            {"files": [{"path": "unknown.cpp", "content": "x"}]}
        )
        with self.assertRaisesRegex(RuntimeError, "Unexpected generated file path"):
            RUNNER.parse_module_output(text, ["a.cpp"])

    def test_rejects_extra_root_field(self) -> None:
        text = json.dumps(
            {"files": [{"path": "a.cpp", "content": "x"}], "note": "bad"}
        )
        with self.assertRaisesRegex(RuntimeError, "only the files array"):
            RUNNER.parse_module_output(text, ["a.cpp"])

    def test_materializes_files_and_manifest(self) -> None:
        config = {
            "granularity": "module_files",
            "source_files": ["include/a.h", "src/a.cpp"],
        }
        response = json.dumps(
            {
                "files": [
                    {"path": "include/a.h", "content": "int f();\n"},
                    {"path": "src/a.cpp", "content": "int f() { return 1; }\n"},
                ]
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            RUNNER.materialize_regeneration_output(config, root, response)
            self.assertTrue((root / "generated/files/include/a.h").is_file())
            self.assertTrue((root / "generated/files/src/a.cpp").is_file())
            manifest = json.loads(
                (root / "generated/generated_files_manifest.json").read_text()
            )
            self.assertEqual(
                [item["path"] for item in manifest["files"]],
                ["include/a.h", "src/a.cpp"],
            )


class ScaffoldTests(unittest.TestCase):
    def test_scaffold_preserves_inline_constructor_initializer_list(self) -> None:
        source = """struct Stat {
    unsigned long long cycle;
    Stat() : cycle(0) {}
    unsigned long long value() const { return cycle; }
};
"""
        scaffold = RUNNER.strip_inline_callable_bodies_for_scaffold(source)
        self.assertIn(
            "Stat() : cycle(0) { /* implementation omitted */ }",
            scaffold,
        )
        self.assertIn("value() const ;", scaffold)
        self.assertNotIn("return cycle", scaffold)

    def test_scaffold_preserves_multiline_constructor_initializer_list(self) -> None:
        source = """class Pair {
public:
    Pair(int left, int right)
        : left_(left),
          right_(right) {}
private:
    int left_;
    int right_;
};
"""
        scaffold = RUNNER.strip_inline_callable_bodies_for_scaffold(source)
        self.assertIn(
            "right_(right) { /* implementation omitted */ }",
            scaffold,
        )

    def test_function_scaffold_preserves_constructor_initializer_list(self) -> None:
        target = """Session::Session(bool debug) : _debug(debug) {
    initialize();
}
"""
        scaffold = RUNNER.make_target_scaffold(
            target,
            {"kind": "function", "symbol": "Session::Session"},
        )
        self.assertEqual(
            scaffold,
            "Session::Session(bool debug) : _debug(debug) {\n"
            "    /* implementation omitted */\n"
            "}\n",
        )

    def test_module_scaffold_uses_headers_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "include").mkdir()
            (root / "src").mkdir()
            (root / "include/a.h").write_text("int f() { return 1; }\n")
            (root / "src/a.cpp").write_text("int f() { return 2; }\n")
            result = RUNNER.build_module_scaffold(
                root,
                ["include/a.h", "src/a.cpp"],
            )
            self.assertIn("===== FILE: include/a.h =====", result)
            self.assertNotIn("src/a.cpp", result)


class LocatorTests(unittest.TestCase):
    def test_function_locator_handles_multiline_signature(self) -> None:
        text = """class X {\npublic:\ninline static void write(\n    const int value) {\n    consume(value);\n}\n};\n"""
        locator = {
            "kind": "function",
            "symbol": "X::write",
            "signature_regex": r"inline\s+static\s+void\s+write\s*\(\s*const\s+int\s+value\s*\)",
        }
        start, end = RUNNER.locate_function_span(text, locator)
        self.assertEqual(text[start:end].splitlines()[0], "inline static void write(")
        self.assertTrue(text[start:end].rstrip().endswith("}"))

    def test_class_locator_includes_template_prefix(self) -> None:
        text = "template<typename T>\nclass Register {\npublic:\n T value;\n};\n"
        start, end = RUNNER.locate_target_span(
            text,
            {"kind": "class", "symbol": "Register"},
        )
        self.assertTrue(text[start:end].startswith("template<typename T>"))


class ConfigValidationTests(unittest.TestCase):
    def base_config(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "target_id": "target",
            "experiment_id": "v2/pilot/target",
            "run_id": "target-run-001",
            "repository_id": "repo",
            "repository_path": "repos/repo",
            "repository_commit": "abc",
            "target_name": "target",
            "model": _model(),
            "evaluation": _evaluation(),
        }

    def test_validates_module_config(self) -> None:
        config = self.base_config()
        config.update(
            {
                "granularity": "module_files",
                "source_files": ["include/a.h", "src/a.cpp"],
                "observation_files": ["include/a.h", "src/a.cpp"],
                "locator": {},
            }
        )
        summary = RUNNER.validate_config(config)
        self.assertEqual(summary["granularity"], "module_files")

    def test_validates_function_config(self) -> None:
        config = self.base_config()
        config.update(
            {
                "granularity": "function",
                "observation_files": ["ini/ini.h"],
                "target_source_file": "ini/ini.h",
                "locator": {
                    "kind": "function",
                    "symbol": "INIWriter::write",
                    "signature_regex": r"inline\s+static\s+void\s+write\s*\(",
                },
            }
        )
        summary = RUNNER.validate_config(config)
        self.assertEqual(summary["granularity"], "target_span")

    def test_rejects_retry(self) -> None:
        config = self.base_config()
        config.update(
            {
                "granularity": "module_files",
                "source_files": ["a.cpp"],
                "locator": {},
            }
        )
        config["model"]["retry"] = True
        with self.assertRaisesRegex(ValueError, "model.retry must be false"):
            RUNNER.validate_config(config)


class EvaluationRestorationTests(unittest.TestCase):
    def test_module_files_are_restored_when_evaluation_raises(self) -> None:
        config = {
            "enabled": True,
            "target_id": "module",
            "experiment_id": "v2/pilot/module",
            "run_id": "module-run-001",
            "repository_id": "repo",
            "repository_path": "repos/repo",
            "repository_commit": "abc",
            "target_name": "module",
            "granularity": "module_files",
            "source_files": ["include/a.h", "src/a.cpp"],
            "observation_files": ["include/a.h", "src/a.cpp"],
            "locator": {},
            "model": _model(),
            "evaluation": _evaluation(),
        }
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            repository = project / "repos/repo"
            experiment = project / "experiments/v2/pilot/module"
            (repository / "include").mkdir(parents=True)
            (repository / "src").mkdir(parents=True)
            (repository / "include/a.h").write_text("original header\n")
            (repository / "src/a.cpp").write_text("original source\n")
            (experiment / "generated/files/include").mkdir(parents=True)
            (experiment / "generated/files/src").mkdir(parents=True)
            (experiment / "generated/files/include/a.h").write_text("generated header\n")
            (experiment / "generated/files/src/a.cpp").write_text("generated source\n")
            (experiment / "raw_output").mkdir(parents=True)
            (experiment / "raw_output/code_regeneration_normalization.json").write_text(
                json.dumps({"normalization_applied": False})
            )

            original_docker_image_id = RUNNER.docker_image_id
            RUNNER.docker_image_id = lambda image: (_ for _ in ()).throw(
                RuntimeError("synthetic failure")
            )
            try:
                result = RUNNER.evaluate(config, project, experiment)
            finally:
                RUNNER.docker_image_id = original_docker_image_id

            self.assertFalse(result["overall_pass"])
            self.assertIn("synthetic failure", result["error"])
            self.assertEqual(
                (repository / "include/a.h").read_text(),
                "original header\n",
            )
            self.assertEqual(
                (repository / "src/a.cpp").read_text(),
                "original source\n",
            )
            self.assertTrue(result["restoration"]["restored"])
            self.assertEqual(len(result["restoration"]["files"]), 2)


if __name__ == "__main__":
    unittest.main()
