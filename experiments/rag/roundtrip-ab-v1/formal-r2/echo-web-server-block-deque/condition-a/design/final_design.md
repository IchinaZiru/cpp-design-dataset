# Design Specification for `BlockDeque` Class

## Overview

This document provides a detailed design specification for the `BlockDeque` class, which is a thread-safe double-ended queue with blocking capabilities. The class ensures that operations on the queue are synchronized and can block if necessary until certain conditions are met (e.g., space availability or non-empty state).

## File Information

- **File Path:** `include/containers/block_deque.h`
- **Role:** Complete target-owned implementation/declaration file
- **Replacement Required:** Yes

## Class Definition

### Namespace

The class is defined within the `ws` namespace.

### Template Parameter

- **T**: The type of elements stored in the queue.

### Public Members

#### Constructors and Destructors

1. **Constructor**
   - **Signature:** `explicit BlockDeque(std::size_t capacity = 1000) noexcept;`
   - **Description:** Initializes a new instance of the `BlockDeque` class with a specified maximum capacity.
   - **Parameters:**
     - `capacity`: The maximum number of elements that can be stored in the queue. Defaults to 1000.

2. **Copy Constructor and Assignment Operator**
   - Deleted to prevent copying.

3. **Move Constructor and Move Assignment Operator**
   - Deleted to prevent moving.

4. **Destructor**
   - **Signature:** `~BlockDeque() noexcept;`
   - **Description:** Cleans up resources associated with the queue, including closing it.

#### Methods

1. **Clear**
   - **Signature:** `void Clear() noexcept;`
   - **Description:** Removes all elements from the queue.

2. **Empty**
   - **Signature:** `bool Empty() const noexcept;`
   - **Description:** Checks if the queue is empty.
   - **Returns:** `true` if the queue is empty, otherwise `false`.

3. **Full**
   - **Signature:** `bool Full() const noexcept;`
   - **Description:** Checks if the queue is full.
   - **Returns:** `true` if the queue is full, otherwise `false`.

4. **Size**
   - **Signature:** `std::size_t Size() const noexcept;`
   - **Description:** Returns the number of elements currently in the queue.
   - **Returns:** The size of the queue.

5. **Capacity**
   - **Signature:** `std::size_t Capacity() const noexcept;`
   - **Description:** Returns the maximum capacity of the queue.
   - **Returns:** The capacity of the queue.

6. **PushBack**
   - **Signature:** `void PushBack(T item) noexcept;`
   - **Description:** Adds an element to the end of the queue and notifies a consumer.
   - **Parameters:**
     - `item`: The element to be added.

7. **PushFront**
   - **Signature:** `void PushFront(T item) noexcept;`
   - **Description:** Inserts an element at the beginning of the queue and notifies a consumer.
   - **Parameters:**
     - `item`: The element to be inserted.

8. **Front (const version)**
   - **Signature:** `const T& Front() const noexcept;`
   - **Description:** Accesses the first element in the queue.
   - **Returns:** A constant reference to the first element.
   - **Precondition:** The queue must not be empty.

9. **Back (const version)**
   - **Signature:** `const T& Back() const noexcept;`
   - **Description:** Accesses the last element in the queue.
   - **Returns:** A constant reference to the last element.
   - **Precondition:** The queue must not be empty.

10. **Front (non-const version)**
    - **Signature:** `T& Front() noexcept;`
    - **Description:** Accesses the first element in the queue.
    - **Returns:** A reference to the first element.
    - **Precondition:** The queue must not be empty.

11. **Back (non-const version)**
    - **Signature:** `T& Back() noexcept;`
    - **Description:** Accesses the last element in the queue.
    - **Returns:** A reference to the last element.
    - **Precondition:** The queue must not be empty.

12. **Pop**
    - **Signature:** `std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept;`
    - **Description:** Attempts to remove and return the first element from the queue.
    - **Parameters:**
      - `time_out`: An optional maximum duration to wait for an element. If not provided, the method will block indefinitely until an element is available or the queue is closed.
    - **Returns:** The first element if successful, otherwise `std::nullopt` if a timeout occurs or the queue is closed.

13. **Flush**
    - **Signature:** `void Flush() noexcept;`
    - **Description:** Notifies one consumer that an element is available for processing.

14. **Close**
    - **Signature:** `void Close() noexcept;`
    - **Description:** Clears all elements from the queue and marks it as closed, notifying all waiting threads.

### Private Members

#### Methods

1. **WaitForSpace**
   - **Signature:** `void WaitForSpace(std::unique_lock<std::mutex>& locker) noexcept;`
   - **Description:** Blocks until there is space available in the queue.
   - **Parameters:**
     - `locker`: A unique lock on the internal mutex.

2. **ClearNoLock**
   - **Signature:** `void ClearNoLock() noexcept;`
   - **Description:** Clears all elements from the queue without acquiring a lock (assumes the caller holds the lock).

#### Variables

1. **mtx_**
   - **Type:** `std::mutex`
   - **Description:** A mutex used to synchronize access to the queue.

2. **closed_**
   - **Type:** `std::atomic_bool`
   - **Description:** An atomic boolean indicating whether the queue is closed.

3. **capacity_**
   - **Type:** `std::size_t`
   - **Description:** The maximum capacity of the queue.

4. **deq_**
   - **Type:** `std::deque<T>`
   - **Description:** The underlying container storing elements in the queue.

5. **consumer_cond_**
   - **Type:** `std::condition_variable`
   - **Description:** A condition variable used to notify consumers when an element is available for processing.

6. **producer_cond_**
   - **Type:** `std::condition_variable`
   - **Description:** A condition variable used to notify producers when there is space available in the queue.

## Usage Example

For a detailed usage example, refer to `tests/containers/block_deque_test.cpp`.

## Author Information

- **Authors:**
  - Chen Zhenshuo (chenzs108@outlook.com)
  - Liu Guowen (liu.guowen@outlook.com)

- **GitHub Repository:** [https://github.com/Zhuagenborn](https://github.com/Zhuagenborn)

- **Version:** 1.0

- **Date:** 2022-04-23

## Notes

- The `BlockDeque` class is designed to be thread-safe and can be used in multi-threaded environments.
- Operations that modify the queue (e.g., `PushBack`, `PushFront`) will block if the queue is full until space becomes available or the queue is closed.
- Operations that remove elements from the queue (e.g., `Pop`) will block if the queue is empty until an element is added or the queue is closed.
- The class uses condition variables to efficiently manage waiting and notification between producers and consumers.

This design specification provides all necessary details for another developer to implement the `BlockDeque` class without referencing the original source code.