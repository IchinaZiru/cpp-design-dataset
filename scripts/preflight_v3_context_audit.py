from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:32b"
DEFAULT_TOKENIZER = "Qwen/Qwen2.5-Coder-32B-Instruct"
BASE_HEADINGS = [
    "責務",
    "公開インターフェース",
    "入力",
    "出力",
    "状態",
    "処理手順",
    "例外・失敗条件",
    "依存関係",
    "重要な不変条件",
]
SYSTEM_PROMPT = (
    "あなたはC++ソフトウェアのリバースエンジニアリング担当者です。"
    "与えられたコードだけを根拠として、再実装に必要な設計文書を日本語で作成してください。"
    "推測で存在しない機能を追加しないでください。"
)


@dataclass
class Row:
    pair_id: str
    target_name: str
    repository_id: str
    granularity: str
    source_files: int
    source_characters: int
    non_rag_input_tokens: int
    rag_input_tokens: int
    rag_overhead_tokens: int
    non_rag_headroom: int | None
    rag_headroom: int | None


def post_json(path: str, payload: dict[str, Any], timeout: int = 60) -> dict[str, Any]:
    request = urllib.request.Request(
        OLLAMA_BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise RuntimeError(f"Ollama API request failed: {error}") from error


def get_json(path: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(OLLAMA_BASE + path, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise RuntimeError(f"Ollama API request failed: {error}") from error


def load_v3_runner(root: Path):
    runner_path = root / "scripts" / "roundtrip_v3" / "run_target_v3.py"
    spec = importlib.util.spec_from_file_location("roundtrip_v3_runner_preflight", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load v3 runner: {runner_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_context_length(model_info: dict[str, Any]) -> int | None:
    values = [
        int(value)
        for key, value in model_info.items()
        if key.endswith(".context_length") and isinstance(value, (int, float))
    ]
    return max(values) if values else None


def command_output(command: list[str]) -> str | None:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout.strip()
    except (FileNotFoundError, OSError):
        return None


def gpu_info() -> list[dict[str, Any]]:
    output = command_output(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ]
    )
    if not output:
        return []
    result: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 3:
            continue
        try:
            result.append(
                {
                    "name": parts[0],
                    "memory_total_mib": int(parts[1]),
                    "memory_free_mib": int(parts[2]),
                }
            )
        except ValueError:
            continue
    return result


def load_tokenizer(tokenizer_name: str):
    try:
        import transformers  # type: ignore
        from transformers import AutoTokenizer  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "transformers is required for offline token counting. "
            "Install it in a separate preflight venv with: "
            "python -m pip install 'transformers>=4.45,<5'"
        ) from error
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, trust_remote_code=False)
    return tokenizer, transformers.__version__


def count_chat_tokens(tokenizer: Any, system: str, prompt: str) -> int:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    ids = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
    )
    return len(ids)


def git_head(repository: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def normalized_granularity(config: dict[str, Any]) -> str:
    raw = config.get("granularity")
    if raw == "module_files":
        return "module_files"
    if raw in {"target_span", "class_span", "function", "function_body"}:
        return "target_span"
    locator = config.get("locator") or {}
    if raw is None and locator.get("kind") in {"class", "function"}:
        return "target_span"
    raise ValueError(f"Unsupported granularity: {raw!r}")


def source_files_for(config: dict[str, Any]) -> list[str]:
    if normalized_granularity(config) == "module_files":
        values = config.get("source_files") or []
    else:
        target_source_file = config.get("target_source_file")
        values = [target_source_file] if target_source_file else config.get("source_files") or []
    if not values or not all(isinstance(x, str) and x for x in values):
        raise ValueError(f"Invalid source files for {config.get('pair_id')}")
    return list(values)


def observation_files_for(config: dict[str, Any]) -> list[str]:
    values = config.get("observation_files")
    return list(values) if isinstance(values, list) and values else source_files_for(config)


def build_observation_bundle(repository: Path, observation_files: list[str]) -> str:
    parts: list[str] = []
    for relative in observation_files:
        path = repository / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        text = path.read_text(encoding="utf-8", errors="strict")
        parts.append(f"===== FILE: {relative} =====\n{text.rstrip()}\n")
    return "\n".join(parts)


def base_output_section() -> str:
    lines = [
        "# 基本設計項目",
        "以下の9見出しを、この名称・順序のまま必ず出力してください。",
        "各見出しは `##` で記述してください。",
        "同じ事実を複数見出しで冗長に繰り返さず、元コードから確認できる内容だけを記述してください。",
    ]
    lines.extend(f"- {heading}" for heading in BASE_HEADINGS)
    return "\n".join(lines)


def rag_section(knowledge_text: str) -> str:
    return f"""# RAGによる追加詳細設計成果物
以下の検索コンテキストは、基本9項目を置き換えるものではありません。
基本9項目をすべて出力した後に、検索コンテキストで指定された追加成果物を指定順で出力してください。
対象に該当しない成果物も省略せず、「該当なし」と簡潔な根拠を記載してください。
図は指定されたMermaid形式で出力してください。
元コードで確認できない内容は推測せず「確認不能」としてください。

----- BEGIN RETRIEVED CONTEXT -----
{knowledge_text.strip()}
----- END RETRIEVED CONTEXT -----"""


def build_prompt(config: dict[str, Any], design_input: str, knowledge_text: str | None) -> str:
    granularity = normalized_granularity(config)
    if granularity == "module_files":
        source_files = source_files_for(config)
        target_description = (
            f"- target: {config['target_name']}\n"
            "- granularity: module_files\n"
            f"- source_files: {json.dumps(source_files, ensure_ascii=False)}"
        )
        scope_description = (
            "元コードとして示したsource_files全体を1つのモジュールとして扱ってください。\n"
            "設計文書は、各ファイルの責務、ファイル間の関係、公開インターフェース、実装上の処理を含めて作成してください。\n"
            "再実装ではsource_filesにある各ファイル全体を生成するため、ファイルごとの構造と責務を区別してください。"
        )
    else:
        locator = dict(config.get("locator") or {})
        target_description = (
            f"- target: {config['target_name']}\n"
            "- granularity: target_span\n"
            f"- target_kind: {locator.get('kind')}\n"
            f"- target_symbol: {locator.get('symbol')}"
        )
        scope_description = (
            "元コード全体は対象部分を理解するための文脈として参照してください。\n"
            "設計文書はtarget_symbolで指定した対象部分だけについて作成してください。\n"
            "対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。"
        )

    extra = ""
    if knowledge_text is not None:
        extra = "\n\n" + rag_section(knowledge_text)

    return f"""# 対象
{target_description}

# 対象範囲
{scope_description}

{base_output_section()}{extra}

# 元コード
{design_input}
"""


def load_formal_configs(root: Path) -> list[dict[str, Any]]:
    config_dir = root / "configs" / "roundtrip_v2" / "formal" / "non-rag"
    if not config_dir.is_dir():
        raise FileNotFoundError(config_dir)
    configs: list[dict[str, Any]] = []
    for path in sorted(config_dir.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and value.get("formal_result_eligible") is True:
            value["_config_path"] = path.as_posix()
            configs.append(value)
    if len(configs) != 17:
        raise RuntimeError(f"Expected 17 formal target configs, found {len(configs)}")
    configs.sort(key=lambda x: int(x.get("pair_sequence", 10**9)))
    return configs


def validate_tokenizer_against_saved_v2(root: Path, tokenizer: Any) -> dict[str, Any]:
    base = root / "experiments" / "v2" / "formal" / "rag"
    samples: list[dict[str, Any]] = []
    if not base.is_dir():
        return {"available": False, "samples": [], "max_abs_delta": None}
    for request_path in sorted(base.glob("*/raw_output/design_generation_request.json")):
        metadata_path = request_path.with_name("design_generation_metadata.json")
        if not metadata_path.is_file():
            continue
        request = json.loads(request_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        observed = metadata.get("prompt_eval_count")
        system = request.get("system")
        prompt = request.get("prompt")
        if not isinstance(observed, int) or not isinstance(system, str) or not isinstance(prompt, str):
            continue
        predicted = count_chat_tokens(tokenizer, system, prompt)
        samples.append(
            {
                "run": request_path.parents[1].name,
                "observed": observed,
                "predicted": predicted,
                "delta": predicted - observed,
            }
        )
    if not samples:
        return {"available": False, "samples": [], "max_abs_delta": None}
    return {
        "available": True,
        "samples": samples,
        "max_abs_delta": max(abs(item["delta"]) for item in samples),
        "mean_abs_delta": sum(abs(item["delta"]) for item in samples) / len(samples),
    }


def probe_context(model: str, requested: int) -> dict[str, Any]:
    # Ollama documents an empty generate request with keep_alive as a preload operation.
    response = post_json(
        "/api/generate",
        {
            "model": model,
            "stream": False,
            "keep_alive": "10m",
            "options": {"num_ctx": requested},
        },
        timeout=600,
    )
    ps = get_json("/api/ps")
    loaded = None
    for item in ps.get("models", []):
        if item.get("name") == model or item.get("model") == model:
            loaded = item
            break
    return {"preload_response": response, "loaded_model": loaded, "ollama_ps": command_output(["ollama", "ps"])}


def main() -> int:
    parser = argparse.ArgumentParser(description="v3 non-RAG/RAG context preflight audit")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--model", default=DEFAULT_LOCAL_MODEL)
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument(
        "--knowledge",
        type=Path,
        default=Path("knowledge/detailed-design/general-v3.md"),
    )
    parser.add_argument(
        "--probe-context",
        type=int,
        default=32768,
        help="Preload Ollama at this context length without a prompt; use 0 to skip.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("analysis/v3/context-preflight"),
    )
    args = parser.parse_args()

    root = args.root.resolve()
    knowledge_path = args.knowledge if args.knowledge.is_absolute() else root / args.knowledge
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/5] Inspecting local Ollama model")
    show = post_json("/api/show", {"model": args.model, "verbose": False})
    native_ctx = native_context_length(show.get("model_info") or {})
    print(f"  model: {args.model}")
    print(f"  parameter_size: {(show.get('details') or {}).get('parameter_size')}")
    print(f"  quantization: {(show.get('details') or {}).get('quantization_level')}")
    print(f"  native_context_length: {native_ctx}")

    probe = None
    if args.probe_context:
        if native_ctx is not None and args.probe_context > native_ctx:
            raise RuntimeError(
                f"Requested probe context {args.probe_context} exceeds model native limit {native_ctx}"
            )
        print(f"[2/5] Preloading model with num_ctx={args.probe_context} (no prompt)")
        probe = probe_context(args.model, args.probe_context)
        loaded = probe.get("loaded_model") or {}
        print(f"  allocated_context_length: {loaded.get('context_length')}")
        print(f"  size_vram: {loaded.get('size_vram')}")
        if probe.get("ollama_ps"):
            print("  ollama ps:")
            print("  " + str(probe["ollama_ps"]).replace("\n", "\n  "))
    else:
        print("[2/5] Context preload probe skipped")

    print("[3/5] Loading tokenizer (no model weights)")
    tokenizer, transformers_version = load_tokenizer(args.tokenizer)
    print(f"  tokenizer: {args.tokenizer}")
    print(f"  transformers: {transformers_version}")

    print("[4/5] Validating tokenizer counts against saved v2 Ollama metadata")
    validation = validate_tokenizer_against_saved_v2(root, tokenizer)
    if validation["available"]:
        print(f"  samples: {len(validation['samples'])}")
        print(f"  max_abs_delta: {validation['max_abs_delta']}")
        print(f"  mean_abs_delta: {validation['mean_abs_delta']:.2f}")
        if validation["max_abs_delta"] > 16:
            print("  WARNING: tokenizer/template mismatch is larger than 16 tokens; counts are estimates.")
    else:
        print("  saved v2 validation artifacts not found; counts cannot be cross-checked locally")

    if not knowledge_path.is_file():
        raise FileNotFoundError(knowledge_path)
    knowledge_text = knowledge_path.read_text(encoding="utf-8")

    print("[5/5] Counting 17-target v3 non-RAG/RAG design-generation inputs")
    configs = load_formal_configs(root)
    budget = None
    if probe and probe.get("loaded_model"):
        value = (probe["loaded_model"] or {}).get("context_length")
        if isinstance(value, int):
            budget = value
    if budget is None:
        budget = native_ctx

    runner = load_v3_runner(root)
    rows: list[Row] = []
    repository_checks: list[dict[str, Any]] = []
    for config in configs:
        repository = root / str(config["repository_path"])
        current_head = git_head(repository)
        expected_head = str(config["repository_commit"])
        repository_checks.append(
            {
                "pair_id": config.get("pair_id"),
                "repository": str(repository),
                "expected_commit": expected_head,
                "actual_commit": current_head,
                "match": current_head == expected_head,
            }
        )
        if current_head != expected_head:
            raise RuntimeError(
                f"Repository commit mismatch for {config.get('pair_id')}: "
                f"expected={expected_head}, actual={current_head}"
            )

        observations = observation_files_for(config)
        design_input = build_observation_bundle(repository, observations)
        control_config = dict(config)
        control_config["condition"] = runner.CONTROL_CONDITION
        rag_config = dict(config)
        rag_config["condition"] = runner.RAG_CONDITION
        non_system, non_prompt = runner.build_design_prompt(
            control_config, design_input, ""
        )
        rag_system, rag_prompt = runner.build_design_prompt(
            rag_config, design_input, knowledge_text
        )
        non_tokens = count_chat_tokens(tokenizer, non_system, non_prompt)
        rag_tokens = count_chat_tokens(tokenizer, rag_system, rag_prompt)
        pair_id = str(config.get("pair_id") or config.get("target_id"))
        rows.append(
            Row(
                pair_id=pair_id,
                target_name=str(config["target_name"]),
                repository_id=str(config["repository_id"]),
                granularity=normalized_granularity(config),
                source_files=len(observations),
                source_characters=len(design_input),
                non_rag_input_tokens=non_tokens,
                rag_input_tokens=rag_tokens,
                rag_overhead_tokens=rag_tokens - non_tokens,
                non_rag_headroom=(budget - non_tokens) if budget else None,
                rag_headroom=(budget - rag_tokens) if budget else None,
            )
        )
        print(f"  {pair_id:36s} nonRAG={non_tokens:6d} RAG={rag_tokens:6d} delta={rag_tokens-non_tokens:5d}")

    csv_path = out_dir / "v3_input_token_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    summary = {
        "schema_version": "1.0",
        "audit_type": "v3_design_generation_input_context_preflight",
        "formal_llm_generation_performed": False,
        "ollama_model": args.model,
        "ollama_version": command_output(["ollama", "--version"]),
        "ollama_show": {
            "details": show.get("details"),
            "native_context_length": native_ctx,
        },
        "probe_context_requested": args.probe_context,
        "probe": probe,
        "gpu": gpu_info(),
        "tokenizer": args.tokenizer,
        "transformers_version": transformers_version,
        "tokenizer_validation": validation,
        "context_budget_used_for_headroom": budget,
        "prompt_profile": runner.PROMPT_PROFILE,
        "reserved_output_tokens": runner.EXPECTED_NUM_PREDICT,
        "knowledge_file": str(knowledge_path.relative_to(root) if knowledge_path.is_relative_to(root) else knowledge_path),
        "repository_checks": repository_checks,
        "target_count": len(rows),
        "max_non_rag_input_tokens": max(row.non_rag_input_tokens for row in rows),
        "max_non_rag_target": max(rows, key=lambda row: row.non_rag_input_tokens).pair_id,
        "max_rag_input_tokens": max(row.rag_input_tokens for row in rows),
        "max_rag_target": max(rows, key=lambda row: row.rag_input_tokens).pair_id,
        "min_rag_headroom": min((row.rag_headroom for row in rows if row.rag_headroom is not None), default=None),
        "min_rag_headroom_after_reserved_output": min(
            (
                row.rag_headroom - runner.EXPECTED_NUM_PREDICT
                for row in rows
                if row.rag_headroom is not None
            ),
            default=None,
        ),
        "rows": [asdict(row) for row in rows],
    }
    json_path = out_dir / "v3_context_preflight.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n===== SUMMARY =====")
    print(f"targets: {len(rows)}")
    print(f"context budget: {budget}")
    print(f"max non-RAG input: {summary['max_non_rag_input_tokens']} ({summary['max_non_rag_target']})")
    print(f"max RAG input: {summary['max_rag_input_tokens']} ({summary['max_rag_target']})")
    print(f"min RAG headroom: {summary['min_rag_headroom']}")
    print(
        "min RAG headroom after reserved output: "
        f"{summary['min_rag_headroom_after_reserved_output']}"
    )
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    print("No design document or regenerated code was generated by this audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
