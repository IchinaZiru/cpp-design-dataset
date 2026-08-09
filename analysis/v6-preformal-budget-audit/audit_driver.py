from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

EXPECTED_BRANCH = "experiment/deterministic-exact-contract-v6"
EXPECTED_HEAD = "4a816dc8e1a0fdae609fd0a098d71d3a8ed03b87"
EXPECTED_TREE_SITTER = "0.26.0"
EXPECTED_TREE_SITTER_CPP = "0.23.4"
TOKENIZER_NAME = "Qwen/Qwen2.5-Coder-32B-Instruct"
DEFAULT_OUT = Path("analysis/v6-preformal-budget-audit")
V5_ROOT = Path("experiments/v5/evaluation/rag")


@dataclass
class AuditRow:
    pair_id: str
    target_name: str
    v5_run_dir: str
    model: str
    num_ctx: int
    num_predict: int
    saved_v5_request_available: bool
    saved_v5_request_exact_match: bool | None
    saved_v5_observed_prompt_tokens: int | None
    reconstructed_v5_prompt_tokens: int
    saved_v5_prompt_token_delta: int | None
    source_contract_chars: int
    dependency_contract_chars: int
    dependency_symbol_match_count: int
    nonrag_repeat_hash_match: bool
    rag_repeat_hash_match: bool
    source_contract_proxy_prompt_tokens: int
    source_contract_proxy_headroom: int
    source_contract_proxy_headroom_after_reserved_output: int
    source_contract_proxy_budget_pass: bool
    rag_contract_proxy_prompt_tokens: int
    rag_contract_proxy_headroom: int
    rag_contract_proxy_headroom_after_reserved_output: int
    rag_contract_proxy_budget_pass: bool


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


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


def augment_design(design: str, contract: str) -> str:
    return design.rstrip() + "\n\n" + contract.rstrip() + "\n"


def build_regeneration_prompt(v2: Any, config: dict[str, Any], design: str, scaffold: str, dependency: str) -> tuple[str, str]:
    granularity = v2.normalized_granularity(config)
    output_schema: dict[str, Any] | None = None

    if granularity == "module_files":
        expected_paths = v2.source_files_for(config)
        output_schema = v2.module_output_schema(expected_paths)
        output_instruction = (
            "出力は指定されたJSON Schemaに一致するJSONのみとし、"
            "Markdownコードフェンスを使用しないでください。"
            "source_filesにある各ファイルを完全な内容として1回ずつ返してください。"
            "pathはsource_filesの文字列をそのまま使用し、追加・省略・重複させないでください。"
            "C++コード中の改行や引用符はJSON文字列として正しくエスケープしてください。"
            "固定インターフェース・スキャフォールドに示された宣言とファイル構成を変更しないでください。"
        )
        target_description = (
            f"- target: {config['target_name']}\n"
            "- granularity: module_files\n"
            f"- source_files: {json.dumps(expected_paths, ensure_ascii=False)}"
        )
    else:
        locator = dict(config["locator"])
        kind = locator["kind"]
        if kind == "class":
            output_instruction = (
                "固定インターフェース・スキャフォールドの宣言内容を変更せず、"
                "対象クラスまたは構造体の定義全体だけをC++コードとして返してください。"
                "template宣言の個数と内容、class/struct宣言、継承、可視性、"
                "メンバ名と型、すべての関数・演算子の戻り値、引数、修飾を保持してください。"
                "一般的なC++慣習に合わせる目的でも、特殊または非標準的に見えるシグネチャを変更しないでください。"
                "スキャフォールドに存在しない宣言を追加せず、関数本体だけを実装してください。"
                "Markdownコードフェンス、説明文、JSONは出力しないでください。"
            )
        elif kind == "function":
            output_instruction = (
                "固定インターフェース・スキャフォールドに示された対象関数の定義全体だけをC++コードとして返してください。"
                "戻り値、関数名、引数、既定値、修飾を含む関数シグネチャを変更しないでください。"
                "Markdownコードフェンス、説明文、JSONは出力しないでください。"
            )
        else:
            raise ValueError(f"Unsupported locator kind: {kind!r}")
        target_description = (
            f"- target: {config['target_name']}\n"
            "- granularity: target_span\n"
            f"- target_kind: {kind}\n"
            f"- target_symbol: {locator['symbol']}\n"
            f"- source_file: {v2.target_source_file_for(config)}"
        )

    system = (
        "あなたはC++実装担当者です。設計文書と固定インターフェースだけを根拠に実装してください。"
        "元実装は与えられていません。公開インターフェースとファイル構成を変更しないでください。"
    )
    schema_section = (
        json.dumps(output_schema, ensure_ascii=False, indent=2)
        if output_schema is not None
        else "N/A"
    )
    prompt = f"""# 対象
{target_description}

# 出力規則
{output_instruction}

# JSON Schema
{schema_section}

# 設計文書
{design}

# 固定インターフェース・スキャフォールド
{scaffold}

# 依存情報
{dependency}
"""
    return system, prompt


def validate_tokenizer_against_saved_v2(root: Path, tokenizer: Any) -> dict[str, Any]:
    base = root / "experiments" / "v2" / "formal" / "rag"
    samples: list[dict[str, Any]] = []
    for request_path in sorted(base.glob("*/raw_output/design_generation_request.json")):
        metadata_path = request_path.with_name("design_generation_metadata.json")
        if not metadata_path.is_file():
            continue
        request = read_json(request_path)
        metadata = read_json(metadata_path)
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
        raise RuntimeError("No saved v2 prompt-count validation samples found")
    max_abs_delta = max(abs(row["delta"]) for row in samples)
    return {
        "samples": samples,
        "sample_count": len(samples),
        "max_abs_delta": max_abs_delta,
        "mean_abs_delta": sum(abs(row["delta"]) for row in samples) / len(samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="No-LLM v6 pre-formal code-regeneration context-budget audit")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--tokenizer", default=TOKENIZER_NAME)
    args = parser.parse_args()

    root = args.root.resolve()
    out_dir = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir

    print("=== PREFLIGHT ===")
    branch = git(root, "branch", "--show-current")
    head = git(root, "rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"Wrong branch: {branch} != {EXPECTED_BRANCH}")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"Wrong HEAD: {head} != {EXPECTED_HEAD}")
    staged = git(root, "diff", "--cached", "--name-only")
    if staged:
        raise RuntimeError(f"Staged changes must be empty before audit:\n{staged}")
    print(f"branch = {branch}")
    print(f"HEAD   = {head}")

    if version("tree-sitter") != EXPECTED_TREE_SITTER:
        raise RuntimeError("tree-sitter version mismatch")
    if version("tree-sitter-cpp") != EXPECTED_TREE_SITTER_CPP:
        raise RuntimeError("tree-sitter-cpp version mismatch")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        args.tokenizer,
        trust_remote_code=False,
        local_files_only=True,
    )
    tokenizer_validation = validate_tokenizer_against_saved_v2(root, tokenizer)
    if tokenizer_validation["sample_count"] != 17 or tokenizer_validation["max_abs_delta"] != 0:
        raise RuntimeError(
            "Tokenizer validation is not exact: "
            f"samples={tokenizer_validation['sample_count']}, "
            f"max_abs_delta={tokenizer_validation['max_abs_delta']}"
        )
    print("tokenizer validation = 17/17 exact")

    v2 = load_module("v6_budget_v2_runner", root / "scripts" / "roundtrip_v2" / "run_target_v2.py")
    contract = load_module("v6_budget_contract_extractor", root / "scripts" / "roundtrip_v6" / "contract_extractor.py")

    v5_root = root / V5_ROOT
    run_dirs = sorted(path for path in v5_root.iterdir() if path.is_dir() and path.name.endswith("-001"))
    if len(run_dirs) != 17:
        raise RuntimeError(f"Expected 17 v5 RAG run directories, found {len(run_dirs)}")

    if out_dir.exists():
        raise RuntimeError(f"Refusing to overwrite existing audit output: {out_dir}")

    rows: list[AuditRow] = []
    saved_request_available = 0
    saved_request_exact = 0
    saved_prompt_count_exact = 0

    print("\n=== 17-TARGET AUDIT ===")
    for run_dir in run_dirs:
        config_path = run_dir / "configs" / "target_config.json"
        design_path = run_dir / "generated" / "design_document.md"
        scaffold_path = run_dir / "input" / "fixed_scaffold.txt"
        dependency_path = run_dir / "input" / "dependency_context.txt"
        retrieval_manifest_path = run_dir / "retrieval" / "retrieval_manifest.json"
        for required in (config_path, design_path, scaffold_path, dependency_path, retrieval_manifest_path):
            if not required.is_file():
                raise FileNotFoundError(required)

        config = read_json(config_path)
        pair_id = str(config["pair_id"])
        model = config.get("model") or {}
        num_ctx = int(model["num_ctx"])
        num_predict = int(model["num_predict"])
        model_name = str(model["name"])

        design = read_text(design_path)
        scaffold = read_text(scaffold_path)
        dependency = read_text(dependency_path)

        original_system, original_prompt = build_regeneration_prompt(
            v2, config, design, scaffold, dependency
        )
        original_tokens = count_chat_tokens(tokenizer, original_system, original_prompt)

        request_path = run_dir / "raw_output" / "code_regeneration_request.json"
        metadata_path = run_dir / "raw_output" / "code_regeneration_metadata.json"
        request_available = request_path.is_file()
        request_match: bool | None = None
        observed_tokens: int | None = None
        token_delta: int | None = None
        if request_available:
            saved_request_available += 1
            saved_request = read_json(request_path)
            request_match = (
                saved_request.get("system") == original_system
                and saved_request.get("prompt") == original_prompt
            )
            if request_match:
                saved_request_exact += 1
            if not request_match:
                raise RuntimeError(f"Reconstructed v5 request differs from saved request: {pair_id}")
            if metadata_path.is_file():
                metadata = read_json(metadata_path)
                if isinstance(metadata.get("prompt_eval_count"), int):
                    observed_tokens = int(metadata["prompt_eval_count"])
                    token_delta = original_tokens - observed_tokens
                    if token_delta == 0:
                        saved_prompt_count_exact += 1
                    else:
                        raise RuntimeError(
                            f"Tokenizer count differs from saved v5 prompt_eval_count for {pair_id}: "
                            f"predicted={original_tokens}, observed={observed_tokens}"
                        )

        nonrag_1 = contract.extract_contracts(
            project_root=root,
            config_path=config_path,
            mode="nonrag",
            retrieval_manifest_path=None,
        )
        nonrag_2 = contract.extract_contracts(
            project_root=root,
            config_path=config_path,
            mode="nonrag",
            retrieval_manifest_path=None,
        )
        rag_1 = contract.extract_contracts(
            project_root=root,
            config_path=config_path,
            mode="rag",
            retrieval_manifest_path=retrieval_manifest_path,
        )
        rag_2 = contract.extract_contracts(
            project_root=root,
            config_path=config_path,
            mode="rag",
            retrieval_manifest_path=retrieval_manifest_path,
        )

        nonrag_hash_match = (
            sha256_text(nonrag_1["combined_contract"])
            == sha256_text(nonrag_2["combined_contract"])
            == str(nonrag_1["manifest"]["combined_contract_sha256"])
            == str(nonrag_2["manifest"]["combined_contract_sha256"])
        )
        rag_hash_match = (
            sha256_text(rag_1["combined_contract"])
            == sha256_text(rag_2["combined_contract"])
            == str(rag_1["manifest"]["combined_contract_sha256"])
            == str(rag_2["manifest"]["combined_contract_sha256"])
        )
        if not nonrag_hash_match or not rag_hash_match:
            raise RuntimeError(f"Contract repeat hash mismatch: {pair_id}")

        source_proxy_design = augment_design(design, nonrag_1["combined_contract"])
        rag_proxy_design = augment_design(design, rag_1["combined_contract"])

        source_system, source_prompt = build_regeneration_prompt(
            v2, config, source_proxy_design, scaffold, dependency
        )
        rag_system, rag_prompt = build_regeneration_prompt(
            v2, config, rag_proxy_design, scaffold, dependency
        )
        source_tokens = count_chat_tokens(tokenizer, source_system, source_prompt)
        rag_tokens = count_chat_tokens(tokenizer, rag_system, rag_prompt)

        source_headroom = num_ctx - source_tokens
        rag_headroom = num_ctx - rag_tokens
        source_reserved = source_headroom - num_predict
        rag_reserved = rag_headroom - num_predict

        row = AuditRow(
            pair_id=pair_id,
            target_name=str(config["target_name"]),
            v5_run_dir=run_dir.relative_to(root).as_posix(),
            model=model_name,
            num_ctx=num_ctx,
            num_predict=num_predict,
            saved_v5_request_available=request_available,
            saved_v5_request_exact_match=request_match,
            saved_v5_observed_prompt_tokens=observed_tokens,
            reconstructed_v5_prompt_tokens=original_tokens,
            saved_v5_prompt_token_delta=token_delta,
            source_contract_chars=int(nonrag_1["manifest"]["source_contract_chars"]),
            dependency_contract_chars=int(rag_1["manifest"]["dependency_contract_chars"]),
            dependency_symbol_match_count=int(rag_1["manifest"]["dependency_symbol_match_count"]),
            nonrag_repeat_hash_match=nonrag_hash_match,
            rag_repeat_hash_match=rag_hash_match,
            source_contract_proxy_prompt_tokens=source_tokens,
            source_contract_proxy_headroom=source_headroom,
            source_contract_proxy_headroom_after_reserved_output=source_reserved,
            source_contract_proxy_budget_pass=source_reserved >= 0,
            rag_contract_proxy_prompt_tokens=rag_tokens,
            rag_contract_proxy_headroom=rag_headroom,
            rag_contract_proxy_headroom_after_reserved_output=rag_reserved,
            rag_contract_proxy_budget_pass=rag_reserved >= 0,
        )
        rows.append(row)
        print(
            f"{pair_id:36s} "
            f"v5={original_tokens:5d} "
            f"src={source_tokens:5d} ({source_reserved:+6d}) "
            f"rag={rag_tokens:5d} ({rag_reserved:+6d})"
        )

    source_pass = sum(row.source_contract_proxy_budget_pass for row in rows)
    rag_pass = sum(row.rag_contract_proxy_budget_pass for row in rows)
    log_rows = [row for row in rows if row.pair_id == "echo-web-server-log"]
    if len(log_rows) != 1:
        raise RuntimeError(f"Expected exactly one log row, found {len(log_rows)}")
    log_row = log_rows[0]

    out_dir.mkdir(parents=True)
    csv_path = out_dir / "v6_preformal_budget_audit.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    all_contract_repeat = all(row.nonrag_repeat_hash_match and row.rag_repeat_hash_match for row in rows)
    proxy_go = source_pass == 17 and rag_pass == 17
    summary = {
        "schema_version": "1.0",
        "audit_type": "v6_preformal_code_regeneration_context_budget_proxy",
        "formal_llm_generation_performed": False,
        "ollama_called": False,
        "docker_called": False,
        "build_or_test_called": False,
        "branch": branch,
        "head": head,
        "tokenizer": args.tokenizer,
        "transformers_version": version("transformers"),
        "tree_sitter_version": version("tree-sitter"),
        "tree_sitter_cpp_version": version("tree-sitter-cpp"),
        "tokenizer_validation": tokenizer_validation,
        "fixed_budget_rule": "assembled_code_regeneration_input_tokens + num_predict <= num_ctx",
        "fixed_budget_rule_scope": (
            "Apply identically to every v6 target and both conditions. During formal execution, "
            "count the actual assembled code-regeneration request after the one-shot design generation; "
            "if the rule fails, stop before the code-regeneration LLM call and retain the formal artifact."
        ),
        "proxy_design_source": "frozen v5 RAG generated/design_document.md for the same pair_id",
        "proxy_interpretation": (
            "This audit is a pre-formal mechanical sizing proxy, not a v6 formal result and not a prediction "
            "of the exact v6 generated design length. It validates the tokenizer, prompt reconstruction, "
            "contract determinism, and whether frozen v5 designs plus v6 contracts fit the fixed rule."
        ),
        "target_count": len(rows),
        "saved_v5_request_available_count": saved_request_available,
        "saved_v5_request_exact_match_count": saved_request_exact,
        "saved_v5_prompt_count_exact_match_count": saved_prompt_count_exact,
        "contract_repeat_hash_match_all": all_contract_repeat,
        "source_contract_proxy_budget_pass_count": source_pass,
        "rag_contract_proxy_budget_pass_count": rag_pass,
        "min_source_contract_proxy_headroom_after_reserved_output": min(
            row.source_contract_proxy_headroom_after_reserved_output for row in rows
        ),
        "min_rag_contract_proxy_headroom_after_reserved_output": min(
            row.rag_contract_proxy_headroom_after_reserved_output for row in rows
        ),
        "max_source_contract_proxy_prompt_tokens": max(
            row.source_contract_proxy_prompt_tokens for row in rows
        ),
        "max_rag_contract_proxy_prompt_tokens": max(
            row.rag_contract_proxy_prompt_tokens for row in rows
        ),
        "log": asdict(log_row),
        "proxy_go_for_preformal_config_preparation": proxy_go,
        "rows": [asdict(row) for row in rows],
    }
    json_path = out_dir / "summary.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n=== SUMMARY ===")
    print(f"tokenizer validation                  = {tokenizer_validation['sample_count']}/17 exact, max_abs_delta={tokenizer_validation['max_abs_delta']}")
    print(f"saved v5 request reconstruction       = {saved_request_exact}/{saved_request_available} exact")
    print(f"saved v5 prompt token validation      = {saved_prompt_count_exact}/{saved_request_available} exact")
    print(f"contract repeat hash match            = {'PASS' if all_contract_repeat else 'FAIL'}")
    print(f"source-contract proxy budget          = {source_pass}/17 PASS")
    print(f"RAG-contract proxy budget             = {rag_pass}/17 PASS")
    print(
        "min source headroom after reserve       = "
        f"{summary['min_source_contract_proxy_headroom_after_reserved_output']}"
    )
    print(
        "min RAG headroom after reserve          = "
        f"{summary['min_rag_contract_proxy_headroom_after_reserved_output']}"
    )
    print("\n=== LOG ===")
    print(f"v5 reconstructed prompt tokens        = {log_row.reconstructed_v5_prompt_tokens}")
    print(f"source-contract proxy prompt tokens    = {log_row.source_contract_proxy_prompt_tokens}")
    print(f"source headroom after reserve          = {log_row.source_contract_proxy_headroom_after_reserved_output}")
    print(f"RAG-contract proxy prompt tokens       = {log_row.rag_contract_proxy_prompt_tokens}")
    print(f"RAG headroom after reserve             = {log_row.rag_contract_proxy_headroom_after_reserved_output}")
    print("\n=== VERDICT ===")
    print(f"proxy_go_for_preformal_config_preparation = {str(proxy_go).upper()}")
    print(f"saved = {json_path.relative_to(root)}")
    print(f"saved = {csv_path.relative_to(root)}")
    print("No LLM, Ollama, Docker, build, or test call was made.")

    return 0 if proxy_go else 2


if __name__ == "__main__":
    raise SystemExit(main())
