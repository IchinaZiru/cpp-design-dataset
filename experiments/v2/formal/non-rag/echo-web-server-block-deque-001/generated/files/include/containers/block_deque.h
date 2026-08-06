/**
 * @file block_deque.h
 * @brief The block double-ended queue.
 *
 * @author Chen Zhenshuo (chenzs108@outlook.com)
 * @author Liu Guowen (liu.guowen@outlook.com)
 * @par GitHub
 * https://github.com/Zhuagenborn
 * @version 1.0
 * @date 2022-04-23
 *
 * @example tests/containers/block_deque_test.cpp
 */

#pragma once

#include <cassert>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <optional>
#include <utility>
#include <chrono>


namespace ws {

//! The block double-ended queue.
template <typename T>
class BlockDeque {
public:
    using Clock = std::chrono::steady_clock;

    /**
     * @brief Create a block double-ended queue.
     *
     * @param capacity
     * The maximum capacity.
     * If the queue is full, push will be blocked and waiting.
     */
    explicit BlockDeque(std::size_t capacity = 1000) noexcept;

    BlockDeque(const BlockDeque&) = delete;

    BlockDeque(BlockDeque&&) = delete;

    BlockDeque& operator=(const BlockDeque&) = delete;

    BlockDeque& operator=(BlockDeque&&) = delete;

    ~BlockDeque() noexcept;

    //! Clear all elements.
    void Clear() noexcept;

    //! Whether the queue is empty.
    bool Empty() const noexcept;

    //! Whether the queue is full.
    bool Full() const noexcept;

    //! Get the number of elements.
    std::size_t Size() const noexcept;

    //! Get the maximum capacity.
    std::size_t Capacity() const noexcept;

    //! Add an element to the end and notify a consumer.
    void PushBack(T item) noexcept;

    //! Insert an element to the beginning and notify a consumer.
    void PushFront(T item) noexcept;

    /**
     * @brief Access the first element.
     *
     * @warning This method can only be called when the queue is not empty.
     */
    const T& Front() const noexcept;

    /**
     * @brief Access the last element.
     *
     * @warning This method can only be called when the queue is not empty.
     */
    const T& Back() const noexcept;

    T& Front() noexcept;

    T& Back() noexcept;

    /**
     * @brief Try to pop the first element.
     *
     * @param time_out
     * An optional maximum time to wait.
     * If it is @p std::nullopt, this will method keep waiting until getting an element or the queue is closed.
     *
     * @return The first element, otherwise @p std::nullopt if getting a time-out or the queue is closed.
     */
    std::optional<T> Pop(
        std::optional<Clock::duration> time_out = std::nullopt) noexcept;

    //! Notify a consumer.
    void Flush() noexcept;

    //! Clear all elements and close the queue.
    void Close() noexcept;

private:
    //! Keep waiting until there is a valid position in the queue, then notify a producer.
    void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept;

    void ClearNoLock() noexcept;

    mutable std::mutex mtx_;
    std::atomic_bool closed_ {false};
    std::size_t capacity_;

    std::deque<T> deq_;

    std::condition_variable consumer_cond_;
    std::condition_variable producer_cond_;
};

template <typename T>
BlockDeque<T>::BlockDeque(const std::size_t capacity) noexcept :
    capacity_ {capacity} {
    assert(capacity > 0);
}

template <typename T>
BlockDeque<T>::~BlockDeque() noexcept {
    Close();
}

template <typename T>
bool BlockDeque<T>::Empty() const noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    return deq_.empty();
}

template <typename T>
bool BlockDeque<T>::Full() const noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    return deq_.size() >= capacity_;
}

template <typename T>
std::size_t BlockDeque<T>::Size() const noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    return deq_.size();
}

template <typename T>
std::size_t BlockDeque<T>::Capacity() const noexcept {
    return capacity_;
}

template <typename T>
void BlockDeque<T>::Close() noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    closed_ = true;
    ClearNoLock();
    consumer_cond_.notify_all();
    producer_cond_.notify_all();
}

template <typename T>
void BlockDeque<T>::ClearNoLock() noexcept {
    deq_.clear();
}

template <typename T>
void BlockDeque<T>::Clear() noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    ClearNoLock();
    consumer_cond_.notify_all();
}

template <typename T>
void BlockDeque<T>::Flush() noexcept {
    consumer_cond_.notify_one();
}

template <typename T>
void BlockDeque<T>::PushBack(T item) noexcept {
    std::unique_lock<std::mutex> locker(mtx_);
    WaitForSpace(locker);
    deq_.emplace_back(std::move(item));
    consumer_cond_.notify_one();
}

template <typename T>
void BlockDeque<T>::PushFront(T item) noexcept {
    std::unique_lock<std::mutex> locker(mtx_);
    WaitForSpace(locker);
    deq_.emplace_front(std::move(item));
    consumer_cond_.notify_one();
}

template <typename T>
const T& BlockDeque<T>::Front() const noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    assert(!deq_.empty());
    return deq_.front();
}

template <typename T>
const T& BlockDeque<T>::Back() const noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    assert(!deq_.empty());
    return deq_.back();
}

template <typename T>
T& BlockDeque<T>::Front() noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    assert(!deq_.empty());
    return deq_.front();
}

template <typename T>
T& BlockDeque<T>::Back() noexcept {
    std::lock_guard<std::mutex> locker(mtx_);
    assert(!deq_.empty());
    return deq_.back();
}

template <typename T>
std::optional<T> BlockDeque<T>::Pop(
    const std::optional<Clock::duration> time_out) noexcept {
    std::unique_lock<std::mutex> locker(mtx_);
    if (time_out.has_value()) {
        consumer_cond_.wait_for(locker, *time_out, [this](){
            return closed_ || !deq_.empty();
        });
    } else {
        consumer_cond_.wait(locker, [this](){
            return closed_ || !deq_.empty();
        });
    }

    if (closed_ && deq_.empty()) {
        return std::nullopt;
    }

    T item = std::move(deq_.front());
    deq_.pop_front();
    producer_cond_.notify_one();
    return item;
}

template <typename T>
void BlockDeque<T>::WaitForSpace(
    std::unique_lock<std::mutex>& locker) noexcept {
    producer_cond_.wait(locker, [this](){
        return closed_ || deq_.size() < capacity_;
    });
}

}  // namespace ws