# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `const auto size {buf.WritableSize()};`
- `std::string str;`
- `const std::string str {buf.RetrieveAllToString()};`
- `const auto buf_bytes {buf.WritableBytes()};`
- `std::array<std::byte, 0x10000> ext_bytes;`
- `const std::array bufs { iovec {.iov_base = buf_bytes.data(), .iov_len = buf_bytes.size_bytes()}, iovec {.iov_base = ext_bytes.data(), .iov_len = ext_bytes.size()}};`
- `const auto size {readv(read_, bufs.data(), bufs.size())};`
- `const auto bytes {buf.ReadableBytes()};`
- `const auto size {write(write_, bytes.data(), bytes.size_bytes())};`

## Exact top-level call expressions

- `buf.WritableSize()`
- `buf.HasWritten(size)`
- `buf.RetrieveAll()`
- `buf.Append(str)`
- `str.length()`
- `buf.RetrieveAllToString()`
- `buf.WritableBytes()`
- `buf_bytes.data()`
- `buf_bytes.size_bytes()`
- `ext_bytes.data()`
- `ext_bytes.size()`
- `readv(read_, bufs.data(), bufs.size())`
- `ThrowLastSystemError()`
- `buf.HasWritten(buf_bytes.size_bytes())`
- `buf.Append({ext_bytes.cbegin(), ext_bytes.cbegin() + (size - buf_bytes.size_bytes())})`
- `buf.ReadableBytes()`
- `write(write_, bytes.data(), bytes.size_bytes())`
- `buf.Retrieve(size)`
