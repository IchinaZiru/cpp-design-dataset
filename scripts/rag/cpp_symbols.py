"""Tree-sitter based, symbol-oriented C/C++ chunk extraction."""

from __future__ import annotations

import importlib.metadata
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .canonical import sha256_bytes
from .config import ChunkingSpec, ParserSpec
from .corpus import SourceFile


class ParserUnavailableError(RuntimeError):
    """Raised when the fixed Tree-sitter environment is unavailable or mismatched."""


class SourceEncodingError(RuntimeError):
    """Raised when a tracked C/C++ source cannot be represented as UTF-8 JSON."""


@dataclass(frozen=True)
class ParseDiagnostic:
    path: str
    node_type: str
    start_byte: int
    end_byte: int
    start_line: int
    end_line: int
    reason: str
    handled: bool
    fallback_method: str | None


@dataclass(frozen=True)
class ParsedSource:
    chunks: tuple[dict[str, Any], ...]
    diagnostics: tuple[ParseDiagnostic, ...]
    parse_only_macro_mask_count: int


_CLASS_TYPES = {"class_specifier", "struct_specifier", "union_specifier"}
_NAME_TYPES = {
    "identifier",
    "field_identifier",
    "type_identifier",
    "namespace_identifier",
    "operator_name",
    "destructor_name",
    "qualified_identifier",
    "scoped_identifier",
    "template_function",
    "template_method",
}
_DOXYGEN_PATTERN = re.compile(
    rb"(?s)(/\*\*.*?\*/|(?:^[ \t]*(?:///|//!)[^\r\n]*(?:\r?\n|$))+)[ \t\r\n]*$",
    re.MULTILINE,
)
_MACRO_START_PATTERN = re.compile(
    rb"(?m)^[ \t]*#[ \t]*define[ \t]+([A-Za-z_][A-Za-z0-9_]*)"
)
_CONDITIONAL_DIRECTIVE_PATTERN = re.compile(
    rb"^[ \t]*#[ \t]*(?:if|ifdef|ifndef|elif|else|endif)\b"
)
_PREPROCESSOR_NODE_PREFIX = "preproc_"
_PREPROCESSOR_CONDITIONAL_TYPES = {
    "preproc_if",
    "preproc_ifdef",
    "preproc_else",
    "preproc_elif",
}
_EMPTY_BRACED_DEFAULT_ARGUMENT_FALLBACK = "empty-braced-default-argument-v1"
_PARAMETER_ANCESTOR_TYPES = {"optional_parameter_declaration", "parameter_list"}


def mask_parse_only_macros(
    data: bytes,
    identifiers: Iterable[str],
) -> tuple[bytes, int]:
    """Mask configured annotation macros without changing source byte offsets."""

    encoded = sorted({item.encode("ascii") for item in identifiers})
    if not encoded:
        return data, 0
    pattern = re.compile(rb"\b(?:" + b"|".join(re.escape(item) for item in encoded) + rb")\b")
    return pattern.subn(lambda match: b" " * len(match.group(0)), data)


def _installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        raise ParserUnavailableError(
            f"required package is not installed: {distribution}"
        ) from exc


def create_cpp_parser(parser_spec: ParserSpec):
    """Create the exact parser declared by retrieval_v1.json."""

    actual_parser = _installed_version(parser_spec.package)
    actual_grammar = _installed_version(parser_spec.grammar_package)
    if actual_parser != parser_spec.package_version:
        raise ParserUnavailableError(
            f"{parser_spec.package} version mismatch: "
            f"expected {parser_spec.package_version}, got {actual_parser}"
        )
    if actual_grammar != parser_spec.grammar_version:
        raise ParserUnavailableError(
            f"{parser_spec.grammar_package} version mismatch: "
            f"expected {parser_spec.grammar_version}, got {actual_grammar}"
        )

    try:
        from tree_sitter import Language, Parser
        import tree_sitter_cpp
    except ImportError as exc:
        raise ParserUnavailableError(f"cannot import Tree-sitter C++ parser: {exc}") from exc

    language = Language(tree_sitter_cpp.language())
    return Parser(language)


def _source_text(data: bytes, start: int, end: int) -> str:
    try:
        return data[start:end].decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SourceEncodingError(
            f"source slice is not valid UTF-8 at bytes [{start}, {end})"
        ) from exc


def _node_text(node: Any, data: bytes) -> str:
    return _source_text(data, node.start_byte, node.end_byte)


def _normalized_code(text: str) -> str:
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def _line_for_offset(data: bytes, offset: int) -> int:
    if offset <= 0:
        return 1
    return data.count(b"\n", 0, min(offset, len(data))) + 1


def _inclusive_end_line(data: bytes, start: int, end: int) -> int:
    if end <= start:
        return _line_for_offset(data, start)
    return _line_for_offset(data, end - 1)


def _column_for_offset(data: bytes, offset: int) -> int:
    previous_newline = data.rfind(b"\n", 0, offset)
    return offset if previous_newline < 0 else offset - previous_newline - 1


def _find_name_node(node: Any) -> Any | None:
    if node is None:
        return None
    if node.type in _NAME_TYPES:
        return node

    for field in ("declarator", "name", "field"):
        child = node.child_by_field_name(field)
        if child is not None:
            found = _find_name_node(child)
            if found is not None:
                return found

    preferred = (
        "function_declarator",
        "pointer_declarator",
        "reference_declarator",
        "array_declarator",
        "parenthesized_declarator",
        "init_declarator",
    )
    for child_type in preferred:
        for child in node.named_children:
            if child.type == child_type:
                found = _find_name_node(child)
                if found is not None:
                    return found

    for child in node.named_children:
        found = _find_name_node(child)
        if found is not None:
            return found
    return None


def _find_descendant(node: Any, node_types: set[str]) -> Any | None:
    if node.type in node_types:
        return node
    for child in node.named_children:
        found = _find_descendant(child, node_types)
        if found is not None:
            return found
    return None


def _contains_descendant(node: Any, node_type: str) -> bool:
    return _find_descendant(node, {node_type}) is not None


def _qualified_name(name: str, namespace: tuple[str, ...], parent_symbol: str | None) -> str:
    compact = name.strip()
    if not compact:
        return "<anonymous>"
    namespace_prefix = "::".join(namespace)
    if "::" in compact:
        if namespace_prefix and not compact.startswith(namespace_prefix + "::"):
            return namespace_prefix + "::" + compact
        return compact
    if parent_symbol:
        return parent_symbol + "::" + compact
    if namespace_prefix:
        return namespace_prefix + "::" + compact
    return compact


def _short_name(canonical_name: str) -> str:
    return canonical_name.rsplit("::", 1)[-1]


def _parent_name(canonical_name: str) -> str | None:
    if "::" not in canonical_name:
        return None
    return canonical_name.rsplit("::", 1)[0]


def _strip_template_arguments(name: str) -> str:
    result: list[str] = []
    depth = 0
    for character in name:
        if character == "<":
            depth += 1
            continue
        if character == ">" and depth > 0:
            depth -= 1
            continue
        if depth == 0:
            result.append(character)
    return "".join(result)


def _resolved_function_parent(
    source_name: str,
    canonical_name: str,
    parent_symbol: str | None,
) -> str | None:
    if parent_symbol is not None:
        return parent_symbol
    if "::" in source_name:
        return _parent_name(canonical_name)
    return None


def _preceding_doxygen_start(data: bytes, symbol_start: int) -> int | None:
    prefix = data[:symbol_start]
    match = _DOXYGEN_PATTERN.search(prefix)
    if match is None:
        return None
    comment = match.group(1)
    if b"@file" in comment or b"\\file" in comment:
        return None
    return match.start(1)


def _line_ranges(data: bytes) -> list[tuple[int, int, bytes]]:
    ranges: list[tuple[int, int, bytes]] = []
    start = 0
    for line in data.splitlines(keepends=True):
        end = start + len(line)
        ranges.append((start, end, line.rstrip(b"\r\n")))
        start = end
    if start < len(data) or not ranges:
        ranges.append((start, len(data), data[start:]))
    return ranges


def _line_index_for_offset(
    ranges: list[tuple[int, int, bytes]], offset: int
) -> int:
    bounded = max(0, offset)
    for index, (start, end, _) in enumerate(ranges):
        if start <= bounded < end:
            return index
    return max(0, len(ranges) - 1)


def _near_conditional_directive(data: bytes, start: int, end: int) -> bool:
    ranges = _line_ranges(data)
    first = _line_index_for_offset(ranges, start)
    last = _line_index_for_offset(ranges, max(start, end - 1))
    for index in range(max(0, first - 1), min(len(ranges), last + 2)):
        if _CONDITIONAL_DIRECTIVE_PATTERN.match(ranges[index][2]):
            return True
    return False


def _has_ancestor_type(node: Any, node_types: set[str]) -> bool:
    current = getattr(node, "parent", None)
    while current is not None:
        if str(current.type) in node_types:
            return True
        current = getattr(current, "parent", None)
    return False


def _is_empty_braced_default_argument_missing(node: Any, data: bytes) -> bool:
    """Recognize tree-sitter-cpp 0.23.4's recovery for `arg = {}`.

    In an optional parameter declaration the fixed grammar requires the default
    value to be an expression. An empty braced initializer is valid C++, but the
    parser recovers by inserting a zero-width missing `type_identifier` between
    `=` and `{}`. Keep the rule deliberately narrow so unrelated missing nodes
    remain fatal.
    """

    if (
        node.type != "type_identifier"
        or not bool(getattr(node, "is_missing", False))
        or node.start_byte != node.end_byte
        or not _has_ancestor_type(node, _PARAMETER_ANCESTOR_TYPES)
    ):
        return False

    offset = node.start_byte
    line_start = data.rfind(b"\n", 0, offset) + 1
    line_end = data.find(b"\n", offset)
    if line_end < 0:
        line_end = len(data)
    before = data[line_start:offset]
    after = data[offset:line_end].rstrip(b"\r")
    before_stripped = before.rstrip(b" \t")
    if not before_stripped.endswith(b"="):
        return False
    if len(before_stripped) >= 2 and before_stripped[-2] in b"=<>!+-*/%&|^":
        return False
    return (
        re.match(rb"^[ \t]*\{[ \t]*\}[ \t]*(?:[,)]|$)", after)
        is not None
    )


def _count_parse_errors(
    root: Any,
    path: str,
    data: bytes,
    *,
    preprocessor_fallback_method: str,
) -> list[ParseDiagnostic]:
    diagnostics: list[ParseDiagnostic] = []
    stack: list[tuple[Any, bool]] = [(root, False)]
    while stack:
        node, inside_preprocessor = stack.pop()
        node_is_preprocessor = str(node.type).startswith(_PREPROCESSOR_NODE_PREFIX)
        current_inside_preprocessor = inside_preprocessor or node_is_preprocessor
        is_error = node.type == "ERROR"
        is_missing = bool(getattr(node, "is_missing", False))
        if is_error or is_missing:
            diagnostic_fallback: str | None = None
            if current_inside_preprocessor or _near_conditional_directive(
                data, node.start_byte, node.end_byte
            ):
                diagnostic_fallback = preprocessor_fallback_method
            elif _is_empty_braced_default_argument_missing(node, data):
                diagnostic_fallback = _EMPTY_BRACED_DEFAULT_ARGUMENT_FALLBACK
            diagnostics.append(
                ParseDiagnostic(
                    path=path,
                    node_type=node.type,
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                    start_line=_line_for_offset(data, node.start_byte),
                    end_line=_inclusive_end_line(data, node.start_byte, node.end_byte),
                    reason="missing_node" if is_missing else "tree_sitter_error_node",
                    handled=diagnostic_fallback is not None,
                    fallback_method=diagnostic_fallback,
                )
            )
        stack.extend(
            (child, current_inside_preprocessor)
            for child in reversed(node.named_children)
        )
    return diagnostics


def _signature_for_node(node: Any, data: bytes) -> str:
    body = node.child_by_field_name("body")
    if body is not None and body.start_byte > node.start_byte:
        return _normalized_code(_source_text(data, node.start_byte, body.start_byte))
    text = _node_text(node, data)
    first_brace = text.find("{")
    if first_brace >= 0 and node.type in _CLASS_TYPES:
        text = text[:first_brace]
    return _normalized_code(text.rstrip(";"))


def _parameter_count(signature: str) -> int | None:
    start = signature.find("(")
    if start < 0:
        return None
    depth = 0
    angle = 0
    commas = 0
    non_space = False
    for character in signature[start + 1 :]:
        if character == "(" and angle == 0:
            depth += 1
        elif character == ")" and angle == 0:
            if depth == 0:
                return 0 if not non_space else commas + 1
            depth -= 1
        elif character == "<":
            angle += 1
        elif character == ">" and angle > 0:
            angle -= 1
        elif character == "," and depth == 0 and angle == 0:
            commas += 1
        elif not character.isspace():
            non_space = True
    return None


def _template_arity(signature: str) -> int:
    template_match = re.search(r"\btemplate\s*<(.+?)>", signature)
    if not template_match:
        return 0
    return len(re.findall(r"\b(?:typename|class)\b", template_match.group(1)))


def _function_kind(
    canonical_name: str,
    parent_symbol: str | None,
    is_definition: bool,
) -> str:
    short = _short_name(canonical_name)
    suffix = "definition" if is_definition else "declaration"
    parent_short = _short_name(parent_symbol) if parent_symbol else None
    constructor_name = (
        _strip_template_arguments(parent_short) if parent_short else None
    )
    if short.startswith("operator"):
        return f"operator_{suffix}"
    if short.startswith("~"):
        return f"destructor_{suffix}"
    if constructor_name and short == constructor_name:
        return f"constructor_{suffix}"
    if parent_symbol:
        return f"method_{suffix}"
    return f"function_{suffix}"


def _stable_chunk_id(
    repository_commit: str,
    path: str,
    start_byte: int,
    end_byte: int,
    kind: str,
    content_sha256: str,
) -> str:
    material = (
        repository_commit
        + "\n"
        + path
        + "\n"
        + f"{start_byte}:{end_byte}"
        + "\n"
        + kind
        + "\n"
        + content_sha256
    ).encode("utf-8")
    return sha256_bytes(material)


def _make_chunk(
    *,
    repository_id: str,
    repository_commit: str,
    source: SourceFile,
    symbol_node: Any | None,
    start_byte: int,
    end_byte: int,
    canonical_name: str,
    kind: str,
    namespace: tuple[str, ...],
    parent_symbol: str | None,
    signature: str,
    chunk_method: str,
    soft_limit_lines: int,
    doxygen_attached: bool,
) -> dict[str, Any]:
    content_bytes = source.data[start_byte:end_byte]
    if not content_bytes:
        raise ValueError(f"empty chunk for {source.path}:{start_byte}-{end_byte}")
    content = _source_text(source.data, start_byte, end_byte)
    content_sha256 = sha256_bytes(content_bytes)
    start_line = _line_for_offset(source.data, start_byte)
    end_line = _inclusive_end_line(source.data, start_byte, end_byte)
    line_count = end_line - start_line + 1
    chunk_id = _stable_chunk_id(
        repository_commit,
        source.path,
        start_byte,
        end_byte,
        kind,
        content_sha256,
    )
    return {
        "canonical_name": canonical_name,
        "chunk_id": chunk_id,
        "chunk_method": chunk_method,
        "content": content,
        "content_sha256": content_sha256,
        "doxygen_attached": doxygen_attached,
        "end_byte": end_byte,
        "end_column": _column_for_offset(source.data, end_byte),
        "end_line": end_line,
        "interface_scope": (
            "full_definition_contiguous" if kind in {"class_interface", "struct_interface"} else None
        ),
        "kind": kind,
        "line_count": line_count,
        "namespace": "::".join(namespace) if namespace else None,
        "oversized_unsplit": line_count > soft_limit_lines,
        "parent_symbol": parent_symbol,
        "path": source.path,
        "repository": repository_id,
        "repository_commit": repository_commit,
        "short_symbol": _short_name(canonical_name),
        "signature": signature,
        "source_sha256": source.sha256,
        "start_byte": start_byte,
        "start_column": _column_for_offset(source.data, start_byte),
        "start_line": start_line,
        "symbol": canonical_name,
        "symbol_end_byte": symbol_node.end_byte if symbol_node is not None else end_byte,
        "symbol_start_byte": symbol_node.start_byte if symbol_node is not None else start_byte,
    }


def _class_base_symbols(node: Any, data: bytes) -> list[str]:
    clause = _find_descendant(node, {"base_class_clause"})
    if clause is None:
        return []
    names: list[str] = []
    stack = list(reversed(clause.named_children))
    while stack:
        current = stack.pop()
        if current.type in {"type_identifier", "qualified_identifier", "scoped_type_identifier"}:
            text = _node_text(current, data).strip()
            if text:
                names.append(text)
            continue
        stack.extend(reversed(current.named_children))
    return sorted(set(names))


class _Extractor:
    def __init__(
        self,
        repository_id: str,
        repository_commit: str,
        source: SourceFile,
        chunking: ChunkingSpec,
    ) -> None:
        self.repository_id = repository_id
        self.repository_commit = repository_commit
        self.source = source
        self.chunking = chunking
        self.chunks: list[dict[str, Any]] = []
        self._emitted_ranges: set[tuple[int, int, str]] = set()

    def emit(
        self,
        node: Any,
        canonical_name: str,
        kind: str,
        namespace: tuple[str, ...],
        parent_symbol: str | None,
        *,
        range_node: Any | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> None:
        range_source = range_node or node
        start_byte = range_source.start_byte
        end_byte = range_source.end_byte
        doxygen_attached = False
        if self.chunking.attach_preceding_doxygen:
            comment_start = _preceding_doxygen_start(self.source.data, start_byte)
            if comment_start is not None:
                start_byte = comment_start
                doxygen_attached = True
        key = (start_byte, end_byte, kind)
        if key in self._emitted_ranges:
            return
        self._emitted_ranges.add(key)
        chunk = _make_chunk(
                repository_id=self.repository_id,
                repository_commit=self.repository_commit,
                source=self.source,
                symbol_node=node,
                start_byte=start_byte,
                end_byte=end_byte,
                canonical_name=canonical_name,
                kind=kind,
                namespace=namespace,
                parent_symbol=parent_symbol,
                signature=_signature_for_node(range_source, self.source.data),
                chunk_method=self.chunking.version,
                soft_limit_lines=self.chunking.large_chunk_soft_limit_lines,
                doxygen_attached=doxygen_attached,
            )
        if extra_metadata:
            chunk.update(extra_metadata)
        self.chunks.append(chunk)

    def visit(
        self,
        node: Any,
        namespace: tuple[str, ...] = (),
        parent_symbol: str | None = None,
        template_wrapper: Any | None = None,
    ) -> None:
        node_type = node.type

        if node_type == "namespace_definition":
            name_node = node.child_by_field_name("name")
            name = _node_text(name_node, self.source.data).strip() if name_node else ""
            next_namespace = namespace + ((name,) if name else ())
            for child in node.named_children:
                if child is name_node:
                    continue
                self.visit(child, next_namespace, parent_symbol)
            return

        if node_type == "template_declaration":
            primary_types = _CLASS_TYPES | {
                "function_definition",
                "declaration",
                "alias_declaration",
                "type_definition",
                "concept_definition",
            }
            primary = next(
                (child for child in node.named_children if child.type in primary_types),
                None,
            )
            if primary is not None:
                self.visit(primary, namespace, parent_symbol, template_wrapper=node)
            return

        if node_type in _CLASS_TYPES:
            name_node = node.child_by_field_name("name") or _find_descendant(node, {"type_identifier"})
            name = _node_text(name_node, self.source.data).strip() if name_node else "<anonymous>"
            canonical = _qualified_name(name, namespace, parent_symbol)
            has_body = node.child_by_field_name("body") is not None
            base_kind = {
                "class_specifier": "class",
                "struct_specifier": "struct",
                "union_specifier": "union",
            }[node_type]
            kind = f"{base_kind}_interface" if has_body else f"{base_kind}_declaration"
            self.emit(
                node,
                canonical,
                kind,
                namespace,
                parent_symbol,
                range_node=template_wrapper,
                extra_metadata={
                    "base_symbols": _class_base_symbols(node, self.source.data),
                    "is_nested_type": parent_symbol is not None,
                    "is_template": template_wrapper is not None,
                },
            )
            body = node.child_by_field_name("body")
            if body is not None:
                for child in body.named_children:
                    self.visit(child, namespace, canonical)
            return

        if node_type == "function_definition":
            declarator = node.child_by_field_name("declarator")
            name_node = _find_name_node(declarator or node)
            if name_node is None:
                return
            name = _node_text(name_node, self.source.data).strip()
            canonical = _qualified_name(name, namespace, parent_symbol)
            resolved_parent = _resolved_function_parent(
                name, canonical, parent_symbol
            )
            kind = _function_kind(canonical, resolved_parent, True)
            self.emit(
                node,
                canonical,
                kind,
                namespace,
                resolved_parent,
                range_node=template_wrapper,
            )
            return

        if node_type in {"declaration", "field_declaration"}:
            function_declarator = _find_descendant(node, {"function_declarator"})
            if function_declarator is not None:
                name_node = _find_name_node(function_declarator)
                if name_node is not None:
                    name = _node_text(name_node, self.source.data).strip()
                    canonical = _qualified_name(name, namespace, parent_symbol)
                    resolved_parent = _resolved_function_parent(
                        name, canonical, parent_symbol
                    )
                    kind = _function_kind(canonical, resolved_parent, False)
                    self.emit(
                        node,
                        canonical,
                        kind,
                        namespace,
                        resolved_parent,
                        range_node=template_wrapper,
                    )
                return

            text = _node_text(node, self.source.data)
            if re.search(r"\b(?:const|constexpr|constinit)\b", text):
                declarator = node.child_by_field_name("declarator") or _find_descendant(
                    node, {"init_declarator"}
                )
                name_node = _find_name_node(declarator or node)
                if name_node is not None:
                    name = _node_text(name_node, self.source.data).strip()
                    canonical = _qualified_name(name, namespace, parent_symbol)
                    self.emit(
                        node,
                        canonical,
                        "constant_definition",
                        namespace,
                        parent_symbol,
                        range_node=template_wrapper,
                    )
                    return

            for child in node.named_children:
                if child.type in _CLASS_TYPES | {"enum_specifier"}:
                    self.visit(child, namespace, parent_symbol, template_wrapper=template_wrapper)
            return

        if node_type == "enum_specifier":
            name_node = node.child_by_field_name("name") or _find_descendant(node, {"type_identifier"})
            name = _node_text(name_node, self.source.data).strip() if name_node else "<anonymous-enum>"
            canonical = _qualified_name(name, namespace, parent_symbol)
            self.emit(
                node,
                canonical,
                "enum_definition",
                namespace,
                parent_symbol,
                range_node=template_wrapper,
            )
            return

        if node_type == "alias_declaration":
            name_node = node.child_by_field_name("name") or _find_descendant(node, {"type_identifier"})
            if name_node is not None:
                name = _node_text(name_node, self.source.data).strip()
                canonical = _qualified_name(name, namespace, parent_symbol)
                self.emit(
                    node,
                    canonical,
                    "alias_definition",
                    namespace,
                    parent_symbol,
                    range_node=template_wrapper,
                )
            return

        if node_type == "type_definition":
            declarator = node.child_by_field_name("declarator")
            name_node = _find_name_node(declarator or node)
            if name_node is not None:
                name = _node_text(name_node, self.source.data).strip()
                canonical = _qualified_name(name, namespace, parent_symbol)
                self.emit(
                    node,
                    canonical,
                    "typedef_definition",
                    namespace,
                    parent_symbol,
                    range_node=template_wrapper,
                )
            return

        if node_type == "concept_definition":
            name_node = node.child_by_field_name("name") or _find_descendant(node, {"identifier"})
            if name_node is not None:
                name = _node_text(name_node, self.source.data).strip()
                canonical = _qualified_name(name, namespace, parent_symbol)
                self.emit(
                    node,
                    canonical,
                    "concept_definition",
                    namespace,
                    parent_symbol,
                    range_node=template_wrapper,
                )
            return

        # Conditional nodes contain ordinary C++ declarations and definitions;
        # recurse through them so header guards do not erase the production API.
        # Other preprocessor forms are handled by the deterministic line fallback.
        if node_type in _PREPROCESSOR_CONDITIONAL_TYPES:
            for child in node.named_children:
                self.visit(child, namespace, parent_symbol)
            return
        if node_type.startswith(_PREPROCESSOR_NODE_PREFIX):
            return

        for child in node.named_children:
            self.visit(child, namespace, parent_symbol)

    def add_macro_fallbacks(self) -> None:
        data = self.source.data
        for match in _MACRO_START_PATTERN.finditer(data):
            start_byte = match.start(0)
            line_start = start_byte
            end_byte = start_byte
            while True:
                newline = data.find(b"\n", line_start)
                if newline < 0:
                    end_byte = len(data)
                    break
                line_without_newline = data[line_start:newline].rstrip(b"\r")
                end_byte = newline
                if not line_without_newline.rstrip().endswith(b"\\"):
                    break
                line_start = newline + 1
            name = match.group(1).decode("ascii")
            key = (start_byte, end_byte, "macro_definition")
            if key in self._emitted_ranges:
                continue
            self._emitted_ranges.add(key)
            text = _source_text(data, start_byte, end_byte)
            self.chunks.append(
                _make_chunk(
                    repository_id=self.repository_id,
                    repository_commit=self.repository_commit,
                    source=self.source,
                    symbol_node=None,
                    start_byte=start_byte,
                    end_byte=end_byte,
                    canonical_name=name,
                    kind="macro_definition",
                    namespace=(),
                    parent_symbol=None,
                    signature=_normalized_code(text),
                    chunk_method=self.chunking.macro_fallback_version,
                    soft_limit_lines=self.chunking.large_chunk_soft_limit_lines,
                    doxygen_attached=False,
                )
            )


def extract_symbol_chunks(
    *,
    parser: Any,
    repository_id: str,
    repository_commit: str,
    source: SourceFile,
    chunking: ChunkingSpec,
    parse_only_macro_identifiers: Iterable[str] = (),
) -> ParsedSource:
    parse_data, mask_count = mask_parse_only_macros(
        source.data,
        parse_only_macro_identifiers,
    )
    tree = parser.parse(parse_data)
    root = tree.root_node
    diagnostics = _count_parse_errors(
        root,
        source.path,
        source.data,
        preprocessor_fallback_method=chunking.preprocessor_error_fallback_version,
    )
    extractor = _Extractor(repository_id, repository_commit, source, chunking)
    extractor.visit(root)
    extractor.add_macro_fallbacks()
    chunks = tuple(
        sorted(
            extractor.chunks,
            key=lambda item: (
                item["path"],
                item["start_byte"],
                item["end_byte"],
                item["kind"],
                item["chunk_id"],
            ),
        )
    )
    return ParsedSource(
        chunks=chunks,
        diagnostics=tuple(diagnostics),
        parse_only_macro_mask_count=mask_count,
    )


def build_exact_symbol_index(
    chunks: Iterable[dict[str, Any]],
    *,
    index_version: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for chunk in chunks:
        canonical_name = str(chunk["canonical_name"])
        short_name = str(chunk["short_symbol"])
        if canonical_name.startswith("<anonymous"):
            continue
        kind = str(chunk["kind"])
        index_role = "declaration" if kind.endswith("_declaration") else "definition"
        signature = str(chunk["signature"])
        lookup_keys = sorted(
            {
                canonical_name,
                short_name,
                (
                    f"{chunk['parent_symbol']}::{short_name}"
                    if chunk.get("parent_symbol")
                    else canonical_name
                ),
            }
        )
        ref_qualifier = None
        if re.search(r"\)\s*&&(?:\s|$)", signature):
            ref_qualifier = "&&"
        elif re.search(r"\)\s*&(?!&)(?:\s|$)", signature):
            ref_qualifier = "&"
        records.append(
            {
                "canonical_name": canonical_name,
                "chunk_id": chunk["chunk_id"],
                "cv_qualifier": "const" if re.search(r"\)\s*const\b", signature) else None,
                "index_role": index_role,
                "index_version": index_version,
                "kind": kind,
                "lookup_keys": lookup_keys,
                "noexcept": bool(re.search(r"\bnoexcept\b", signature)),
                "parameter_count": _parameter_count(signature),
                "parent_symbol": chunk.get("parent_symbol"),
                "path": chunk["path"],
                "ref_qualifier": ref_qualifier,
                "short_name": short_name,
                "signature": signature,
                "start_line": chunk["start_line"],
                "template_arity": _template_arity(signature),
            }
        )
    return sorted(
        records,
        key=lambda item: (
            item["canonical_name"],
            item["index_role"],
            item["path"],
            item["start_line"],
            item["chunk_id"],
        ),
    )
