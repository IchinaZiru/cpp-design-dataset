"""Deterministic no-LLM token preflight for the 17-target A/B freeze candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from transformers import AutoTokenizer

from scripts.rag.canonical import canonical_json_bytes, sha256_bytes
from scripts.rag.roundtrip_ab import load_json, load_target_inputs, resolve_repository_root
from scripts.rag.roundtrip_ab_formal import (
    build_design_request_v2,
    build_code_request_v2,
    build_retrieval_bundle_v2,
    load_common_v2,
    load_formal_manifest,
)


TOKENIZER_ID = "Qwen/Qwen2.5-Coder-32B-Instruct"
TEMPLATE_OVERHEAD_RESERVE = 256


def _count(tokenizer: Any, text: str) -> int:
    return len(tokenizer.encode(text, add_special_tokens=True))


def build_report(root: Path, common_path: Path, manifest_path: Path, tokenizer: Any) -> dict[str, Any]:
    common = load_common_v2(common_path, root)
    manifest = load_formal_manifest(manifest_path, root)
    design_options = common["generation"]["design_options"]
    code_options = common["generation"]["code_options"]
    design_num_ctx = int(design_options["num_ctx"])
    design_num_predict = int(design_options["num_predict"])
    code_num_ctx = int(code_options["num_ctx"])
    code_num_predict = int(code_options["num_predict"])
    records: list[dict[str, Any]] = []
    for entry in manifest["targets"]:
        config = load_json(root / entry["target_config_path"])
        repository_root = resolve_repository_root(config, root)
        inputs = load_target_inputs(config, repository_root)
        retrieval = build_retrieval_bundle_v2(config, common, root, repository_root)
        requests = {
            "A": build_design_request_v2(config, common, root, inputs, condition="A", repository_context=None),
            "B": build_design_request_v2(config, common, root, inputs, condition="B", repository_context=retrieval.context),
        }
        units = config["replacement_units"]
        placeholder_request = build_code_request_v2("DESIGN", common, root, expected_units=units)
        code_wrapper_tokens = (
            _count(tokenizer, str(placeholder_request.payload.get("system", "")))
            + _count(tokenizer, placeholder_request.prompt.replace("DESIGN", ""))
            + TEMPLATE_OVERHEAD_RESERVE
        )
        original_code_tokens = sum(_count(tokenizer, item.content) for item in inputs if item.replacement_required)
        code_input_upper_bound = code_wrapper_tokens + design_num_predict
        condition_records: dict[str, Any] = {}
        for condition, request in requests.items():
            input_tokens = _count(tokenizer, request.prompt) + TEMPLATE_OVERHEAD_RESERVE
            total = input_tokens + design_num_predict
            condition_records[condition] = {
                "input_tokens": input_tokens,
                "input_plus_max_output": total,
                "num_ctx": design_num_ctx,
                "num_predict": design_num_predict,
                "overflow_or_truncation_risk": total > design_num_ctx,
                "remaining_context": design_num_ctx - total,
            }
        code_total = code_input_upper_bound + code_num_predict
        records.append(
            {
                "code_generation_request": {
                    "input_tokens_upper_bound": code_input_upper_bound,
                    "input_plus_max_output": code_total,
                    "num_ctx": code_num_ctx,
                    "num_predict": code_num_predict,
                    "original_replacement_code_tokens_reference": original_code_tokens,
                    "overflow_or_truncation_risk": code_total > code_num_ctx,
                    "remaining_context": code_num_ctx - code_total,
                },
                "condition_a_design_request": condition_records["A"],
                "condition_b_design_request": condition_records["B"],
                "dependency_header_count": retrieval.manifest["dependency_header_count"],
                "target_id": config["target_id"],
            }
        )
    risk_count = sum(
        1
        for record in records
        if record["condition_a_design_request"]["overflow_or_truncation_risk"]
        or record["condition_b_design_request"]["overflow_or_truncation_risk"]
        or record["code_generation_request"]["overflow_or_truncation_risk"]
    )
    return {
        "artifact_schema_version": "roundtrip-ab-token-preflight-v1",
        "assumptions": {
            "code_generation_design_input_upper_bound_tokens": design_num_predict,
            "format_schema_is_grammar_not_semantic_prompt": True,
            "template_overhead_reserve_tokens": TEMPLATE_OVERHEAD_RESERVE,
        },
        "common_generation": {
            "model": common["generation"]["model"],
            "design_num_ctx": design_num_ctx,
            "design_num_predict": design_num_predict,
            "code_num_ctx": code_num_ctx,
            "code_num_predict": code_num_predict,
        },
        "formal_target_count": len(records),
        "generation_server_contacted": False,
        "llm_call_count": 0,
        "risk_target_count": risk_count,
        "status": "pass" if risk_count == 0 else "fail",
        "targets": records,
        "tokenizer": {"id": TOKENIZER_ID, "local_files_only": True, "transformers_class": type(tokenizer).__name__},
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Design-only A/B formal token preflight v1",
        "",
        f"Status: **{report['status'].upper()}**  ",
        f"Targets: {report['formal_target_count']}  ",
        f"Design num_ctx / num_predict: {report['common_generation']['design_num_ctx']} / {report['common_generation']['design_num_predict']}  ",
        f"Code num_ctx / num_predict: {report['common_generation']['code_num_ctx']} / {report['common_generation']['code_num_predict']}  ",
        "LLM calls: 0",
        "",
        "| Target | A input | A total | A remain | B input | B total | B remain | Code input upper | Code total | Code remain | Risk |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for item in report["targets"]:
        a, b, c = item["condition_a_design_request"], item["condition_b_design_request"], item["code_generation_request"]
        risk = a["overflow_or_truncation_risk"] or b["overflow_or_truncation_risk"] or c["overflow_or_truncation_risk"]
        lines.append(
            f"| {item['target_id']} | {a['input_tokens']} | {a['input_plus_max_output']} | {a['remaining_context']} | "
            f"{b['input_tokens']} | {b['input_plus_max_output']} | {b['remaining_context']} | "
            f"{c['input_tokens_upper_bound']} | {c['input_plus_max_output']} | {c['remaining_context']} | {'YES' if risk else 'no'} |"
        )
    lines.extend(
        [
            "",
            "Code-generation input is a conservative upper bound: the final design document is reserved up to num_predict tokens, plus the shared code prompt/system/template overhead. The model was not contacted.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--common", type=Path, default=Path("configs/rag/roundtrip_ab_v1/common.json"))
    parser.add_argument("--manifest", type=Path, default=Path("configs/rag/roundtrip_ab_v1/formal/evaluation_manifest.json"))
    parser.add_argument("--output-json", type=Path, default=Path("reports/rag/roundtrip-ab-v1/formal-preflight/token-preflight-v1.json"))
    parser.add_argument("--output-md", type=Path, default=Path("reports/rag/roundtrip-ab-v1/formal-preflight/token-preflight-v1.md"))
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    resolve = lambda value: value if value.is_absolute() else root / value
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_ID, local_files_only=True)
    report = build_report(root, resolve(args.common), resolve(args.manifest), tokenizer)
    outputs = {resolve(args.output_json): canonical_json_bytes(report), resolve(args.output_md): markdown(report).encode("utf-8")}
    for path, data in outputs.items():
        if path.exists():
            if path.read_bytes() != data:
                if args.refresh:
                    path.write_bytes(data)
                else:
                    raise RuntimeError(f"refusing to overwrite differing token preflight: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(json.dumps({"risk_target_count": report["risk_target_count"], "status": report["status"], "target_count": report["formal_target_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
