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

    using TimeOutCallback = std::function<void(const Key&)>&gt;;

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
        bool Expired() const noexcept {
            return expiration <= Clock::now();
        }

        void Swap(Node& o) noexcept {
            std::swap(key, o.key);
            std::swap(expiration, o.expiration);
            std::swap(callback, o.callback);
        }

        friend std::weak_ordering operator<=>(const Node& lhs,
                                              const Node& rhs) noexcept {
            return lhs.expiration <=> rhs.expiration;
        }
    };

    void Swap(std::size_t idx1, std::size_t idx2) noexcept {
        nodes_[idx1].Swap(nodes_[idx2]);
        key_to_idx_[nodes_[idx1].key] = idx1;
        key_to_idx_[nodes_[idx2].key] = idx2;
    }

    /**
     * @brief Adjust a node.
     *
     * @exception std::out_of_range The timer system does not contain any node with the specific key.
     */
    void Adjust(const Key& key, Clock::time_point expiration,
                std::optional<TimeOutCallback> callback) {
        auto it = key_to_idx_.find(key);
        if (it == key_to_idx_.end()) {
            throw std::out_of_range("Key not found");
        }

        std::size_t idx = it->second;
        nodes_[idx].expiration = expiration;
        if (callback) {
            nodes_[idx].callback = *callback;
        }

        ShiftUp(idx);
        ShiftDown(idx);
    }

    //! Remove a node and return its key.
    Key RemoveByIndex(std::size_t idx) noexcept {
        assert(ValidIndex(idx));
        Key key = nodes_[idx].key;
        Swap(idx, nodes_.size() - 1);
        nodes_.pop_back();
        key_to_idx_.erase(key);

        if (idx < nodes_.size()) {
            ShiftUp(idx);
            ShiftDown(idx);
        }

        return key;
    }

    /**
     * @brief
     * Recursively swap a node with its parent if it is smaller than the parent.
     *
     * @details
     * This method will continue shift-up even if the parent is equal to the node.
     * Finally, the node will be moved to the top of other nodes with the same value.
     */
    void ShiftUp(std::size_t idx) noexcept {
        while (auto parent = Parent(idx)) {
            if (nodes_[*parent] <= nodes_[idx]) {
                break;
            }

            Swap(*parent, idx);
            idx = *parent;
        }
    }

    //! Recursively swap a node with its smallest child if it is larger than the child.
    void ShiftDown(std::size_t idx) noexcept {
        while (auto small_child = SmallChild(idx)) {
            if (nodes_[idx] <= nodes_[*small_child]) {
                break;
            }

            Swap(*small_child, idx);
            idx = *small_child;
        }
    }

    bool ValidIndex(std::size_t idx) const noexcept {
        return idx < nodes_.size();
    }

    //! Get the index of a node's parent, or @p std::nullopt if it does not exist.
    std::optional<std::size_t> Parent(std::size_t idx) const noexcept {
        if (idx == 0) {
            return std::nullopt;
        }

        return (idx - 1) / 2;
    }

    /**
     * @brief
     * Get the index of a node's child that has a shorter expiration time,
     * or @p std::nullopt if it does not exist.
     */
    std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept {
        std::optional<std::size_t> left = 2 * idx + 1;
        std::optional<std::size_t> right = 2 * idx + 2;

        if (!ValidIndex(*left)) {
            return std::nullopt;
        }

        if (!ValidIndex(*right) || nodes_[*left] < nodes_[*right]) {
            return left;
        }

        return right;
    }

    log::Logger::Ptr logger_;

    //! A map from user-defined keys to array indices.
    std::unordered_map<Key, std::size_t> key_to_idx_;
    std::deque<Node> nodes_;
};

template <typename Key>
HeapTimer<Key>::HeapTimer(log::Logger::Ptr logger) noexcept : logger_{std::move(logger)} {
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
    auto it = key_to_idx_.find(key);
    if (it == key_to_idx_.end()) {
        return false;
    }

    RemoveByIndex(it->second);
    return true;
}

template <typename Key>
bool HeapTimer<Key>::ValidIndex(const std::size_t idx) const noexcept {
    return idx < nodes_.size();
}

template <typename Key>
bool HeapTimer<Key>::Contain(const Key& key) const noexcept {
    return key_to_idx_.find(key) != key_to_idx_.end();
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
void HeapTimer<Key>::Push(const Key& key, const Clock::duration expiration,
                          TimeOutCallback callback) noexcept {
    Push(key, Clock::now() + expiration, callback);
}

template <typename Key>
void HeapTimer<Key>::Push(const Key& key, const Clock::time_point expiration,
                          TimeOutCallback callback) noexcept {
    nodes_.emplace_back(Node{key, expiration, callback});
    std::size_t idx = nodes_.size() - 1;
    key_to_idx_[key] = idx;

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
void HeapTimer<Key>::Tick() noexcept {
    while (!Empty() && nodes_[0].Expired()) {
        try {
            nodes_[0].callback(nodes_[0].key);
        } catch (const std::exception& e) {
            logger_->Log(log::LogLevel::Error, "Exception in callback: {}", e.what());
        }

        RemoveByIndex(0);
    }
}

template <typename Key>
typename HeapTimer<Key>::Clock::duration HeapTimer<Key>::ToNextTick() noexcept {
    Tick();

    if (Empty()) {
        return Clock::duration::zero();
    }

    return nodes_[0].expiration - Clock::now();
}

template <typename Key>
Key HeapTimer<Key>::Pop() noexcept {
    assert(!Empty());
    return RemoveByIndex(0);
}

template <typename Key>
void HeapTimer<Key>::Invoke(const Key& key) {
    auto it = key_to_idx_.find(key);
    if (it == key_to_idx_.end()) {
        throw std::out_of_range("Key not found");
    }

    try {
        nodes_[it->second].callback(nodes_[it->second].key);
    } catch (const std::exception& e) {
        logger_->Log(log::LogLevel::Error, "Exception in callback: {}", e.what());
    }

    RemoveByIndex(it->second);
}

}  // namespace ws