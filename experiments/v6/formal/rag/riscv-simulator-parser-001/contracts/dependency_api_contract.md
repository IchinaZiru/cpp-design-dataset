# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `write_word`

### Exact declarations

- `void write_word(unsigned int addr, Immediate imm);`

### Exact target-source usages

- `mem.write_word(base_addr, parse_hex(hex))`
