# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `static T ins {std::move(args)...};`
- `static const std::shared_ptr<T> ins { std::make_shared<T>(std::move(args)...)};`
- `std::ostringstream ss;`
- `const auto begin {str.find(from)};`
- `std::vector<std::string> strs;`
- `const std::sregex_token_iterator begin {str.cbegin(), str.cend(), pattern, -1};`
- `static const std::regex pattern {"\r*\n"};`
- `const YAML::Node node {YAML::Load(str.data())};`
- `std::unique_ptr<VoidPtr[]> buffer {new VoidPtr[size] {}};`
- `const auto ret_size {backtrace(buffer.get(), static_cast<int>(size))};`
- `char** const stack_strs {backtrace_symbols(buffer.get(), ret_size)};`
- `auto i {skip};`
- `std::vector<std::string> stack;`
- `std::ostringstream backtrace;`
- `const RAII fd {open(path_.c_str(), O_RDONLY), [](const auto fd) noexcept { if (IsValidFileDescriptor(fd)) { close(fd); } }};`
- `const auto map_base {mmap(nullptr, stat_.st_size, PROT_READ, MAP_PRIVATE, fd.Object(), 0)};`

## Exact top-level call expressions

- `std::move(args)`
- `std::make_shared<T>(std::move(args)...)`
- `std::move(obj)`
- `std::move(cleaner)`
- `cleaner_(obj_)`
- `std::ranges::transform( str.begin(), str.end(), str.begin(), [](const unsigned char c) noexcept { return std::tolower(c); })`
- `std::ranges::transform( str.begin(), str.end(), str.begin(), [](const unsigned char c) noexcept { return std::toupper(c); })`
- `str.empty()`
- `str.find(from)`
- `str.substr(0, begin)`
- `str.substr(begin + from.length())`
- `ss.str()`
- `str.cbegin()`
- `str.cend()`
- `std::copy(begin, std::sregex_token_iterator {}, std::back_inserter(strs))`
- `SplitString(str, pattern)`
- `YAML::Load(str.data())`
- `std::ranges::for_each( required_fields, [&node, &str](const std::string_view field) { if (!node[field.data()]) { throw std::invalid_argument { fmt::format("Invalid YAML value: '{}'", str)}; } })`
- `node[field.data()].IsScalar()`
- `fmt::format("Invalid YAML field: '{}'", field)`
- `std::system_category()`
- `assert(IsValidFileDescriptor(fd))`
- `fcntl(fd, F_SETFL, fcntl(fd, F_GETFD) | O_NONBLOCK)`
- `ThrowLastSystemError()`
- `static_cast<std::uint32_t>(syscall(SYS_gettid))`
- `backtrace(buffer.get(), static_cast<int>(size))`
- `backtrace_symbols(buffer.get(), ret_size)`
- `stack.push_back(stack_strs[i])`
- `free(stack_strs)`
- `Backtrace(stack, size, skip)`
- `std::ranges::for_each(stack, [&backtrace, &prefix](const auto& call) noexcept { backtrace << prefix << call << "\n"; })`
- `backtrace.str()`
- `std::move(o.stat_)`
- `std::move(o.path_)`
- `Unmap()`
- `assert(!path_.empty())`
- `stat(path_.data(), &stat_)`
- `S_ISDIR(stat_.st_mode)`
- `fmt::format("'{}' is a directory", path_)`
- `fmt::format("No permission to access '{}'", path_)`
- `std::move(path)`
- `Check()`
- `open(path_.c_str(), O_RDONLY)`
- `close(fd)`
- `mmap(nullptr, stat_.st_size, PROT_READ, MAP_PRIVATE, fd.Object(), 0)`
- `static_cast<std::byte*>(map_base)`
- `munmap(data_, stat_.st_size)`
- `path_.clear()`

# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.
