# Round-trip v2 module_files implementation

## Scope

This change extends `scripts/roundtrip_v2/run_target_v2.py` without changing the frozen non-RAG 17-result artifacts.

Supported replacement modes after this change:

- `class` locator: replace one class/struct span, including contiguous template declarations.
- `function` locator: replace one function definition selected by `signature_regex`.
- `module_files`: replace every file listed in `source_files` as a complete file.

The design-generation observation scope remains full files. RAG knowledge is inserted only in design generation. Code regeneration receives only the generated design document, fixed scaffold, and dependency/include information.

## module_files behavior

1. Read every `observation_files` file into the design-generation input.
2. Back up the observed files under the experiment directory.
3. Build a fixed scaffold from header files in `source_files`.
4. Request code regeneration with an Ollama JSON Schema.
5. Require exactly one non-empty `content` value for every expected path.
6. Reject missing, duplicate, unknown, unsafe, or extra paths/fields.
7. Materialize generated files under `generated/files/<path>`.
8. Temporarily replace all `source_files` for configure/build/direct/full testing.
9. Restore every source file in `finally` and record per-file SHA-256 values.
10. Treat the run as PASS only when all stages pass and every file is restored.

## Static validation

The runner adds:

```text
--validate-config-only
```

This mode validates config fields and referenced files without calling Ollama, Docker, CMake, build, or tests. Disabled configs can be validated with this option.

## Compatibility

Existing v2 pilot configs that omit `granularity` remain supported when their locator kind is `class` or `function`.

Canonical older config values are also accepted:

- `class_span` -> target-span behavior
- `function` / `function_body` -> target-span behavior
- `module_files` -> complete-file behavior

## Included pilot configs

Both configs are disabled, mechanics-only, and outside the frozen 17-target formal set:

- `riscv-simulator-session-module-files-pilot-001.json`
- `riscv-simulator-session-constructor-function-pilot-001.json`

Both use the excluded `Session` target. `Session.Construct` checks only construction and destruction, so a pilot PASS must not be interpreted as broad behavioral correctness. The purpose is limited to pipeline mechanics such as prompt serialization, target/file replacement, test invocation, and source restoration.

The earlier disabled configs that referenced formal targets (`io` and `INIWriter::write`) were removed before any pilot execution. No artifacts were generated from those configs.

## Not included

- No formal 17-target config generation.
- No formal target enabling.
- No LLM, Docker, build, or test execution.
- No retry, automatic repair, or generated-code editing.
- No changes to frozen non-RAG results.

## Module-files mechanics pilot 001

The first formal-outside `Session` module pilot reached configure successfully
but failed during build. The first compiler error was produced by the fixed
scaffold: the shared lexical body stripper converted the inline constructor
`Stat() : cycle(0) {}` into the invalid declaration `Stat() : cycle(0) ;`.
Both source files were restored to their original SHA-256 values, and no retry
or automatic repair was performed.

The v2 runner now uses a local scaffold stripper that keeps constructor
initializer lists and replaces only their inline bodies with
`{ /* implementation omitted */ }`. Ordinary inline member-function bodies
continue to be replaced with `;`. Pilot 001 remains frozen; pilot 002 uses a
new experiment directory and run ID.
