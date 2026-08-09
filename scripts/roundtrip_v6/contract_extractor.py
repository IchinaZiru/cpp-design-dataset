from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path, PurePosixPath
from typing import Any

from tree_sitter import Language, Parser
import tree_sitter_cpp


EXPECTED_TREE_SITTER_VERSION = "0.26.0"
EXPECTED_TREE_SITTER_CPP_VERSION = "0.23.4"

EXTRACTOR_VERSION = "v6-ast-contract-1"
SCHEMA_VERSION = "1.0"


def normalize(text: str) -> str:
    return " ".join(text.split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def git_output(
    repository: Path,
    *args: str,
) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            *args,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )

    return result.stdout.strip()


def runtime_versions() -> dict[str, str]:
    try:
        ts_version = version(
            "tree-sitter"
        )

        cpp_version = version(
            "tree-sitter-cpp"
        )

    except PackageNotFoundError as exc:
        raise RuntimeError(
            f"Missing required Tree-sitter package: {exc}"
        ) from exc

    versions = {
        "tree_sitter": ts_version,
        "tree_sitter_cpp": cpp_version,
    }

    if (
        ts_version
        != EXPECTED_TREE_SITTER_VERSION
    ):
        raise RuntimeError(
            "tree-sitter version mismatch: "
            f"{ts_version} != "
            f"{EXPECTED_TREE_SITTER_VERSION}"
        )

    if (
        cpp_version
        != EXPECTED_TREE_SITTER_CPP_VERSION
    ):
        raise RuntimeError(
            "tree-sitter-cpp version mismatch: "
            f"{cpp_version} != "
            f"{EXPECTED_TREE_SITTER_CPP_VERSION}"
        )

    return versions


def make_parser() -> Parser:
    language = Language(
        tree_sitter_cpp.language()
    )

    try:
        return Parser(language)

    except TypeError:
        parser = Parser()
        parser.set_language(language)
        return parser


def load_roundtrip_v2(
    project_root: Path,
):
    path = (
        project_root
        / "scripts"
        / "roundtrip_v2"
        / "run_target_v2.py"
    )

    if not path.is_file():
        raise FileNotFoundError(path)

    spec = importlib.util.spec_from_file_location(
        "roundtrip_v2_for_v6_contract",
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            f"Could not import {path}"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(module)

    return module


def node_text(
    node,
    data: bytes,
) -> str:
    return data[
        node.start_byte:node.end_byte
    ].decode(
        "utf-8",
        errors="replace",
    )


def walk(node):
    yield node

    for child in node.children:
        yield from walk(child)


def has_ancestor(
    node,
    kinds: set[str],
) -> bool:
    parent = node.parent

    while parent is not None:
        if parent.type in kinds:
            return True

        parent = parent.parent

    return False


def last_identifier(
    node,
    data: bytes,
) -> str | None:
    values: list[str] = []

    for child in walk(node):
        if child.type in {
            "identifier",
            "field_identifier",
            "type_identifier",
            "destructor_name",
        }:
            values.append(
                node_text(
                    child,
                    data,
                )
            )

    return (
        values[-1]
        if values
        else None
    )


def function_name(
    node,
    data: bytes,
) -> str | None:
    for child in walk(node):
        if (
            child.type
            != "function_declarator"
        ):
            continue

        declarator = (
            child.child_by_field_name(
                "declarator"
            )
        )

        if declarator is not None:
            name = last_identifier(
                declarator,
                data,
            )

            if name:
                return name

        name = last_identifier(
            child,
            data,
        )

        if name:
            return name

    return None


def function_arity(
    node,
    data: bytes,
) -> tuple[int, int] | None:
    for child in walk(node):
        if (
            child.type
            != "function_declarator"
        ):
            continue

        parameters = (
            child.child_by_field_name(
                "parameters"
            )
        )

        if parameters is None:
            return None

        named = [
            item
            for item
            in parameters.named_children
            if item.type != "comment"
        ]

        if (
            len(named) == 1
            and normalize(
                node_text(
                    named[0],
                    data,
                )
            ) == "void"
        ):
            return (0, 0)

        required = sum(
            "="
            not in node_text(
                item,
                data,
            )
            for item in named
        )

        return (
            required,
            len(named),
        )

    return None


def parse_cpp(
    parser: Parser,
    text: str,
) -> tuple[
    bytes,
    Any,
    list[dict[str, Any]],
]:
    data = text.encode("utf-8")
    tree = parser.parse(data)

    errors: list[
        dict[str, Any]
    ] = []

    for node in walk(
        tree.root_node
    ):
        if node.type != "ERROR":
            continue

        errors.append({
            "start": list(
                node.start_point
            ),
            "end": list(
                node.end_point
            ),
            "text": normalize(
                node_text(
                    node,
                    data,
                )
            )[:300],
        })

    return data, tree, errors


def target_fragments(
    config: dict[str, Any],
    project_root: Path,
    repository: Path,
    roundtrip_v2: Any,
) -> list[
    tuple[str, str]
]:
    granularity = (
        roundtrip_v2
        .normalized_granularity(
            config
        )
    )

    if granularity == "module_files":
        result: list[
            tuple[str, str]
        ] = []

        for relative in (
            roundtrip_v2
            .source_files_for(
                config
            )
        ):
            path = (
                repository
                / relative
            )

            result.append((
                relative,
                path.read_text(
                    encoding="utf-8",
                    errors="replace",
                ),
            ))

        return result

    relative = (
        roundtrip_v2
        .target_source_file_for(
            config
        )
    )

    path = repository / relative

    whole = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    start, end = (
        roundtrip_v2
        .locate_target_span(
            whole,
            config["locator"],
        )
    )

    return [(
        relative,
        whole[start:end],
    )]


def extract_target_facts(
    parser: Parser,
    text: str,
) -> dict[str, Any]:
    data, tree, errors = (
        parse_cpp(
            parser,
            text,
        )
    )

    locals_: list[str] = []
    calls: list[
        dict[str, Any]
    ] = []

    own_names: set[str] = set()

    for node in walk(
        tree.root_node
    ):
        if node.type in {
            "function_definition",
            "declaration",
            "field_declaration",
            "template_declaration",
        }:
            name = function_name(
                node,
                data,
            )

            if name:
                own_names.add(name)

        if (
            node.type == "declaration"
            and has_ancestor(
                node,
                {"compound_statement"},
            )
        ):
            value = normalize(
                node_text(
                    node,
                    data,
                )
            )

            if value not in locals_:
                locals_.append(value)

        if (
            node.type
            == "call_expression"
        ):
            function = (
                node.child_by_field_name(
                    "function"
                )
            )

            arguments = (
                node.child_by_field_name(
                    "arguments"
                )
            )

            if function is None:
                continue

            callee = normalize(
                node_text(
                    function,
                    data,
                )
            )

            name = last_identifier(
                function,
                data,
            )

            if not name:
                continue

            calls.append({
                "name": name,
                "callee": callee,
                "argc": (
                    len(
                        arguments
                        .named_children
                    )
                    if arguments
                    is not None
                    else 0
                ),
                "expression": normalize(
                    node_text(
                        node,
                        data,
                    )
                ),
                "nested_call": (
                    has_ancestor(
                        node,
                        {
                            "call_expression"
                        },
                    )
                ),
            })

    deduped_calls: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[Any, ...]
    ] = set()

    for call in calls:
        key = (
            call["name"],
            call["callee"],
            call["argc"],
            call["expression"],
        )

        if key in seen:
            continue

        seen.add(key)
        deduped_calls.append(
            call
        )

    return {
        "locals": locals_,
        "calls": deduped_calls,
        "own_names": own_names,
        "errors": errors,
    }


def extract_dependency_declarations(
    parser: Parser,
    text: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    data, tree, errors = (
        parse_cpp(
            parser,
            text,
        )
    )

    declarations: list[
        dict[str, Any]
    ] = []

    for node in walk(
        tree.root_node
    ):
        if node.type not in {
            "declaration",
            "field_declaration",
            "function_definition",
            "template_declaration",
        }:
            continue

        name = function_name(
            node,
            data,
        )

        if not name:
            continue

        raw = node_text(
            node,
            data,
        )

        if (
            node.type
            == "function_definition"
        ):
            body = (
                node.child_by_field_name(
                    "body"
                )
            )

            if body is not None:
                raw = data[
                    node.start_byte:
                    body.start_byte
                ].decode(
                    "utf-8",
                    errors="replace",
                ).rstrip() + ";"

        declarations.append({
            "name": name,
            "arity": function_arity(
                node,
                data,
            ),
            "text": normalize(raw),
        })

    output: list[
        dict[str, Any]
    ] = []

    seen: set[
        tuple[Any, ...]
    ] = set()

    for declaration in declarations:
        key = (
            declaration["name"],
            (
                tuple(
                    declaration[
                        "arity"
                    ]
                )
                if declaration[
                    "arity"
                ]
                else None
            ),
            declaration["text"],
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(
            declaration
        )

    return output, errors


def compatible(
    call: dict[str, Any],
    declaration: dict[str, Any],
) -> bool:
    arity = declaration[
        "arity"
    ]

    if arity is None:
        return True

    required, total = arity

    return (
        required
        <= call["argc"]
        <= total
    )


def dependency_candidate_calls(
    calls: list[
        dict[str, Any]
    ],
    own_names: set[str],
) -> list[
    dict[str, Any]
]:
    result: list[
        dict[str, Any]
    ] = []

    for call in calls:
        callee = call["callee"]
        name = call["name"]

        if callee.startswith(
            "std::"
        ):
            continue

        if (
            callee == name
            and name in own_names
        ):
            continue

        if callee.startswith(
            "this->"
        ):
            continue

        result.append(call)

    return result


def render_source_contract(
    locals_: list[str],
    calls: list[
        dict[str, Any]
    ],
) -> str:
    lines = [
        "# Machine-extracted Source-local Implementation Contract",
        "",
        "This appendix is deterministic evidence extracted from the target source.",
        "It is not an LLM summary and it does not contain complete function bodies.",
        "",
        "During regeneration:",
        "- preserve the exact local declaration types, containers, initializers, and literals listed below;",
        "- preserve the exact call targets and argument expressions listed below;",
        "- do not substitute a different representation or accessor merely because it looks similar;",
        "- treat these items as exact constraints, not as pseudocode suggestions.",
        "",
        "## Exact local declarations",
        "",
    ]

    lines.extend(
        f"- `{value}`"
        for value in locals_
    )

    lines.extend([
        "",
        "## Exact top-level call expressions",
        "",
    ])

    for call in calls:
        if not call[
            "nested_call"
        ]:
            lines.append(
                f"- `{call['expression']}`"
            )

    return (
        "\n".join(lines)
        .rstrip()
        + "\n"
    )


def render_dependency_contract(
    matches: dict[
        str,
        dict[
            str,
            list[str],
        ],
    ],
) -> str:
    lines = [
        "# Machine-extracted Dependency API Contract",
        "",
        "This appendix is deterministic evidence derived from the selected repository context and target-source usages.",
        "It is not an LLM summary.",
        "",
        "During regeneration:",
        "- preserve the exact dependency declarations and call patterns listed below;",
        "- do not invent replacement APIs, member functions, overloads, or adapters;",
        "- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;",
        "- do not consume a void return value as a value.",
        "",
    ]

    for name in sorted(matches):
        entry = matches[name]

        lines.extend([
            f"## `{name}`",
            "",
            "### Exact declarations",
            "",
        ])

        lines.extend(
            f"- `{value}`"
            for value
            in entry[
                "declarations"
            ]
        )

        lines.extend([
            "",
            "### Exact target-source usages",
            "",
        ])

        lines.extend(
            f"- `{value}`"
            for value
            in entry["usages"]
        )

        lines.append("")

    return (
        "\n".join(lines)
        .rstrip()
        + "\n"
    )


def validate_relative_path(
    value: str,
    field_name: str,
) -> str:
    normalized = value.replace(
        "\\",
        "/",
    )

    path = PurePosixPath(
        normalized
    )

    if (
        path.is_absolute()
        or ".." in path.parts
        or normalized.startswith(
            "./"
        )
    ):
        raise ValueError(
            "Unsafe path in "
            f"{field_name}: "
            f"{value!r}"
        )

    return path.as_posix()


def selected_paths_from_manifest(
    manifest_path: Path,
    expected_commit: str,
) -> tuple[
    list[str],
    dict[str, Any],
]:
    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8-sig"
        )
    )

    manifest_commit = (
        manifest.get(
            "repository_commit"
        )
    )

    if (
        manifest_commit
        and manifest_commit
        != expected_commit
    ):
        raise RuntimeError(
            "Retrieval manifest commit mismatch: "
            f"{manifest_commit} != "
            f"{expected_commit}"
        )

    raw_paths = (
        manifest.get(
            "selected_paths"
        )
        or []
    )

    if not isinstance(
        raw_paths,
        list,
    ):
        raise ValueError(
            "retrieval_manifest.selected_paths "
            "must be a list"
        )

    paths = [
        validate_relative_path(
            str(item),
            "selected_paths",
        )
        for item in raw_paths
    ]

    return (
        list(
            dict.fromkeys(
                paths
            )
        ),
        manifest,
    )


def extract_contracts(
    *,
    project_root: Path,
    config_path: Path,
    mode: str,
    retrieval_manifest_path: Path | None = None,
) -> dict[str, Any]:
    if mode not in {
        "nonrag",
        "rag",
    }:
        raise ValueError(
            "mode must be "
            "'nonrag' or 'rag'"
        )

    versions = runtime_versions()
    parser = make_parser()

    roundtrip_v2 = (
        load_roundtrip_v2(
            project_root
        )
    )

    config = json.loads(
        config_path.read_text(
            encoding="utf-8-sig"
        )
    )

    repository = (
        project_root
        / str(
            config[
                "repository_path"
            ]
        )
    )

    if not repository.is_dir():
        raise FileNotFoundError(
            repository
        )

    tracked_status = git_output(
        repository,
        "status",
        "--short",
        "--untracked-files=no",
    )

    if tracked_status:
        raise RuntimeError(
            "Repository has tracked changes "
            "before contract extraction:\n"
            f"{tracked_status}"
        )

    head = git_output(
        repository,
        "rev-parse",
        "HEAD",
    )

    expected_commit = str(
        config[
            "repository_commit"
        ]
    )

    if head != expected_commit:
        raise RuntimeError(
            "Repository commit mismatch: "
            f"{head} != "
            f"{expected_commit}"
        )

    fragments = target_fragments(
        config,
        project_root,
        repository,
        roundtrip_v2,
    )

    target_sources = [
        relative
        for relative, _
        in fragments
    ]

    target_hashes = {
        relative: sha256_text(text)
        for relative, text
        in fragments
    }

    all_locals: list[str] = []
    all_calls: list[
        dict[str, Any]
    ] = []
    own_names: set[str] = set()

    target_errors: list[
        dict[str, Any]
    ] = []

    for source_name, text in fragments:
        extracted = (
            extract_target_facts(
                parser,
                text,
            )
        )

        all_locals.extend(
            extracted[
                "locals"
            ]
        )

        all_calls.extend(
            extracted[
                "calls"
            ]
        )

        own_names.update(
            extracted[
                "own_names"
            ]
        )

        for error in extracted[
            "errors"
        ]:
            target_errors.append({
                **error,
                "source": source_name,
            })

    if target_errors:
        raise RuntimeError(
            "Tree-sitter target "
            "parse errors: "
            f"{target_errors}"
        )

    all_locals = list(
        dict.fromkeys(
            all_locals
        )
    )

    deduped_calls: list[
        dict[str, Any]
    ] = []

    seen_calls: set[
        tuple[Any, ...]
    ] = set()

    for call in all_calls:
        key = (
            call["name"],
            call["callee"],
            call["argc"],
            call["expression"],
        )

        if key in seen_calls:
            continue

        seen_calls.add(key)
        deduped_calls.append(
            call
        )

    all_calls = deduped_calls

    source_contract = (
        render_source_contract(
            all_locals,
            all_calls,
        )
    )

    selected_paths: list[str] = []
    retrieval_manifest: dict[str, Any] | None = None
    dependency_contract = ""
    dependency_hashes: dict[str, str] = {}
    dependency_symbols: list[str] = []
    overload_sets: dict[str, int] = {}
    unmatched_symbols: list[str] = []

    if mode == "rag":
        if (
            retrieval_manifest_path
            is None
        ):
            raise ValueError(
                "rag mode requires "
                "--retrieval-manifest"
            )

        (
            selected_paths,
            retrieval_manifest,
        ) = (
            selected_paths_from_manifest(
                retrieval_manifest_path,
                expected_commit,
            )
        )

        target_source_set = set(
            roundtrip_v2
            .source_files_for(
                config
            )
        )

        overlap = sorted(
            target_source_set
            .intersection(
                selected_paths
            )
        )

        if overlap:
            raise RuntimeError(
                "Target source leaked "
                "into dependency paths: "
                f"{overlap}"
            )

        declarations: list[
            dict[str, Any]
        ] = []

        dependency_errors: list[
            dict[str, Any]
        ] = []

        for relative in selected_paths:
            path = (
                repository
                / relative
            )

            if not path.is_file():
                raise FileNotFoundError(
                    path
                )

            try:
                git_output(
                    repository,
                    "ls-files",
                    "--error-unmatch",
                    relative,
                )

            except subprocess.CalledProcessError as exc:
                raise RuntimeError(
                    "Dependency path "
                    "is not tracked: "
                    f"{relative}"
                ) from exc

            dependency_hashes[
                relative
            ] = sha256_file(
                path
            )

            rows, errors = (
                extract_dependency_declarations(
                    parser,
                    path.read_text(
                        encoding="utf-8",
                        errors="replace",
                    ),
                )
            )

            declarations.extend(
                rows
            )

            for error in errors:
                dependency_errors.append({
                    **error,
                    "source": relative,
                })

        if dependency_errors:
            raise RuntimeError(
                "Tree-sitter dependency "
                "parse errors: "
                f"{dependency_errors}"
            )

        matches: dict[
            str,
            dict[
                str,
                list[str],
            ],
        ] = {}

        unmatched: list[
            dict[str, Any]
        ] = []

        for call in (
            dependency_candidate_calls(
                all_calls,
                own_names,
            )
        ):
            candidates = [
                declaration
                for declaration
                in declarations
                if (
                    declaration[
                        "name"
                    ]
                    == call["name"]
                    and compatible(
                        call,
                        declaration,
                    )
                )
            ]

            if not candidates:
                unmatched.append(
                    call
                )
                continue

            entry = (
                matches.setdefault(
                    call["name"],
                    {
                        "declarations": [],
                        "usages": [],
                    },
                )
            )

            for candidate in candidates:
                if (
                    candidate["text"]
                    not in entry[
                        "declarations"
                    ]
                ):
                    entry[
                        "declarations"
                    ].append(
                        candidate[
                            "text"
                        ]
                    )

            if (
                call["expression"]
                not in entry[
                    "usages"
                ]
            ):
                entry[
                    "usages"
                ].append(
                    call[
                        "expression"
                    ]
                )

        dependency_contract = (
            render_dependency_contract(
                matches
            )
        )

        dependency_symbols = sorted(
            matches
        )

        overload_sets = {
            name: len(
                entry[
                    "declarations"
                ]
            )
            for name, entry
            in matches.items()
            if len(
                entry[
                    "declarations"
                ]
            ) > 1
        }

        unmatched_symbols = sorted({
            call["name"]
            for call in unmatched
        })

    elif (
        retrieval_manifest_path
        is not None
    ):
        raise ValueError(
            "nonrag mode must not receive "
            "--retrieval-manifest"
        )

    combined_contract = source_contract

    if dependency_contract:
        combined_contract = (
            source_contract.rstrip()
            + "\n\n"
            + dependency_contract
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "mode": mode,
        "target_id": config.get(
            "target_id"
        ),
        "pair_id": config.get(
            "pair_id"
        ),
        "repository_id": config.get(
            "repository_id"
        ),
        "repository_commit": expected_commit,
        "tree_sitter": versions,
        "target_sources": target_sources,
        "target_fragment_sha256": target_hashes,
        "selected_dependency_paths": selected_paths,
        "dependency_file_sha256": dependency_hashes,
        "source_local_declaration_count": len(
            all_locals
        ),
        "all_call_count": len(
            all_calls
        ),
        "top_level_call_count": sum(
            not call[
                "nested_call"
            ]
            for call
            in all_calls
        ),
        "dependency_symbol_match_count": len(
            dependency_symbols
        ),
        "dependency_symbols": dependency_symbols,
        "overload_sets": overload_sets,
        "unmatched_candidate_symbols": unmatched_symbols,
        "source_contract_sha256": sha256_text(
            source_contract
        ),
        "dependency_contract_sha256": (
            sha256_text(
                dependency_contract
            )
            if dependency_contract
            else None
        ),
        "combined_contract_sha256": sha256_text(
            combined_contract
        ),
        "source_contract_chars": len(
            source_contract
        ),
        "dependency_contract_chars": len(
            dependency_contract
        ),
        "combined_contract_chars": len(
            combined_contract
        ),
        "retrieval_manifest_sha256": (
            sha256_file(
                retrieval_manifest_path
            )
            if (
                retrieval_manifest_path
                is not None
            )
            else None
        ),
        "retrieval_context_sha256": (
            retrieval_manifest.get(
                "combined_context_sha256"
            )
            if (
                retrieval_manifest
                is not None
            )
            else None
        ),
        "llm_called": False,
        "deterministic": True,
    }

    return {
        "source_contract": source_contract,
        "dependency_contract": dependency_contract,
        "combined_contract": combined_contract,
        "manifest": manifest,
    }


def write_outputs(
    result: dict[str, Any],
    output_dir: Path,
) -> None:
    if output_dir.exists():
        raise RuntimeError(
            "Output directory "
            "already exists: "
            f"{output_dir}"
        )

    output_dir.mkdir(
        parents=True
    )

    (
        output_dir
        / "source_local_contract.md"
    ).write_text(
        result[
            "source_contract"
        ],
        encoding="utf-8",
    )

    if result[
        "dependency_contract"
    ]:
        (
            output_dir
            / "dependency_api_contract.md"
        ).write_text(
            result[
                "dependency_contract"
            ],
            encoding="utf-8",
        )

    (
        output_dir
        / "combined_contract.md"
    ).write_text(
        result[
            "combined_contract"
        ],
        encoding="utf-8",
    )

    (
        output_dir
        / "contract_manifest.json"
    ).write_text(
        json.dumps(
            result["manifest"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract deterministic v6 "
            "source-local and RAG "
            "dependency contracts."
        )
    )

    parser.add_argument(
        "--config",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=(
            "nonrag",
            "rag",
        ),
    )

    parser.add_argument(
        "--retrieval-manifest",
        type=Path,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=(
            Path(__file__)
            .resolve()
            .parents[2]
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = extract_contracts(
        project_root=(
            args.project_root
            .resolve()
        ),
        config_path=(
            args.config.resolve()
        ),
        mode=args.mode,
        retrieval_manifest_path=(
            args.retrieval_manifest
            .resolve()
            if args.retrieval_manifest
            else None
        ),
    )

    write_outputs(
        result,
        args.output_dir.resolve(),
    )

    print(
        json.dumps(
            result["manifest"],
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
