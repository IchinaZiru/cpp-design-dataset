from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


ERROR_PATTERNS = [
    re.compile(r"fatal error:", re.IGNORECASE),
    re.compile(r"\berror:", re.IGNORECASE),
    re.compile(r"undefined reference", re.IGNORECASE),
    re.compile(r"multiple definition", re.IGNORECASE),
]

CONSEQUENCE_PATTERNS = [
    re.compile(r"^\s*(?:g?make)(?:\[\d+\])?:\s+\*\*\*", re.IGNORECASE),
    re.compile(r"^\s*ninja:\s+build stopped", re.IGNORECASE),
    re.compile(r"collect2:\s+error:\s+ld returned", re.IGNORECASE),
]

FAILED_TEST_RE = re.compile(r"^\s*\[\s*FAILED\s*\]\s+(.+?)(?:\s+\(|$)")


def boolish(value: Any) -> bool | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return value if isinstance(value, dict) else {}


def classify_build_line(line: str) -> str:
    lower = line.lower()
    syntax_tokens = [
        "expected ';'",
        'expected ";"',
        "expected '{'",
        'expected "{"',
        "expected ')'",
        'expected ")"',
        "expected primary-expression",
        "stray ",
        "missing terminating",
        "unterminated",
    ]
    if any(token in lower for token in syntax_tokens):
        return "syntax_error"
    if "redefinition" in lower or "multiple definition" in lower:
        return "duplicate_definition"
    missing_tokens = [
        "was not declared",
        "has not been declared",
        "no such file or directory",
        "undefined reference",
        "does not name a type",
    ]
    if any(token in lower for token in missing_tokens):
        return "missing_definition_or_dependency"
    interface_tokens = [
        "no matching function",
        "cannot convert",
        "could not convert",
        "invalid conversion",
        "no member named",
        "has no member named",
        "has no member",
        "request for member",
        "invalid use of",
        "conflicting return type",
        "no viable",
        "invalid operands",
    ]
    if any(token in lower for token in interface_tokens):
        return "type_or_interface_mismatch"
    return "other_build_failure"


def extract_decisive_error(path: Path, context_lines: int = 4) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    for index, line in enumerate(lines):
        if any(p.search(line) for p in CONSEQUENCE_PATTERNS):
            continue
        if not any(p.search(line) for p in ERROR_PATTERNS):
            continue
        start = max(0, index - context_lines)
        end = min(len(lines), index + context_lines + 1)
        return {
            "file": path.as_posix(),
            "line_number": index + 1,
            "line": line,
            "classification_hint": classify_build_line(line),
            "context": lines[start:end],
        }
    return None


def extract_failed_tests(paths: list[Path]) -> tuple[list[str], dict[str, Any] | None]:
    failed: list[str] = []
    first_context: dict[str, Any] | None = None
    for path in paths:
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            match = FAILED_TEST_RE.match(line)
            if match:
                name = match.group(1).strip()
                if name not in failed:
                    failed.append(name)
            if first_context is None and (
                line.strip() == "Failure"
                or "Expected equality" in line
                or line.lstrip().startswith("Expected:")
                or line.lstrip().startswith("Actual:")
            ):
                start = max(0, index - 5)
                end = min(len(lines), index + 8)
                first_context = {
                    "file": path.as_posix(),
                    "line_number": index + 1,
                    "context": lines[start:end],
                }
    return failed, first_context


def infer_stage(row: dict[str, str]) -> str:
    if row.get("failed_stage"):
        return row["failed_stage"]
    for stage, column in [
        ("configure", "configure_passed"),
        ("build", "build_passed"),
        ("direct_test", "direct_test_passed"),
        ("full_test", "full_test_passed"),
    ]:
        value = boolish(row.get(column))
        if value is False:
            return stage
    return "unknown"


def experiment_root(project_root: Path, row: dict[str, str]) -> Path:
    return project_root / "experiments" / row["experiment_id"]


def collect_record(project_root: Path, row: dict[str, str]) -> dict[str, Any]:
    stage = infer_stage(row)
    run_id = row.get("run_id", "")
    log_dir = project_root / "logs" / "roundtrip_v2" / run_id
    exp_root = experiment_root(project_root, row)
    record: dict[str, Any] = {
        "pair_id": row.get("pair_id"),
        "condition": row.get("condition"),
        "target_id": row.get("target_id"),
        "run_id": run_id,
        "experiment_id": row.get("experiment_id"),
        "terminal_artifact_kind": row.get("terminal_artifact_kind"),
        "failure_stage": stage,
        "artifact_path": row.get("artifact_path"),
        "restored": boolish(row.get("restored")),
        "log_directory": log_dir.as_posix(),
        "log_directory_exists": log_dir.is_dir(),
    }

    if stage == "code_regeneration":
        metadata = read_json(exp_root / "raw_output" / "code_regeneration_metadata.json")
        pipeline = read_json(exp_root / "evaluation" / "pipeline_failure.json")
        record["classification_hint"] = (
            "output_truncation"
            if metadata.get("done_reason") == "length"
            else "code_regeneration_failure"
        )
        record["done_reason"] = metadata.get("done_reason")
        record["eval_count"] = metadata.get("eval_count")
        record["error"] = pipeline.get("error") or row.get("error")
        return record

    if stage == "build":
        candidates = []
        for name in ("build.stderr.txt", "build.stdout.txt"):
            evidence = extract_decisive_error(log_dir / name)
            if evidence is not None:
                evidence["file"] = str(Path(evidence["file"]).relative_to(project_root))
                candidates.append(evidence)
        record["decisive_error_candidates"] = candidates
        if len(candidates) == 1:
            record["classification_hint"] = candidates[0]["classification_hint"]
        elif candidates:
            record["classification_hint"] = "review_multiple_stream_candidates"
        else:
            record["classification_hint"] = "missing_local_build_log_or_no_error_match"
        return record

    if stage in {"direct_test", "full_test"}:
        names = [f"{stage}.stdout.txt", f"{stage}.stderr.txt"]
        failed_tests, context = extract_failed_tests([log_dir / name for name in names])
        record["classification_hint"] = f"{stage}_failure"
        record["failed_tests"] = failed_tests
        record["first_assertion_context"] = context
        return record

    if stage == "configure":
        candidates = []
        for name in ("configure.stderr.txt", "configure.stdout.txt"):
            evidence = extract_decisive_error(log_dir / name)
            if evidence is not None:
                evidence["file"] = str(Path(evidence["file"]).relative_to(project_root))
                candidates.append(evidence)
        record["classification_hint"] = "configure_failure"
        record["decisive_error_candidates"] = candidates
        return record

    record["classification_hint"] = "unknown"
    return record


def write_markdown(path: Path, records: list[dict[str, Any]]) -> None:
    counts: dict[str, dict[str, int]] = {}
    for record in records:
        condition = "rag" if "rag" in str(record["condition"]).lower() and "non_rag" not in str(record["condition"]).lower() else "non_rag"
        counts.setdefault(condition, {})
        stage = str(record["failure_stage"])
        counts[condition][stage] = counts[condition].get(stage, 0) + 1

    lines = [
        "# Formal v2 failure evidence extracted from local logs",
        "",
        "This report is evidence extraction only. It does not rerun LLM, build, or tests, and it does not modify generated artifacts.",
        "",
        "## Stage counts",
        "",
    ]
    for condition in ("non_rag", "rag"):
        stage_text = ", ".join(f"{k}={v}" for k, v in sorted(counts.get(condition, {}).items())) or "none"
        lines.append(f"- {condition}: {stage_text}")

    lines += [
        "",
        "## Records",
        "",
        "| pair | condition | stage | hint | failed tests / decisive error |",
        "|---|---|---|---|---|",
    ]
    for record in records:
        detail = ""
        if record.get("failed_tests"):
            detail = ", ".join(record["failed_tests"])
        elif record.get("decisive_error_candidates"):
            detail = " / ".join(c["line"] for c in record["decisive_error_candidates"])
        elif record.get("error"):
            detail = str(record["error"])
        detail = detail.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {record.get('pair_id','')} | {record.get('condition','')} | "
            f"{record.get('failure_stage','')} | {record.get('classification_hint','')} | {detail} |"
        )

    lines += ["", "## Detailed evidence", ""]
    for record in records:
        lines.append(f"### {record.get('pair_id')} / {record.get('condition')}")
        lines.append("")
        lines.append(f"- stage: `{record.get('failure_stage')}`")
        lines.append(f"- hint: `{record.get('classification_hint')}`")
        lines.append(f"- run_id: `{record.get('run_id')}`")
        lines.append(f"- local log directory exists: `{record.get('log_directory_exists')}`")
        if record.get("done_reason") is not None:
            lines.append(f"- done_reason: `{record.get('done_reason')}`")
            lines.append(f"- eval_count: `{record.get('eval_count')}`")
        if record.get("failed_tests"):
            lines.append(f"- failed tests: `{', '.join(record['failed_tests'])}`")
        if record.get("first_assertion_context"):
            lines.append("")
            lines.append("```text")
            lines.extend(record["first_assertion_context"]["context"])
            lines.append("```")
        for candidate in record.get("decisive_error_candidates", []):
            lines.append("")
            lines.append(f"Candidate from `{candidate['file']}` line {candidate['line_number']}:")
            lines.append("")
            lines.append("```text")
            lines.extend(candidate["context"])
            lines.append("```")
        if record.get("error"):
            lines.append("")
            lines.append(f"- pipeline error: `{record['error']}`")
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("analysis/formal_v2/formal_results.csv"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("analysis/formal_v2/failure_evidence_local.json"),
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("analysis/formal_v2/failure_evidence_local.md"),
    )
    args = parser.parse_args()

    root = args.project_root.resolve()
    results_path = args.results if args.results.is_absolute() else root / args.results
    output_json = args.output_json if args.output_json.is_absolute() else root / args.output_json
    output_md = args.output_md if args.output_md.is_absolute() else root / args.output_md

    with results_path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    failures = [row for row in rows if boolish(row.get("overall_pass")) is not True]
    records = [collect_record(root, row) for row in failures]

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source_results": str(results_path.relative_to(root)),
                "failure_count": len(records),
                "records": records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_markdown(output_md, records)

    missing_logs = sum(1 for record in records if not record["log_directory_exists"])
    print(f"Extracted {len(records)} failed-run records")
    print(f"Missing local log directories: {missing_logs}")
    print(output_json)
    print(output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
