## Design Specification for `BlockDeque` (F01/U01)

This document details the design specification for the `BlockDeque` class, based on the provided C++ source code.  It is intended to guide a re-implementation of this class by another LLM.

**1. Overview**

The `BlockDeque` class implements a thread-safe bounded deque (double-ended queue). It provides methods for adding and removing elements from both ends, with optional blocking behavior when the queue is full or empty.  It uses a standard `std::deque` internally to store the data and utilizes mutexes and condition variables for synchronization.

**2. Namespaces**

*   `ws`: All code related to `BlockDeque` resides within the `ws` namespace.

**3. Class Definition: `BlockDeque<T>`**

*   **Template Parameter:**  `T` - The type of element stored in the deque.
*   **Inheritance:** None.

**4. Member Variables (Private)**

*   `mtx_`: A `std::mutex` used to protect access to the internal data structures.  Mutable, as it's locked within methods that don't claim const-ness.
*   `closed_`: An `std::atomic_bool` indicating whether the deque is closed (no more elements will be added). Initialized to `false`.
*   `capacity_`: A `std::size_t` representing the maximum number of elements the deque can hold.  Initialized in the constructor and remains constant throughout the object's lifetime.
*   `deq_`: A `std::deque<T>` used as the underlying storage for the deque’s elements.
*   `consumer_cond_`: A `std::condition_variable` used to signal consumers (popping threads) that an element is available.
*   `producer_cond_`: A `std::condition_variable` used to signal producers (pushing threads) that space is available.

**5. Constructors and Destructor**

*   `BlockDeque(const std::size_t capacity = 1000) noexcept;`
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
    *   Calls `Close()` to ensure proper cleanup before destruction.

**6. Public Methods**

*   `void Clear() noexcept;`
    *   Clears the contents of the deque by calling `ClearNoLock()` under a lock.
*   `bool Empty() const noexcept;`
    *   Returns `true` if the deque is empty, `false` otherwise.  Uses a `std::lock_guard`.
*   `bool Full() const noexcept;`
    *   Returns `true` if the deque is full (reached its capacity), `false` otherwise. Uses a `std::lock_guard`. Asserts that the current size does not exceed the capacity before checking for fullness.
*   `std::size_t Size() const noexcept;`
    *   Returns the number of elements currently in the deque.  Uses a `std::lock_guard`.
*   `std::size_t Capacity() const noexcept;`
    *   Returns the maximum capacity of the deque (the value passed to the constructor).
*   `void PushBack(T item) noexcept;`
    *   Adds an element to the back of the deque.  Blocks if the deque is full until space becomes available, using `WaitForSpace()`. Uses a `std::unique_lock`. Notifies consumers via `Flush()` after adding the element. Moves the input `item` into the deque.
*   `void PushFront(T item) noexcept;`
    *   Adds an element to the front of the deque. Blocks if the deque is full until space becomes available, using `WaitForSpace()`. Uses a `std::unique_lock`. Notifies consumers via `Flush()` after adding the element. Moves the input `item` into the deque.
*   `const T& Front() const noexcept;`
    *   Returns a constant reference to the element at the front of the deque. Asserts that the deque is not empty before returning the element. Uses a `std::lock_guard`.
*   `const T& Back() const noexcept;`
    *   Returns a constant reference to the element at the back of the deque. Asserts that the deque is not empty before returning the element. Uses a `std::lock_guard`.
*   `T& Front() noexcept;`
    *   Returns a non-constant reference to the element at the front of the deque.  Uses `const_cast` to cast away constness from the result of calling `Front() const`.
*   `T& Back() noexcept;`
    *   Returns a non-constant reference to the element at the back of the deque. Uses `const_cast` to cast away constness from the result of calling `Back() const`.
*   `std::optional<T> Pop(const std::optional<Clock::duration> time_out = std::nullopt) noexcept;`
    *   Removes and returns an element from the front of the deque.
        *   If `time_out` is provided, blocks for up to that duration waiting for an element to become available. Returns `std::nullopt` if the timeout expires before an element becomes available or if the queue is closed.
        *   If `time_out` is not provided, blocks indefinitely until an element becomes available or the deque is closed.  Returns `std::nullopt` if the deque is closed.
        *   Notifies producers via `producer_cond_.notify_one()` after removing an element. Uses a `std::unique_lock`.
*   `void Flush() noexcept;`
    *   Notifies one waiting consumer thread that an element may be available.
*   `void Close() noexcept;`
    *   Closes the deque, preventing further additions. Clears the internal data using `ClearNoLock()`, sets `closed_` to `true`, and notifies all waiting producers and consumers.

**7. Private Methods**

*   `void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept;`
    *   Blocks until there is space available in the deque (i.e., the size is less than the capacity). Uses `producer_cond_.wait()` with a predicate to check for available space.  Takes a `std::unique_lock` as an argument, which it uses during the wait operation.
*   `void ClearNoLock() noexcept;`
    *   Clears the contents of the internal `deq_` without acquiring any locks. This method is intended to be called from within locked sections (e.g., `Clear()` and `Close()`).

**8.  Thread Safety**

The class is designed to be thread-safe, using a mutex (`mtx_`) to protect access to the internal data structures and condition variables (`consumer_cond_`, `producer_cond_`) to signal between threads. All public methods are either `noexcept` or handle potential exceptions internally by acquiring appropriate locks.

**9.  Error Handling/Assertions**

*   The constructor asserts that the initial capacity is greater than 0.
*   `Front()` and `Back()` assert that the deque is not empty before accessing elements.
*   `Full()` asserts that the size does not exceed the capacity.

**10. Clock Type**

*   Uses `std::chrono::steady_clock` for timing operations in `Pop()`.  This clock is monotonic and suitable for measuring durations.
