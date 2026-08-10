# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `Append`

### Exact declarations

- `void Append(std::span<const std::byte> bytes) noexcept;`
- `void Append(std::initializer_list<std::byte> bytes) noexcept;`
- `void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept;`
- `void Append(const Buffer& buf) noexcept;`

### Exact target-source usages

- `buf.Append(str)`
- `buf.Append({ext_bytes.cbegin(), ext_bytes.cbegin() + (size - buf_bytes.size_bytes())})`

## `HasWritten`

### Exact declarations

- `void HasWritten(std::size_t size) noexcept;`

### Exact target-source usages

- `buf.HasWritten(size)`
- `buf.HasWritten(buf_bytes.size_bytes())`

## `ReadableBytes`

### Exact declarations

- `std::span<const std::byte> ReadableBytes() const noexcept;`

### Exact target-source usages

- `buf.ReadableBytes()`

## `Retrieve`

### Exact declarations

- `void Retrieve(std::size_t size) noexcept;`

### Exact target-source usages

- `buf.Retrieve(size)`

## `RetrieveAll`

### Exact declarations

- `std::size_t RetrieveAll() noexcept;`

### Exact target-source usages

- `buf.RetrieveAll()`

## `RetrieveAllToString`

### Exact declarations

- `std::string RetrieveAllToString() noexcept;`

### Exact target-source usages

- `buf.RetrieveAllToString()`

## `ThrowLastSystemError`

### Exact declarations

- `[[noreturn]] void ThrowLastSystemError();`

### Exact target-source usages

- `ThrowLastSystemError()`

## `WritableBytes`

### Exact declarations

- `std::span<std::byte> WritableBytes() const noexcept;`

### Exact target-source usages

- `buf.WritableBytes()`

## `WritableSize`

### Exact declarations

- `std::size_t WritableSize() const noexcept;`

### Exact target-source usages

- `buf.WritableSize()`
