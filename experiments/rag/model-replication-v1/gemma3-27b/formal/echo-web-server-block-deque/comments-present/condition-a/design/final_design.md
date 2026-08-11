## Design Specification for `BlockDeque`

This document details the design specification for a thread-safe block deque (`BlockDeque`) implemented using a `std::deque` as its underlying storage. This specification is based on the provided C++ header file and aims to enable re-implementation without access to the original source code.

**1. Overview**

The `BlockDeque` class provides a double-ended queue with blocking behavior when full or empty. Producers can block when attempting to add elements to a full queue, and consumers can block when attempting to retrieve elements from an empty queue.  It uses condition variables for signaling between producers and consumers.

**2. Namespace:**

*   `ws`

**3. Class: `BlockDeque<T>`**

*   **Template Parameter:**
    *   `T`: The type of element stored in the deque.

*   **Member Variables (Private):**
    *   `mtx_`: A `std::mutex` to protect access to the internal data structures.  Mutable, as it's used within const methods via `const_cast`.
    *   `closed_`: An `std::atomic_bool` indicating whether the queue is closed (no more elements will be added). Initialized to `false`.
    *   `capacity_`: A `std::size_t` representing the maximum capacity of the deque.  Initialized in the constructor and remains constant throughout the object's lifetime.
    *   `deq_`: A `std::deque<T>` used as the underlying storage for the elements.
    *   `consumer_cond_`: A `std::condition_variable` to signal consumers when an element becomes available.
    *   `producer_cond_`: A `std::condition_variable` to signal producers when space becomes available.

**4. Constructors & Destructor:**

*   `BlockDeque(std::size_t capacity = 1000) noexcept;`
    *   Initializes the `capacity_` member variable with the provided `capacity`.  Asserts that `capacity > 0`.
*   `BlockDeque(const BlockDeque&) = delete;`
    *   Copy constructor is deleted.
*   `BlockDeque(BlockDeque&&) = delete;`
    *   Move constructor is deleted.
*   `BlockDeque& operator=(const BlockDeque&) = delete;`
    *   Copy assignment operator is deleted.
*   `BlockDeque& operator=(BlockDeque&&) = delete;`
    *   Move assignment operator is deleted.
*   `~BlockDeque() noexcept;`
    *   Calls `Close()` to clear the queue and signal any waiting threads before destruction.

**5. Public Methods:**

*   `void Clear() noexcept;`
    *   Acquires a lock on `mtx_`.
    *   Clears all elements from the underlying `deq_`.
*   `bool Empty() const noexcept;`
    *   Acquires a lock on `mtx_`.
    *   Returns `true` if the deque is empty, `false` otherwise.
*   `bool Full() const noexcept;`
    *   Acquires a lock on `mtx_`.
    *   Returns `true` if the deque is full (size equals capacity), `false` otherwise.  Asserts that size <= capacity_.
*   `std::size_t Size() const noexcept;`
    *   Acquires a lock on `mtx_`.
    *   Returns the number of elements currently in the deque.
*   `std::size_t Capacity() const noexcept;`
    *   Returns the maximum capacity of the deque (initialized in constructor).
*   `void PushBack(T item) noexcept;`
    *   Acquires a `std::unique_lock` on `mtx_`.
    *   Calls `WaitForSpace()` to block if the queue is full.
    *   Adds the provided `item` to the back of the underlying `deq_` using `push_back()`.  The item should be moved into the deque.
    *   Calls `Flush()` to notify a consumer.
*   `void PushFront(T item) noexcept;`
    *   Acquires a `std::unique_lock` on `mtx_`.
    *   Calls `WaitForSpace()` to block if the queue is full.
    *   Adds the provided `item` to the front of the underlying `deq_` using `push_front()`. The item should be moved into the deque.
    *   Calls `Flush()` to notify a consumer.
*   `const T& Front() const noexcept;`
    *   Acquires a lock on `mtx_`.
    *   Asserts that the queue is not empty.
    *   Returns a constant reference to the first element in the deque.
*   `const T& Back() const noexcept;`
    *   Acquires a lock on `mtx_`.
    *   Asserts that the queue is not empty.
    *   Returns a constant reference to the last element in the deque.
*   `T& Front() noexcept;`
    *   Calls `const_cast<T&>(std::as_const(*this).Front())`.  Provides non-const access to the front element.
*   `T& Back() noexcept;`
    *   Calls `const_cast<T&>(std::as_const(*this).Back())`. Provides non-const access to the back element.
*   `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept;`
    *   Acquires a `std::unique_lock` on `mtx_`.
    *   If `time_out` is provided:
        *   Waits on `consumer_cond_` for up to the specified `time_out`, checking if the queue is not empty or closed.  Returns `std::nullopt` if the timeout expires before an element becomes available.
    *   Otherwise (if `time_out` is `std::nullopt`):
        *   Waits indefinitely on `consumer_cond_` until the queue is not empty or closed.
    *   If the queue is closed, returns `std::nullopt`.
    *   Otherwise:
        *   Retrieves the first element from the deque using `deq_.front()`.
        *   Removes the first element from the deque using `deq_.pop_front()`.
        *   Notifies a producer via `producer_cond_.notify_one()`.
        *   Returns the retrieved element wrapped in `std::optional<T>`.
*   `void Flush() noexcept;`
    *   Notifies one waiting consumer on `consumer_cond_`.
*   `void Close() noexcept;`
    *   Acquires a lock on `mtx_`.
    *   Calls `ClearNoLock()` to clear the deque.
    *   Sets `closed_` to `true`.
    *   Notifies all waiting producers and consumers via `producer_cond_.notify_all()` and `consumer_cond_.notify_all()`.

**6. Private Methods:**

*   `void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept;`
    *   Waits on `producer_cond_` until the deque has space available (size < capacity).
*   `void ClearNoLock() noexcept;`
    *   Clears all elements from the underlying `deq_`.  This method is intended to be called while holding a lock.

**7. Type Definitions:**

*   `using Clock = std::chrono::steady_clock;` Defines a clock type for time durations.

**8. Thread Safety:**

The `BlockDeque` class is designed to be thread-safe by using a mutex (`mtx_`) and condition variables (`consumer_cond_`, `producer_cond_`) to synchronize access to the underlying data structures.  All public methods acquire appropriate locks before accessing shared resources.
