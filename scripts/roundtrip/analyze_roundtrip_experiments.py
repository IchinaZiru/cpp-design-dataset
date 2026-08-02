#!/usr/bin/env python3
"""Analyze the fixed main-study round-trip experiment artifacts.

This script is read-only with respect to experiment inputs. It does not call an
LLM, Docker, CMake, tests, or Git. It scans the saved artifacts and writes
machine-readable and thesis-oriented summaries under reports/analysis.

Expected study layout
---------------------
- configs/roundtrip/targets/*.json       standard target configurations
- experiments/<target-id>-roundtrip/     standard experiment artifacts
- experiments/ini-writer-minimal/        legacy INIWriter experiment
- manifests/runs.csv                     optional run registry
- manifests/targets.csv                  optional target registry
- reports/batch/batch_execution.json     optional fallback status source

The current main study is expected to contain 17 targets: 16 standard targets
plus the legacy INIWriter experiment. By default, the script validates the
known final summary (17 total, 6 PASS, 11 FAIL). Use
--allow-unexpected-summary only when deliberately analyzing a different set.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCRIPT_VERSION = "1.3.0"
EXPECTED_TOTAL = 17
EXPECTED_PASS = 6
EXPECTED_FAIL = 11

STAGE_ORDER = (
    "design_generation",
    "code_regeneration",
    "configure",
    "build",
    "direct_test",
    "full_test",
)

# The one experiment created before the standard harness. The fallback values
# are used only when its legacy files do not expose the field directly.
LEGACY_INI_WRITER = {
    "directory": "ini-writer-minimal",
    "target_id": "ini-cpp-ini-writer",
    "run_id": "ini-writer-minimal",
    "repository": "ini-cpp",
    "target_name": "INIWriter::write",
    "granularity": "function",
    "expected_direct_tests": 3,
    "expected_full_tests": 27,
    "overall_pass": True,
}

FAILURE_CATEGORY_LABELS = {
    "none": "成功",
    "output_truncation": "生成出力の打ち切り",
    "output_format_or_pipeline": "出力形式・パイプライン失敗",
    "timeout_or_hang": "タイムアウト・停止",
    "hang_external_stop_deadlock_suspected": "ハング・外部停止（デッドロック疑い）",
    "configure_failure": "configure失敗",
    "syntax_error": "構文エラー",
    "type_interface_misunderstanding": "型・インタフェースの誤理解",
    "missing_definition_or_dependency": "定義・依存関係の欠落",
    "duplicate_definition": "重複定義",
    "build_failure_other": "その他のビルド失敗",
    "direct_test_failure": "直接テスト失敗",
    "full_test_failure": "全体テスト失敗",
    "unknown_failure": "原因未分類",
}


class AnalysisError(RuntimeError):
    """Raised when the saved experiment artifacts are inconsistent."""


@dataclass
class StageResult:
    name: str
    status: str = "unknown"  # passed, failed, skipped, not_recorded, unknown
    exit_code: int | None = None
    timed_out: bool | None = None
    elapsed_seconds: float | None = None
    tests_ran: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    stdout_log: str | None = None
    stderr_log: str | None = None


@dataclass
class TargetRecord:
    target_id: str
    run_id: str
    repository: str
    target_name: str
    experiment_directory: str
    config_path: str | None = None
    legacy_format: bool = False
    result_source: str = "unknown"

    granularity: str | None = None
    source_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    expected_direct_tests: int | None = None
    expected_full_tests: int | None = None
    num_ctx: int | None = None
    num_predict: int | None = None

    design_done_reason: str | None = None
    design_prompt_eval_count: int | None = None
    design_eval_count: int | None = None
    code_done_reason: str | None = None
    code_prompt_eval_count: int | None = None
    code_eval_count: int | None = None

    normalization_applied: bool | None = None
    normalization_type: str | None = None
    strict_format_pass: bool | None = None
    retry_performed: bool | None = None
    automatic_repair_performed: bool | None = None

    stages: dict[str, StageResult] = field(default_factory=dict)
    overall_pass: bool | None = None
    failure_stage: str | None = None
    failure_category: str = "none"
    failure_category_ja: str = FAILURE_CATEGORY_LABELS["none"]
    failure_detail: str | None = None

    original_loc: int | None = None
    original_chars: int | None = None
    original_measurement_scope: str | None = None
    generated_loc: int | None = None
    generated_chars: int | None = None
    generated_original_loc_ratio: float | None = None

    restored: bool | None = None
    repository_clean: bool | None = None
    total_recorded_elapsed_seconds: float | None = None
    data_quality_notes: list[str] = field(default_factory=list)

    def flat_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "target_id": self.target_id,
            "run_id": self.run_id,
            "repository": self.repository,
            "target_name": self.target_name,
            "experiment_directory": self.experiment_directory,
            "config_path": self.config_path,
            "legacy_format": self.legacy_format,
            "result_source": self.result_source,
            "granularity": self.granularity,
            "source_files": "; ".join(self.source_files),
            "test_files": "; ".join(self.test_files),
            "expected_direct_tests": self.expected_direct_tests,
            "expected_full_tests": self.expected_full_tests,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
            "design_done_reason": self.design_done_reason,
            "design_prompt_eval_count": self.design_prompt_eval_count,
            "design_eval_count": self.design_eval_count,
            "code_done_reason": self.code_done_reason,
            "code_prompt_eval_count": self.code_prompt_eval_count,
            "code_eval_count": self.code_eval_count,
            "normalization_applied": self.normalization_applied,
            "normalization_type": self.normalization_type,
            "strict_format_pass": self.strict_format_pass,
            "retry_performed": self.retry_performed,
            "automatic_repair_performed": self.automatic_repair_performed,
            "overall_pass": self.overall_pass,
            "result": "PASS" if self.overall_pass is True else "FAIL",
            "failure_stage": self.failure_stage,
            "failure_category": self.failure_category,
            "failure_category_ja": self.failure_category_ja,
            "failure_detail": self.failure_detail,
            "original_loc": self.original_loc,
            "original_chars": self.original_chars,
            "original_measurement_scope": self.original_measurement_scope,
            "generated_loc": self.generated_loc,
            "generated_chars": self.generated_chars,
            "generated_original_loc_ratio": self.generated_original_loc_ratio,
            "restored": self.restored,
            "repository_clean": self.repository_clean,
            "total_recorded_elapsed_seconds": self.total_recorded_elapsed_seconds,
            "data_quality_notes": " | ".join(self.data_quality_notes),
        }
        for stage_name in STAGE_ORDER:
            stage = self.stages.get(stage_name, StageResult(stage_name, "not_recorded"))
            prefix = stage_name
            row[f"{prefix}_status"] = stage.status
            row[f"{prefix}_exit_code"] = stage.exit_code
            row[f"{prefix}_timed_out"] = stage.timed_out
            row[f"{prefix}_elapsed_seconds"] = stage.elapsed_seconds
            row[f"{prefix}_tests_ran"] = stage.tests_ran
            row[f"{prefix}_tests_passed"] = stage.tests_passed
            row[f"{prefix}_tests_failed"] = stage.tests_failed
        return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Repository root. Default: inferred from script location or current directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default: <project-root>/reports/analysis",
    )
    parser.add_argument(
        "--allow-unexpected-summary",
        action="store_true",
        help="Do not fail when the result is not exactly 17 targets / 6 PASS / 11 FAIL.",
    )
    parser.add_argument(
        "--include-pilot-failures",
        action="store_true",
        help="Include experiments under experiments/pilot-failures (off by default).",
    )
    parser.add_argument(
        "--no-svg",
        action="store_true",
        help="Skip generation of dependency-free SVG figures.",
    )
    return parser.parse_args()


def infer_project_root(explicit: Path | None) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
    else:
        script_path = Path(__file__).resolve()
        candidates = [Path.cwd().resolve()]
        if len(script_path.parents) >= 3:
            candidates.append(script_path.parents[2])
        candidates.extend(script_path.parents)
        root = next(
            (
                candidate
                for candidate in candidates
                if (candidate / "experiments").is_dir()
                and (candidate / "configs" / "roundtrip" / "targets").is_dir()
            ),
            Path.cwd().resolve(),
        )
    required = [root / "experiments", root / "configs" / "roundtrip" / "targets"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise AnalysisError(
            "Project root does not contain the expected paths: " + ", ".join(missing)
        )
    return root


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except (OSError, UnicodeError, csv.Error):
        return []


def nested_get(data: Mapping[str, Any] | None, *paths: str) -> Any:
    if data is None:
        return None
    for dotted in paths:
        current: Any = data
        ok = True
        for part in dotted.split("."):
            if isinstance(current, Mapping) and part in current:
                current = current[part]
            else:
                ok = False
                break
        if ok:
            return current
    return None


def first_nonempty(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "" and value != []:
            return value
    return None


def coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "pass", "passed", "success"}:
            return True
        if normalized in {"false", "no", "0", "fail", "failed", "error"}:
            return False
    return None


def coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_status(value: Any) -> str | None:
    if isinstance(value, bool):
        return "passed" if value else "failed"
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace(" ", "_")
    if normalized in {"pass", "passed", "success", "successful", "ok", "complete", "completed"}:
        return "passed"
    if normalized in {"fail", "failed", "failure", "error", "timed_out", "timeout", "hung"}:
        return "failed"
    if normalized in {"skip", "skipped", "not_run", "not_executed"}:
        return "skipped"
    if normalized in {"unknown", "pending", "ready", "disabled"}:
        return "unknown"
    return None


def repository_from_target_id(target_id: str) -> str:
    lowered = target_id.lower()
    if lowered.startswith("echo-web-server"):
        return "Echo-Web-Server"
    if lowered.startswith("riscv-simulator"):
        return "RISCV-Simulator"
    if lowered.startswith("ini-cpp") or "ini-writer" in lowered:
        return "ini-cpp"
    return target_id.split("-", 1)[0]


def target_name_from_id(target_id: str, repository: str) -> str:
    prefixes = {
        "Echo-Web-Server": "echo-web-server-",
        "RISCV-Simulator": "riscv-simulator-",
        "ini-cpp": "ini-cpp-",
    }
    prefix = prefixes.get(repository, "")
    name = target_id[len(prefix) :] if prefix and target_id.startswith(prefix) else target_id
    return name.replace("-", "_")


def config_experiment_directory(config: Mapping[str, Any], target_id: str) -> str:
    configured = first_nonempty(
        nested_get(config, "experiment_directory", "paths.experiment_directory"),
        nested_get(config, "experiment_dir", "paths.experiment_dir"),
    )
    if isinstance(configured, str):
        return configured.replace("\\", "/").strip("/")
    return f"experiments/{target_id}-roundtrip"


def list_standard_configs(root: Path) -> list[Path]:
    config_dir = root / "configs" / "roundtrip" / "targets"
    return sorted(
        path
        for path in config_dir.glob("*.json")
        if not path.name.endswith(".draft.json")
    )


def find_experiment_dir(root: Path, config: Mapping[str, Any], target_id: str) -> Path:
    configured = config_experiment_directory(config, target_id)
    candidate = root / configured
    if candidate.is_dir():
        return candidate
    direct = root / "experiments" / f"{target_id}-roundtrip"
    if direct.is_dir():
        return direct
    matches = sorted(
        path
        for path in (root / "experiments").glob(f"*{target_id}*")
        if path.is_dir() and "pilot-failures" not in path.parts
    )
    return matches[0] if matches else direct


def find_first_named(exp_dir: Path, names: Sequence[str]) -> Path | None:
    for name in names:
        direct = exp_dir / name
        if direct.is_file():
            return direct
    if exp_dir.is_dir():
        for name in names:
            matches = sorted(exp_dir.rglob(Path(name).name))
            if matches:
                return matches[0]
    return None


def load_metadata(exp_dir: Path, stem: str) -> dict[str, Any] | None:
    candidates = [
        exp_dir / "raw_output" / f"{stem}_metadata.json",
        exp_dir / f"{stem}_metadata.json",
    ]
    for path in candidates:
        value = read_json(path)
        if value is not None:
            return value
    return None


def load_normalization(exp_dir: Path, evaluation: Mapping[str, Any] | None) -> dict[str, Any] | None:
    from_eval = nested_get(evaluation, "code_regeneration_normalization")
    if isinstance(from_eval, Mapping):
        return dict(from_eval)
    for path in (
        exp_dir / "raw_output" / "code_regeneration_normalization.json",
        exp_dir / "code_regeneration_normalization.json",
    ):
        value = read_json(path)
        if value is not None:
            return value
    return None


def load_evaluation(exp_dir: Path) -> tuple[dict[str, Any] | None, Path | None]:
    candidates = [
        exp_dir / "evaluation" / "evaluation_manifest.json",
        exp_dir / "evaluation_manifest.json",
        exp_dir / "report" / "evaluation_manifest.json",
    ]
    for path in candidates:
        value = read_json(path)
        if value is not None:
            return value, path
    # Legacy fallback: find the most evaluation-like JSON containing overall_pass.
    if exp_dir.is_dir():
        for path in sorted(exp_dir.rglob("*.json")):
            value = read_json(path)
            if value is not None and (
                "overall_pass" in value or isinstance(value.get("stages"), Mapping)
            ):
                return value, path
    return None, None


def load_pipeline_failure(exp_dir: Path) -> tuple[dict[str, Any] | None, Path | None]:
    path = find_first_named(
        exp_dir,
        (
            "pipeline_failure.json",
            "evaluation/pipeline_failure.json",
            "report/pipeline_failure.json",
        ),
    )
    return (read_json(path), path) if path else (None, None)


def recursive_find_target_entry(value: Any, target_id: str) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        current_id = first_nonempty(
            value.get("target_id"), value.get("id"), value.get("target")
        )
        if current_id == target_id:
            return dict(value)
        for child in value.values():
            found = recursive_find_target_entry(child, target_id)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = recursive_find_target_entry(child, target_id)
            if found is not None:
                return found
    return None


def load_batch_entry(root: Path, target_id: str) -> dict[str, Any] | None:
    for path in (
        root / "reports" / "batch" / "batch_execution.json",
        root / "reports" / "batch" / "batch_plan.json",
    ):
        data = read_json(path)
        if data is not None:
            found = recursive_find_target_entry(data, target_id)
            if found is not None:
                return found
    return None


def row_for_identifier(rows: Sequence[Mapping[str, str]], identifier: str, keys: Sequence[str]) -> dict[str, str] | None:
    for row in rows:
        for key in keys:
            if row.get(key) == identifier:
                return dict(row)
    return None


def stage_from_mapping(name: str, value: Any) -> StageResult:
    if not isinstance(value, Mapping):
        return StageResult(name=name, status="not_recorded")
    skipped = coerce_bool(value.get("skipped"))
    passed = coerce_bool(value.get("passed"))
    timed_out = coerce_bool(first_nonempty(value.get("timed_out"), value.get("timeout")))
    if skipped is True:
        status = "skipped"
    elif passed is True:
        status = "passed"
    elif passed is False:
        status = "failed"
    else:
        status = normalize_status(first_nonempty(value.get("status"), value.get("result"))) or "unknown"
    return StageResult(
        name=name,
        status=status,
        exit_code=coerce_int(value.get("exit_code")),
        timed_out=timed_out,
        elapsed_seconds=coerce_float(
            first_nonempty(value.get("elapsed_seconds"), value.get("duration_seconds"))
        ),
        tests_ran=coerce_int(
            first_nonempty(value.get("tests_ran"), value.get("ran"), value.get("total"))
        ),
        tests_passed=coerce_int(
            first_nonempty(value.get("tests_passed"), value.get("passed_count"))
        ),
        tests_failed=coerce_int(
            first_nonempty(value.get("tests_failed"), value.get("failed_count"))
        ),
        stdout_log=value.get("stdout_log") if isinstance(value.get("stdout_log"), str) else None,
        stderr_log=value.get("stderr_log") if isinstance(value.get("stderr_log"), str) else None,
    )


def read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    except OSError:
        return ""


def resolve_log(root: Path, exp_dir: Path, log_ref: str | None) -> Path | None:
    if not log_ref:
        return None
    ref_path = Path(log_ref)
    candidates = [
        ref_path if ref_path.is_absolute() else root / ref_path,
        exp_dir / ref_path,
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def stage_log_text(root: Path, exp_dir: Path, stage: StageResult) -> str:
    parts: list[str] = []
    for ref in (stage.stderr_log, stage.stdout_log):
        path = resolve_log(root, exp_dir, ref)
        if path:
            parts.append(read_text_if_exists(path))
    return "\n".join(parts)


def first_error_line(text: str) -> str | None:
    patterns = (
        r"^.*(?:fatal error|error:|undefined reference|Assertion.*failed|FAILED|Traceback).*$",
        r"^.*(?:timed out|timeout|hung|killed|terminated).*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()[:500]
    return None


def count_tree_text(root: Path) -> tuple[int | None, int | None]:
    if not root.is_dir():
        return None, None
    files = [path for path in root.rglob("*") if path.is_file()]
    if not files:
        return None, None
    total_loc = 0
    total_chars = 0
    read_any = False
    for path in files:
        text = read_text_if_exists(path)
        if text == "" and path.stat().st_size > 0:
            continue
        read_any = True
        total_chars += len(text)
        total_loc += len(text.splitlines())
    return (total_loc, total_chars) if read_any else (None, None)


SOURCE_CODE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}


def strip_one_outer_markdown_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(
        r"```[A-Za-z0-9_+.-]*\s*\n(?P<body>.*)\n```",
        stripped,
        flags=re.DOTALL,
    )
    return match.group("body") if match else text


def count_text_value(text: str) -> tuple[int, int]:
    return len(text.splitlines()), len(text)


def count_selected_files(paths: Sequence[Path]) -> tuple[int | None, int | None]:
    if not paths:
        return None, None
    total_loc = 0
    total_chars = 0
    read_any = False
    for path in paths:
        text = read_text_if_exists(path)
        if text == "" and path.stat().st_size > 0:
            continue
        read_any = True
        total_loc += len(text.splitlines())
        total_chars += len(text)
    return (total_loc, total_chars) if read_any else (None, None)


def extract_response_text(response: Mapping[str, Any] | None) -> str | None:
    value = nested_get(
        response,
        "response",
        "content",
        "message.content",
        "choices.0.message.content",
        "choices.0.text",
    )
    return value if isinstance(value, str) and value.strip() else None


def count_original_target_code(
    exp_dir: Path, granularity: str | None
) -> tuple[int | None, int | None, str | None]:
    """Measure the original code at the same replacement granularity as output.

    module_files targets replace complete files, while class_span targets replace
    only a located class definition. Counting backup/files for every target mixes
    whole-file LOC with generated class-span LOC, so prefer the span backup saved
    by the harness.
    """
    if granularity == "class_span":
        span_path = exp_dir / "backup" / "original_target.cpp"
        if span_path.is_file():
            text = read_text_if_exists(span_path)
            loc, chars = count_text_value(text)
            return loc, chars, "class_span_backup"

        # The standard harness writes exactly the extracted class span to this
        # input file. This is a safe fallback when an older run lacks the
        # dedicated span backup.
        design_input = exp_dir / "input" / "design_input.txt"
        if design_input.is_file():
            text = read_text_if_exists(design_input)
            loc, chars = count_text_value(text)
            return loc, chars, "class_span_design_input_fallback"

    if granularity == "module_files":
        loc, chars = count_tree_text(exp_dir / "backup" / "files")
        if loc is not None:
            return loc, chars, "module_files_backup"

    # Generic fallback for nonstandard or older experiments.
    loc, chars = count_tree_text(exp_dir / "backup" / "files")
    if loc is not None:
        return loc, chars, "whole_source_files_fallback"
    return None, None, None


def count_generated_code(exp_dir: Path, code_done_reason: str | None) -> tuple[int | None, int | None]:
    # Preferred representation for module_files targets.
    loc, chars = count_tree_text(exp_dir / "generated" / "files")
    if loc is not None:
        return loc, chars

    # Class-span targets may save a single regenerated source file directly
    # under generated/. Count only source-like files, never design documents.
    generated_root = exp_dir / "generated"
    if generated_root.is_dir():
        source_files = sorted(
            path
            for path in generated_root.rglob("*")
            if path.is_file() and path.suffix.lower() in SOURCE_CODE_SUFFIXES
        )
        loc, chars = count_selected_files(source_files)
        if loc is not None:
            return loc, chars

    # Final fallback for class-span runs: the Ollama response contains the
    # regenerated C++ body. Do not measure a truncated response because it is
    # not a complete generated program.
    if code_done_reason == "length":
        return None, None
    response = read_json(exp_dir / "raw_output" / "code_regeneration_response.json")
    text = extract_response_text(response)
    if text is None:
        return None, None
    return count_text_value(strip_one_outer_markdown_fence(text))


def generation_stage_from_metadata(name: str, metadata: Mapping[str, Any] | None) -> StageResult:
    if not isinstance(metadata, Mapping):
        return StageResult(name=name, status="not_recorded")
    done_reason = str(metadata.get("done_reason") or "").strip().lower()
    error_value = first_nonempty(metadata.get("error"), metadata.get("error_message"))
    if done_reason == "length" or error_value:
        return StageResult(name=name, status="failed")
    if done_reason in {"stop", "complete", "completed", "success"}:
        return StageResult(name=name, status="passed")
    return StageResult(name=name, status="unknown")


def count_configured_files(root: Path, repository: str, source_files: Sequence[str]) -> tuple[int | None, int | None]:
    repo_candidates = [
        root / "repos" / repository,
        root / "repos" / repository.lower(),
    ]
    repo_dir = next((path for path in repo_candidates if path.is_dir()), None)
    if repo_dir is None or not source_files:
        return None, None
    loc = 0
    chars = 0
    found = 0
    for rel in source_files:
        path = repo_dir / rel
        if path.is_file():
            text = read_text_if_exists(path)
            loc += len(text.splitlines())
            chars += len(text)
            found += 1
    return (loc, chars) if found else (None, None)


def classify_failure(
    root: Path,
    exp_dir: Path,
    record: TargetRecord,
    pipeline_failure: Mapping[str, Any] | None,
) -> tuple[str | None, str, str | None]:
    if record.overall_pass is True:
        return None, "none", None

    for stage_name, stage in record.stages.items():
        if stage.timed_out is True:
            detail = first_error_line(stage_log_text(root, exp_dir, stage))
            return stage_name, "timeout_or_hang", detail or f"{stage_name} timed out"

    if record.design_done_reason == "length":
        return "design_generation", "output_truncation", "design generation ended with done_reason=length"
    if record.code_done_reason == "length":
        return "code_regeneration", "output_truncation", "code regeneration ended with done_reason=length"

    if pipeline_failure is not None:
        stage = first_nonempty(
            nested_get(pipeline_failure, "stage", "failure_stage"),
            "pipeline",
        )
        message = first_nonempty(
            nested_get(pipeline_failure, "error", "message", "reason", "detail"),
            json.dumps(pipeline_failure, ensure_ascii=False)[:500],
        )
        message_text = str(message)
        if re.search(r"length|truncat|token limit|incomplete", message_text, re.IGNORECASE):
            return str(stage), "output_truncation", message_text[:500]
        return str(stage), "output_format_or_pipeline", message_text[:500]

    configure = record.stages.get("configure")
    if configure and configure.status == "failed":
        detail = first_error_line(stage_log_text(root, exp_dir, configure))
        return "configure", "configure_failure", detail

    build = record.stages.get("build")
    if build and build.status == "failed":
        text = stage_log_text(root, exp_dir, build)
        detail = first_error_line(text)
        # Classify the first compiler/linker error rather than scanning every
        # cascading error in a parallel build. This prevents a later secondary
        # message from overriding the root failure.
        classification_text = (detail or text[:5000]).lower()
        if re.search(
            r"stray .* in program|expected .* before|expected .* after|"
            r"expected primary-expression|expected declaration|unterminated|"
            r"syntax error",
            classification_text,
        ):
            category = "syntax_error"
        elif re.search(r"redefinition|multiple definition", classification_text):
            category = "duplicate_definition"
        elif re.search(
            r"undefined reference|no such file or directory|cannot find -l|"
            r"has not been declared|was not declared in this scope|"
            r"not declared in this scope|not found",
            classification_text,
        ):
            category = "missing_definition_or_dependency"
        elif re.search(
            r"request for member.*non-class type|has no member|no member named|"
            r"no matching function|cannot convert|invalid conversion|conflicting types|"
            r"invalid use of|incomplete type|no declaration matches",
            classification_text,
        ):
            category = "type_interface_misunderstanding"
        elif re.search(r"timed out|timeout|killed|terminated|hang", classification_text):
            category = "timeout_or_hang"
        else:
            category = "build_failure_other"
        return "build", category, detail

    direct = record.stages.get("direct_test")
    if direct and direct.status == "failed":
        detail = first_error_line(stage_log_text(root, exp_dir, direct))
        # Older runs predate the fixed harness timeout. Exit 137/143 with no
        # recorded test counts indicates that the test process was externally
        # terminated before completion, not an ordinary assertion failure.
        externally_terminated = (
            direct.exit_code in {124, 137, 143}
            and direct.tests_ran is None
            and direct.tests_passed is None
            and direct.tests_failed is None
        )
        if externally_terminated:
            if record.target_id == "echo-web-server-block-deque":
                fallback = (
                    "直接テスト中に処理の進行が停止し、外部から終了された。"
                    "デッドロックの可能性があるが、スレッドダンプ等による厳密な確定はしていない"
                    f"（exit_code={direct.exit_code}, "
                    f"elapsed_seconds={direct.elapsed_seconds}）"
                )
                return (
                    "direct_test",
                    "hang_external_stop_deadlock_suspected",
                    detail or fallback,
                )
            fallback = (
                f"direct_test terminated before test counts were recorded "
                f"(exit_code={direct.exit_code}, "
                f"elapsed_seconds={direct.elapsed_seconds})"
            )
            return "direct_test", "timeout_or_hang", detail or fallback
        return "direct_test", "direct_test_failure", detail

    full = record.stages.get("full_test")
    if full and full.status == "failed":
        detail = first_error_line(stage_log_text(root, exp_dir, full))
        return "full_test", "full_test_failure", detail

    batch_detail = record.failure_detail
    if batch_detail and re.search(r"timeout|hung|stopp", batch_detail, re.IGNORECASE):
        return record.failure_stage or "unknown", "timeout_or_hang", batch_detail
    return record.failure_stage or "unknown", "unknown_failure", batch_detail


def parse_standard_target(
    root: Path,
    config_path: Path,
    target_rows: Sequence[Mapping[str, str]],
    run_rows: Sequence[Mapping[str, str]],
) -> TargetRecord:
    config = read_json(config_path)
    if config is None:
        raise AnalysisError(f"Invalid JSON config: {config_path}")
    target_id = str(first_nonempty(config.get("target_id"), config_path.stem))
    run_id = str(first_nonempty(config.get("run_id"), f"{target_id}-unknown-run"))
    exp_dir = find_experiment_dir(root, config, target_id)
    evaluation, evaluation_path = load_evaluation(exp_dir)
    pipeline_failure, pipeline_path = load_pipeline_failure(exp_dir)
    batch_entry = load_batch_entry(root, target_id)
    target_row = row_for_identifier(target_rows, target_id, ("target_id", "id", "target"))
    run_row = row_for_identifier(run_rows, run_id, ("run_id", "id", "run"))

    repository = str(
        first_nonempty(
            nested_get(config, "repository", "repository_name", "project.repository"),
            nested_get(target_row, "repository", "repository_name", "project"),
            repository_from_target_id(target_id),
        )
    )
    target_name = str(
        first_nonempty(
            nested_get(config, "target_name", "name", "symbol"),
            nested_get(target_row, "target_name", "name", "symbol"),
            target_name_from_id(target_id, repository),
        )
    )
    source_files = nested_get(config, "source_files", "design_input.source_files")
    test_files = nested_get(config, "test_files", "evaluation.test_files")
    record = TargetRecord(
        target_id=target_id,
        run_id=run_id,
        repository=repository,
        target_name=target_name,
        experiment_directory=str(exp_dir.relative_to(root)).replace("\\", "/") if exp_dir.is_relative_to(root) else str(exp_dir),
        config_path=str(config_path.relative_to(root)).replace("\\", "/"),
        legacy_format=False,
        result_source=(
            str(evaluation_path.relative_to(root)).replace("\\", "/")
            if evaluation_path and evaluation_path.is_relative_to(root)
            else "batch/manifests fallback"
        ),
        granularity=first_nonempty(config.get("granularity"), nested_get(target_row, "granularity")),
        source_files=[str(x) for x in source_files] if isinstance(source_files, list) else [],
        test_files=[str(x) for x in test_files] if isinstance(test_files, list) else [],
        expected_direct_tests=coerce_int(
            first_nonempty(
                nested_get(config, "evaluation.expected_direct_tests"),
                nested_get(target_row, "expected_direct_tests"),
            )
        ),
        expected_full_tests=coerce_int(
            first_nonempty(
                nested_get(config, "evaluation.expected_full_tests"),
                nested_get(target_row, "expected_full_tests"),
            )
        ),
        num_ctx=coerce_int(nested_get(config, "model.num_ctx")),
        num_predict=coerce_int(nested_get(config, "model.num_predict")),
    )

    design_meta = load_metadata(exp_dir, "design_generation")
    code_meta = load_metadata(exp_dir, "code_regeneration")
    record.design_done_reason = nested_get(design_meta, "done_reason")
    record.design_prompt_eval_count = coerce_int(nested_get(design_meta, "prompt_eval_count"))
    record.design_eval_count = coerce_int(nested_get(design_meta, "eval_count"))
    record.code_done_reason = nested_get(code_meta, "done_reason")
    record.code_prompt_eval_count = coerce_int(nested_get(code_meta, "prompt_eval_count"))
    record.code_eval_count = coerce_int(nested_get(code_meta, "eval_count"))

    normalization = load_normalization(exp_dir, evaluation)
    record.normalization_applied = coerce_bool(nested_get(normalization, "normalization_applied"))
    record.normalization_type = nested_get(normalization, "normalization_type")
    record.strict_format_pass = coerce_bool(nested_get(normalization, "strict_format_pass"))
    record.retry_performed = coerce_bool(nested_get(normalization, "retry_performed"))
    record.automatic_repair_performed = coerce_bool(
        nested_get(normalization, "automatic_repair_performed")
    )

    stages_data = nested_get(evaluation, "stages")
    if isinstance(stages_data, Mapping):
        for stage_name in STAGE_ORDER:
            record.stages[stage_name] = stage_from_mapping(stage_name, stages_data.get(stage_name))
    else:
        for stage_name in STAGE_ORDER:
            record.stages[stage_name] = StageResult(stage_name, "not_recorded")

    # Generation is recorded outside evaluation_manifest.json. Infer these two
    # stage results from the saved generation metadata so the funnel does not
    # incorrectly report all generation stages as unrecorded.
    record.stages["design_generation"] = generation_stage_from_metadata(
        "design_generation", design_meta
    )
    record.stages["code_regeneration"] = generation_stage_from_metadata(
        "code_regeneration", code_meta
    )

    record.overall_pass = coerce_bool(nested_get(evaluation, "overall_pass"))
    if record.overall_pass is None:
        record.overall_pass = coerce_bool(
            first_nonempty(
                nested_get(batch_entry, "overall_pass", "passed"),
                nested_get(batch_entry, "status", "result"),
                nested_get(run_row, "overall_pass", "passed", "status", "result"),
            )
        )
    if record.overall_pass is None:
        # A complete, passing full-test stage is sufficient positive evidence.
        if record.stages["full_test"].status == "passed":
            record.overall_pass = True
        elif pipeline_failure is not None or any(
            stage.status == "failed" for stage in record.stages.values()
        ):
            record.overall_pass = False

    record.restored = coerce_bool(nested_get(evaluation, "restoration.restored"))
    record.repository_clean = coerce_bool(nested_get(evaluation, "restoration.repository_clean"))

    backup_loc, backup_chars, measurement_scope = count_original_target_code(
        exp_dir, record.granularity
    )
    generated_loc, generated_chars = count_generated_code(exp_dir, record.code_done_reason)
    if backup_loc is None:
        backup_loc, backup_chars = count_configured_files(root, repository, record.source_files)
        if backup_loc is not None:
            measurement_scope = "whole_source_files_repository_fallback"
            record.data_quality_notes.append(
                "Target-granularity backup was unavailable; original size was measured "
                "from complete restored repository source file(s)."
            )
    record.original_loc = backup_loc
    record.original_chars = backup_chars
    record.original_measurement_scope = measurement_scope
    record.generated_loc = generated_loc
    record.generated_chars = generated_chars
    if record.original_loc and record.generated_loc is not None:
        record.generated_original_loc_ratio = record.generated_loc / record.original_loc

    elapsed = [
        stage.elapsed_seconds
        for stage in record.stages.values()
        if stage.elapsed_seconds is not None
    ]
    record.total_recorded_elapsed_seconds = sum(elapsed) if elapsed else None

    record.failure_stage = first_nonempty(
        nested_get(pipeline_failure, "stage", "failure_stage"),
        nested_get(batch_entry, "failure_stage", "stage"),
        nested_get(run_row, "failure_stage", "stage"),
    )
    record.failure_detail = first_nonempty(
        nested_get(pipeline_failure, "error", "message", "reason", "detail"),
        nested_get(batch_entry, "error", "message", "reason", "detail"),
        nested_get(run_row, "error", "message", "reason", "detail"),
    )

    if evaluation is None:
        record.data_quality_notes.append("No evaluation_manifest.json was found; fallback status sources were used.")
    if pipeline_path:
        record.data_quality_notes.append(
            f"Pipeline failure file: {pipeline_path.relative_to(root) if pipeline_path.is_relative_to(root) else pipeline_path}"
        )
    if record.overall_pass is None:
        record.data_quality_notes.append("Overall result could not be determined.")
    stage, category, detail = classify_failure(root, exp_dir, record, pipeline_failure)
    record.failure_stage = stage
    record.failure_category = category
    record.failure_category_ja = FAILURE_CATEGORY_LABELS[category]
    if detail:
        record.failure_detail = detail
    return record


def infer_legacy_pass(exp_dir: Path) -> tuple[bool | None, str]:
    evaluation, path = load_evaluation(exp_dir)
    if evaluation is not None:
        value = coerce_bool(nested_get(evaluation, "overall_pass", "passed", "status", "result"))
        if value is not None:
            return value, str(path) if path else "legacy evaluation"
    for report in sorted(exp_dir.rglob("*.md")) if exp_dir.is_dir() else []:
        text = read_text_if_exists(report)
        if re.search(r"\boverall\s*(?:result|status)?\s*[:|]\s*pass\b", text, re.IGNORECASE):
            return True, str(report)
        if re.search(r"\boverall\s*(?:result|status)?\s*[:|]\s*fail\b", text, re.IGNORECASE):
            return False, str(report)
    return None, "legacy fallback"


def parse_legacy_ini_writer(root: Path) -> TargetRecord | None:
    exp_dir = root / "experiments" / LEGACY_INI_WRITER["directory"]
    if not exp_dir.is_dir():
        return None
    inferred, source = infer_legacy_pass(exp_dir)
    overall = LEGACY_INI_WRITER["overall_pass"] if inferred is None else inferred
    record = TargetRecord(
        target_id=LEGACY_INI_WRITER["target_id"],
        run_id=LEGACY_INI_WRITER["run_id"],
        repository=LEGACY_INI_WRITER["repository"],
        target_name=LEGACY_INI_WRITER["target_name"],
        experiment_directory=str(exp_dir.relative_to(root)).replace("\\", "/"),
        legacy_format=True,
        result_source=source,
        granularity=LEGACY_INI_WRITER["granularity"],
        expected_direct_tests=LEGACY_INI_WRITER["expected_direct_tests"],
        expected_full_tests=LEGACY_INI_WRITER["expected_full_tests"],
        overall_pass=overall,
        failure_category="none" if overall else "unknown_failure",
        failure_category_ja=FAILURE_CATEGORY_LABELS["none" if overall else "unknown_failure"],
    )
    if inferred is None:
        record.data_quality_notes.append(
            "Legacy result used the fixed main-study definition because no standard manifest was available."
        )
    original_body = exp_dir / "backup" / "original_write_body.cpp"
    regenerated_body = exp_dir / "generated" / "regenerated_write_body.cpp"
    if original_body.is_file():
        original_text = read_text_if_exists(original_body)
        backup_loc, backup_chars = count_text_value(original_text)
        record.original_measurement_scope = "function_body_backup"
    else:
        backup_loc, backup_chars = count_tree_text(exp_dir / "backup")
        record.original_measurement_scope = "legacy_backup_tree_fallback"
        record.data_quality_notes.append(
            "The legacy function-body backup was unavailable; original size used "
            "the complete legacy backup tree."
        )
    if regenerated_body.is_file():
        generated_text = read_text_if_exists(regenerated_body)
        generated_loc, generated_chars = count_text_value(generated_text)
    else:
        generated_loc, generated_chars = count_tree_text(exp_dir / "generated")
        record.data_quality_notes.append(
            "The legacy regenerated function body was unavailable; generated size "
            "used the complete legacy generated tree."
        )
    record.original_loc = backup_loc
    record.original_chars = backup_chars
    record.generated_loc = generated_loc
    record.generated_chars = generated_chars
    if record.original_loc and record.generated_loc is not None:
        record.generated_original_loc_ratio = record.generated_loc / record.original_loc
    # The established legacy result is a full pass. Mark stages only when the
    # legacy files do not expose standard stage data.
    if overall:
        for stage_name in ("configure", "build", "direct_test", "full_test"):
            record.stages[stage_name] = StageResult(stage_name, "passed")
    for stage_name in STAGE_ORDER:
        record.stages.setdefault(stage_name, StageResult(stage_name, "not_recorded"))
    return record


def discover_records(root: Path, include_pilots: bool) -> list[TargetRecord]:
    target_rows = read_csv_rows(root / "manifests" / "targets.csv")
    run_rows = read_csv_rows(root / "manifests" / "runs.csv")
    records = [
        parse_standard_target(root, config_path, target_rows, run_rows)
        for config_path in list_standard_configs(root)
    ]
    legacy = parse_legacy_ini_writer(root)
    if legacy is not None:
        records.append(legacy)
    if include_pilots:
        pilot_root = root / "experiments" / "pilot-failures"
        for exp_dir in sorted(path for path in pilot_root.glob("*") if path.is_dir()):
            target_id = f"pilot::{exp_dir.name}"
            evaluation, evaluation_path = load_evaluation(exp_dir)
            pipeline, _ = load_pipeline_failure(exp_dir)
            record = TargetRecord(
                target_id=target_id,
                run_id=target_id,
                repository="pilot-failures",
                target_name=exp_dir.name,
                experiment_directory=str(exp_dir.relative_to(root)).replace("\\", "/"),
                legacy_format=True,
                result_source=str(evaluation_path) if evaluation_path else "pilot failure",
                overall_pass=coerce_bool(nested_get(evaluation, "overall_pass")) or False,
            )
            for stage_name in STAGE_ORDER:
                record.stages[stage_name] = StageResult(stage_name, "not_recorded")
            stage, category, detail = classify_failure(root, exp_dir, record, pipeline)
            record.failure_stage = stage
            record.failure_category = category
            record.failure_category_ja = FAILURE_CATEGORY_LABELS[category]
            record.failure_detail = detail
            records.append(record)
    records.sort(key=lambda item: (item.repository.lower(), item.target_id.lower()))
    return records


def validate_records(records: Sequence[TargetRecord], strict_summary: bool) -> list[str]:
    issues: list[str] = []
    ids = [record.target_id for record in records]
    duplicates = sorted(target_id for target_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        issues.append("Duplicate target IDs: " + ", ".join(duplicates))
    unknown = [record.target_id for record in records if record.overall_pass is None]
    if unknown:
        issues.append("Unknown overall result: " + ", ".join(unknown))
    for record in records:
        if record.granularity in {"class_span", "function"} and record.original_measurement_scope in {
            "whole_source_files_fallback",
            "whole_source_files_repository_fallback",
            "legacy_backup_tree_fallback",
        }:
            issues.append(
                f"{record.target_id}: original LOC could not be measured at target granularity "
                f"(scope={record.original_measurement_scope})"
            )
        if record.overall_pass is True:
            failed_stages = [
                name for name, stage in record.stages.items() if stage.status == "failed"
            ]
            if failed_stages:
                issues.append(
                    f"{record.target_id}: overall PASS conflicts with failed stage(s): {failed_stages}"
                )
        if record.retry_performed is True or record.automatic_repair_performed is True:
            issues.append(
                f"{record.target_id}: retry/automatic repair was recorded, violating the main protocol"
            )
        if (
            not record.legacy_format
            and record.code_done_reason == "stop"
            and record.generated_loc is None
        ):
            issues.append(
                f"{record.target_id}: code generation completed but generated code size could not be measured"
            )
        if record.design_done_reason == "stop" and record.stages.get(
            "design_generation", StageResult("design_generation", "not_recorded")
        ).status != "passed":
            issues.append(
                f"{record.target_id}: design done_reason=stop conflicts with generation stage status"
            )
        expected_code_status = (
            "failed" if record.code_done_reason == "length"
            else "passed" if record.code_done_reason == "stop"
            else None
        )
        if expected_code_status is not None and record.stages.get(
            "code_regeneration", StageResult("code_regeneration", "not_recorded")
        ).status != expected_code_status:
            issues.append(
                f"{record.target_id}: code done_reason conflicts with generation stage status"
            )
    total = len(records)
    passed = sum(record.overall_pass is True for record in records)
    failed = sum(record.overall_pass is False for record in records)
    if strict_summary and (total, passed, failed) != (EXPECTED_TOTAL, EXPECTED_PASS, EXPECTED_FAIL):
        issues.append(
            "Unexpected main-study summary: "
            f"actual total/pass/fail={total}/{passed}/{failed}, "
            f"expected={EXPECTED_TOTAL}/{EXPECTED_PASS}/{EXPECTED_FAIL}"
        )
    return issues


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def mean_or_none(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median_or_none(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def pearson_correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    dx = [x - mean_x for x in xs]
    dy = [y - mean_y for y in ys]
    denom = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    if denom == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / denom


def rankdata(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        end = index + 1
        while end < len(indexed) and indexed[end][1] == indexed[index][1]:
            end += 1
        average_rank = (index + 1 + end) / 2
        for cursor in range(index, end):
            ranks[indexed[cursor][0]] = average_rank
        index = end
    return ranks


def spearman_correlation(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) < 3 or len(xs) != len(ys):
        return None
    return pearson_correlation(rankdata(xs), rankdata(ys))


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    # Table [[a, b], [c, d]], fixed margins.
    row1 = a + b
    row2 = c + d
    col1 = a + c
    total = row1 + row2

    def probability(x: int) -> float:
        return math.comb(col1, x) * math.comb(total - col1, row1 - x) / math.comb(total, row1)

    lower = max(0, row1 - (total - col1))
    upper = min(row1, col1)
    observed = probability(a)
    return min(
        1.0,
        sum(probability(x) for x in range(lower, upper + 1) if probability(x) <= observed + 1e-12),
    )


def group_statistics(records: Sequence[TargetRecord], field_name: str) -> list[dict[str, Any]]:
    groups: dict[str, list[TargetRecord]] = defaultdict(list)
    for record in records:
        key = getattr(record, field_name) or "unknown"
        groups[str(key)].append(record)
    rows: list[dict[str, Any]] = []
    for group, items in sorted(groups.items()):
        total = len(items)
        passed = sum(item.overall_pass is True for item in items)
        failed = sum(item.overall_pass is False for item in items)
        low, high = wilson_interval(passed, total)
        rows.append(
            {
                "dimension": field_name,
                "group": group,
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate": passed / total if total else None,
                "wilson_95_low": low,
                "wilson_95_high": high,
            }
        )
    return rows


def quantitative_analysis(records: Sequence[TargetRecord]) -> dict[str, Any]:
    metrics = {
        "original_loc": lambda record: record.original_loc,
        "original_chars": lambda record: record.original_chars,
        "generated_loc": lambda record: record.generated_loc,
        "expected_direct_tests": lambda record: record.expected_direct_tests,
        "expected_full_tests": lambda record: record.expected_full_tests,
        "code_eval_count": lambda record: record.code_eval_count,
    }
    result: dict[str, Any] = {}
    for name, getter in metrics.items():
        available = [
            (float(value), 1.0 if record.overall_pass else 0.0)
            for record in records
            if (value := getter(record)) is not None and record.overall_pass is not None
        ]
        passed_values = [value for value, outcome in available if outcome == 1.0]
        failed_values = [value for value, outcome in available if outcome == 0.0]
        xs = [value for value, _ in available]
        ys = [outcome for _, outcome in available]
        result[name] = {
            "n": len(available),
            "pass_mean": mean_or_none(passed_values),
            "pass_median": median_or_none(passed_values),
            "fail_mean": mean_or_none(failed_values),
            "fail_median": median_or_none(failed_values),
            "point_biserial_r": pearson_correlation(xs, ys),
            "spearman_rho": spearman_correlation(xs, ys),
        }
    return result


def inferential_analysis(group_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    granularity = {
        row["group"]: row
        for row in group_rows
        if row["dimension"] == "granularity"
    }
    result: dict[str, Any] = {
        "note": "Exploratory only: targets are few and not guaranteed to be independent."
    }
    if "class_span" in granularity and "module_files" in granularity:
        left = granularity["class_span"]
        right = granularity["module_files"]
        result["class_span_vs_module_files_fisher_two_sided_p"] = fisher_two_sided(
            left["passed"], left["failed"], right["passed"], right["failed"]
        )
        result["class_span_table"] = [left["passed"], left["failed"]]
        result["module_files_table"] = [right["passed"], right["failed"]]
    return result


def stage_funnel(records: Sequence[TargetRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_name in STAGE_ORDER:
        statuses = Counter(record.stages.get(stage_name, StageResult(stage_name, "not_recorded")).status for record in records)
        reached = sum(statuses.get(status, 0) for status in ("passed", "failed"))
        rows.append(
            {
                "stage": stage_name,
                "reached": reached,
                "passed": statuses.get("passed", 0),
                "failed": statuses.get("failed", 0),
                "skipped": statuses.get("skipped", 0),
                "not_recorded_or_unknown": statuses.get("not_recorded", 0) + statuses.get("unknown", 0),
            }
        )
    return rows


def build_summary(records: Sequence[TargetRecord], validation_issues: Sequence[str]) -> dict[str, Any]:
    total = len(records)
    passed = sum(record.overall_pass is True for record in records)
    failed = sum(record.overall_pass is False for record in records)
    low, high = wilson_interval(passed, total)
    group_rows = group_statistics(records, "repository") + group_statistics(records, "granularity")
    failure_stage_counts = Counter(
        record.failure_stage or "none" for record in records if record.overall_pass is False
    )
    failure_category_counts = Counter(
        record.failure_category for record in records if record.overall_pass is False
    )
    normalization_total = sum(record.normalization_applied is not None for record in records)
    normalization_applied = sum(record.normalization_applied is True for record in records)
    normalized_pass = sum(
        record.normalization_applied is True and record.overall_pass is True for record in records
    )
    strict_failures = sum(record.strict_format_pass is False for record in records)
    truncations = sum(
        record.design_done_reason == "length" or record.code_done_reason == "length"
        for record in records
    )
    return {
        "schema_version": "1.0",
        "script_version": SCRIPT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total else None,
            "wilson_95_low": low,
            "wilson_95_high": high,
        },
        "group_statistics": group_rows,
        "stage_funnel": stage_funnel(records),
        "failure_stage_counts": dict(sorted(failure_stage_counts.items())),
        "failure_category_counts": dict(sorted(failure_category_counts.items())),
        "normalization": {
            "records_with_metadata": normalization_total,
            "normalization_applied": normalization_applied,
            "normalization_applied_and_passed": normalized_pass,
            "strict_format_failures": strict_failures,
        },
        "generation": {
            "done_reason_length_count": truncations,
            "design_stop_count": sum(record.design_done_reason == "stop" for record in records),
            "code_stop_count": sum(record.code_done_reason == "stop" for record in records),
        },
        "quantitative_analysis": quantitative_analysis(records),
        "inferential_analysis": inferential_analysis(group_rows),
        "data_quality": {
            "validation_issue_count": len(validation_issues),
            "validation_issues": list(validation_issues),
            "legacy_record_count": sum(record.legacy_format for record in records),
            "missing_original_loc_count": sum(record.original_loc is None for record in records),
            "missing_generated_loc_count": sum(record.generated_loc is None for record in records),
        },
    }


def json_ready_record(record: TargetRecord) -> dict[str, Any]:
    value = asdict(record)
    value["stages"] = {name: asdict(stage) for name, stage in record.stages.items()}
    return value


def format_percent(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value * 100:.{digits}f}%"


def format_number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def md_escape(value: Any) -> str:
    if value is None or value == "":
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(value) for value in row) + " |")
    return "\n".join(lines)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_summary_markdown(path: Path, records: Sequence[TargetRecord], summary: Mapping[str, Any]) -> None:
    overall = summary["overall"]
    inferential = summary.get("inferential_analysis", {})
    fisher_p = inferential.get("class_span_vs_module_files_fisher_two_sided_p")
    class_span_table = inferential.get("class_span_table", [None, None])
    module_files_table = inferential.get("module_files_table", [None, None])
    lines = [
        "# ラウンドトリップ実験の統合分析",
        "",
        f"生成日時（UTC）：{summary['generated_at_utc']}",
        "",
        "## 1．全体結果",
        "",
        f"主実験の対象は{overall['total']}件であり，PASSは{overall['passed']}件，FAILは{overall['failed']}件であった．",
        f"通過率は{format_percent(overall['pass_rate'])}であり，Wilson法による95%信頼区間は{format_percent(overall['wilson_95_low'])}〜{format_percent(overall['wilson_95_high'])}である．",
        "",
        markdown_table(
            ["総数", "PASS", "FAIL", "通過率", "95% CI"],
            [[
                overall["total"],
                overall["passed"],
                overall["failed"],
                format_percent(overall["pass_rate"]),
                f"{format_percent(overall['wilson_95_low'])}–{format_percent(overall['wilson_95_high'])}",
            ]],
        ),
        "",
        "## 2．対象別結果",
        "",
        markdown_table(
            ["リポジトリ", "対象", "粒度", "configure", "build", "直接", "全体", "判定", "失敗分類"],
            [
                [
                    record.repository,
                    record.target_name,
                    record.granularity,
                    record.stages.get("configure", StageResult("configure", "not_recorded")).status,
                    record.stages.get("build", StageResult("build", "not_recorded")).status,
                    record.stages.get("direct_test", StageResult("direct_test", "not_recorded")).status,
                    record.stages.get("full_test", StageResult("full_test", "not_recorded")).status,
                    "PASS" if record.overall_pass else "FAIL",
                    record.failure_category_ja if not record.overall_pass else "—",
                ]
                for record in records
            ],
        ),
        "",
        "## 3．リポジトリ別・粒度別結果",
        "",
        markdown_table(
            ["分類軸", "群", "総数", "PASS", "FAIL", "通過率", "95% CI"],
            [
                [
                    row["dimension"],
                    row["group"],
                    row["total"],
                    row["passed"],
                    row["failed"],
                    format_percent(row["pass_rate"]),
                    f"{format_percent(row['wilson_95_low'])}–{format_percent(row['wilson_95_high'])}",
                ]
                for row in summary["group_statistics"]
            ],
        ),
        "",
        "## 4．失敗段階",
        "",
        markdown_table(
            ["段階", "到達", "PASS", "FAIL", "SKIP", "未記録"],
            [
                [
                    row["stage"],
                    row["reached"],
                    row["passed"],
                    row["failed"],
                    row["skipped"],
                    row["not_recorded_or_unknown"],
                ]
                for row in summary["stage_funnel"]
            ],
        ),
        "",
        "## 5．失敗原因",
        "",
        markdown_table(
            ["失敗分類", "件数"],
            [
                [FAILURE_CATEGORY_LABELS.get(category, category), count]
                for category, count in sorted(
                    summary["failure_category_counts"].items(), key=lambda item: (-item[1], item[0])
                )
            ],
        ),
        "",
        markdown_table(
            ["対象", "失敗段階", "失敗分類", "代表的なエラー"],
            [
                [record.target_id, record.failure_stage, record.failure_category_ja, record.failure_detail]
                for record in records
                if record.overall_pass is False
            ],
        ),
        "",
        "## 6．コード規模・テスト数との関係",
        "",
        "相関係数は探索的な記述値である．対象数が17件と少なく，各対象も独立同分布とは限らないため，因果関係や一般的傾向の証明としては扱わない．",
        "また，コード規模，テスト数，生成トークン数はリポジトリおよび粒度と交絡している．特に全体テスト数はリポジトリごとにほぼ固定されているため，その相関をテスト数単独の効果とは解釈しない．",
        "",
        markdown_table(
            ["指標", "n", "PASS平均", "FAIL平均", "PASS中央値", "FAIL中央値", "点双列相関", "Spearman ρ"],
            [
                [
                    metric,
                    values["n"],
                    format_number(values["pass_mean"]),
                    format_number(values["fail_mean"]),
                    format_number(values["pass_median"]),
                    format_number(values["fail_median"]),
                    format_number(values["point_biserial_r"]),
                    format_number(values["spearman_rho"]),
                ]
                for metric, values in summary["quantitative_analysis"].items()
            ],
        ),
        "",
        "### 粒度間の探索的比較",
        "",
        "class_spanとmodule_filesのPASS／FAIL分布についてFisherの正確確率検定（両側）を行った．ただし，粒度とリポジトリ構成が強く対応しているため，粒度そのものの因果効果を示す検定ではない．",
        "",
        markdown_table(
            ["比較", "class_span PASS/FAIL", "module_files PASS/FAIL", "Fisher p（両側）"],
            [[
                "class_span vs module_files",
                f"{class_span_table[0]}/{class_span_table[1]}",
                f"{module_files_table[0]}/{module_files_table[1]}",
                format_number(fisher_p, digits=4),
            ]],
        ),
        "",
        "## 7．出力形式・正規化",
        "",
        markdown_table(
            ["メタデータあり", "正規化実施", "正規化後PASS", "strict format失敗", "length終了"],
            [[
                summary["normalization"]["records_with_metadata"],
                summary["normalization"]["normalization_applied"],
                summary["normalization"]["normalization_applied_and_passed"],
                summary["normalization"]["strict_format_failures"],
                summary["generation"]["done_reason_length_count"],
            ]],
        ),
        "",
        "## 8．解釈上の注意",
        "",
        "- テスト通過は既存テストスイートが観測する範囲での正当性を示すものであり，未検証機能を含む完全な意味的等価性を保証しない．",
        "- リポジトリ別・粒度別の対象数は均等ではなく，対象選定にも条件があるため，群間差は探索的に解釈する．",
        "- 粒度とリポジトリは独立ではない．class_spanの大部分はRISCV-Simulator，module_filesの大部分はEcho-Web-Serverであるため，両者の通過率差を粒度だけに帰属させない．",
        "- original_locとgenerated_locは置換粒度をそろえて測定する．module_filesは対象ファイル全体，class_spanは抽出したクラス定義，旧形式のfunctionは対象関数本体を数える．",
        "- generated_locは完全なコード再生成が得られた対象だけを測定し，done_reason=lengthの不完全出力は除外する．",
        "- BlockDequeは直接テスト中にハングして外部停止した．デッドロックの可能性はあるが，スレッドダンプ等で厳密に確定していないため，『ハング・外部停止（デッドロック疑い）』と記録する．",
        "- 旧形式のINIWriter実験は標準ハーネス外であるため，利用できるメタデータが他の16対象より少ない可能性がある．",
        "- 感度分析やpilot-failuresは主実験の17件には含めていない．",
        "",
        "## 9．データ品質",
        "",
        f"検証上の問題件数：{summary['data_quality']['validation_issue_count']}",
    ]
    if summary["data_quality"]["validation_issues"]:
        lines.extend(["", *[f"- {issue}" for issue in summary["data_quality"]["validation_issues"]]])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_thesis_tables(path: Path, records: Sequence[TargetRecord], summary: Mapping[str, Any]) -> None:
    lines = [
        "# 論文掲載用集計表",
        "",
        "## 表A　対象別の主実験結果",
        "",
        markdown_table(
            ["No.", "Repository", "Target", "Granularity", "Direct tests", "Full tests", "Result", "Failure stage", "Failure cause"],
            [
                [
                    index,
                    record.repository,
                    record.target_name,
                    record.granularity,
                    record.expected_direct_tests,
                    record.expected_full_tests,
                    "PASS" if record.overall_pass else "FAIL",
                    record.failure_stage,
                    record.failure_category_ja if not record.overall_pass else "—",
                ]
                for index, record in enumerate(records, start=1)
            ],
        ),
        "",
        "## 表B　リポジトリ別結果",
        "",
        markdown_table(
            ["Repository", "N", "PASS", "FAIL", "Pass rate"],
            [
                [row["group"], row["total"], row["passed"], row["failed"], format_percent(row["pass_rate"])]
                for row in summary["group_statistics"]
                if row["dimension"] == "repository"
            ],
        ),
        "",
        "## 表C　粒度別結果",
        "",
        markdown_table(
            ["Granularity", "N", "PASS", "FAIL", "Pass rate"],
            [
                [row["group"], row["total"], row["passed"], row["failed"], format_percent(row["pass_rate"])]
                for row in summary["group_statistics"]
                if row["dimension"] == "granularity"
            ],
        ),
        "",
        "## 表D　粒度間の探索的比較",
        "",
        markdown_table(
            ["Comparison", "Group 1 PASS/FAIL", "Group 2 PASS/FAIL", "Fisher p (two-sided)"],
            [[
                "class_span vs module_files",
                f"{summary.get('inferential_analysis', {}).get('class_span_table', [None, None])[0]}/{summary.get('inferential_analysis', {}).get('class_span_table', [None, None])[1]}",
                f"{summary.get('inferential_analysis', {}).get('module_files_table', [None, None])[0]}/{summary.get('inferential_analysis', {}).get('module_files_table', [None, None])[1]}",
                format_number(summary.get('inferential_analysis', {}).get('class_span_vs_module_files_fisher_two_sided_p'), digits=4),
            ]],
        ),
        "",
        "## 表E　失敗原因別件数",
        "",
        markdown_table(
            ["Failure cause", "Count"],
            [
                [FAILURE_CATEGORY_LABELS.get(category, category), count]
                for category, count in sorted(summary["failure_category_counts"].items(), key=lambda item: (-item[1], item[0]))
            ],
        ),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def svg_bar_chart(
    path: Path,
    title: str,
    labels: Sequence[str],
    values: Sequence[float],
    value_suffix: str = "",
) -> None:
    width = 960
    margin_left = 240
    margin_right = 80
    margin_top = 90
    row_height = 52
    bar_height = 28
    height = margin_top + row_height * len(labels) + 70
    max_value = max(values) if values else 1.0
    if max_value <= 0:
        max_value = 1.0
    plot_width = width - margin_left - margin_right
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2}" y="42" text-anchor="middle" font-family="sans-serif" font-size="24" font-weight="bold">{xml_escape(title)}</text>',
    ]
    for index, (label, value) in enumerate(zip(labels, values)):
        y = margin_top + index * row_height
        bar_width = plot_width * value / max_value
        elements.extend(
            [
                f'<text x="{margin_left-12}" y="{y+bar_height-6}" text-anchor="end" font-family="sans-serif" font-size="16">{xml_escape(label)}</text>',
                f'<rect x="{margin_left}" y="{y}" width="{bar_width:.2f}" height="{bar_height}" fill="#4c78a8"/>',
                f'<text x="{margin_left+bar_width+8:.2f}" y="{y+bar_height-6}" font-family="sans-serif" font-size="16">{value:g}{xml_escape(value_suffix)}</text>',
            ]
        )
    elements.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(elements) + "\n", encoding="utf-8", newline="\n")


def xml_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_outputs(
    root: Path,
    output_dir: Path,
    records: Sequence[TargetRecord],
    summary: Mapping[str, Any],
    make_svg: bool,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    flat_rows = [record.flat_dict() for record in records]
    generated: list[Path] = []

    detailed_csv = output_dir / "main_results.csv"
    write_csv(detailed_csv, flat_rows)
    generated.append(detailed_csv)

    detailed_json = output_dir / "main_results.json"
    write_json(detailed_json, {"records": [json_ready_record(record) for record in records]})
    generated.append(detailed_json)

    summary_json = output_dir / "summary.json"
    write_json(summary_json, summary)
    generated.append(summary_json)

    summary_md = output_dir / "summary.md"
    write_summary_markdown(summary_md, records, summary)
    generated.append(summary_md)

    thesis_md = output_dir / "thesis_tables.md"
    write_thesis_tables(thesis_md, records, summary)
    generated.append(thesis_md)

    failure_rows = [
        {
            "target_id": record.target_id,
            "repository": record.repository,
            "target_name": record.target_name,
            "failure_stage": record.failure_stage,
            "failure_category": record.failure_category,
            "failure_category_ja": record.failure_category_ja,
            "failure_detail": record.failure_detail,
            "design_done_reason": record.design_done_reason,
            "code_done_reason": record.code_done_reason,
            "normalization_applied": record.normalization_applied,
        }
        for record in records
        if record.overall_pass is False
    ]
    failure_csv = output_dir / "failure_analysis.csv"
    write_csv(failure_csv, failure_rows)
    generated.append(failure_csv)

    group_csv = output_dir / "group_statistics.csv"
    write_csv(group_csv, summary["group_statistics"])
    generated.append(group_csv)

    funnel_csv = output_dir / "stage_funnel.csv"
    write_csv(funnel_csv, summary["stage_funnel"])
    generated.append(funnel_csv)

    if make_svg:
        figures = output_dir / "figures"
        overall_svg = figures / "overall_result.svg"
        svg_bar_chart(
            overall_svg,
            "Main-study results",
            ["PASS", "FAIL"],
            [summary["overall"]["passed"], summary["overall"]["failed"]],
        )
        generated.append(overall_svg)

        repo_rows = [row for row in summary["group_statistics"] if row["dimension"] == "repository"]
        repo_svg = figures / "repository_pass_rate.svg"
        svg_bar_chart(
            repo_svg,
            "Pass rate by repository",
            [row["group"] for row in repo_rows],
            [round(row["pass_rate"] * 100, 1) for row in repo_rows],
            "%",
        )
        generated.append(repo_svg)

        category_items = sorted(
            summary["failure_category_counts"].items(), key=lambda item: (-item[1], item[0])
        )
        category_svg = figures / "failure_categories.svg"
        svg_bar_chart(
            category_svg,
            "Failure categories",
            [FAILURE_CATEGORY_LABELS.get(key, key) for key, _ in category_items],
            [value for _, value in category_items],
        )
        generated.append(category_svg)

    manifest_path = output_dir / "analysis_manifest.json"
    manifest = {
        "schema_version": "1.0",
        "script_version": SCRIPT_VERSION,
        "project_root": str(root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "main_target_count": len(records),
        "output_files": [],
        "read_only_analysis": True,
        "external_commands_executed": False,
        "llm_called": False,
        "docker_called": False,
        "tests_called": False,
    }
    for path in generated:
        manifest["output_files"].append(
            {
                "path": str(path.relative_to(root)).replace("\\", "/") if path.is_relative_to(root) else str(path),
                "sha256": hash_file(path),
            }
        )
    write_json(manifest_path, manifest)
    generated.append(manifest_path)
    return generated


def main() -> int:
    args = parse_args()
    try:
        root = infer_project_root(args.project_root)
        output_dir = (
            args.output_dir.expanduser().resolve()
            if args.output_dir is not None
            else root / "reports" / "analysis"
        )
        records = discover_records(root, args.include_pilot_failures)
        validation_issues = validate_records(
            records,
            strict_summary=not args.allow_unexpected_summary and not args.include_pilot_failures,
        )
        fatal_issues = [
            issue
            for issue in validation_issues
            if issue.startswith("Duplicate target IDs")
            or issue.startswith("Unknown overall result")
            or issue.startswith("Unexpected main-study summary")
            or "violating the main protocol" in issue
        ]
        if fatal_issues:
            raise AnalysisError("\n".join(fatal_issues))
        summary = build_summary(records, validation_issues)
        generated = write_outputs(
            root,
            output_dir,
            records,
            summary,
            make_svg=not args.no_svg,
        )
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # Guardrail for reproducible CLI failure reporting.
        print(f"UNEXPECTED ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3

    overall = summary["overall"]
    print(
        "Analysis complete: "
        f"total={overall['total']}, passed={overall['passed']}, failed={overall['failed']}, "
        f"pass_rate={overall['pass_rate'] * 100:.1f}%"
    )
    print(f"Output directory: {output_dir}")
    for path in generated:
        print(f"  {path.relative_to(root) if path.is_relative_to(root) else path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
