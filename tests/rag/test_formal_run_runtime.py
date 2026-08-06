from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.rag.formal_run_policy import sha256_file
from scripts.rag.formal_run_runtime import RuntimeHooks, read_json
from scripts.rag.run_formal_target import run_formal_target


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def base_isolation() -> dict[str, list[str]]:
    return {
        "design_generation_allowed_inputs": [
            "frozen design instruction",
            "frozen target source",
            "frozen context.txt",
        ],
        "code_regeneration_allowed_inputs": [
            "single one-shot generated design document",
            "fixed scaffold equivalent to the corresponding non-RAG target",
        ],
        "code_regeneration_forbidden_inputs": [
            "original target source body",
            "retrieved context",
            "selected chunks",
            "candidates",
            "query artifact",
            "repository source",
            "design-generation request or prompt",
            "design audit findings",
            "previous generated output",
        ],
    }


def create_context(root: Path, target_id: str) -> tuple[str, str]:
    path = root / f"rag/retrieval/formal/{target_id}/context.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Repository context\nHELPER_TOKEN\n", encoding="utf-8")
    digest = sha256_file(path)
    write_json(
        path.parent / "retrieval_manifest.json",
        {
            "target_id": target_id,
            "status": "pass",
            "deterministic": True,
            "context_sha256": digest,
            "llm_calls": {
                "design_generation": 0,
                "code_regeneration": 0,
            },
        },
    )
    return path.relative_to(root).as_posix(), digest


def create_standard_target(
    root: Path,
    *,
    target_id: str = "sample",
    enabled: bool = True,
) -> Path:
    context_path, context_sha = create_context(root, target_id)
    repository = root / "repos/sample"
    (repository / "include").mkdir(parents=True, exist_ok=True)
    (repository / "src").mkdir(parents=True, exist_ok=True)
    (repository / "include/sample.h").write_text(
        "class Sample { public: int value() const { return 7; } };\n",
        encoding="utf-8",
    )
    (repository / "src/sample.cpp").write_text(
        "#include \"sample.h\"\nint implementation_marker = 1;\n",
        encoding="utf-8",
    )
    config = {
        "artifact_schema_version": "rag-formal-target-config-v1",
        "condition_id": "rag-design-context-v1",
        "context_path": context_path,
        "context_sha256": context_sha,
        "context_status": "generated_and_audited",
        "enabled": enabled,
        "target_id": target_id,
        "target_name": "sample",
        "target_kind": "standard",
        "granularity": "module_files",
        "repository_id": "sample",
        "repository_path": "repos/sample",
        "repository_commit": "repo-commit",
        "source_files": ["include/sample.h", "src/sample.cpp"],
        "run_id": f"rag-v1-formal-{target_id}",
        "formal_run_id": f"rag-v1-formal-{target_id}",
        "experiment_id": f"rag-v1-formal-{target_id}",
        "output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
        "formal_output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
        "model": {
            "name": "model",
            "stream": False,
            "temperature": 0,
            "seed": 42,
            "num_ctx": 16384,
            "num_predict": 8192,
            "top_k": 40,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "retry": False,
            "automatic_repair": False,
            "generations": 1,
        },
        "one_shot_generation_policy": {
            "design_generation_count": 1,
            "code_generation_count": 1,
            "retry": False,
            "automatic_repair": False,
            "manual_patch": False,
            "overwrite": False,
        },
        "input_isolation": base_isolation(),
        "evaluation": {
            "docker_image": "image",
            "docker_image_id": "image-id",
            "configure_command": "configure",
            "build_command": "build",
            "direct_test_command": "direct",
            "full_test_command": "full",
            "full_test_kind": "gtest",
            "expected_direct_tests": 1,
            "expected_full_tests": 2,
            "stage_timeouts_seconds": {
                "configure": 1,
                "build": 1,
                "direct_test": 1,
                "full_test": 1,
            },
        },
    }
    path = root / f"configs/rag/targets/{target_id}.json"
    write_json(path, config)
    return path


class FakeRuntime:
    def __init__(self, *, build_pass: bool = True, invalid_code: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.build_pass = build_pass
        self.invalid_code = invalid_code

    def hooks(self) -> RuntimeHooks:
        return RuntimeHooks(
            git_output=self.git_output,
            docker_image_id=lambda image: "image-id",
            docker_run=self.docker_run,
            call_ollama=self.call_ollama,
            run_command=self.run_command,
        )

    def git_output(self, repository: Path, *args: str) -> str:
        if args[:2] == ("rev-parse", "HEAD"):
            return "nested-commit" if repository.name == "googletest" else "repo-commit"
        return ""

    def call_ollama(self, **kwargs: Any) -> tuple[dict[str, Any], float]:
        self.calls.append(dict(kwargs))
        if len(self.calls) == 1:
            response = "DESIGN_DOCUMENT_ONLY"
        elif self.invalid_code:
            response = "not-json"
        else:
            response = json.dumps(
                {
                    "files": [
                        {
                            "path": "include/sample.h",
                            "content": "class Sample { public: int value() const; };\n",
                        },
                        {
                            "path": "src/sample.cpp",
                            "content": "int implementation_marker = 2;\n",
                        },
                    ]
                }
            )
        return {
            "response": response,
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 20,
        }, 0.1

    def docker_run(self, **kwargs: Any) -> dict[str, Any]:
        stage = kwargs["stage"]
        passed = not (stage == "build" and not self.build_pass)
        if stage == "direct_test":
            stdout = "[==========] 1 test from 1 test suite ran.\n[  PASSED  ] 1 test.\n"
        elif stage == "full_test":
            stdout = "[==========] 2 tests from 1 test suite ran.\n[  PASSED  ] 2 tests.\n"
        else:
            stdout = ""
        return {
            "stage": stage,
            "exit_code": 0 if passed else 1,
            "passed": passed,
            "timed_out": False,
            "stdout": stdout,
            "stderr": "",
        }

    def run_command(self, **kwargs: Any) -> dict[str, Any]:
        stage = kwargs["stage"]
        if stage == "direct_test":
            stdout = "[==========] 3 tests from 1 test suite ran.\n[  PASSED  ] 3 tests.\n"
        elif stage == "full_test":
            stdout = "[==========] 27 tests from 1 test suite ran.\n[  PASSED  ] 27 tests.\n"
        elif stage == "ctest":
            stdout = "100% tests passed, 0 tests failed out of 27\n"
        else:
            stdout = ""
        return {
            "stage": stage,
            "exit_code": 0,
            "passed": True,
            "timed_out": False,
            "stdout": stdout,
            "stderr": "",
        }


def test_standard_formal_target_calls_each_generation_once_and_restores_source(
    tmp_path: Path,
) -> None:
    config_path = create_standard_target(tmp_path)
    original_header = (tmp_path / "repos/sample/include/sample.h").read_bytes()
    original_source = (tmp_path / "repos/sample/src/sample.cpp").read_bytes()
    fake = FakeRuntime()

    exit_code = run_formal_target(
        config_path,
        tmp_path,
        hooks=fake.hooks(),
    )

    assert exit_code == 0
    assert len(fake.calls) == 2
    design_prompt = fake.calls[0]["payload"]["prompt"]
    code_prompt = fake.calls[1]["payload"]["prompt"]
    assert design_prompt.index("BEGIN RETRIEVED CONTEXT") < design_prompt.index("# \u5143\u30b3\u30fc\u30c9")
    assert "HELPER_TOKEN" in design_prompt
    assert "BEGIN RETRIEVED CONTEXT" not in code_prompt
    assert "implementation_marker = 1" not in code_prompt
    assert (tmp_path / "repos/sample/include/sample.h").read_bytes() == original_header
    assert (tmp_path / "repos/sample/src/sample.cpp").read_bytes() == original_source
    evaluation = read_json(
        tmp_path
        / "experiments/rag/rag-v1-formal-sample/evaluation/evaluation_manifest.json"
    )
    assert evaluation["overall_pass"] is True
    assert evaluation["restoration"]["restored"] is True


def test_failed_build_is_terminal_and_source_is_restored(tmp_path: Path) -> None:
    config_path = create_standard_target(tmp_path)
    original = (tmp_path / "repos/sample/src/sample.cpp").read_bytes()
    fake = FakeRuntime(build_pass=False)

    exit_code = run_formal_target(config_path, tmp_path, hooks=fake.hooks())

    assert exit_code == 1
    assert (tmp_path / "repos/sample/src/sample.cpp").read_bytes() == original
    evaluation = read_json(
        tmp_path
        / "experiments/rag/rag-v1-formal-sample/evaluation/evaluation_manifest.json"
    )
    assert evaluation["overall_pass"] is False
    assert evaluation["stages"]["build"]["passed"] is False
    assert evaluation["stages"]["direct_test"]["skipped"] is True


def test_invalid_generated_module_records_pipeline_failure_without_retry(
    tmp_path: Path,
) -> None:
    config_path = create_standard_target(tmp_path)
    original = (tmp_path / "repos/sample/src/sample.cpp").read_bytes()
    fake = FakeRuntime(invalid_code=True)

    with pytest.raises(Exception, match="not valid JSON"):
        run_formal_target(config_path, tmp_path, hooks=fake.hooks())

    assert len(fake.calls) == 2
    assert (tmp_path / "repos/sample/src/sample.cpp").read_bytes() == original
    failure = read_json(
        tmp_path
        / "experiments/rag/rag-v1-formal-sample/evaluation/pipeline_failure.json"
    )
    assert failure["failed_stage"] == "materialize_code"
    assert failure["llm_calls"] == {
        "design_generation": 1,
        "code_regeneration": 1,
    }
    assert failure["retry_performed"] is False


def create_legacy_target(root: Path) -> Path:
    target_id = "ini-cpp-ini-writer"
    context_path, context_sha = create_context(root, target_id)
    repository = root / "repos/ini-cpp"
    (repository / "ini").mkdir(parents=True, exist_ok=True)
    (repository / "googletest").mkdir(parents=True, exist_ok=True)
    source = (
        "class INIWriter {\npublic:\n"
        "    inline static void write(int value) {\n"
        "        int old_body = value;\n"
        "    }\n};\n"
    )
    (repository / "ini/ini.h").write_text(source, encoding="utf-8")
    design = root / "frozen/design_input.cpp"
    scaffold = root / "frozen/fixed_scaffold.cpp"
    design.parent.mkdir(parents=True)
    design.write_text(source, encoding="utf-8")
    scaffold.write_text("inline static void write(int value);\n", encoding="utf-8")
    prompt = root / "experiments/ini-writer-minimal/prompts/design_generation_prompt.md"
    prompt.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text(
        "# Role\nlegacy\n\n# \u5bfe\u8c61\u30bd\u30fc\u30b9\u30b3\u30fc\u30c9\n\n{{DESIGN_INPUT}}\n",
        encoding="utf-8",
    )
    config = {
        "artifact_schema_version": "rag-formal-target-config-v1",
        "condition_id": "rag-design-context-v1",
        "context_path": context_path,
        "context_sha256": context_sha,
        "context_status": "generated_and_audited",
        "enabled": True,
        "target_id": target_id,
        "target_name": "INIWriter::write",
        "target_kind": "legacy_function",
        "granularity": "function_body",
        "repository_id": "ini-cpp",
        "repository_path": "repos/ini-cpp",
        "repository_commit": "repo-commit",
        "submodule_commit": "nested-commit",
        "source_file": "ini/ini.h",
        "run_id": f"rag-v1-formal-{target_id}",
        "formal_run_id": f"rag-v1-formal-{target_id}",
        "experiment_id": f"rag-v1-formal-{target_id}",
        "output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
        "formal_output_directory": f"experiments/rag/rag-v1-formal-{target_id}",
        "model": {"name": "model"},
        "generation": {
            "stream": False,
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_ctx": 8192,
                "num_predict": 2048,
                "top_k": 40,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        },
        "conditions": {
            "generations_per_stage": 1,
            "retry_on_failure": False,
            "automatic_repair": False,
        },
        "one_shot_generation_policy": {
            "design_generation_count": 1,
            "code_generation_count": 1,
            "retry": False,
            "automatic_repair": False,
            "manual_patch": False,
            "overwrite": False,
        },
        "input_isolation": base_isolation(),
        "design_input": {
            "path": design.relative_to(root).as_posix(),
            "sha256": sha256_file(design),
        },
        "regeneration_input": {
            "fixed_scaffold": scaffold.relative_to(root).as_posix(),
            "original_function_body_excluded": True,
        },
        "evaluation": {
            "docker_image": "image",
            "docker_image_id": "image-id",
            "configure_command": ["docker", "run", "<PROJECT_ROOT>", "configure"],
            "build_command": ["docker", "run", "<PROJECT_ROOT>", "build"],
            "direct_test_command": ["docker", "run", "<PROJECT_ROOT>", "direct"],
            "full_test_command": ["docker", "run", "<PROJECT_ROOT>", "full"],
            "ctest_command": ["docker", "run", "<PROJECT_ROOT>", "ctest"],
            "expected_direct_tests": 3,
            "expected_full_tests": 27,
        },
    }
    path = root / f"configs/rag/targets/{target_id}.json"
    write_json(path, config)
    return path


def test_legacy_target_uses_no_dependency_context_and_restores_body(tmp_path: Path) -> None:
    config_path = create_legacy_target(tmp_path)
    source_path = tmp_path / "repos/ini-cpp/ini/ini.h"
    original = source_path.read_bytes()
    fake = FakeRuntime()

    def legacy_call(**kwargs: Any) -> tuple[dict[str, Any], float]:
        fake.calls.append(dict(kwargs))
        text = "LEGACY DESIGN" if len(fake.calls) == 1 else "int new_body = value;"
        return {"response": text, "done": True, "done_reason": "stop"}, 0.1

    hooks = fake.hooks()
    hooks = RuntimeHooks(
        git_output=hooks.git_output,
        docker_image_id=hooks.docker_image_id,
        docker_run=hooks.docker_run,
        call_ollama=legacy_call,
        run_command=hooks.run_command,
    )
    exit_code = run_formal_target(config_path, tmp_path, hooks=hooks)

    assert exit_code == 0
    assert len(fake.calls) == 2
    code_prompt = fake.calls[1]["payload"]["prompt"]
    assert "LEGACY DESIGN" in code_prompt
    assert "HELPER_TOKEN" not in code_prompt
    assert "DEPENDENCY_CONTEXT" not in code_prompt
    assert source_path.read_bytes() == original
    evaluation = read_json(
        tmp_path
        / "experiments/rag/rag-v1-formal-ini-cpp-ini-writer/evaluation/evaluation_manifest.json"
    )
    assert evaluation["overall_pass"] is True
    assert set(evaluation["stages"]) == {
        "configure",
        "build",
        "direct_test",
        "full_test",
        "ctest",
    }
