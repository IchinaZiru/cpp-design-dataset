# BlockDeque Design Specification

## Overview
This document specifies the design of `BlockDeque`, a thread-safe double-ended queue implementation with bounded capacity. The class provides blocking operations for both producers and consumers, ensuring thread safety through mutexes and condition variables.

## Class Structure

### Template Parameters
- `T`: The type of elements stored in the deque (must be movable)

### Public Members

#### Constructors/Destructor
- `BlockDeque(std::size_t capacity = 1000) noexcept`
  - Creates a new BlockDeque with specified capacity
  - Default capacity is 1000
  - Throws: None
  - Postcondition: Queue is empty and not closed

- `~BlockDeque() noexcept`
  - Destructor that calls Close()
  - Ensures proper cleanup of resources

#### Copy/Move Semantics
- All copy and move operations are deleted (constexpr)
  - `BlockDeque(const BlockDeque&) = delete`
  - `BlockDeque(BlockDeque&&) = delete`
  - `operator=(const BlockDeque&) = delete`
  - `operator=(BlockDeque&&) = delete`

#### State Query Methods
- `bool Empty() const noexcept`
  - Returns true if queue is empty
  - Thread-safe

- `bool Full() const noexcept`
  - Returns true if queue has reached capacity
  - Thread-safe

- `std::size_t Size() const noexcept`
  - Returns current number of elements
  - Thread-safe

- `std::size_t Capacity() const noexcept`
  - Returns maximum capacity
  - Thread-safe

#### Element Access Methods
- `const T& Front() const noexcept`
  - Returns reference to first element
  - Precondition: Queue is not empty
  - Thread-safe

- `const T& Back() const noexcept`
  - Returns reference to last element
  - Precondition: Queue is not empty
  - Thread-safe

- `T& Front() noexcept`
  - Non-const version of Front()
  - Uses const_cast for implementation

- `T& Back() noexcept`
  - Non-const version of Back()
  - Uses const_cast for implementation

#### Modification Methods
- `void PushBack(T item) noexcept`
  - Adds element to end of queue
  - Blocks if queue is full until space becomes available
  - Notifies consumers after insertion
  - Thread-safe

- `void PushFront(T item) noexcept`
  - Adds element to beginning of queue
  - Blocks if queue is full until space becomes available
  - Notifies consumers after insertion
  - Thread-safe

- `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept`
  - Removes and returns first element
  - Parameters:
    - `time_out`: Optional maximum wait time (steady_clock duration)
      - If nullopt, waits indefinitely
      - If specified, returns nullopt if timeout occurs
  - Returns nullopt if queue is closed
  - Notifies producers after removal
  - Thread-safe

- `void Flush() noexcept`
  - Notifies one waiting consumer
  - Useful for waking up consumers when new data is available
  - Thread-safe

#### Management Methods
- `void Clear() noexcept`
  - Removes all elements from queue
  - Does not change closed state
  - Thread-safe

- `void Close() noexcept`
  - Marks queue as closed and clears all elements
  - Notifies all waiting producers and consumers
  - Subsequent Pop operations will return nullopt
  - Thread-safe

### Private Members

#### Data Members
- `mutable std::mutex mtx_`: Mutex for thread synchronization
- `std::atomic_bool closed_`: Flag indicating queue is closed
- `std::size_t capacity_`: Maximum number of elements allowed
- `std::deque<T> deq_`: Underlying storage container
- `std::condition_variable consumer_cond_`: Condition variable for consumers
- `std::condition_variable producer_cond_`: Condition variable for producers

#### Helper Methods
- `void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept`
  - Blocks until space becomes available in the queue
  - Used by PushBack and PushFront
  - Thread-safe (assumes caller holds lock)

- `void ClearNoLock() noexcept`
  - Clears the underlying deque without locking
  - Precondition: Caller must hold mtx_

## Implementation Details

### Thread Safety Guarantees
1. All public methods are thread-safe except where noted
2. Internal state is protected by mtx_
3. Condition variables ensure proper blocking/waking of threads
4. Atomic flag for closed_ state allows lock-free checks in some cases

### Blocking Behavior
- Push operations block when queue is full until space becomes available
- Pop operations block when queue is empty until elements become available or timeout occurs
- Close operation wakes all waiting threads immediately

### Memory Management
- Elements are moved into the deque (using std::move)
- No dynamic memory allocation beyond the underlying deque's requirements
- Destructor ensures proper cleanup via Close()

### Error Handling
- Assertions used for internal consistency checks (debug builds only)
- No exceptions thrown from public interface (noexcept methods)
- Closed state is communicated via return values (std::optional)

## Usage Examples

```cpp
ws::BlockDeque<int> queue(10);

// Producer thread
queue.PushBack(42);
queue.PushFront(10);

// Consumer thread
auto item = queue.Pop();
if (item) {
    // Process item
}

// Close the queue when done
queue.Close();
```

## Design Rationale

1. **Bounded Capacity**: Prevents unbounded memory growth, important for long-running applications
2. **Blocking Operations**: Natural fit for producer-consumer patterns common in concurrent programming
3. **Double-Ended**: Supports both FIFO and FILO access patterns
4. **Thread Safety**: Comprehensive use of mutexes and condition variables ensures safe concurrent access
5. **Move Semantics**: Efficient handling of elements through std::move

## Performance Considerations

1. Lock contention may occur under high contention scenarios
2. Condition variable notifications are optimized to wake only necessary threads
3. Underlying deque provides O(1) complexity for push/pop operations at both ends

This specification provides all necessary information for a complete reimplementation of the BlockDeque class while preserving all target-owned identifiers and contracts.