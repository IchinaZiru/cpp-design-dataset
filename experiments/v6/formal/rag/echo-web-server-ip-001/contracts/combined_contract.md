# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `std::array<char, max_length + 1> ip;`

## Exact top-level call expressions

- `std::move(addr)`
- `inet_ntop(version, &raw_.sin_addr, ip.data(), ip.size())`
- `ThrowLastSystemError()`
- `std::move(ip)`
- `htons(port)`
- `inet_pton(version, ip_.data(), &raw_.sin_addr)`
- `ntohs(raw_.sin_port)`
- `reinterpret_cast<const sockaddr*>(&raw_)`
- `inet_ntop(version, &raw_.sin6_addr, ip.data(), ip.size())`
- `inet_pton(version, ip_.data(), &raw_.sin6_addr)`
- `ntohs(raw_.sin6_port)`

# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `ThrowLastSystemError`

### Exact declarations

- `[[noreturn]] void ThrowLastSystemError();`

### Exact target-source usages

- `ThrowLastSystemError()`
