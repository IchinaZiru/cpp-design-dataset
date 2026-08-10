# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `const std::lock_guard locker {mtx_};`
- `const auto size {this->Size()};`
- `std::unique_lock locker {mtx_};`
- `const auto not_empty_or_closed {[this]() noexcept { // Consumer threads may not have started to wait when closing the deque. // If a close notification has been sent before they wait, // the condition variable will permanently block the thread. // So we should check if the queue has been closed when waiting. return !deq_.empty() || closed_; }};`
- `const auto item {deq_.front()};`

## Exact top-level call expressions

- `assert(capacity > 0)`
- `Close()`
- `deq_.empty()`
- `this->Size()`
- `assert(size <= capacity_)`
- `deq_.size()`
- `ClearNoLock()`
- `producer_cond_.notify_all()`
- `consumer_cond_.notify_all()`
- `deq_.clear()`
- `consumer_cond_.notify_one()`
- `WaitForSpace(locker)`
- `deq_.push_back(std::move(item))`
- `Flush()`
- `deq_.push_front(std::move(item))`
- `assert(!deq_.empty())`
- `deq_.front()`
- `deq_.back()`
- `const_cast<T&>(std::as_const(*this).Front())`
- `const_cast<T&>(std::as_const(*this).Back())`
- `time_out.has_value()`
- `consumer_cond_.wait_for(locker, *time_out, not_empty_or_closed)`
- `consumer_cond_.wait(locker, not_empty_or_closed)`
- `deq_.pop_front()`
- `producer_cond_.notify_one()`
- `producer_cond_.wait(locker, [this]() { return deq_.size() < capacity_; })`
