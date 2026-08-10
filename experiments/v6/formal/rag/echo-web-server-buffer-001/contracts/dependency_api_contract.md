# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `ReadFrom`

### Exact declarations

- `virtual std::size_t ReadFrom(Buffer& buf) = 0;`
- `std::size_t ReadFrom(Buffer& buf) noexcept override;`
- `std::size_t ReadFrom(Buffer& buf) override;`

### Exact target-source usages

- `io.ReadFrom(*this)`

## `WriteTo`

### Exact declarations

- `virtual std::size_t WriteTo(Buffer& buf) = 0;`
- `std::size_t WriteTo(Buffer& buf) noexcept override;`
- `std::size_t WriteTo(Buffer& buf) override;`

### Exact target-source usages

- `io.WriteTo(*this)`
