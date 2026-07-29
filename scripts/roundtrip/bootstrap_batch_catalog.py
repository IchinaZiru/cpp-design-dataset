from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


EXPECTED_TARGET_COUNT = 17
SOURCE_SUFFIXES = r"(?:cpp|cxx|hpp|hxx|cc|hh|c|h)"


@dataclass
class TargetRecord:
    repository_id: str
    target_id: str
    target_name: str
    adoption_status: str = ""
    granularity: str = ""
    source_descriptor: str = ""
    test_descriptor: str = ""
    source_files: list[str] | None = None
    test_files: list[str] | None = None
    direct_test_count: int | None = None
    direct_test_filter: str = ""
    direct_test_names: list[str] | None = None
    expected_full_tests: int | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_files"] = self.source_files or []
        value["test_files"] = self.test_files or []
        value["direct_test_names"] = self.direct_test_names or []
        return value


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def slug(text: str) -> str:
    value = text.strip().lower()
    value = re.sub(r"::", "-", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "target"


def split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def parse_markdown_tables(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    tables: list[dict[str, Any]] = []
    index = 0
    while index + 1 < len(lines):
        header = split_markdown_row(lines[index])
        separator = split_markdown_row(lines[index + 1])
        if (
            header
            and separator
            and len(header) == len(separator)
            and is_separator_row(separator)
        ):
            rows: list[list[str]] = []
            index += 2
            while index < len(lines):
                cells = split_markdown_row(lines[index])
                if not cells or len(cells) != len(header):
                    break
                rows.append(cells)
                index += 1
            tables.append({"header": header, "rows": rows})
            continue
        index += 1
    return tables


def find_column(header: list[str], keywords: list[str]) -> int | None:
    lowered = [cell.lower() for cell in header]
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for index, cell in enumerate(lowered):
            if keyword_lower in cell:
                return index
    return None


def parse_count(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def clean_target_name(value: str) -> str:
    return value.strip().strip("`").strip("*").strip()


def extract_source_paths(value: str) -> list[str]:
    paths = re.findall(
        (
            rf"(?<![A-Za-z0-9_.-])"
            rf"([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.{SOURCE_SUFFIXES})"
            rf"(?![A-Za-z0-9_.-])"
        ),
        value,
    )
    result: list[str] = []
    for path in paths:
        if path not in result:
            result.append(path)
    return result


def merge_record(
    records: dict[tuple[str, str], TargetRecord],
    repository_id: str,
    target_name: str,
    **updates: Any,
) -> TargetRecord:
    cleaned = clean_target_name(target_name)
    key = (repository_id, cleaned.lower())
    if key not in records:
        records[key] = TargetRecord(
            repository_id=repository_id,
            target_id=f"{slug(repository_id)}-{slug(cleaned)}",
            target_name=cleaned,
            source_files=[],
            test_files=[],
            direct_test_names=[],
        )
    record = records[key]
    for field, value in updates.items():
        if value in (None, "", []):
            continue
        current = getattr(record, field)
        if current in (None, "", []):
            setattr(record, field, value)
        elif field == "notes" and value not in current:
            setattr(record, field, f"{current}; {value}")
    return record


def detect_repository_id(path: Path) -> str:
    name = path.stem.lower()
    if "echo-web-server" in name:
        return "Echo-Web-Server"
    if "ini-cpp" in name:
        return "ini-cpp"
    if "riscv-simulator" in name:
        return "RISCV-Simulator"
    return path.stem.replace("_report", "")


def detect_full_test_count(text: str) -> int | None:
    patterns = [
        r"全GoogleTest[^\n]*?(\d+)\s*/\s*\1",
        r"CTest[^\n]*?(\d+)\s*/\s*\1",
        r"全(\d+)件",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def parse_report(
    path: Path,
    records: dict[tuple[str, str], TargetRecord],
) -> None:
    repository_id = detect_repository_id(path)
    text = read_text(path)
    tables = parse_markdown_tables(text)
    expected_full_tests = detect_full_test_count(text)

    for table in tables:
        header = table["header"]
        rows = table["rows"]
        target_col = find_column(header, ["target", "対象"])
        if target_col is None:
            continue

        judgment_col = find_column(header, ["判定", "status"])
        granularity_col = find_column(header, ["granularity", "scope", "粒度"])
        source_col = find_column(header, ["宣言・実装", "source", "実装"])
        test_col = find_column(header, ["対応test", "test file", "テスト"])
        selected_count_col = find_column(header, ["選択数", "discovered"])
        selected_names_col = find_column(header, ["選択テスト名", "test names"])
        filter_col = find_column(header, ["filter"])

        for row in rows:
            target_name = clean_target_name(row[target_col])
            if not target_name or target_name.lower() in {"target", "対象"}:
                continue

            updates: dict[str, Any] = {
                "expected_full_tests": expected_full_tests,
            }
            if judgment_col is not None:
                updates["adoption_status"] = row[judgment_col]
            if granularity_col is not None:
                updates["granularity"] = row[granularity_col]
            if source_col is not None:
                source_descriptor = row[source_col]
                updates["source_descriptor"] = source_descriptor
                updates["source_files"] = extract_source_paths(source_descriptor)
            if test_col is not None:
                test_descriptor = row[test_col]
                updates["test_descriptor"] = test_descriptor
                updates["test_files"] = extract_source_paths(test_descriptor)
            if selected_count_col is not None:
                updates["direct_test_count"] = parse_count(row[selected_count_col])
            if selected_names_col is not None:
                names = [
                    item.strip()
                    for item in row[selected_names_col].split(",")
                    if item.strip()
                ]
                updates["direct_test_names"] = names
                updates["direct_test_filter"] = ":".join(names)
            if filter_col is not None:
                filter_text = row[filter_col].strip("` ")
                updates["direct_test_filter"] = filter_text
                if updates.get("direct_test_count") is None:
                    updates["direct_test_count"] = parse_count(filter_text)

            merge_record(records, repository_id, target_name, **updates)

    for match in re.finditer(
        r"^\s*-\s+\*\*(.+?)\s+[—-]\s+([^*]+)\*\*",
        text,
        flags=re.MULTILINE,
    ):
        merge_record(
            records,
            repository_id,
            clean_target_name(match.group(1)),
            adoption_status=match.group(2).strip(),
            expected_full_tests=expected_full_tests,
        )

    for match in re.finditer(
        r"^\|\s*([A-Za-z][A-Za-z0-9_-]*)\s*\|\s*"
        r"(条件付き採用|採用|除外)\s*\|\s*(.*?)\s*\|$",
        text,
        flags=re.MULTILINE,
    ):
        merge_record(
            records,
            repository_id,
            match.group(1),
            adoption_status=match.group(2),
            notes=match.group(3),
            expected_full_tests=expected_full_tests,
        )

    if repository_id == "ini-cpp":
        for target_name in ("INIReader", "INIWriter"):
            key = (repository_id, target_name.lower())
            if key in records:
                record = records[key]
                record.source_descriptor = record.source_descriptor or "ini/ini.h"
                record.source_files = record.source_files or ["ini/ini.h"]


def normalize_record(record: TargetRecord) -> None:
    value = record.granularity.lower()
    if record.repository_id == "Echo-Web-Server":
        if "module" in value:
            record.granularity = "module_files"
        elif "class" in value:
            record.granularity = "class_span"
    elif record.repository_id == "ini-cpp":
        if "class" in value or record.target_name in {"INIReader", "INIWriter"}:
            record.granularity = "class_span"

    if not record.direct_test_filter and record.direct_test_names:
        record.direct_test_filter = ":".join(record.direct_test_names)


def metadata_missing(record: TargetRecord) -> list[str]:
    missing: list[str] = []
    if not record.granularity:
        missing.append("granularity")
    if not record.source_files:
        missing.append("source_files")
    if not record.direct_test_filter and not record.direct_test_names:
        missing.append("direct_test_filter")
    if record.direct_test_count is None:
        missing.append("expected_direct_tests")
    if record.expected_full_tests is None:
        missing.append("expected_full_tests")
    return missing


def execution_missing(record: TargetRecord) -> list[str]:
    missing = metadata_missing(record)
    missing.extend(
        [
            "verified replacement locator",
            "fixed scaffold/dependency context",
            "verified Docker image",
            "configure/build/test commands",
            "stage_commands",
        ]
    )
    return missing


def build_draft_config(record: TargetRecord) -> dict[str, Any]:
    return {
        "schema_version": "2.0",
        "enabled": False,
        "target_id": record.target_id,
        "experiment_id": f"{record.target_id}-roundtrip",
        "repository_id": record.repository_id,
        "target_name": record.target_name,
        "adoption_status": record.adoption_status,
        "granularity": record.granularity,
        "source_files": record.source_files or [],
        "test_files": record.test_files or [],
        "source_descriptor_from_report": record.source_descriptor,
        "locator": {},
        "design_input": {
            "source_files": record.source_files or [],
            "extra_context_files": [],
        },
        "regeneration_input": {
            "fixed_scaffold_files": [],
            "dependency_context_files": [],
            "output_mode": (
                "file_map_json"
                if record.granularity == "module_files"
                else "single_code"
            ),
        },
        "evaluation": {
            "direct_test_filter": record.direct_test_filter,
            "direct_test_names": record.direct_test_names or [],
            "expected_direct_tests": record.direct_test_count,
            "expected_full_tests": record.expected_full_tests,
            "docker_image": "",
            "configure_command": "",
            "build_command": "",
            "direct_test_command": "",
            "full_test_command": "",
            "ctest_command": "",
        },
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
        "stage_commands": {},
        "readiness": {
            "metadata_complete": not metadata_missing(record),
            "metadata_missing": metadata_missing(record),
            "execution_ready": False,
            "execution_missing": execution_missing(record),
        },
        "notes": record.notes,
    }


def remove_stale_drafts(
    target_dir: Path,
    expected_paths: set[Path],
) -> list[str]:
    removed: list[str] = []
    for path in target_dir.glob("*.draft.json"):
        if path in expected_paths:
            continue
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError:
            continue
        if data.get("enabled") is False:
            path.unlink()
            removed.append(path.name)
    return removed


def write_csv(path: Path, records: list[TargetRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "repository_id",
        "target_id",
        "target_name",
        "adoption_status",
        "granularity",
        "source_files",
        "test_files",
        "direct_test_count",
        "direct_test_filter",
        "expected_full_tests",
        "metadata_complete",
        "metadata_missing",
        "execution_ready",
        "execution_missing",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "repository_id": record.repository_id,
                    "target_id": record.target_id,
                    "target_name": record.target_name,
                    "adoption_status": record.adoption_status,
                    "granularity": record.granularity,
                    "source_files": ";".join(record.source_files or []),
                    "test_files": ";".join(record.test_files or []),
                    "direct_test_count": record.direct_test_count,
                    "direct_test_filter": record.direct_test_filter,
                    "expected_full_tests": record.expected_full_tests,
                    "metadata_complete": not metadata_missing(record),
                    "metadata_missing": ";".join(metadata_missing(record)),
                    "execution_ready": False,
                    "execution_missing": ";".join(execution_missing(record)),
                    "notes": record.notes,
                }
            )


def build_readiness_markdown(
    records: list[TargetRecord],
    excluded: list[TargetRecord],
    removed_stale: list[str],
) -> str:
    metadata_complete_count = sum(not metadata_missing(record) for record in records)
    lines = [
        "# Round-trip batch readiness",
        "",
        "既存metadataから対象情報を抽出した結果である．",
        "この段階ではLLM生成・ソース置換・テスト実行を行わない．",
        "",
        f"- 実験対象数: **{len(records)}**",
        f"- 想定対象数: **{EXPECTED_TARGET_COUNT}**",
        f"- metadata自動抽出完了: **{metadata_complete_count}**",
        f"- 実行設定完了: **0**",
        f"- 除外対象: **{len(excluded)}**",
        "",
        "| repository | target | adoption | granularity | source files | direct tests | full tests | metadata | execution |",
        "|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for record in records:
        metadata_ok = not metadata_missing(record)
        lines.append(
            "| "
            + " | ".join(
                [
                    record.repository_id,
                    record.target_name,
                    record.adoption_status or "N/A",
                    record.granularity or "N/A",
                    str(len(record.source_files or [])),
                    (
                        str(record.direct_test_count)
                        if record.direct_test_count is not None
                        else "N/A"
                    ),
                    (
                        str(record.expected_full_tests)
                        if record.expected_full_tests is not None
                        else "N/A"
                    ),
                    "COMPLETE" if metadata_ok else "INCOMPLETE",
                    "DRAFT",
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 除外対象",
            "",
        ]
    )
    if excluded:
        for record in excluded:
            lines.append(
                f"- `{record.repository_id}/{record.target_name}`: "
                f"{record.adoption_status}"
            )
    else:
        lines.append("- なし")

    if removed_stale:
        lines.extend(
            [
                "",
                "## 削除した古いdraft",
                "",
                *[f"- `{name}`" for name in removed_stale],
            ]
        )

    if len(records) != EXPECTED_TARGET_COUNT:
        lines.extend(
            [
                "",
                "## 警告",
                "",
                f"対象数が{EXPECTED_TARGET_COUNT}件と一致しないため，"
                "実行設定作成へ進まないこと．",
            ]
        )

    lines.extend(
        [
            "",
            "## 状態の意味",
            "",
            "- `metadata COMPLETE`: レポートから対象・粒度・テスト数等を抽出できた．",
            "- `execution DRAFT`: 置換境界と実行コマンドが未検証であり，まだ実験できない．",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the 17-target catalog from metadata reports."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    metadata_dir = project_root / "metadata"
    config_dir = project_root / "configs" / "roundtrip"
    target_dir = config_dir / "targets"
    report_dir = project_root / "reports" / "batch"

    report_paths = sorted(metadata_dir.glob("*_report.md"))
    if not report_paths:
        raise FileNotFoundError(f"No *_report.md files found in {metadata_dir}")

    records_map: dict[tuple[str, str], TargetRecord] = {}
    for report_path in report_paths:
        parse_report(report_path, records_map)

    all_records = sorted(
        records_map.values(),
        key=lambda item: (item.repository_id.lower(), item.target_name.lower()),
    )
    for record in all_records:
        normalize_record(record)

    excluded = [
        record
        for record in all_records
        if "除外" in record.adoption_status
    ]
    records = [
        record
        for record in all_records
        if "除外" not in record.adoption_status
    ]

    target_dir.mkdir(parents=True, exist_ok=True)
    expected_paths = {
        target_dir / f"{record.target_id}.draft.json"
        for record in records
    }
    removed_stale = remove_stale_drafts(target_dir, expected_paths)

    for record in records:
        write_json(
            target_dir / f"{record.target_id}.draft.json",
            build_draft_config(record),
        )

    write_json(
        config_dir / "target_catalog.json",
        {
            "schema_version": "2.0",
            "expected_target_count": EXPECTED_TARGET_COUNT,
            "detected_target_count": len(records),
            "excluded_targets": [record.to_dict() for record in excluded],
            "targets": [record.to_dict() for record in records],
        },
    )
    write_csv(report_dir / "batch_readiness.csv", records)
    write_text(
        report_dir / "batch_readiness.md",
        build_readiness_markdown(records, excluded, removed_stale),
    )

    print(f"Detected experiment targets: {len(records)}/{EXPECTED_TARGET_COUNT}")
    print(f"Excluded targets:            {len(excluded)}")
    print(f"Removed stale drafts:        {len(removed_stale)}")
    print(f"Catalog:                     {config_dir / 'target_catalog.json'}")
    print(f"Readiness report:            {report_dir / 'batch_readiness.md'}")
    return 0 if len(records) == EXPECTED_TARGET_COUNT else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
