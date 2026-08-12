# BlockDeque Design Specification

## Overview
The `BlockDeque` is a thread-safe, bounded double-ended queue (deque) implementation that supports both producer and consumer operations with blocking behavior when the container is full or empty. It uses condition variables to coordinate between producers and consumers.

## Class Structure

### Template Parameters
- `T`: The type of elements stored in the deque

### Public Members

#### Types
- `Clock`: Alias for `std::chrono::steady_clock` used for timeout specifications

#### Constructors/Destructor
- `BlockDeque(std::size_t capacity = 1000) noexcept`
  - Creates a new BlockDeque with specified capacity (default: 1000)
  - Throws: None
  - Postcondition: The deque is empty and not closed

- `~BlockDeque() noexcept`
  - Destructor that ensures proper cleanup
  - Calls `Close()` to clean up resources

#### Copy/Move Semantics
- All copy and move operations are deleted (not allowed)

#### Public Methods

##### Capacity Management
- `void Clear() noexcept`
  - Removes all elements from the deque
  - Thread-safe: acquires mutex lock

- `bool Empty() const noexcept`
  - Returns true if the deque is empty
  - Thread-safe: acquires mutex lock

- `bool Full() const noexcept`
  - Returns true if the deque has reached capacity
  - Thread-safe: acquires mutex lock

- `std::size_t Size() const noexcept`
  - Returns current number of elements in deque
  - Thread-safe: acquires mutex lock

- `std::size_t Capacity() const noexcept`
  - Returns maximum capacity of the deque
  - Thread-safe: no lock needed (read-only atomic operation)

##### Element Access
- `const T& Front() const noexcept`
  - Returns reference to first element
  - Thread-safe: acquires mutex lock
  - Precondition: Deque is not empty

- `const T& Back() const noexcept`
  - Returns reference to last element
  - Thread-safe: acquires mutex lock
  - Precondition: Deque is not empty

- `T& Front() noexcept`
  - Non-const version of Front()
  - Uses const_cast for convenience

- `T& Back() noexcept`
  - Non-const version of Back()
  - Uses const_cast for convenience

##### Modification Operations
- `void PushBack(T item) noexcept`
  - Adds element to the end of deque
  - Thread-safe: acquires mutex lock
  - Blocks if deque is full until space becomes available
  - Moves the item into the deque

- `void PushFront(T item) noexcept`
  - Adds element to the front of deque
  - Thread-safe: acquires mutex lock
  - Blocks if deque is full until space becomes available
  - Moves the item into the deque

- `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept`
  - Removes and returns first element
  - Thread-safe: acquires mutex lock
  - If timeout is specified, waits up to that duration for an element
  - Returns nullopt if:
    - Timeout occurs before element available
    - Deque is closed
  - Notifies producer when space becomes available

- `void Flush() noexcept`
  - Notifies one waiting consumer (if any)
  - Used internally after push operations

- `void Close() noexcept`
  - Closes the deque, preventing further pushes
  - Clears all elements and notifies all waiting threads
  - Thread-safe: acquires mutex lock

### Private Members

#### Methods
- `void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept`
  - Blocks until space is available in the deque
  - Uses producer condition variable for waiting

- `void ClearNoLock() noexcept`
  - Clears the underlying deque without acquiring lock
  - Used by methods that already hold the lock

#### Data Members
- `mutable std::mutex mtx_`: Mutex for thread synchronization
- `std::atomic_bool closed_`: Flag indicating if deque is closed
- `std::size_t capacity_`: Maximum number of elements allowed
- `std::deque<T> deq_`: Underlying storage container
- `std::condition_variable consumer_cond_`: Condition variable for consumers waiting on elements
- `std::condition_variable producer_cond_`: Condition variable for producers waiting on space

## Thread Safety Guarantees

1. All public methods are thread-safe except where noted otherwise
2. The mutex is held during all operations that modify or read the deque state
3. Condition variables coordinate between producers and consumers:
   - `producer_cond_` signals when space becomes available
   - `consumer_cond_` signals when elements become available

## Behavior Specifications

### Blocking Behavior
- `PushBack`/`PushFront`: Block if deque is full until space becomes available or deque is closed
- `Pop`: Block if deque is empty until element becomes available, timeout occurs, or deque is closed

### Closure Semantics
When `Close()` is called:
1. All elements are removed from the deque
2. The `closed_` flag is set to true
3. All waiting producers and consumers are notified
4. Subsequent push operations will not block but will return immediately (though behavior isn't specified for this case)

### Timeout Handling
- When a timeout is specified in `Pop()`, the method returns `std::nullopt` if:
  - The timeout period elapses before an element becomes available
  - The deque is closed during the wait

## Implementation Notes

1. The implementation uses move semantics (`std::move`) for push operations to avoid unnecessary copies
2. The underlying container is a standard `std::deque`
3. Assertions are used to verify internal invariants (e.g., size <= capacity)
4. The destructor ensures proper cleanup by calling `Close()`

## Error Handling

The class uses assertions to verify internal consistency:
- Capacity must be > 0 in constructor
- Size must not exceed capacity when checking Full()
- Deque must not be empty when accessing Front()/Back()

No exceptions are thrown from public methods (all marked noexcept)

## Usage Example

```cpp
ws::BlockDeque<int> deque(10);

// Producer thread
deque.PushBack(42);

// Consumer thread
auto item = deque.Pop();
if (item) {
    // Process item
}

// Close when done
deque.Close();
```

This specification provides all necessary information for another LLM to implement an equivalent `BlockDeque` class while preserving the original interface and behavior.