### Design Specification for `BlockDeque` Class

#### Overview
The `BlockDeque` class is a thread-safe double-ended queue (deque) implementation that supports blocking operations with optional timeouts. It ensures that multiple threads can safely push and pop elements from either end of the deque without causing data races.

#### Namespace
- **Namespace**: `ws`

#### Template Parameter
- **T**: The type of elements stored in the deque.

#### Class Definition

```cpp
template <typename T>
class BlockDeque {
public:
    using Clock = std::chrono::steady_clock;

    // Constructors and Destructors
    explicit BlockDeque(std::size_t capacity = 1000) noexcept;
    BlockDeque(const BlockDeque&) = delete;
    BlockDeque(BlockDeque&&) = delete;
    BlockDeque& operator=(const BlockDeque&) = delete;
    BlockDeque& operator=(BlockDeque&&) = delete;
    ~BlockDeque() noexcept;

    // Public Methods
    void Clear() noexcept;
    bool Empty() const noexcept;
    bool Full() const noexcept;
    std::size_t Size() const noexcept;
    std::size_t Capacity() const noexcept;
    void PushBack(T item) noexcept;
    void PushFront(T item) noexcept;
    const T& Front() const noexcept;
    const T& Back() const noexcept;
    T& Front() noexcept;
    T& Back() noexcept;
    std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept;
    void Flush() noexcept;
    void Close() noexcept;

private:
    // Private Methods
    void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept;
    void ClearNoLock() noexcept;

    // Member Variables
    mutable std::mutex mtx_;
    std::atomic_bool closed_ {false};
    std::size_t capacity_;

    std::deque<T> deq_;

    std::condition_variable consumer_cond_;
    std::condition_variable producer_cond_;
};
```

#### Detailed Method Descriptions

1. **Constructors and Destructors**
   - `explicit BlockDeque(std::size_t capacity = 1000) noexcept`: Initializes the deque with a specified capacity.
     - **Parameters**: 
       - `capacity`: The maximum number of elements that can be stored in the deque.
     - **Preconditions**: `capacity > 0`.
   - `BlockDeque(const BlockDeque&) = delete;`: Deleted copy constructor to prevent copying.
   - `BlockDeque(BlockDeque&&) = delete;`: Deleted move constructor to prevent moving.
   - `BlockDeque& operator=(const BlockDeque&) = delete;`: Deleted copy assignment operator to prevent copying.
   - `BlockDeque& operator=(BlockDeque&&) = delete;`: Deleted move assignment operator to prevent moving.
   - `~BlockDeque() noexcept;`: Destructor that closes the deque and cleans up resources.

2. **Public Methods**
   - `void Clear() noexcept;`: Clears all elements from the deque.
   - `bool Empty() const noexcept;`: Checks if the deque is empty.
     - **Returns**: `true` if the deque is empty, otherwise `false`.
   - `bool Full() const noexcept;`: Checks if the deque is full.
     - **Returns**: `true` if the deque is full, otherwise `false`.
   - `std::size_t Size() const noexcept;`: Returns the current number of elements in the deque.
   - `std::size_t Capacity() const noexcept;`: Returns the maximum capacity of the deque.
   - `void PushBack(T item) noexcept;`: Adds an element to the back of the deque, blocking if necessary until space is available.
     - **Parameters**: 
       - `item`: The element to be added.
   - `void PushFront(T item) noexcept;`: Adds an element to the front of the deque, blocking if necessary until space is available.
     - **Parameters**: 
       - `item`: The element to be added.
   - `const T& Front() const noexcept;`: Returns a reference to the first element in the deque.
     - **Preconditions**: Deque must not be empty.
   - `const T& Back() const noexcept;`: Returns a reference to the last element in the deque.
     - **Preconditions**: Deque must not be empty.
   - `T& Front() noexcept;`: Returns a modifiable reference to the first element in the deque.
     - **Preconditions**: Deque must not be empty.
   - `T& Back() noexcept;`: Returns a modifiable reference to the last element in the deque.
     - **Preconditions**: Deque must not be empty.
   - `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept;`: Removes and returns an element from the front of the deque, blocking if necessary until an element is available or a timeout occurs.
     - **Parameters**: 
       - `time_out`: Optional duration to wait for an element. If not provided, waits indefinitely.
     - **Returns**: The removed element wrapped in `std::optional<T>`, or `std::nullopt` if the deque was closed or timed out.
   - `void Flush() noexcept;`: Notifies one waiting consumer that an element is available.
   - `void Close() noexcept;`: Closes the deque, preventing further operations and notifying all waiting threads.

3. **Private Methods**
   - `void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept;`: Waits until there is space in the deque for a new element.
     - **Parameters**: 
       - `locker`: A unique lock on the internal mutex.
   - `void ClearNoLock() noexcept;`: Clears all elements from the deque without acquiring the lock.

#### Member Variables
- `mutable std::mutex mtx_`: Mutex used to synchronize access to the deque.
- `std::atomic_bool closed_ {false}`: Atomic boolean flag indicating whether the deque is closed.
- `std::size_t capacity_`: The maximum number of elements that can be stored in the deque.
- `std::deque<T> deq_`: The underlying container storing the elements.
- `std::condition_variable consumer_cond_`: Condition variable used to notify waiting consumers.
- `std::condition_variable producer_cond_`: Condition variable used to notify waiting producers.

#### Usage Notes
- The `BlockDeque` class is designed for use in multi-threaded environments where multiple threads may push and pop elements concurrently.
- The `PushBack`, `PushFront`, and `Pop` methods are blocking operations that will wait until the operation can be performed or a timeout occurs.
- The `Close` method should be called to properly shut down the deque, which will notify all waiting threads and prevent further operations.

#### Assumptions
- The provided capacity is greater than zero.
- The `T` type must support move semantics for efficient element management.

This design specification provides a comprehensive overview of the `BlockDeque` class, including its interface, behavior, and internal workings. It ensures that another developer can accurately reimplement this class without needing to refer to the original source code.