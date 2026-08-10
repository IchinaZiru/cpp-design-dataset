# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `unsigned base_addr = 0;`
- `std::string line;`
- `std::stringstream ss(line);`
- `std::string hex;`
- `char data = parse_hex(hex);`

## Exact top-level call expressions

- `strtol(hex.c_str(), NULL, 16)`
- `std::getline(in, line)`
- `strtol(line.c_str() + 1, NULL, 16)`
- `hex.length()`
- `parse_hex(hex)`
- `mem.write_word(base_addr, parse_hex(hex))`

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
