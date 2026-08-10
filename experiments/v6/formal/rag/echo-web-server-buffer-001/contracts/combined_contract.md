# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `std::string full_str {str};`
- `const auto base {reinterpret_cast<const std::byte*>(data)};`
- `const auto readable_size {ReadableSize()};`
- `const auto read_size {ReadableSize()};`
- `const auto str {ReadableString()};`
- `const auto end {static_cast<const std::byte*>(addr)};`
- `const auto begin {ReadIter().base()};`
- `const auto read_size {end - begin};`

## Exact top-level call expressions

- `Append(bytes)`
- `Append(bytes.begin(), bytes.size())`
- `Append(str)`
- `o.read_pos_.load()`
- `o.write_pos_.load()`
- `std::move(o.buf_)`
- `buf_.size()`
- `Empty()`
- `ReadIter()`
- `Append(bytes.data(), bytes.size_bytes())`
- `new_line.has_value()`
- `assert(false)`
- `Append(full_str.data(), full_str.length())`
- `assert(data)`
- `EnsureWriteableSize(size)`
- `reinterpret_cast<const std::byte*>(data)`
- `std::copy(base, base + size, WriteIter())`
- `HasWritten(size)`
- `assert(ReadableSize() >= size)`
- `Append(buf.ReadableBytes())`
- `WritableSize()`
- `MakeSpace(size)`
- `assert(WritableSize() >= size)`
- `PrependableSize()`
- `buf_.resize(write_pos_ + size)`
- `std::copy(ReadIter(), WriteIter(), buf_.begin())`
- `assert(readable_size == ReadableSize())`
- `ReadIter().base()`
- `reinterpret_cast<char*>(ReadIter().base())`
- `WriteIter().base()`
- `Clear()`
- `ReadableString()`
- `static_cast<const std::byte*>(addr)`
- `assert(begin <= end)`
- `Retrieve(read_size)`
- `assert(Empty())`
- `const_cast<Buffer*>(this)->buf_.begin()`
- `io.WriteTo(*this)`
- `io.ReadFrom(*this)`
- `buf.Append(str)`
- `to.Append(from)`
- `buf.Append(bytes)`

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
