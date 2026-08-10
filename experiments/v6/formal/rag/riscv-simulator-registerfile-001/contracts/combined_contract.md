# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `static std::vector<std::string> rf_name = {"0", "ra", "sp", "gp", "tp", "t0", "t1", "t2", "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"};`
- `int i = 0;`
- `int j = i * 8;`
- `char buffer[20];`

## Exact top-level call expressions

- `memset(prev, 0, sizeof(prev))`
- `memset(next, 0, sizeof(next))`
- `memcpy(prev, next, sizeof(prev))`
- `sprintf(buffer, "#%d", j)`
- `std::setw(20)`
- `std::setw(4)`
- `debug_immediate(next[j], 11)`

# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `debug_immediate`

### Exact declarations

- `void debug_immediate(Immediate v, unsigned width = 0);`

### Exact target-source usages

- `debug_immediate(next[j], 11)`
