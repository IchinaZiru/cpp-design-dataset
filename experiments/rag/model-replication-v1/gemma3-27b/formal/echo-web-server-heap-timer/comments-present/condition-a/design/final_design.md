## Design Specification for HeapTimer (F01/U01)

This document details the design of a `HeapTimer` class, based on the provided C++ source code. It is intended to be used by another LLM to re-implement this functionality without access to the original source.  The specification focuses solely on the content within the `===== BEGIN F01/U01 =====` and `===== END F01/U01 =====` markers.

**1. Overview**

The `HeapTimer` class implements a timer system based on a min-heap data structure. It allows users to schedule tasks (callbacks) to be executed at specific points in time.  Timers are stored in the heap, ordered by their expiration time. The `Tick()` method removes and executes expired timers.

**2. Namespaces & Includes**

*   **Namespace:** `ws`
*   **Includes:**
    *   `log.h`: For logging functionality (assumed to exist).  The logger is used for error reporting within callbacks.
    *   `util.h`: For utility functions (assumed to exist, not detailed in the provided code).
    *   `<algorithm>`: Standard algorithm library.
    *   `<cassert>`: Assertions for debugging.
    *   `<chrono>`: Time-related functionalities.
    *   `<compare>`:  For `<=>` operator (comparison operators).
    *   `<deque>`: Double-ended queue used as the underlying heap storage.
    *   `<functional>`: For `std::function`.
    *   `<optional>`: For optional values (`std::optional`).
    *   `<stdexcept>`: Standard exception library.
    *   `<unordered_map>`: Unordered map for key-to-index mapping.

**3. Class Definition: `HeapTimer<Key>`**

A template class parameterized by the type of the timer key (`Key`).

**4. Type Definitions (within `HeapTimer<Key>`)**

*   `Clock`:  Alias for `std::chrono::steady_clock`.
*   `TimeOutCallback`: Alias for `std::function<void(const Key&)>`. This represents a callback function that takes a constant reference to the key as input and returns void.

**5. Member Variables (Private)**

*   `logger_`: A pointer to a `log::Logger` object used for logging errors.  Defaults to the root logger if not provided during construction.
*   `key_to_idx_`: An `std::unordered_map<Key, std::size_t>` that maps timer keys to their corresponding indices in the `nodes_` deque.
*   `nodes_`: A `std::deque<Node>` representing the min-heap of timers.

**6. Nested Structure: `Node` (Private)**

Represents a single timer node within the heap.

*   `key`: The user-defined key for the timer (`Key` type).
*   `expiration`: A `Clock::time_point` representing the time at which the timer expires.
*   `callback`: A `TimeOutCallback` function to be executed when the timer expires.
*   `Expired()`:  A `noexcept` method that returns `true` if the current time is greater than or equal to the `expiration` time, and `false` otherwise.
*   `Swap(Node&)`: A `noexcept` method that swaps the contents of two `Node` objects.

**7. Public Methods**

*   **`HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept;`**: Constructor. Initializes the `logger_`. If a null logger is provided, it defaults to the root logger.
*   **`HeapTimer(HeapTimer&&) = delete;`**, **`HeapTimer& operator=(HeapTimer&&) = delete;`**, **`HeapTimer(const HeapTimer&) = delete;`**, **`HeapTimer& operator=(const HeapTimer&) = delete;`**: Deleted copy constructor and assignment operators.  The class is not copyable.
*   **`void Adjust(const Key& key, Clock::duration expiration);`**: Adjusts the expiration time of a timer identified by `key`. The duration is added to the current time to calculate the new absolute expiration time. Throws `std::out_of_range` if the key doesn't exist.
*   **`void Adjust(const Key& key, Clock::time_point expiration);`**: Adjusts the expiration time of a timer identified by `key`.  Throws `std::out_of_range` if the key doesn't exist.
*   **`void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept;`**: Adds a new timer to the heap with the given `key`, relative `expiration` (added to current time), and `callback`.  Does not throw exceptions. If the key already exists, it adjusts the existing timer's expiration and callback.
*   **`void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept;`**: Adds a new timer to the heap with the given `key`, absolute `expiration`, and `callback`. Does not throw exceptions. If the key already exists, it adjusts the existing timer's expiration and callback.
*   **`void Tick() noexcept;`**: Removes expired timers from the heap and executes their callbacks.  Exceptions thrown by callbacks are caught, logged (using `logger_`), but *not* rethrown.
*   **`bool Remove(const Key& key) noexcept;`**: Removes a timer identified by `key`. Returns `true` if the timer was removed successfully, `false` otherwise. Does not throw exceptions.
*   **`void Invoke(const Key& key);`**:  Removes a timer identified by `key` and immediately invokes its callback function. Throws `std::out_of_range` if the key doesn't exist. Exceptions thrown by callbacks are caught, logged (using `logger_`), but *not* rethrown.
*   **`Key Pop() noexcept;`**: Removes and returns the key of the timer with the earliest expiration time (the top element of the heap).  Asserts that the heap is not empty before proceeding. Does not throw exceptions.
*   **`void Clear() noexcept;`**: Removes all timers from the heap, clearing both `nodes_` and `key_to_idx_`.
*   **`bool Contain(const Key& key) const noexcept;`**: Returns `true` if a timer with the given `key` exists in the heap, `false` otherwise.
*   **`bool Empty() const noexcept;`**: Returns `true` if the heap is empty, `false` otherwise.  Asserts that `nodes_.empty()` and `key_to_idx_.empty()` have the same value.
*   **`std::size_t Size() const noexcept;`**: Returns the number of timers in the heap. Asserts that `nodes_.size()` and `key_to_idx_.size()` are equal.
*   **`Clock::duration ToNextTick() noexcept;`**: Removes expired timers (like `Tick()`) and then returns the time remaining until the next timer expires. If the heap is empty, it returns a zero duration.

**8. Private Helper Methods**

*   **`void Swap(std::size_t idx1, std::size_t idx2) noexcept;`**: Swaps two nodes in the `nodes_` deque and updates their corresponding entries in `key_to_idx_`.
*   **`void Adjust(const Key& key, Clock::time_point expiration, std::optional<TimeOutCallback> callback);`**: Internal helper function to adjust a timer's expiration time and optionally its callback.  Throws `std::out_of_range` if the key doesn't exist.
*   **`Key RemoveByIndex(std::size_t idx) noexcept;`**: Removes the node at the given index from the heap, updates `key_to_idx_`, and returns the removed node’s key.  Handles the case where there is only one element in the heap.
*   **`void ShiftUp(std::size_t idx) noexcept;`**: Moves a node up the heap (towards the root) until it reaches its correct position based on expiration time.
*   **`void ShiftDown(std::size_t idx) noexcept;`**: Moves a node down the heap (towards the leaves) until it reaches its correct position based on expiration time.
*   **`bool ValidIndex(std::size_t idx) const noexcept;`**: Checks if an index is within the bounds of the `nodes_` deque.
*   **`std::optional<std::size_t> Parent(std::size_t idx) const noexcept;`**: Returns the index of the parent node, or `std::nullopt` if the node has no parent (is the root).
*   **`std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept;`**: Returns the index of the child with the smallest expiration time, or `std::nullopt` if the node has no children.

**9. Comparison Operator Overload (within Node struct)**

*   `friend std::weak_ordering operator<=>(const Node& lhs, const Node& rhs) noexcept`: Defines a three-way comparison operator for `Node` objects based on their `expiration` time. This is used to maintain the min-heap property.
