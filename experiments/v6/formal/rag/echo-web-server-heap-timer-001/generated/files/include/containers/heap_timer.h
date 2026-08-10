/**
 * @file heap_timer.h
 * @brief The timer system based on a min-heap.
 *
 * @author Zhenshuo Chen (chenzs108@outlook.com)
 * @par GitHub
 * https://github.com/Zhuagenborn
 * @version 1.0
 * @date 2022-06-01
 *
 * @example tests/containers/heap_timer_test.cpp
 */

#pragma once

#include "log.h"
#include "util.h"

#include <algorithm>
#include <cassert>
#include <chrono>
#include <compare>
#include <deque>
#include <functional>
#include <optional>
#include <stdexcept>
#include <unordered_map>


namespace ws {

/**
 * @brief
 * The timer system based on a min-heap.
 *
 * @details
 * Timers are maintained in a min-heap ordered by expiration time.
 * When a timer expires, its callback will be invoked.
 *
 * @tparam Key The type of node keys.
 */
template <typename Key>
class HeapTimer {
public:
    using Clock = std::chrono::steady_clock;

    using TimeOutCallback = std::function<void(const Key&)>;

    /**
     * @brief Create a timer system.
     *
     * @param logger
     * A logger. If it is @p nullptr, the timer system will use the global root logger.
     */
    explicit HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept;

    HeapTimer(HeapTimer&&) = delete;

    HeapTimer& operator=(HeapTimer&&) = delete;

    HeapTimer(const HeapTimer&) = delete;

    HeapTimer& operator=(const HeapTimer&) = delete;

    /**
     * @brief Adjust a node's expiration time.
     *
     * @param key A key.
     * @param expiration A new duration from now to its expiration time.
     *
     * @exception std::out_of_range The timer system does not contain any node with the specific key.
     */
    void Adjust(const Key& key, Clock::duration expiration);

    /**
     * @brief Adjust a node's expiration time.
     *
     * @param key A key.
     * @param expiration A new expiration time.
     *
     * @exception std::out_of_range The timer system does not contain any node with the specific key.
     */
    void Adjust(const Key& key, Clock::time_point expiration);

    /**
     * @brief Push a node into the timer system.
     *
     * @param key A key.
     * @param expiration A duration from now to its expiration time.
     * @param callback A time-out callback that will be invoked when the node expires.
     */
    void Push(const Key& key, Clock::duration expiration,
              TimeOutCallback callback) noexcept;

    /**
     * @brief Push a node into the timer system.
     *
     * @param key A key.
     * @param expiration An expiration time.
     * @param callback A time-out callback that will be invoked when the node expires.
     */
    void Push(const Key& key, Clock::time_point expiration,
              TimeOutCallback callback) noexcept;

    /**
     * @brief Remove expired nodes and invoke their callbacks.
     *
     * @warning
     * Any exceptions raised in callbacks will not be rethrown.
     * Exception messages will be recorded in the logger.
     */
    void Tick() noexcept;

    /**
     * @brief Remove a node by its key.
     *
     * @return Whether the node was removed.
     */
    bool Remove(const Key& key) noexcept;

    /**
     * @brief Remove a node by its key and invoke the callback.
     *
     * @exception std::out_of_range The timer system does not contain any node with the specific key.
     *
     * @warning
     * Any exceptions raised in callbacks will not be rethrown.
     * Exception messages will be recorded in the logger.
     */
    void Invoke(const Key& key);

    /**
     * @brief Pop the top node and return its key.
     *
     * @warning This method can only be called when the timer system is not empty.
     */
    Key Pop() noexcept;

    //! Clear the timer system.
    void Clear() noexcept;

    //! Whether the timer system contains the node with a specific key.
    bool Contain(const Key& key) const noexcept;

    //! Whether the timer system is empty.
    bool Empty() const noexcept;

    //! Get the number of nodes.
    std::size_t Size() const noexcept;

    /**
     * @brief
     * Remove expired nodes and invoke their callbacks.
     * Then return the interval from now to the next node's expiration time.
     * The interval is greater than or equal to zero.
     *
     * @warning
     * Any exceptions raised in callbacks will not be rethrown.
     * Exception messages will be recorded in the logger.
     */
    Clock::duration ToNextTick() noexcept;

private:
    struct Node {
        //! A user-defined unique key.
        Key key;

        //! An expiration time.
        Clock::time_point expiration;

        //! A time-out callback which will be invoked when the node expires.
        TimeOutCallback callback;

        //! Whether the node has expired.
        bool Expired() const noexcept;

        void Swap(Node&) noexcept;

        friend std::weak_ordering operator<=>(const Node& lhs,
                                              const Node& rhs) noexcept ;
    };

    void Swap(std::size_t idx1, std::size_t idx2) noexcept;

    /**
     * @brief Adjust a node.
     *
     * @exception std::out_of_range The timer system does not contain any node with the specific key.
     */
    void Adjust(const Key& key, Clock::time_point expiration,
                std::optional<TimeOutCallback> callback);

    //! Remove a node and return its key.
    Key RemoveByIndex(std::size_t idx) noexcept;

    /**
     * @brief
     * Recursively swap a node with its parent if it is smaller than the parent.
     *
     * @details
     * This method will continue shift-up even if the parent is equal to the node.
     * Finally, the node will be moved to the top of other nodes with the same value.
     */
    void ShiftUp(std::size_t idx) noexcept;

    //! Recursively swap a node with its smallest child if it is larger than the child.
    void ShiftDown(std::size_t idx) noexcept;

    bool ValidIndex(std::size_t idx) const noexcept;

    //! Get the index of a node's parent, or @p std::nullopt if it does not exist.
    std::optional<std::size_t> Parent(std::size_t idx) const noexcept;

    /**
     * @brief
     * Get the index of a node's child that has a shorter expiration time,
     * or @p std::nullopt if it does not exist.
     */
    std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept;

    log::Logger::Ptr logger_;

    //! A map from user-defined keys to array indices.
    std::unordered_map<Key, std::size_t> key_to_idx_;
    std::deque<Node> nodes_;
};

template <typename Key>
bool HeapTimer<Key>::Node::Expired() const noexcept {
    return expiration <= Clock::now();
}

template <typename Key>
void HeapTimer<Key>::Node::Swap(Node& o) noexcept {
    using std::swap;
    swap(key, o.key);
    swap(expiration, o.expiration);
    swap(callback, o.callback);
}

template <typename Key>
HeapTimer<Key>::HeapTimer(log::Logger::Ptr logger) noexcept :
    logger_ {std::move(logger)} {
    if (!logger_) {
        logger_ = log::RootLogger();
    }
}

template <typename Key>
void HeapTimer<Key>::Clear() noexcept {
    nodes_.clear();
    key_to_idx_.clear();
}

template <typename Key>
bool HeapTimer<Key>::Remove(const Key& key) noexcept {
    if (!Contain(key)) {
        return false;
    }
    RemoveByIndex(key_to_idx_[key]);
    return true;
}

template <typename Key>
bool HeapTimer<Key>::ValidIndex(const std::size_t idx) const noexcept {
    return idx < nodes_.size();
}

template <typename Key>
bool HeapTimer<Key>::Contain(const Key& key) const noexcept {
    return key_to_idx_.contains(key);
}

template <typename Key>
void HeapTimer<Key>::Adjust(const Key& key, const Clock::duration expiration) {
    Adjust(key, Clock::now() + expiration);
}

template <typename Key>
void HeapTimer<Key>::Adjust(const Key& key,
                            const Clock::time_point expiration) {
    Adjust(key, expiration, std::nullopt);
}

template <typename Key>
void HeapTimer<Key>::Adjust(const Key& key, const Clock::time_point expiration,
                            const std::optional<TimeOutCallback> callback) {
    const auto idx {key_to_idx_.at(key)};
    nodes_[idx].expiration = expiration;
    if (callback.has_value()) {
        nodes_[idx].callback = *callback;
    }
    const auto shift_up {expiration < nodes_[idx].expiration};
    if (shift_up) {
        ShiftUp(idx);
    } else {
        ShiftDown(idx);
    }
}

template <typename Key>
void HeapTimer<Key>::Push(const Key& key, const Clock::duration expiration,
                          TimeOutCallback callback) noexcept {
    Push(key, Clock::now() + expiration, std::move(callback));
}

template <typename Key>
void HeapTimer<Key>::Push(const Key& key, const Clock::time_point expiration,
                          TimeOutCallback callback) noexcept {
    if (Contain(key)) {
        Adjust(key, expiration, std::move(callback));
        return;
    }
    const auto idx {Size()};
    nodes_.push_back({key, expiration, std::move(callback)});
    key_to_idx_.emplace(key, idx);
    ShiftUp(idx);
}

template <typename Key>
bool HeapTimer<Key>::Empty() const noexcept {
    return nodes_.empty();
}

template <typename Key>
std::size_t HeapTimer<Key>::Size() const noexcept {
    return nodes_.size();
}

template <typename Key>
void HeapTimer<Key>::ShiftUp(std::size_t idx) noexcept {
    auto parent {Parent(idx)};
    while (parent.has_value() && nodes_[*parent] >= nodes_[idx]) {
        Swap(*parent, idx);
        idx = *parent;
        parent = Parent(idx);
    }
}

template <typename Key>
void HeapTimer<Key>::ShiftDown(std::size_t idx) noexcept {
    auto child {SmallChild(idx)};
    while (child.has_value() && nodes_[idx] >= nodes_[*child]) {
        Swap(*child, idx);
        idx = *child;
        child = SmallChild(idx);
    }
}

template <typename Key>
std::optional<std::size_t> HeapTimer<Key>::Parent(
    const std::size_t idx) const noexcept {
    if (idx == 0) {
        return std::nullopt;
    }
    return (idx - 1) / 2;
}

template <typename Key>
std::optional<std::size_t> HeapTimer<Key>::SmallChild(
    const std::size_t idx) const noexcept {
    const auto left {idx * 2 + 1};
    if (!ValidIndex(left)) {
        return std::nullopt;
    }
    const auto right {left + 1};
    if (!ValidIndex(right)) {
        return left;
    }
    auto smaller {left};
    if (nodes_[right] < nodes_[left]) {
        smaller = right;
    }
    return smaller;
}

template <typename Key>
void HeapTimer<Key>::Swap(const std::size_t idx1,
                          const std::size_t idx2) noexcept {
    assert(ValidIndex(idx1) && ValidIndex(idx2));
    nodes_[idx1].Swap(nodes_[idx2]);
    key_to_idx_[nodes_[idx1].key] = idx1;
    key_to_idx_[nodes_[idx2].key] = idx2;
}

template <typename Key>
void HeapTimer<Key>::Tick() noexcept {
    while (!Empty()) {
        auto& node {nodes_.front()};
        if (!node.Expired()) {
            break;
        }
        const auto callback {std::move(node.callback)};
        const auto key {node.key};
        RemoveByIndex(0);
        try {
            assert(callback);
            callback(key);
        } catch (const std::exception& err) {
            logger_->Log(log::Event::Create(log::Level::Error) << fmt::format("Exception raised in timer's callback: {}", err.what()));
        }
    }
}

template <typename Key>
typename HeapTimer<Key>::Clock::duration HeapTimer<Key>::ToNextTick() noexcept {
    Tick();
    if (Empty()) {
        return Clock::duration::zero();
    }
    const auto interval {nodes_.front().expiration - Clock::now()};
    return std::max(interval, Clock::duration::zero());
}

template <typename Key>
Key HeapTimer<Key>::Pop() noexcept {
    assert(!Empty());
    return RemoveByIndex(0);
}

template <typename Key>
void HeapTimer<Key>::Invoke(const Key& key) {
    const auto idx {key_to_idx_.at(key)};
    assert(nodes_[idx].callback);
    nodes_[idx].callback(key);
    RemoveByIndex(idx);
}

/**
 * @note
 * This method relies on the implementation of @p ShiftUp.
 * It assigns the minimum value to the node.
 * After shift-up, the node will be moved to the top, then swap the top and the last node.
 */
template <typename Key>
Key HeapTimer<Key>::RemoveByIndex(const std::size_t idx) noexcept {
    assert(ValidIndex(idx));
    const auto key {nodes_[idx].key};
    if (idx != Size() - 1) {
        nodes_[idx].Swap(nodes_.back());
        std::swap(key_to_idx_[nodes_[idx].key], key_to_idx_[nodes_.back().key]);
        ShiftUp(idx);
        ShiftDown(idx);
    }
    nodes_.pop_back();
    key_to_idx_.erase(key);
    return key;
}

}  // namespace ws