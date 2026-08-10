# Machine-extracted Dependency API Contract

This appendix is deterministic evidence derived from the selected repository context and target-source usages.
It is not an LLM summary.

During regeneration:
- preserve the exact dependency declarations and call patterns listed below;
- do not invent replacement APIs, member functions, overloads, or adapters;
- preserve return types, parameter types, defaults, qualifiers, and argument expressions as written;
- do not consume a void return value as a value.

## `AddListener`

### Exact declarations

- `std::uint64_t AddListener(OnChange listener) noexcept;`

### Exact target-source usages

- `loggers->AddListener( [manager](const std::unordered_set<LoggerConfig>& old_cfgs, const std::unordered_set<LoggerConfig>& new_cfgs) noexcept { for (const auto& logger_cfg : new_cfgs) { if (const auto cfg {old_cfgs.find(logger_cfg)}; cfg != old_cfgs.cend() && *cfg == logger_cfg) { continue; } // Remove the old logger. manager->RemoveLogger(logger_cfg.name); // Create a new logger. const auto logger {manager->FindLogger( logger_cfg.name, logger_cfg.level, logger_cfg.capacity)}; if (!logger_cfg.formatter.empty()) { logger->SetDefaultFormatter(logger_cfg.formatter); } // Add appenders. logger->ClearAppenders(); for (const auto& appender_cfg : logger_cfg.appenders) { Appender::Ptr appender; switch (appender_cfg.type) { case AppenderType::StdOut: { appender = std::make_shared<StdOutAppender>( logger->GetDefaultFormatter()); break; } case AppenderType::File: { appender = std::make_shared<FileAppender>( appender_cfg.file, logger->GetDefaultFormatter()); break; } default: { assert(false); } } logger->AddAppender(appender); } } })`

## `Close`

### Exact declarations

- `void Close() noexcept;`
- `template <typename T> void BlockDeque<T>::Close() noexcept { const std::lock_guard locker {mtx_}; ClearNoLock(); closed_ = true; producer_cond_.notify_all(); consumer_cond_.notify_all(); }`
- `void BlockDeque<T>::Close() noexcept;`

### Exact target-source usages

- `event_deque_->Close()`

## `CurrentThreadId`

### Exact declarations

- `std::uint32_t CurrentThreadId() noexcept;`

### Exact target-source usages

- `CurrentThreadId()`

## `LoadYamlString`

### Exact declarations

- `YAML::Node LoadYamlString( std::string_view str, std::initializer_list<std::string_view> required_fields = {});`

### Exact target-source usages

- `LoadYamlString(str, {"type"})`
- `LoadYamlString(str, {"name", "level", "appenders"})`

## `Lookup`

### Exact declarations

- `template <typename T> typename Var<T>::Ptr Lookup(const std::string_view name, const T& default_val, const std::string_view description = "") { if (const auto var {Lookup<T>(name)}; !var) { const auto new_var { std::make_shared<Var<T>>(name, default_val, description)}; const std::unique_lock locker {mtx_}; vars_.emplace(name, new_var); return new_var; } else { return var; } }`
- `typename Var<T>::Ptr Lookup(const std::string_view name, const T& default_val, const std::string_view description = "");`

### Exact target-source usages

- `cfg::RootConfig()->Lookup( "loggers", std::unordered_set<LoggerConfig> {}, "Loggers")`

## `Name`

### Exact declarations

- `std::string_view Name() const noexcept;`

### Exact target-source usages

- `logger.Name()`

## `Pop`

### Exact declarations

- `std::optional<T> Pop( std::optional<Clock::duration> time_out = std::nullopt) noexcept;`

### Exact target-source usages

- `event_deque_->Pop()`

## `PushBack`

### Exact declarations

- `void PushBack(T item) noexcept;`
- `template <typename T> void BlockDeque<T>::PushBack(T item) noexcept { std::unique_lock locker {mtx_}; WaitForSpace(locker); deq_.push_back(std::move(item)); Flush(); }`
- `void BlockDeque<T>::PushBack(T item) noexcept;`

### Exact target-source usages

- `event_deque_->PushBack(std::move(event))`

## `RootConfig`

### Exact declarations

- `Config::Ptr RootConfig() noexcept;`

### Exact target-source usages

- `cfg::RootConfig()`

## `StringToUpper`

### Exact declarations

- `std::string StringToUpper(std::string str) noexcept;`

### Exact target-source usages

- `StringToUpper(str)`

## `ThrowIfYamlFieldIsNotScalar`

### Exact declarations

- `void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node, std::string_view field);`

### Exact target-source usages

- `ThrowIfYamlFieldIsNotScalar(node, "type")`
- `ThrowIfYamlFieldIsNotScalar(node, "file")`
- `ThrowIfYamlFieldIsNotScalar(node, "formatters")`
- `ThrowIfYamlFieldIsNotScalar(node, "name")`
- `ThrowIfYamlFieldIsNotScalar(node, "level")`
- `ThrowIfYamlFieldIsNotScalar(node, "capacity")`
- `ThrowIfYamlFieldIsNotScalar(node, "formatter")`

## `ThrowLastSystemError`

### Exact declarations

- `[[noreturn]] void ThrowLastSystemError();`

### Exact target-source usages

- `ThrowLastSystemError()`
