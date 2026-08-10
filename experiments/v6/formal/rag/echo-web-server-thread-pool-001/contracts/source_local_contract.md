# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `auto i {0};`
- `const std::lock_guard locker {mtx_};`
- `const auto not_empty_or_closed {[this]() noexcept { // Working threads may not have started to wait when closing the thread pool. // If a close notification has been sent before they wait, // the condition variable will permanently block the thread. // So we should check if the thread pool has been closed when waiting. return !tasks_.empty() || closed_; }};`
- `Task task;`
- `std::unique_lock locker {mtx_};`

## Exact top-level call expressions

- `log::RootLogger()`
- `std::move(logger)`
- `thread_count.value_or(0)`
- `std::thread::hardware_concurrency()`
- `Close()`
- `assert(thread.joinable())`
- `thread.join()`
- `assert(closed_)`
- `threads_.emplace_back(&ThreadPool::ExecProc, this)`
- `assert(!closed_)`
- `tasks_.push_back(std::move(task))`
- `cond_.notify_one()`
- `tasks_.empty()`
- `cond_.wait(locker, not_empty_or_closed)`
- `std::move(tasks_.front())`
- `tasks_.pop_front()`
- `assert(task)`
- `task()`
- `logger_->Log( log::Event::Create(log::Level::Error) << fmt::format( "Exception raised in thread pool's task: {}", err.what()))`
- `cond_.notify_all()`
