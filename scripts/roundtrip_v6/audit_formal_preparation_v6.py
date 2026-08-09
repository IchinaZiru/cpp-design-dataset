from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_BRANCH = "experiment/deterministic-exact-contract-v6"
EXPECTED_HEAD = "3c17ad77de563e819208b0f0901cfbd22b91e2fb"
EXPECTED_TREE_SITTER = "0.26.0"
EXPECTED_TREE_SITTER_CPP = "0.23.4"
EXPECTED_TRANSFORMERS = "4.57.6"
MANIFEST_PATH = Path("configs/roundtrip_v6/formal/generation_manifest.json")
OUTPUT_DIR = Path("analysis/v6-preformal-config-audit")
BUDGET_AUDIT = Path("analysis/v6-preformal-budget-audit/summary.json")
LEAKAGE_PARTS = {
    "test",
    "tests",
    "generated",
    "report",
    "reports",
    "build",
    "experiments",
    "analysis",
}


@dataclass
class PairRow:
    pair_id: str
    pair_sequence: int
    repository_id: str
    granularity: str
    nonrag_enabled: bool
    rag_enabled: bool
    common_fields_match: bool
    repository_head_match: bool
    source_contract_repeat_match: bool
    rag_contract_repeat_match: bool
    source_contract_same_across_conditions: bool
    rag_retrieval_hash_match: bool
    rag_selected_paths_match: bool
    rag_target_overlap_count: int
    rag_leakage_path_count: int
    experiment_roots_absent: bool
    passed: bool


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    import subprocess

    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_parts(path: str) -> set[str]:
    pure = PurePosixPath(path.replace("\\", "/"))
    return {part.lower() for part in pure.parts}


def is_suspicious_selected_path(path: str) -> bool:
    return bool(normalized_parts(path).intersection(LEAKAGE_PARTS))


def compare_common_fields(nonrag: dict[str, Any], rag: dict[str, Any]) -> tuple[bool, list[str]]:
    keys = [
        "pair_id",
        "pair_sequence",
        "repository_id",
        "repository_path",
        "repository_commit",
        "target_name",
        "adoption_status",
        "granularity",
        "observation_files",
        "source_files",
        "target_source_file",
        "locator",
        "design_knowledge",
        "model",
        "evaluation",
        "design_prompt_profile",
        "context_budget",
    ]
    mismatches = [key for key in keys if nonrag.get(key) != rag.get(key)]

    non_design_context = nonrag.get("design_context") or {}
    rag_design_context = rag.get("design_context") or {}
    for key in (
        "common_context_file",
        "common_render_mode",
        "common_context_sha256",
    ):
        if non_design_context.get(key) != rag_design_context.get(key):
            mismatches.append(f"design_context.{key}")
    if non_design_context.get("repository_context_enabled") is not False:
        mismatches.append("design_context.repository_context_enabled(non-RAG)")
    if rag_design_context.get("repository_context_enabled") is not True:
        mismatches.append("design_context.repository_context_enabled(RAG)")

    non_protocol = nonrag.get("protocol") or {}
    rag_protocol = rag.get("protocol") or {}
    protocol_common_keys = [
        "protocol_id",
        "result_classification",
        "formal_target_set_member",
        "formal_pair_id",
        "observation_scope",
        "replacement_scope",
        "code_regeneration_inputs",
        "original_source_in_code_regeneration",
        "retrieved_context_in_code_regeneration",
        "module_output_format",
        "retry",
        "automatic_repair",
        "generated_code_manual_edit",
        "generations_per_stage",
        "design_prompt_profile",
        "base_level2_sections",
        "treatment_root_level2_section",
        "treatment_detail_level3_sections",
        "allow_other_level2_sections",
        "design_contract_validation_required",
        "design_done_reason_required",
        "code_regeneration_done_reason_required",
        "num_ctx",
        "num_predict",
        "design_contract_validation_mode",
        "design_contract_violation_is_terminal",
        "allow_heading_level_variation",
        "allow_heading_order_variation",
        "allow_additional_headings",
        "generated_design_automatic_normalization",
        "contract_extractor_version",
        "source_local_contract_common_to_both_conditions",
        "context_budget_rule",
        "context_budget_tokenizer",
        "formal_enablement_state",
    ]
    for key in protocol_common_keys:
        if non_protocol.get(key) != rag_protocol.get(key):
            mismatches.append(f"protocol.{key}")

    return not mismatches, mismatches


def extract_twice(
    contract: Any,
    *,
    root: Path,
    config_path: Path,
    mode: str,
    retrieval_manifest: Path | None,
) -> tuple[dict[str, Any], bool]:
    first = contract.extract_contracts(
        project_root=root,
        config_path=config_path,
        mode=mode,
        retrieval_manifest_path=retrieval_manifest,
    )
    second = contract.extract_contracts(
        project_root=root,
        config_path=config_path,
        mode=mode,
        retrieval_manifest_path=retrieval_manifest,
    )
    keys = [
        "source_contract_sha256",
        "dependency_contract_sha256",
        "combined_contract_sha256",
        "target_fragment_sha256",
        "dependency_file_sha256",
        "selected_dependency_paths",
        "dependency_symbols",
        "overload_sets",
        "unmatched_candidate_symbols",
    ]
    same = all(first["manifest"].get(key) == second["manifest"].get(key) for key in keys)
    return first, same


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit all-disabled paired v6 formal preparation without LLM/build/test."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.project_root.resolve()

    print("=== PREFLIGHT ===")
    branch = git(root, "branch", "--show-current")
    head = git(root, "rev-parse", "HEAD")
    if branch != EXPECTED_BRANCH:
        raise RuntimeError(f"Wrong branch: {branch} != {EXPECTED_BRANCH}")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"Wrong HEAD: {head} != {EXPECTED_HEAD}")
    if git(root, "diff", "--cached", "--name-only"):
        raise RuntimeError("Staged changes must be empty before v6 preparation audit")
    print(f"branch = {branch}")
    print(f"HEAD   = {head}")

    if version("tree-sitter") != EXPECTED_TREE_SITTER:
        raise RuntimeError("tree-sitter version mismatch")
    if version("tree-sitter-cpp") != EXPECTED_TREE_SITTER_CPP:
        raise RuntimeError("tree-sitter-cpp version mismatch")
    if version("transformers") != EXPECTED_TRANSFORMERS:
        raise RuntimeError("transformers version mismatch")

    budget = read_json(root / BUDGET_AUDIT)
    if budget.get("proxy_go_for_preformal_config_preparation") is not True:
        raise RuntimeError("Frozen budget audit is not GO")
    if int((budget.get("tokenizer_validation") or {}).get("max_abs_delta", -1)) != 0:
        raise RuntimeError("Frozen tokenizer validation is not exact")

    manifest = read_json(root / MANIFEST_PATH)
    if manifest.get("pair_count") != 17 or manifest.get("config_count") != 34:
        raise RuntimeError("v6 generation manifest count mismatch")
    if manifest.get("all_enabled") is not False:
        raise RuntimeError("v6 generation manifest must be all-disabled")

    runner = load_module(
        "roundtrip_v6_runner_for_preformal_audit",
        root / "scripts" / "roundtrip_v6" / "run_target_v6.py",
    )
    contract = runner.contract_extractor

    rows: list[PairRow] = []
    details: list[dict[str, Any]] = []
    all_config_paths: list[str] = []

    print("\n=== 17-PAIR AUDIT ===")
    for target in sorted(manifest["targets"], key=lambda row: int(row["pair_sequence"])):
        pair_id = str(target["pair_id"])
        sequence = int(target["pair_sequence"])
        conditions = target["conditions"]
        non_rel = str(conditions["non_rag"]["config_path"])
        rag_rel = str(conditions["rag"]["config_path"])
        all_config_paths.extend([non_rel, rag_rel])
        non_path = root / non_rel
        rag_path = root / rag_rel
        non = read_json(non_path)
        rag = read_json(rag_path)

        if sha256_file(non_path) != conditions["non_rag"]["config_sha256"]:
            raise RuntimeError(f"non-RAG config hash mismatch: {pair_id}")
        if sha256_file(rag_path) != conditions["rag"]["config_sha256"]:
            raise RuntimeError(f"RAG config hash mismatch: {pair_id}")

        runner.validate_v6_config(non, project_root=root, check_files=True)
        runner.validate_v6_config(rag, project_root=root, check_files=True)

        common_match, common_mismatches = compare_common_fields(non, rag)
        if not common_match:
            raise RuntimeError(
                f"Paired common fields differ for {pair_id}: {common_mismatches}"
            )

        repository = root / str(non["repository_path"])
        repo_head = git(repository, "rev-parse", "HEAD")
        repo_head_match = repo_head == str(non["repository_commit"])
        if not repo_head_match:
            raise RuntimeError(
                f"Repository HEAD mismatch for {pair_id}: {repo_head} != {non['repository_commit']}"
            )
        if git(repository, "status", "--short", "--untracked-files=no"):
            raise RuntimeError(f"Tracked submodule changes detected for {pair_id}")

        frozen_retrieval_rel = str(
            rag["repository_retrieval"]["frozen_reference_manifest"]
        )
        frozen_retrieval = root / frozen_retrieval_rel
        frozen_sha = sha256_file(frozen_retrieval)
        if frozen_sha != rag["repository_retrieval"]["frozen_reference_manifest_sha256"]:
            raise RuntimeError(f"Frozen retrieval manifest hash mismatch: {pair_id}")

        non_extract, non_repeat = extract_twice(
            contract,
            root=root,
            config_path=non_path,
            mode="nonrag",
            retrieval_manifest=None,
        )
        rag_extract, rag_repeat = extract_twice(
            contract,
            root=root,
            config_path=rag_path,
            mode="rag",
            retrieval_manifest=frozen_retrieval,
        )

        non_manifest = non_extract["manifest"]
        rag_manifest = rag_extract["manifest"]
        expected_non = non["deterministic_contract"]
        expected_rag = rag["deterministic_contract"]
        for actual, expected, label in (
            (
                non_manifest["source_contract_sha256"],
                expected_non["expected_source_contract_sha256"],
                "non-RAG source",
            ),
            (
                non_manifest["combined_contract_sha256"],
                expected_non["expected_combined_contract_sha256"],
                "non-RAG combined",
            ),
            (
                rag_manifest["source_contract_sha256"],
                expected_rag["expected_source_contract_sha256"],
                "RAG source",
            ),
            (
                rag_manifest["dependency_contract_sha256"],
                expected_rag["expected_dependency_contract_sha256"],
                "RAG dependency",
            ),
            (
                rag_manifest["combined_contract_sha256"],
                expected_rag["expected_combined_contract_sha256"],
                "RAG combined",
            ),
        ):
            if actual != expected:
                raise RuntimeError(f"{label} contract freeze mismatch for {pair_id}")

        same_source = (
            non_manifest["source_contract_sha256"]
            == rag_manifest["source_contract_sha256"]
        )
        if not same_source:
            raise RuntimeError(f"Source-local contract differs across pair for {pair_id}")

        rebuilt = runner.retrieval.build_bundle(
            repository=repository,
            repository_commit=str(rag["repository_commit"]),
            source_files=runner.v2.source_files_for(rag),
            generic_knowledge_path=root / runner.GENERIC_KNOWLEDGE_FILE,
            pair_id=pair_id,
        )
        if rebuilt["unresolved"] or rebuilt["ambiguous"]:
            raise RuntimeError(f"RAG retrieval rebuild incomplete for {pair_id}")
        rag_hash_match = (
            rebuilt["combined_context_sha256"]
            == rag["repository_retrieval"]["expected_combined_context_sha256"]
        )
        rag_paths_match = list(rebuilt["selected_paths"]) == list(
            rag["repository_retrieval"]["expected_selected_paths"]
        )
        if not rag_hash_match or not rag_paths_match:
            raise RuntimeError(f"RAG retrieval freeze mismatch for {pair_id}")

        target_sources = set(runner.v2.source_files_for(rag))
        overlap = sorted(target_sources.intersection(rebuilt["selected_paths"]))
        suspicious = [
            path for path in rebuilt["selected_paths"] if is_suspicious_selected_path(path)
        ]
        if overlap:
            raise RuntimeError(f"Target source overlap in RAG paths for {pair_id}: {overlap}")
        if suspicious:
            raise RuntimeError(
                f"Potential generated/test/report leakage paths for {pair_id}: {suspicious}"
            )

        non_root = runner.v2.resolve_experiment_root(non, root)
        rag_root = runner.v2.resolve_experiment_root(rag, root)
        roots_absent = not non_root.exists() and not rag_root.exists()
        if not roots_absent:
            raise RuntimeError(
                f"Formal experiment output already exists for {pair_id}: "
                f"nonrag={non_root.exists()}, rag={rag_root.exists()}"
            )

        passed = all(
            [
                not non.get("enabled", False),
                not rag.get("enabled", False),
                common_match,
                repo_head_match,
                non_repeat,
                rag_repeat,
                same_source,
                rag_hash_match,
                rag_paths_match,
                not overlap,
                not suspicious,
                roots_absent,
            ]
        )
        row = PairRow(
            pair_id=pair_id,
            pair_sequence=sequence,
            repository_id=str(non["repository_id"]),
            granularity=str(non["granularity"]),
            nonrag_enabled=bool(non.get("enabled", False)),
            rag_enabled=bool(rag.get("enabled", False)),
            common_fields_match=common_match,
            repository_head_match=repo_head_match,
            source_contract_repeat_match=non_repeat,
            rag_contract_repeat_match=rag_repeat,
            source_contract_same_across_conditions=same_source,
            rag_retrieval_hash_match=rag_hash_match,
            rag_selected_paths_match=rag_paths_match,
            rag_target_overlap_count=len(overlap),
            rag_leakage_path_count=len(suspicious),
            experiment_roots_absent=roots_absent,
            passed=passed,
        )
        rows.append(row)
        details.append(
            {
                **asdict(row),
                "non_rag_config": non_rel,
                "rag_config": rag_rel,
                "frozen_retrieval_manifest": frozen_retrieval_rel,
                "frozen_retrieval_manifest_sha256": frozen_sha,
                "rag_context_sha256": rebuilt["combined_context_sha256"],
                "selected_paths": rebuilt["selected_paths"],
                "source_contract_sha256": non_manifest["source_contract_sha256"],
                "rag_dependency_contract_sha256": rag_manifest[
                    "dependency_contract_sha256"
                ],
                "rag_combined_contract_sha256": rag_manifest[
                    "combined_contract_sha256"
                ],
                "non_rag_experiment_root": str(non_root),
                "rag_experiment_root": str(rag_root),
            }
        )
        print(
            f"{pair_id:36s} configs=PASS contracts=PASS retrieval=PASS roots=ABSENT"
        )

    if len(rows) != 17:
        raise RuntimeError(f"Expected 17 audited pairs, got {len(rows)}")
    if len(all_config_paths) != 34 or len(set(all_config_paths)) != 34:
        raise RuntimeError("Expected 34 unique config paths")

    if OUTPUT_DIR.is_absolute():
        out_dir = OUTPUT_DIR
    else:
        out_dir = root / OUTPUT_DIR
    if out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite preformal audit output: {out_dir}")
    out_dir.mkdir(parents=True)

    summary = {
        "schema_version": "6.0",
        "audit_type": "v6_all_disabled_formal_preparation_audit",
        "branch": branch,
        "head": head,
        "pair_count": len(rows),
        "config_count": len(all_config_paths),
        "all_configs_disabled": all(
            not row.nonrag_enabled and not row.rag_enabled for row in rows
        ),
        "all_pair_common_fields_match": all(row.common_fields_match for row in rows),
        "all_repository_heads_match": all(row.repository_head_match for row in rows),
        "all_contract_repeat_hash_match": all(
            row.source_contract_repeat_match and row.rag_contract_repeat_match
            for row in rows
        ),
        "all_source_contracts_same_across_conditions": all(
            row.source_contract_same_across_conditions for row in rows
        ),
        "all_rag_retrieval_hashes_match": all(
            row.rag_retrieval_hash_match for row in rows
        ),
        "all_rag_selected_paths_match": all(
            row.rag_selected_paths_match for row in rows
        ),
        "rag_target_overlap_total": sum(row.rag_target_overlap_count for row in rows),
        "rag_leakage_path_total": sum(row.rag_leakage_path_count for row in rows),
        "all_experiment_roots_absent": all(row.experiment_roots_absent for row in rows),
        "budget_proxy_go": budget.get("proxy_go_for_preformal_config_preparation"),
        "tokenizer_validation_max_abs_delta": (
            budget.get("tokenizer_validation") or {}
        ).get("max_abs_delta"),
        "tree_sitter_version": version("tree-sitter"),
        "tree_sitter_cpp_version": version("tree-sitter-cpp"),
        "transformers_version": version("transformers"),
        "llm_called": False,
        "ollama_called": False,
        "docker_called": False,
        "build_or_test_called": False,
        "go_for_baseline_probe": all(row.passed for row in rows),
        "go_for_formal_enablement": False,
        "note": (
            "This audit permits the next no-LLM formal-preparation step only. "
            "Baseline source/test readiness and enable-plan commit remain separate."
        ),
        "rows": details,
    }
    write_json(out_dir / "summary.json", summary)

    csv_path = out_dir / "pairs.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    print("\n=== SUMMARY ===")
    print(f"pairs                            = {len(rows)}/17")
    print(f"configs                          = {len(all_config_paths)}/34")
    print(f"all configs disabled             = {summary['all_configs_disabled']}")
    print(f"paired common fields             = {summary['all_pair_common_fields_match']}")
    print(f"contract repeat hashes           = {summary['all_contract_repeat_hash_match']}")
    print(f"RAG retrieval hashes             = {summary['all_rag_retrieval_hashes_match']}")
    print(f"RAG target overlap total         = {summary['rag_target_overlap_total']}")
    print(f"RAG leakage path total           = {summary['rag_leakage_path_total']}")
    print(f"formal experiment roots absent   = {summary['all_experiment_roots_absent']}")
    print(f"go_for_baseline_probe            = {summary['go_for_baseline_probe']}")
    print("go_for_formal_enablement          = False")
    print(f"saved = {(OUTPUT_DIR / 'summary.json').as_posix()}")
    print(f"saved = {(OUTPUT_DIR / 'pairs.csv').as_posix()}")
    print("No LLM, Ollama, Docker, build, or test call was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
