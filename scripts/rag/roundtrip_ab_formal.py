"""Frozen-candidate formal runner support for the design-only A/B experiment.

The v2 path is deliberately separate from the development v1 runner.  Generic
design knowledge is common to A and B; only deterministic repository-derived
dependency context is added to B.  Formal execution additionally requires an
external authorization artifact whose hashes bind every frozen input.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from scripts.rag.canonical import canonical_json_bytes, canonical_jsonl_bytes, sha256_bytes, sha256_file
from scripts.rag.roundtrip_ab import (
    CONDITIONS,
    RequestBundle,
    RetrievalBundle,
    RoundtripABError,
    SourceReplacementTransaction,
    _mapping,
    _ollama_text,
    _run_stage,
    _write_exclusive,
    build_code_request,
    contact_generation_server,
    git_output,
    load_json,
    load_target_inputs,
    read_prompt,
    resolve_project_path,
    resolve_repository_root,
    retrieve_dependency_headers,
    utc_now,
    verify_repository,
)


COMMON_SCHEMA = "roundtrip-design-only-ab-common-v2"
TARGET_SCHEMA = "roundtrip-design-only-ab-target-v2"
MANIFEST_SCHEMA = "roundtrip-ab-formal-evaluation-manifest-v1"
AUTHORIZATION_SCHEMA = "roundtrip-ab-formal-execution-authorization-v1"
GENERIC_KNOWLEDGE_MODE = "common-fixed-v4-v5-plus-roundtrip-v1"
DEPENDENCY_MODE = "direct-project-local-quoted-include-whole-file-one-hop-v1"
NORMALIZATION_MODE = "utf8-bom-aware-newlines-to-lf-v1"

COMMON_KNOWLEDGE_TARGET_KEYS = {
    "design_knowledge_mode",
    "fixed_design_knowledge_path",
    "fixed_design_knowledge_sha256",
    "fixed_design_knowledge_content_sha256",
    "roundtrip_completeness_mode",
    "roundtrip_completeness_path",
    "roundtrip_completeness_sha256",
    "roundtrip_completeness_content_sha256",
}
TARGET_TUNING_KEYS = {
    "knowledge_index_path",
    "knowledge_index_sha256",
    "knowledge_top_k",
    "pilot_top_k",
    "retrieval_top_k",
    "context_budget_tokens",
    "manual_query",
    "query_text",
}


def _verify_file_and_content(
    project_root: Path, record: Mapping[str, Any], *, field: str
) -> tuple[Path, str]:
    path = resolve_project_path(project_root, str(record["path"]), field=field)
    actual_file_hash = sha256_file(path)
    if actual_file_hash != str(record.get("file_sha256", "")):
        raise RoundtripABError(f"{field} file SHA-256 mismatch")
    text = read_prompt(path)
    actual_content_hash = sha256_bytes(text.encode("utf-8"))
    if actual_content_hash != str(record.get("content_sha256", "")):
        raise RoundtripABError(f"{field} content SHA-256 mismatch")
    return path, text


def load_common_v2(path: Path, project_root: Path) -> dict[str, Any]:
    common = load_json(path)
    if common.get("artifact_schema_version") != COMMON_SCHEMA:
        raise RoundtripABError("formal common config schema differs")
    if common.get("formal_execution_authorized") is not False:
        raise RoundtripABError("common config must not authorize formal execution")
    generation = _mapping(common.get("generation"), "common.generation")
    if generation.get("stream") is not False:
        raise RoundtripABError("streaming generation is prohibited")
    option_sets = {
        stage: _mapping(generation.get(f"{stage}_options"), f"common.generation.{stage}_options")
        for stage in ("design", "code")
    }
    for stage, options in option_sets.items():
        for key in ("num_ctx", "num_predict", "seed", "temperature"):
            if key not in options:
                raise RoundtripABError(f"common {stage} generation option is missing: {key}")
    if option_sets["design"]["num_ctx"] != option_sets["code"]["num_ctx"]:
        raise RoundtripABError("design/code context settings must be common")
    for key in ("seed", "temperature", "top_k", "top_p", "repeat_penalty"):
        if option_sets["design"].get(key) != option_sets["code"].get(key):
            raise RoundtripABError(f"design/code shared generation option differs: {key}")

    prompts = _mapping(common.get("prompts"), "common.prompts")
    for name in (
        "design_generation",
        "code_generation_system",
        "code_generation_user",
        "code_generation_schema",
    ):
        prompt_path = resolve_project_path(project_root, str(prompts[name]), field=name)
        if sha256_file(prompt_path) != str(prompts.get(f"{name}_sha256", "")):
            raise RoundtripABError(f"common prompt/schema hash mismatch for {name}")

    knowledge = _mapping(common.get("common_design_knowledge"), "common_design_knowledge")
    if knowledge.get("mode") != GENERIC_KNOWLEDGE_MODE:
        raise RoundtripABError("common design knowledge mode differs")
    _verify_file_and_content(
        project_root,
        _mapping(knowledge.get("detailed_design_guidance"), "detailed_design_guidance"),
        field="detailed design guidance",
    )
    _verify_file_and_content(
        project_root,
        _mapping(knowledge.get("roundtrip_completeness"), "roundtrip_completeness"),
        field="round-trip completeness knowledge",
    )
    isolation = _mapping(common.get("input_isolation"), "common.input_isolation")
    if isolation.get("code_generation_allowed_semantic_inputs") != [
        "final design specification"
    ]:
        raise RoundtripABError("code generation is not design-only")
    return common


def load_common_knowledge(common: Mapping[str, Any], project_root: Path) -> dict[str, str]:
    knowledge = _mapping(common.get("common_design_knowledge"), "common_design_knowledge")
    _, detailed = _verify_file_and_content(
        project_root,
        _mapping(knowledge["detailed_design_guidance"], "detailed_design_guidance"),
        field="detailed design guidance",
    )
    _, completeness = _verify_file_and_content(
        project_root,
        _mapping(knowledge["roundtrip_completeness"], "roundtrip_completeness"),
        field="round-trip completeness knowledge",
    )
    return {"detailed_design_guidance": detailed, "roundtrip_completeness": completeness}


def validate_target_v2(config: Mapping[str, Any], *, formal: bool | None = None) -> None:
    if config.get("artifact_schema_version") != TARGET_SCHEMA:
        raise RoundtripABError("formal target config schema differs")
    if config.get("formal_execution_authorized") is not False:
        raise RoundtripABError("target config must not authorize formal execution")
    if formal is not None and config.get("formal_target_member") is not formal:
        raise RoundtripABError("formal target membership differs")
    if config.get("granularity") not in {
        "full_file",
        "module_files",
        "class_span",
        "function",
    }:
        raise RoundtripABError("unsupported replacement granularity")
    inputs = config.get("target_owned_inputs")
    units = config.get("replacement_units")
    if not isinstance(inputs, list) or not inputs:
        raise RoundtripABError("target_owned_inputs must be non-empty")
    if not isinstance(units, list) or not units:
        raise RoundtripABError("replacement_units must be non-empty")
    required: set[tuple[str, str]] = set()
    for raw in inputs:
        item = _mapping(raw, "target_owned_inputs item")
        pair = (str(item.get("file_id", "")), str(item.get("unit_id", "")))
        if not re.fullmatch(r"F\d{2}", pair[0]) or not re.fullmatch(r"U\d{2}", pair[1]):
            raise RoundtripABError("target input IDs must use Fxx/Uxx")
        if item.get("scope") not in {"full_file", "byte_span"}:
            raise RoundtripABError("target input scope differs")
        if item.get("replacement_required") is True:
            required.add(pair)
    configured = {
        (str(_mapping(raw, "replacement unit")["file_id"]), str(raw["unit_id"]))
        for raw in units
    }
    if configured != required:
        raise RoundtripABError("replacement units do not exactly match replacement inputs")

    one_shot = _mapping(config.get("one_shot"), "one_shot")
    expected_policy = {
        "automatic_repair": False,
        "code_generation_count": 1,
        "design_generation_count": 1,
        "manual_patch": False,
        "overwrite": False,
        "retry": False,
    }
    for key, value in expected_policy.items():
        if one_shot.get(key) != value:
            raise RoundtripABError(f"one_shot.{key} must be {value!r}")

    retrieval = _mapping(config.get("retrieval"), "retrieval")
    if retrieval.get("dependency_header_mode") != DEPENDENCY_MODE:
        raise RoundtripABError("dependency retrieval mode differs")
    if retrieval.get("dependency_header_normalization") != NORMALIZATION_MODE:
        raise RoundtripABError("dependency normalization differs")
    if retrieval.get("target_specific_manual_query") is not False:
        raise RoundtripABError("target-specific manual query is prohibited")
    forbidden = sorted((COMMON_KNOWLEDGE_TARGET_KEYS | TARGET_TUNING_KEYS) & set(retrieval))
    if forbidden:
        raise RoundtripABError("target-level common knowledge/tuning fields are prohibited: " + ", ".join(forbidden))


def _input_envelope(inputs: Sequence[Any]) -> str:
    replacement_ids = [f"{item.file_id}/{item.unit_id}" for item in inputs if item.replacement_required]
    reference_ids = [f"{item.file_id}/{item.unit_id}" for item in inputs if not item.replacement_required]
    parts = [
        "TARGET-OWNED INPUTS",
        "Fxx/Uxx identifiers are opaque. Preserve names, types, signatures, namespaces, and replacement boundaries in the final specification.",
        "",
        "REPLACEMENT UNIT CONTRACT",
        "Only replacement_required=true units will be regenerated. Reference-only units must inform the design but must not become output units.",
        f"REPLACEMENT UNITS: {', '.join(replacement_ids)}",
        f"REFERENCE-ONLY INPUTS: {', '.join(reference_ids) if reference_ids else 'none'}",
    ]
    for item in inputs:
        parts.extend(
            [
                "",
                f"===== BEGIN {item.file_id}/{item.unit_id} =====",
                f"path: {item.path}",
                f"role: {item.role}",
                f"replacement_required: {str(item.replacement_required).lower()}",
                item.content.rstrip(),
                f"===== END {item.file_id}/{item.unit_id} =====",
            ]
        )
    return "\n".join(parts)


def compose_repository_context(dependencies: Sequence[Mapping[str, Any]]) -> str:
    chunks = ["RAG_CONTEXT repository-dependencies-v1\n"]
    for record in dependencies:
        path = str(record["path"])
        chunks.extend(
            [
                f"\n### PATH: {path}\n",
                f"SOURCE_SHA256: {record['source_sha256']}\n",
                f"CONTENT_SHA256: {record['content_sha256']}\n",
                f"----- BEGIN DEPENDENCY HEADER CONTENT: {path} -----\n",
                str(record["content"]),
                f"\n----- END DEPENDENCY HEADER CONTENT: {path} -----\n",
            ]
        )
    return "".join(chunks)


def build_retrieval_bundle_v2(
    config: Mapping[str, Any], common: Mapping[str, Any], project_root: Path, repository_root: Path
) -> RetrievalBundle:
    validate_target_v2(config)
    inputs = load_target_inputs(config, repository_root)
    dependencies = retrieve_dependency_headers(config, repository_root, inputs)
    context = compose_repository_context(dependencies)
    dependency_text = "\n".join(str(item["content"]) for item in dependencies)
    leakage = {
        "forbidden_path_count": 0,
        "target_owned_path_overlap_count": sum(1 for item in dependencies if item["path"] in {x.path for x in inputs}),
        "test_content_injected": bool(re.search(r"\b(?:TEST|TEST_F|EXPECT_[A-Z_]+|ASSERT_[A-Z_]+)\s*\(", dependency_text)),
        "previous_generated_artifact_injected": bool(re.search(r"previous LLM output|generated design document|experiment result", dependency_text, re.I)),
    }
    status = "pass" if not any(leakage.values()) else "fail"
    knowledge = load_common_knowledge(common, project_root)
    query = {
        "artifact_schema_version": "roundtrip-ab-retrieval-query-v4",
        "dependency_header_mode": DEPENDENCY_MODE,
        "manual_query_used": False,
        "source_feature_selection_used": False,
        "target_id": config["target_id"],
        "target_specific_override_used": False,
    }
    manifest = {
        "artifact_schema_version": "roundtrip-ab-retrieval-manifest-v4",
        "condition": "B",
        "context_bytes": len(context.encode("utf-8")),
        "context_sha256": sha256_bytes(context.encode("utf-8")),
        "dependency_header_count": len(dependencies),
        "dependency_header_mode": DEPENDENCY_MODE,
        "generic_knowledge_in_rag_context": False,
        "leakage": leakage,
        "llm_call_count": 0,
        "generation_server_contacted": False,
        "status": status,
        "target_id": config["target_id"],
    }
    return RetrievalBundle(
        context=context,
        query=query,
        fixed_design_knowledge=knowledge["detailed_design_guidance"],
        roundtrip_completeness_knowledge=knowledge["roundtrip_completeness"],
        dependency_records=tuple(dict(item) for item in dependencies),
        manifest=manifest,
    )


def build_design_request_v2(
    config: Mapping[str, Any],
    common: Mapping[str, Any],
    project_root: Path,
    inputs: Sequence[Any],
    *,
    condition: str,
    repository_context: str | None,
) -> RequestBundle:
    if condition not in CONDITIONS:
        raise RoundtripABError("condition must be A or B")
    if condition == "A" and repository_context is not None:
        raise RoundtripABError("Condition A must not receive repository context")
    if condition == "B" and repository_context is None:
        raise RoundtripABError("Condition B requires repository context")
    prompts = _mapping(common.get("prompts"), "common.prompts")
    base_path = resolve_project_path(project_root, str(prompts["design_generation"]), field="design prompt")
    base = read_prompt(base_path)
    knowledge = load_common_knowledge(common, project_root)
    common_knowledge = (
        "===== BEGIN COMMON GENERIC DESIGN KNOWLEDGE =====\n"
        "----- BEGIN V4/V5 DETAILED-DESIGN GUIDANCE -----\n"
        + knowledge["detailed_design_guidance"]
        + "\n----- END V4/V5 DETAILED-DESIGN GUIDANCE -----\n\n"
        "----- BEGIN ROUND-TRIP COMPLETENESS KNOWLEDGE -----\n"
        + knowledge["roundtrip_completeness"]
        + "\n----- END ROUND-TRIP COMPLETENESS KNOWLEDGE -----\n"
        "===== END COMMON GENERIC DESIGN KNOWLEDGE ====="
    )
    parts = [base, "", common_knowledge, "", _input_envelope(inputs)]
    if condition == "B":
        parts.extend(["", "===== BEGIN RAG_CONTEXT =====", str(repository_context).rstrip(), "===== END RAG_CONTEXT ====="])
    prompt = "\n".join(parts).rstrip() + "\n"
    generation = _mapping(common.get("generation"), "common.generation")
    payload = {
        "model": generation["model"],
        "prompt": prompt,
        "stream": False,
        "options": dict(_mapping(generation.get("design_options"), "generation.design_options")),
    }
    audit = {
        "artifact_schema_version": "roundtrip-ab-design-request-audit-v2",
        "base_prompt_sha256": sha256_bytes(base.encode("utf-8")),
        "common_knowledge_sha256": sha256_bytes(common_knowledge.encode("utf-8")),
        "condition": condition,
        "fixed_scaffold_loaded": False,
        "prompt_sha256": sha256_bytes(prompt.encode("utf-8")),
        "repository_context_injected": condition == "B",
        "target_id": config["target_id"],
    }
    return RequestBundle(payload=payload, prompt=prompt, audit=audit)


def build_plan_v2(
    config: Mapping[str, Any], common: Mapping[str, Any], project_root: Path
) -> dict[str, Any]:
    validate_target_v2(config)
    repository_root = resolve_repository_root(config, project_root)
    repository = verify_repository(config, repository_root)
    inputs = load_target_inputs(config, repository_root)
    retrieval = build_retrieval_bundle_v2(config, common, project_root, repository_root)
    requests = {
        "A": build_design_request_v2(config, common, project_root, inputs, condition="A", repository_context=None),
        "B": build_design_request_v2(config, common, project_root, inputs, condition="B", repository_context=retrieval.context),
    }
    a, b = requests["A"], requests["B"]
    for key in ("model", "options", "stream"):
        if a.payload[key] != b.payload[key]:
            raise RoundtripABError(f"A/B generation field differs: {key}")
    if a.audit["base_prompt_sha256"] != b.audit["base_prompt_sha256"] or a.audit["common_knowledge_sha256"] != b.audit["common_knowledge_sha256"]:
        raise RoundtripABError("A/B common design inputs differ")
    return {
        "artifact_schema_version": "roundtrip-ab-plan-v2",
        "a_b_primary_difference": "target-specific repository dependency context is present only in B",
        "code_generation_semantic_input": "final_design_specification_only",
        "conditions": {
            condition: {
                "design_prompt_sha256": sha256_bytes(bundle.prompt.encode("utf-8")),
                "design_request_sha256": sha256_bytes(canonical_json_bytes(bundle.payload)),
                "repository_context_injected": bundle.audit["repository_context_injected"],
            }
            for condition, bundle in requests.items()
        },
        "generation_server_contacted": False,
        "llm_call_count": 0,
        "repository": repository,
        "retrieval_context_sha256": retrieval.manifest["context_sha256"],
        "retrieval_status": retrieval.manifest["status"],
        "target_id": config["target_id"],
    }


def build_code_request_v2(
    final_design_document: str,
    common: Mapping[str, Any],
    project_root: Path,
    *,
    expected_units: Sequence[Mapping[str, Any]],
) -> RequestBundle:
    """Use the frozen code-stage options while preserving design-only inputs."""
    common_for_code = dict(common)
    generation = dict(_mapping(common.get("generation"), "generation"))
    generation["options"] = dict(_mapping(generation.get("code_options"), "generation.code_options"))
    common_for_code["generation"] = generation
    return build_code_request(
        final_design_document,
        common_for_code,
        project_root,
        expected_units=expected_units,
    )
def write_retrieval_v2(output_root: Path, bundle: RetrievalBundle) -> None:
    if output_root.exists():
        raise RoundtripABError(f"refusing to overwrite retrieval artifacts: {output_root}")
    _write_exclusive(output_root / "query.json", canonical_json_bytes(bundle.query))
    _write_exclusive(output_root / "candidates_selected.jsonl", canonical_jsonl_bytes(bundle.dependency_records))
    _write_exclusive(output_root / "actual_rag_context.txt", bundle.context.encode("utf-8"))
    manifest = dict(bundle.manifest)
    manifest["artifact_hashes"] = {
        "actual_rag_context.txt": sha256_bytes(bundle.context.encode("utf-8")),
        "candidates_selected.jsonl": sha256_bytes(canonical_jsonl_bytes(bundle.dependency_records)),
        "query.json": sha256_bytes(canonical_json_bytes(bundle.query)),
    }
    _write_exclusive(output_root / "retrieval_manifest.json", canonical_json_bytes(manifest))


def write_plan_v2(
    config: Mapping[str, Any], common: Mapping[str, Any], project_root: Path
) -> dict[str, Any]:
    plan = build_plan_v2(config, common, project_root)
    execution = _mapping(config.get("execution"), "execution")
    plan_root = resolve_project_path(project_root, str(execution["plan_root"]), field="plan_root")
    if plan_root.exists():
        raise RoundtripABError(f"plan output already exists: {plan_root}")
    repository_root = resolve_repository_root(config, project_root)
    inputs = load_target_inputs(config, repository_root)
    retrieval = build_retrieval_bundle_v2(config, common, project_root, repository_root)
    requests = {
        "A": build_design_request_v2(config, common, project_root, inputs, condition="A", repository_context=None),
        "B": build_design_request_v2(config, common, project_root, inputs, condition="B", repository_context=retrieval.context),
    }
    _write_exclusive(plan_root / "snapshots/common_config.json", canonical_json_bytes(common))
    _write_exclusive(plan_root / "snapshots/target_config.json", canonical_json_bytes(config))
    for condition, request in requests.items():
        root = plan_root / f"condition-{condition.lower()}"
        _write_exclusive(root / "design_prompt.txt", request.prompt.encode("utf-8"))
        _write_exclusive(root / "design_request.json", canonical_json_bytes(request.payload))
        _write_exclusive(root / "design_request_audit.json", canonical_json_bytes(request.audit))
    write_retrieval_v2(plan_root / "condition-b/retrieval", retrieval)
    _write_exclusive(plan_root / "plan_manifest.json", canonical_json_bytes(plan))
    return plan


def _artifact_hashes(root: Path, *, exclude: set[str] | None = None) -> dict[str, str]:
    skipped = exclude or set()
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in skipped
    }


GenerationCall = Callable[[str, Mapping[str, str], bytes, int], bytes]


def execute_condition_v2_once(
    config: Mapping[str, Any],
    common: Mapping[str, Any],
    project_root: Path,
    condition: str,
    *,
    formal: bool,
    call_generation: GenerationCall = contact_generation_server,
) -> dict[str, Any]:
    validate_target_v2(config, formal=formal)
    if condition not in CONDITIONS:
        raise RoundtripABError("condition must be A or B")
    execution = _mapping(config.get("execution"), "execution")
    if execution.get("enabled") is not True:
        raise RoundtripABError("execution is disabled")
    repository_root = resolve_repository_root(config, project_root)
    repository_state = verify_repository(config, repository_root)
    run_root = resolve_project_path(project_root, str(execution["output_root"]), field="output_root") / f"condition-{condition.lower()}"
    if run_root.exists():
        raise RoundtripABError(f"one-shot attempt or result already exists: {run_root}")
    attempt = {
        "artifact_schema_version": "roundtrip-ab-attempt-v2",
        "condition": condition,
        "formal": formal,
        "reserved_at_utc": utc_now(),
        "retry_allowed": False,
        "target_id": config["target_id"],
    }
    _write_exclusive(run_root / "attempt.json", canonical_json_bytes(attempt))
    _write_exclusive(run_root / "snapshots" / "common_config.json", canonical_json_bytes(common))
    _write_exclusive(run_root / "snapshots" / "target_config.json", canonical_json_bytes(config))

    inputs = load_target_inputs(config, repository_root)
    retrieval = build_retrieval_bundle_v2(config, common, project_root, repository_root)
    repository_context = retrieval.context if condition == "B" else None
    if condition == "B":
        write_retrieval_v2(run_root / "retrieval", retrieval)
    else:
        _write_exclusive(run_root / "retrieval" / "actual_rag_context.txt", b"")
        _write_exclusive(
            run_root / "retrieval" / "retrieval_manifest.json",
            canonical_json_bytes({"artifact_schema_version": "roundtrip-ab-retrieval-not-applied-v1", "condition": "A", "context_sha256": sha256_bytes(b""), "repository_context_injected": False}),
        )
    design_request = build_design_request_v2(config, common, project_root, inputs, condition=condition, repository_context=repository_context)
    design_bytes = canonical_json_bytes(design_request.payload)
    _write_exclusive(run_root / "design" / "prompt.txt", design_request.prompt.encode("utf-8"))
    _write_exclusive(run_root / "design" / "request.json", design_bytes)
    _write_exclusive(run_root / "design" / "request_audit.json", canonical_json_bytes(design_request.audit))

    generation = _mapping(common.get("generation"), "generation")
    endpoint = str(generation["endpoint"])
    headers = dict(_mapping(generation.get("headers"), "generation.headers"))
    timeout = int(generation["timeout_seconds"])
    transaction: SourceReplacementTransaction | None = None
    restored: dict[str, str] = {}
    stages: dict[str, Any] = {}
    contacts = 0
    primary_error: Exception | None = None
    restore_error: Exception | None = None
    try:
        _write_exclusive(run_root / "design" / "contact.json", canonical_json_bytes({"contact_attempted": True, "request_sha256": sha256_bytes(design_bytes), "retry": False, "started_at_utc": utc_now()}))
        contacts += 1
        design_response = call_generation(endpoint, headers, design_bytes, timeout)
        _write_exclusive(run_root / "design" / "response.json", design_response)
        design_document = _ollama_text(design_response, "design generation")
        _write_exclusive(run_root / "design" / "final_design.md", design_document.encode("utf-8"))

        units = config["replacement_units"]
        code_request = build_code_request_v2(design_document, common, project_root, expected_units=units)
        code_bytes = canonical_json_bytes(code_request.payload)
        _write_exclusive(run_root / "code" / "prompt.txt", code_request.prompt.encode("utf-8"))
        _write_exclusive(run_root / "code" / "request.json", code_bytes)
        _write_exclusive(run_root / "code" / "request_audit.json", canonical_json_bytes(code_request.audit))
        _write_exclusive(run_root / "code" / "contact.json", canonical_json_bytes({"contact_attempted": True, "request_sha256": sha256_bytes(code_bytes), "retry": False, "started_at_utc": utc_now()}))
        contacts += 1
        code_response = call_generation(endpoint, headers, code_bytes, timeout)
        _write_exclusive(run_root / "code" / "response.json", code_response)
        generated_text = _ollama_text(code_response, "code generation")
        from scripts.rag.roundtrip_ab import validate_generated_units
        generated = validate_generated_units(generated_text, units)
        generated_artifact = {"units": [{"file_id": pair[0], "unit_id": pair[1], "content": content} for pair, content in sorted(generated.items())]}
        _write_exclusive(run_root / "code" / "generated_units.json", canonical_json_bytes(generated_artifact))

        transaction = SourceReplacementTransaction(repository_root, units, generated)
        transaction.apply()
        workspace = run_root / "evaluation-workspace"
        workspace.mkdir(parents=True, exist_ok=False)
        commands = _mapping(execution.get("commands"), "execution.commands")
        timeouts = _mapping(execution.get("stage_timeouts_seconds"), "execution.stage_timeouts_seconds")
        stage_order = execution.get("stage_order", ["configure", "build", "direct_test", "full_test"])
        if not isinstance(stage_order, list) or not stage_order:
            raise RoundtripABError("execution.stage_order must be non-empty")
        for stage in stage_order:
            command = commands.get(stage)
            if not isinstance(command, list) or not command:
                raise RoundtripABError(f"execution command is missing: {stage}")
            record = _run_stage(str(stage), [str(x) for x in command], repository_root, workspace, int(timeouts[stage]))
            stages[str(stage)] = record
            _write_exclusive(run_root / "evaluation" / f"{stage}.json", canonical_json_bytes(record))
            if record["status"] != "pass":
                break
    except Exception as exc:
        primary_error = exc
    finally:
        if transaction is not None:
            try:
                restored = transaction.restore()
            except Exception as exc:
                restore_error = exc
        restoration = {
            "artifact_schema_version": "roundtrip-ab-restoration-v1",
            "error": str(restore_error) if restore_error else None,
            "repository_clean": git_output(repository_root, "status", "--short") == "",
            "restored_hashes": restored,
            "status": "fail" if restore_error else "pass",
        }
        _write_exclusive(run_root / "evaluation" / "source_restoration.json", canonical_json_bytes(restoration))

    stage_order = [str(x) for x in execution.get("stage_order", [])]
    all_stages = bool(stage_order) and list(stages) == stage_order and all(x["status"] == "pass" for x in stages.values())
    repository_clean = git_output(repository_root, "status", "--short") == ""
    success = primary_error is None and restore_error is None and all_stages and repository_clean
    result = {
        "artifact_schema_version": "roundtrip-ab-result-v2",
        "condition": condition,
        "error": str(primary_error) if primary_error else (str(restore_error) if restore_error else None),
        "formal": formal,
        "generation_server_contact_count": contacts,
        "llm_call_count": contacts,
        "overall_pass": success,
        "repository_clean_after_restoration": repository_clean,
        "repository_commit": repository_state["commit"],
        "retry_performed": False,
        "stages": {stage: record["status"] for stage, record in stages.items()},
        "status": "pass" if success else "fail",
        "target_id": config["target_id"],
    }
    terminal_name = "result.json" if primary_error is None and restore_error is None else "failure.json"
    _write_exclusive(run_root / terminal_name, canonical_json_bytes(result))
    _write_exclusive(
        run_root / "aggregate_run_entry.json",
        canonical_json_bytes(
            {
                "artifact_schema_version": "roundtrip-ab-aggregate-run-entry-v1",
                "condition": condition,
                "result_path": terminal_name,
                "result_sha256": sha256_file(run_root / terminal_name),
                "status": result["status"],
                "target_id": config["target_id"],
            }
        ),
    )
    hashes = _artifact_hashes(run_root, exclude={"artifact_hashes.json"})
    _write_exclusive(run_root / "artifact_hashes.json", canonical_json_bytes({"artifact_schema_version": "roundtrip-ab-artifact-hashes-v1", "hashes": hashes}))
    if primary_error is not None:
        raise primary_error
    if restore_error is not None:
        raise RoundtripABError(f"source restoration failed: {restore_error}") from restore_error
    return result


def load_formal_manifest(path: Path, project_root: Path) -> dict[str, Any]:
    manifest = load_json(path)
    if manifest.get("artifact_schema_version") != MANIFEST_SCHEMA:
        raise RoundtripABError("formal evaluation manifest schema differs")
    targets = manifest.get("targets")
    if not isinstance(targets, list) or len(targets) != 17:
        raise RoundtripABError("formal evaluation manifest must contain 17 targets")
    ids = [str(item.get("target_id")) for item in targets]
    if len(set(ids)) != 17:
        raise RoundtripABError("formal target IDs are not unique")
    for item in targets:
        config_path = resolve_project_path(project_root, str(item["target_config_path"]), field="target config")
        if sha256_file(config_path) != str(item["target_config_sha256"]):
            raise RoundtripABError(f"formal target config hash mismatch: {item['target_id']}")
        config = load_json(config_path)
        validate_target_v2(config, formal=True)
        if config["target_id"] != item["target_id"]:
            raise RoundtripABError("manifest/config target ID mismatch")
        repository_root = resolve_repository_root(config, project_root)
        verify_repository(config, repository_root)
        load_target_inputs(config, repository_root)
    return manifest


def verify_formal_authorization(
    authorization_path: Path,
    manifest_path: Path,
    common_path: Path,
    project_root: Path,
) -> dict[str, Any]:
    authorization = load_json(authorization_path)
    if authorization.get("artifact_schema_version") != AUTHORIZATION_SCHEMA:
        raise RoundtripABError("formal authorization schema differs")
    if authorization.get("authorized") is not True:
        raise RoundtripABError("formal execution is not authorized")
    expected = {
        "manifest_sha256": sha256_file(manifest_path),
        "common_config_sha256": sha256_file(common_path),
    }
    for key, value in expected.items():
        if authorization.get(key) != value:
            raise RoundtripABError(f"formal authorization {key} mismatch")
    return authorization
