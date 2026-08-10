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
