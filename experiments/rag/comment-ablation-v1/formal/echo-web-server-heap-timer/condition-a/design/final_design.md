# Design Specification for HeapTimer Class

## Overview

This document provides a detailed design specification for the `HeapTimer` class, which is implemented in C++. The `HeapTimer` class manages a collection of timed events using a heap data structure. Each event is associated with a key and has an expiration time. When an event expires, its callback function is invoked.

## Namespace

- **Namespace**: `ws`

## Class: HeapTimer<Key>

### Template Parameter
- **Key**: A type that uniquely identifies each timer entry in the heap.

### Public Types
1. **Clock**
   - Type alias for `std::chrono::steady_clock`.
2. **TimeOutCallback**
   - Type alias for `std::function<void(const Key&)>`. This is a function object that will be called when a timer expires.

### Constructors and Assignment Operators

1. **Constructor**
   ```cpp
   explicit HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept;
   ```
   - Initializes the `HeapTimer` with an optional logger.
   - If no logger is provided, it defaults to the root logger.

2. **Move Constructor and Assignment Operator**
   ```cpp
   HeapTimer(HeapTimer&&) = delete;
   HeapTimer& operator=(HeapTimer&&) = delete;
   ```
   - Deleted to prevent moving of `HeapTimer` objects.

3. **Copy Constructor and Assignment Operator**
   ```cpp
   HeapTimer(const HeapTimer&) = delete;
   HeapTimer& operator=(const HeapTimer&) = delete;
   ```
   - Deleted to prevent copying of `HeapTimer` objects.

### Public Member Functions

1. **Adjust**
   ```cpp
   void Adjust(const Key& key, Clock::duration expiration);
   void Adjust(const Key& key, Clock::time_point expiration);
   ```
   - Adjusts the expiration time for an existing timer identified by `key`.
   - The first overload takes a duration relative to the current time.
   - The second overload takes an absolute expiration time point.

2. **Push**
   ```cpp
   void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept;
   void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept;
   ```
   - Adds a new timer to the heap.
   - The first overload takes a duration relative to the current time.
   - The second overload takes an absolute expiration time point.

3. **Tick**
   ```cpp
   void Tick() noexcept;
   ```
   - Processes all expired timers by invoking their callbacks and removing them from the heap.

4. **Remove**
   ```cpp
   bool Remove(const Key& key) noexcept;
   ```
   - Removes a timer identified by `key` from the heap.
   - Returns `true` if the timer was successfully removed, otherwise `false`.

5. **Invoke**
   ```cpp
   void Invoke(const Key& key);
   ```
   - Manually invokes the callback for a timer identified by `key`.
   - Removes the timer from the heap after invocation.

6. **Pop**
   ```cpp
   Key Pop() noexcept;
   ```
   - Removes and returns the key of the timer that is about to expire next.
   - Assumes the heap is not empty.

7. **Clear**
   ```cpp
   void Clear() noexcept;
   ```
   - Clears all timers from the heap.

8. **Contain**
   ```cpp
   bool Contain(const Key& key) const noexcept;
   ```
   - Checks if a timer identified by `key` exists in the heap.
   - Returns `true` if the timer is found, otherwise `false`.

9. **Empty**
   ```cpp
   bool Empty() const noexcept;
   ```
   - Checks if the heap is empty.
   - Returns `true` if there are no timers, otherwise `false`.

10. **Size**
    ```cpp
    std::size_t Size() const noexcept;
    ```
    - Returns the number of timers currently in the heap.

11. **ToNextTick**
    ```cpp
    Clock::duration ToNextTick() noexcept;
    ```
    - Processes expired timers and returns the duration until the next timer is due to expire.
    - If no timers are left, returns a zero duration.

### Private Types

1. **Node**
   - A struct representing a single timer entry in the heap.
   - Contains:
     - `Key key`: The unique identifier for the timer.
     - `Clock::time_point expiration`: The absolute time when the timer expires.
     - `TimeOutCallback callback`: The function to be called when the timer expires.
   - Methods:
     - `bool Expired() const noexcept;`
       - Checks if the current time is greater than or equal to the expiration time.
     - `void Swap(Node&) noexcept;`
       - Swaps the contents of two nodes.

### Private Member Functions

1. **Adjust**
   ```cpp
   void Adjust(const Key& key, Clock::time_point expiration, std::optional<TimeOutCallback> callback);
   ```
   - Internal function to adjust a timer's expiration time and optionally update its callback.
   - Used by the public `Adjust` functions.

2. **RemoveByIndex**
   ```cpp
   Key RemoveByIndex(std::size_t idx) noexcept;
   ```
   - Removes a timer at a specific index in the heap.
   - Returns the key of the removed timer.

3. **ShiftUp**
   ```cpp
   void ShiftUp(std::size_t idx) noexcept;
   ```
   - Maintains the heap property by shifting a node up from a given index to its correct position.

4. **ShiftDown**
   ```cpp
   void ShiftDown(std::size_t idx) noexcept;
   ```
   - Maintains the heap property by shifting a node down from a given index to its correct position.

5. **ValidIndex**
   ```cpp
   bool ValidIndex(const std::size_t idx) const noexcept;
   ```
   - Checks if an index is within the valid range of the heap.
   - Returns `true` if the index is valid, otherwise `false`.

6. **Parent**
   ```cpp
   std::optional<std::size_t> Parent(std::size_t idx) const noexcept;
   ```
   - Calculates and returns the parent index of a given node index.
   - Returns an empty optional if the node has no parent.

7. **SmallChild**
   ```cpp
   std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept;
   ```
   - Finds and returns the index of the child node with the smallest expiration time for a given node.
   - Returns an empty optional if there are no valid children.

8. **Swap**
   ```cpp
   void Swap(const std::size_t idx1, const std::size_t idx2) noexcept;
   ```
   - Swaps two nodes in the heap and updates their indices in the `key_to_idx_` map.

### Private Member Variables

1. **logger_**
   - A pointer to a logger object used for logging errors.
   
2. **key_to_idx_**
   - An unordered map that maps keys to their corresponding indices in the `nodes_` deque.
   
3. **nodes_**
   - A deque of `Node` objects representing the heap.

## Usage

The `HeapTimer` class is designed to manage a collection of timed events efficiently using a min-heap data structure. Timers can be added, adjusted, and removed as needed. The `Tick` method should be called periodically to process expired timers and invoke their callbacks.

### Example Usage
```cpp
#include "containers/heap_timer.h"
#include <iostream>

int main() {
    ws::HeapTimer<int> timer;

    // Add a timer with key 1 that expires in 5 seconds
    timer.Push(1, std::chrono::seconds(5), [](const int& key) {
        std::cout << "Timer " << key << " expired!" << std::endl;
    });

    // Adjust the expiration time of timer 1 to expire in 3 seconds from now
    timer.Adjust(1, std::chrono::seconds(3));

    // Process timers and invoke callbacks for expired timers
    timer.Tick();

    return 0;
}
```

## Conclusion

This design specification provides a comprehensive overview of the `HeapTimer` class, including its public interface, private implementation details, and usage examples. The class is designed to be efficient and easy to use, making it suitable for managing timed events in various applications.