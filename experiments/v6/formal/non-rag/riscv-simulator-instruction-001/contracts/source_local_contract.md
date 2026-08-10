# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `static std::string opi[] = { "addi", "slli", "slti", "sltiu", "xori", "srli / srai", "ori", "andi" };`

## Exact top-level call expressions

- `InstructionBase(0)`
- `bin_mask(hi - lo + 1)`
- `is_valid(key)`
- `InvalidAccess()`
- `get_digits(inst, 6, 0)`
- `get_digits(inst, 11, 7)`
- `get_digits(inst, 14, 12)`
- `get_digits(inst, 19, 15)`
- `get_digits(inst, 24, 20)`
- `get_digits(inst, 31, 25)`
- `get_digits(inst, 30, 20)`
- `expand_digit(get_digits(inst, 31, 31), 11)`
- `get_digits(inst, 30, 25)`
- `get_digits(inst, 11, 8)`
- `get_digits(inst, 7, 7)`
- `expand_digit(get_digits(inst, 31, 31), 12)`
- `get_digits(inst, 19, 12)`
- `get_digits(inst, 30, 21)`
- `get_digits(inst, 20, 20)`
- `expand_digit(get_digits(inst, 31, 31), 20)`
