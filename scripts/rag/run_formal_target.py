"""Execute one frozen formal repository-context RAG target exactly once."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.rag.formal_run_policy import (
    FormalRunPolicyError,
    build_code_request,
    build_design_request,
    validate_formal_target,
)
from scripts.rag.formal_run_runtime import (
    FormalRunExecutionError,
    RuntimeHooks,
    default_hooks,
    evaluate_generated_code,
    execute_llm_request,
    materialize_code_output,
    prepare_inputs,
    record_pipeline_failure,
    write_json,
    write_target_reports,
    write_text,
)


def run_formal_target(
    config_path: Path,
    project_root: Path,
    *,
    hooks: RuntimeHooks | None = None,
) -> int:
    root = project_root.resolve()
    runtime = hooks or default_hooks()
    target = validate_formal_target(
        config_path,
        root,
        require_enabled=True,
        require_output_absent=True,
    )
    target.experiment_root.mkdir(parents=True, exist_ok=False)
    llm_calls = {"design_generation": 0, "code_regeneration": 0}
    stage = "prepare"
    try:
        prepared = prepare_inputs(target, root, runtime)

        stage = "design_generation"
        design_request = build_design_request(
            target,
            root,
            prepared.design_input,
        )
        llm_calls["design_generation"] += 1
        _, design_text = execute_llm_request(
            target=target,
            request=design_request,
            stage="design_generation",
            hooks=runtime,
            call_index=1,
        )
        write_text(
            target.experiment_root / "generated" / "design_document.md",
            design_text.rstrip() + "\n",
        )

        stage = "code_regeneration"
        code_request = build_code_request(
            target,
            design_text,
            prepared.fixed_scaffold,
        )
        llm_calls["code_regeneration"] += 1
        _, code_text = execute_llm_request(
            target=target,
            request=code_request,
            stage="code_regeneration",
            hooks=runtime,
            call_index=1,
        )

        stage = "materialize_code"
        materialize_code_output(target, code_text)

        stage = "evaluate"
        evaluation = evaluate_generated_code(
            target,
            root,
            prepared,
            runtime,
        )

        stage = "report"
        evaluation["generation_policy"] = {
            "design_generation_calls": llm_calls["design_generation"],
            "code_regeneration_calls": llm_calls["code_regeneration"],
            "retry_performed": False,
            "automatic_repair_performed": False,
            "manual_patch_performed": False,
        }
        write_json(
            target.experiment_root / "evaluation" / "evaluation_manifest.json",
            evaluation,
        )
        write_target_reports(target, evaluation)
        return 0 if evaluation.get("overall_pass") is True else 1
    except Exception as error:
        record_pipeline_failure(
            target=target,
            project_root=root,
            stage=stage,
            error=error,
            llm_calls=llm_calls,
            hooks=runtime,
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute one frozen formal RAG target exactly once."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    return run_formal_target(args.config, args.project_root)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
