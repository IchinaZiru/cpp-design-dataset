# HeapTimer Design Specification

## Overview
This document provides a detailed specification for the `HeapTimer` class, a timer system based on a min-heap. The implementation maintains timers ordered by expiration time and invokes callbacks when timers expire.

## Class Structure

### Template Parameters
- `Key`: Type of node keys (user-defined unique identifier)

### Public Members

#### Types
```cpp
using Clock = std::chrono::steady_clock;
using TimeOutCallback = std::function<void(const Key&)>;
```

#### Constructor
```cpp
explicit HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept;
```
- Creates a timer system with optional logger (defaults to root logger)
- Logger is moved into the object if provided

#### Methods

1. **Adjust**
   ```cpp
   void Adjust(const Key& key, Clock::duration expiration);
   void Adjust(const Key& key, Clock::time_point expiration);
   ```
   - Updates a node's expiration time
   - Throws `std::out_of_range` if key doesn't exist
   - First version converts duration to time point (now + duration)

2. **Push**
   ```cpp
   void Push(const Key& key, Clock::duration expiration,
             TimeOutCallback callback) noexcept;
   void Push(const Key& key, Clock::time_point expiration,
             TimeOutCallback callback) noexcept;
   ```
   - Adds a new timer or updates existing one with same key
   - First version converts duration to time point

3. **Tick**
   ```cpp
   void Tick() noexcept;
   ```
   - Processes all expired timers (invokes callbacks)
   - Catches and logs exceptions from callbacks

4. **Remove**
   ```cpp
   bool Remove(const Key& key) noexcept;
   ```
   - Removes timer without invoking callback
   - Returns true if removal occurred

5. **Invoke**
   ```cpp
   void Invoke(const Key& key);
   ```
   - Removes timer and invokes its callback immediately
   - Throws `std::out_of_range` if key doesn't exist

6. **Pop**
   ```cpp
   Key Pop() noexcept;
   ```
   - Removes and returns the next-to-expire timer's key
   - Undefined behavior if empty (assertion)

7. **Clear**
   ```cpp
   void Clear() noexcept;
   ```
   - Removes all timers

8. **Contain**
   ```cpp
   bool Contain(const Key& key) const noexcept;
   ```
   - Checks if timer with given key exists

9. **Empty**
   ```cpp
   bool Empty() const noexcept;
   ```
   - Returns true if no timers exist

10. **Size**
    ```cpp
    std::size_t Size() const noexcept;
    ```
    - Returns number of timers

11. **ToNextTick**
    ```cpp
    Clock::duration ToNextTick() noexcept;
    ```
    - Processes expired timers then returns time until next expiration
    - Returns zero duration if no timers or all expired

### Private Members

#### Node Structure
```cpp
struct Node {
    Key key;
    Clock::time_point expiration;
    TimeOutCallback callback;

    bool Expired() const noexcept;
    void Swap(Node&) noexcept;
    friend std::weak_ordering operator<=>(const Node&, const Node&) noexcept;
};
```
- `Expired()`: Returns true if current time >= expiration
- `Swap()`: Exchanges contents with another node
- Comparison based on expiration time

#### Data Members
```cpp
log::Logger::Ptr logger_;
std::unordered_map<Key, std::size_t> key_to_idx_;
std::deque<Node> nodes_;
```

#### Private Methods

1. **Heap Operations**
   ```cpp
   void ShiftUp(std::size_t idx) noexcept;
   void ShiftDown(std::size_t idx) noexcept;
   ```
   - Maintain heap property after insertion/removal
   - `ShiftUp`: Moves node up until parent is smaller
   - `ShiftDown`: Moves node down until children are larger

2. **Helper Methods**
   ```cpp
   void Swap(std::size_t idx1, std::size_t idx2) noexcept;
   bool ValidIndex(std::size_t idx) const noexcept;
   std::optional<std::size_t> Parent(std::size_t idx) const noexcept;
   std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept;
   ```
   - `Swap`: Exchanges two nodes and updates index map
   - `ValidIndex`: Checks if index is within bounds
   - `Parent`: Returns parent index or nullopt
   - `SmallChild`: Returns smaller child index or nullopt

3. **Internal Adjust**
   ```cpp
   void Adjust(const Key& key, Clock::time_point expiration,
               std::optional<TimeOutCallback> callback);
   ```
   - Core adjustment logic with optional callback update

4. **RemoveByIndex**
   ```cpp
   Key RemoveByIndex(std::size_t idx) noexcept;
   ```
   - Removes node at index and returns its key
   - Uses special removal technique (assign min value, shift up)

## Implementation Details

### Heap Structure
- Min-heap based on expiration time
- Nodes stored in deque for efficient removal from middle
- Index map provides O(1) key-to-index lookup

### Timer Processing
1. `Tick()` processes all expired timers at once
2. Callbacks are invoked with the timer's key
3. Exceptions in callbacks are caught and logged

### Removal Strategy
- Special technique for efficient removal:
  1. Assign minimum value to target node
  2. Shift up to move to root
  3. Swap with last element
  4. Remove last element
  5. Shift down new root

## Error Handling
- Exceptions from callbacks are caught and logged
- Invalid operations throw appropriate exceptions:
  - `std::out_of_range` for missing keys
  - Assertions for invalid internal states

## Thread Safety
- Not thread-safe (no synchronization mechanisms)
- Caller must ensure proper synchronization if used in multi-threaded context

## Performance Characteristics
- O(log n) for insert, remove, adjust operations
- O(1) for empty/size checks
- O(n log n) worst-case for Tick() when all timers expire

This specification provides all necessary information to reimplement the `HeapTimer` class while preserving its behavior and interface.