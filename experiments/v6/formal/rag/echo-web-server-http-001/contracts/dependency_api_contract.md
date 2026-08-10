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

- `void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept;`
- `void Append(const void* data, std::size_t size) noexcept;`
- `void Append(std::span<const std::byte> bytes) noexcept;`
- `void Append(std::initializer_list<std::byte> bytes) noexcept;`
- `void Append(const Buffer& buf) noexcept;`

### Exact target-source usages

- `buf.Append( fmt::format("HTTP/{} {} {}", version, StatusCodeToInteger(status_code_), StatusCodeToMessage(status_code_)), NewLine::CRLF)`
- `buf.Append("Connection: ")`
- `buf.Append("keep-alive", NewLine::CRLF)`
- `buf.Append("keep-alive: max=6, timeout=120", NewLine::CRLF)`
- `buf.Append("close", NewLine::CRLF)`
- `buf.Append(fmt::format("Content-type: {}", ContentTypeByFileName(file_path_.c_str())), NewLine::CRLF)`
- `buf.Append(fmt::format("Content-length: {}", file_.Size()), NewLine::CRLF)`
- `buf.Append(new_line)`
- `buf.Append(fmt::format("Content-length: {}", length), NewLine::CRLF)`
- `buf.Append(lines[i], NewLine::CRLF)`
- `buf.Append(lines[i])`
- `buf.Append("Content-type: text/html", NewLine::CRLF)`
- `buf.Append(fmt::format("Content-length: {}", body.size()), NewLine::CRLF)`
- `buf.Append(body)`

## `Data`

### Exact declarations

- `std::byte* Data() const noexcept;`

### Exact target-source usages

- `file_.Data()`

## `Empty`

### Exact declarations

- `bool Empty() const noexcept;`

### Exact target-source usages

- `write_buf_.Empty()`
- `buf.Empty()`

## `IPAddress`

### Exact declarations

- `virtual std::string IPAddress() const noexcept = 0;`
- `std::string IPAddress() const noexcept override;`

### Exact target-source usages

- `addr_.IPAddress()`

## `IsValidFileDescriptor`

### Exact declarations

- `constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept;`

### Exact target-source usages

- `IsValidFileDescriptor(socket_)`

## `Map`

### Exact declarations

- `std::byte* Map(std::string path);`

### Exact target-source usages

- `file_.Map(root_dir_ / file_path_.relative_path())`
- `file_.Map(file_path_)`

## `Path`

### Exact declarations

- `std::string_view Path() const noexcept;`

### Exact target-source usages

- `request.Path()`

## `Port`

### Exact declarations

- `virtual std::uint16_t Port() const noexcept = 0;`
- `std::uint16_t Port() const noexcept override;`

### Exact target-source usages

- `addr_.Port()`

## `ReadFrom`

### Exact declarations

- `std::size_t ReadFrom(io::IReadWriter& io);`
- `virtual std::size_t ReadFrom(Buffer& buf) = 0;`
- `std::size_t ReadFrom(Buffer& buf) noexcept override;`
- `std::size_t ReadFrom(Buffer& buf) override;`

### Exact target-source usages

- `read_buf_.ReadFrom(io)`

## `ReadableSize`

### Exact declarations

- `std::size_t ReadableSize() const noexcept;`

### Exact target-source usages

- `read_buf_.ReadableSize()`

## `ReadableString`

### Exact declarations

- `std::string ReadableString() const noexcept;`

### Exact target-source usages

- `buf.ReadableString()`

## `ReplaceAllSubstring`

### Exact declarations

- `std::string ReplaceAllSubstring(std::string_view str, std::string_view from, std::string_view to) noexcept;`

### Exact target-source usages

- `ReplaceAllSubstring(html, HTMLPlaceholder(key), val)`
- `ReplaceAllSubstring(content, HTMLPlaceholder(key), val)`

## `Retrieve`

### Exact declarations

- `void Retrieve(std::size_t size) noexcept;`

### Exact target-source usages

- `buf.Retrieve(line.length())`
- `buf.Retrieve(new_line.length())`

## `Size`

### Exact declarations

- `virtual std::size_t Size() const noexcept = 0;`
- `std::size_t Size() const noexcept override;`
- `std::size_t Size() const noexcept;`

### Exact target-source usages

- `file_.Size()`

## `SplitStringToLines`

### Exact declarations

- `std::vector<std::string> SplitStringToLines(const std::string& str) noexcept;`

### Exact target-source usages

- `SplitStringToLines(content)`

## `StringToLower`

### Exact declarations

- `std::string StringToLower(std::string str) noexcept;`

### Exact target-source usages

- `StringToLower(std::filesystem::path {name}.extension())`

## `StringToUpper`

### Exact declarations

- `std::string StringToUpper(std::string str) noexcept;`

### Exact target-source usages

- `StringToUpper(str)`

## `ThrowLastSystemError`

### Exact declarations

- `[[noreturn]] void ThrowLastSystemError();`

### Exact target-source usages

- `ThrowLastSystemError()`

## `Unmap`

### Exact declarations

- `void Unmap() noexcept;`

### Exact target-source usages

- `file_.Unmap()`

## `WriteTo`

### Exact declarations

- `std::size_t WriteTo(io::IReadWriter& io);`
- `virtual std::size_t WriteTo(Buffer& buf) = 0;`
- `std::size_t WriteTo(Buffer& buf) noexcept override;`
- `std::size_t WriteTo(Buffer& buf) override;`

### Exact target-source usages

- `write_buf_.WriteTo(io)`
