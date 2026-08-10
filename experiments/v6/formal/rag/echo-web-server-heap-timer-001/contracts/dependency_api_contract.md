# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `Create`

### Exact declarations

- `static Ptr Create(log::Level level, std::experimental::source_location location = std::experimental::source_location::current(), std::uint32_t thread_id = CurrentThreadId(), Clock::time_point time = Clock::now()) noexcept;`

### Exact target-source usages

- `log::Event::Create(log::Level::Error)`

## `Log`

### Exact declarations

- `void Log(Event::Ptr event) noexcept;`

### Exact target-source usages

- `logger_->Log( log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`
- `logger_->Log(log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`

## `RootLogger`

### Exact declarations

- `Logger::Ptr RootLogger() noexcept;`

### Exact target-source usages

- `log::RootLogger()`
