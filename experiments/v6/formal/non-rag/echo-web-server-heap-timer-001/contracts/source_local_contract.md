# Machine-extracted Source-local Implementation Contract

This appendix is deterministic evidence extracted from the target source.
It is not an LLM summary and it does not contain complete function bodies.

During regeneration:
- preserve the exact local declaration types, containers, initializers, and literals listed below;
- preserve the exact call targets and argument expressions listed below;
- do not substitute a different representation or accessor merely because it looks similar;
- treat these items as exact constraints, not as pseudocode suggestions.

## Exact local declarations

- `const auto idx {key_to_idx_.at(key)};`
- `const auto shift_up {expiration < nodes_[idx].expiration};`
- `const auto idx {Size()};`
- `auto parent {Parent(idx)};`
- `auto child {SmallChild(idx)};`
- `const auto left {idx * 2 + 1};`
- `const auto right {left + 1};`
- `auto smaller {left};`
- `auto& node {nodes_.front()};`
- `const auto callback {std::move(node.callback)};`
- `const auto key {node.key};`
- `const auto interval {nodes_.front().expiration - Clock::now()};`
- `const auto key {nodes_[idx].key};`

## Exact top-level call expressions

- `log::RootLogger()`
- `Clock::now()`
- `swap(key, o.key)`
- `swap(expiration, o.expiration)`
- `swap(callback, o.callback)`
- `std::move(logger)`
- `nodes_.clear()`
- `key_to_idx_.clear()`
- `Contain(key)`
- `RemoveByIndex(key_to_idx_[key])`
- `Size()`
- `key_to_idx_.contains(key)`
- `Adjust(key, Clock::now() + expiration)`
- `Adjust(key, expiration, std::nullopt)`
- `key_to_idx_.at(key)`
- `callback.has_value()`
- `ShiftUp(idx)`
- `ShiftDown(idx)`
- `Push(key, Clock::now() + expiration, std::move(callback))`
- `key_to_idx_.emplace(key, idx)`
- `nodes_.push_back({key, expiration, std::move(callback)})`
- `Adjust(key, expiration, std::move(callback))`
- `assert(nodes_.empty() == key_to_idx_.empty())`
- `assert(nodes_.size() == key_to_idx_.size())`
- `assert(ValidIndex(idx))`
- `Parent(idx)`
- `parent.has_value()`
- `assert(*parent < idx)`
- `Swap(*parent, idx)`
- `SmallChild(idx)`
- `child.has_value()`
- `assert(*child > idx)`
- `Swap(*child, idx)`
- `ValidIndex(left)`
- `ValidIndex(right)`
- `assert(ValidIndex(idx1) && ValidIndex(idx2))`
- `nodes_[idx1].Swap(nodes_[idx2])`
- `Empty()`
- `nodes_.front()`
- `node.Expired()`
- `std::move(node.callback)`
- `Pop()`
- `assert(callback)`
- `callback(key)`
- `logger_->Log( log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`
- `Tick()`
- `Clock::duration::zero()`
- `assert(!Empty())`
- `RemoveByIndex(0)`
- `assert(nodes_[idx].callback)`
- `nodes_[idx].callback(key)`
- `logger_->Log(log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()))`
- `RemoveByIndex(idx)`
- `assert(!Contain(key))`
- `Clear()`
- `assert(nodes_.front().key == key)`
- `nodes_.front().Swap(nodes_.back())`
- `std::swap(key_to_idx_[nodes_.front().key], key_to_idx_[nodes_.back().key])`
- `nodes_.pop_back()`
- `key_to_idx_.erase(key)`
- `ShiftDown(0)`
- `assert(key_to_idx_.size() == nodes_.size())`
