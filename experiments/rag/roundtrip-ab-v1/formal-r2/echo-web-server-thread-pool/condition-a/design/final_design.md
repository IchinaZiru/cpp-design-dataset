# Design Specification for Thread Pool Implementation

## Overview

This document provides a detailed design specification for the `ThreadPool` class, which is part of a larger software system. The `ThreadPool` class manages a pool of threads to execute tasks concurrently. This specification covers both the declaration and implementation aspects of the `ThreadPool` class.

## Target Audience

- Developers responsible for implementing or maintaining the `ThreadPool` class.
- Other stakeholders involved in the development process who need an understanding of the `ThreadPool` functionality and design.

## File Structure

The `ThreadPool` class is defined across two files:

1. **Header File (`thread_pool.h`)**: Contains the declaration of the `ThreadPool` class, including its public interface and private members.
2. **Source File (`thread_pool.cpp`)**: Contains the implementation of the methods declared in `thread_pool.h`.

## Namespaces

- All classes and functions are encapsulated within the `ws` namespace.

## Dependencies

The `ThreadPool` class depends on the following external libraries:

- `<condition_variable>`
- `<functional>`
- `<list>`
- `<mutex>`
- `<optional>`
- `<thread>`

Additionally, it uses a custom logging library (`log.h`) and utility functions (`util.h`).

## Class Declaration: `ThreadPool`

### File Path

`include/containers/thread_pool.h`

### Purpose

The `ThreadPool` class manages a pool of threads to execute tasks concurrently. It provides methods to start the thread pool, push tasks into it, and close the thread pool.

### Public Interface

#### Types

- **Task**: A type alias for `std::function<void()>`, representing a task that can be executed by the thread pool.

#### Constructors

- **ThreadPool(std::optional<std::size_t> thread_count = std::nullopt, log::Logger::Ptr logger = log::RootLogger()) noexcept**
  - **Parameters**:
    - `thread_count`: The number of working threads. If it is `std::nullopt` or zero, the thread pool will use the number of concurrent threads supported by hardware.
    - `logger`: A logger. If it is `nullptr`, the thread pool will use the global root logger.

#### Destructor

- **~ThreadPool() noexcept**
  - Cleans up resources and ensures all threads are joined before destruction.

#### Deleted Methods

- **Copy Constructor**: Deleted to prevent copying of `ThreadPool` objects.
- **Move Constructor**: Deleted to prevent moving of `ThreadPool` objects.
- **Copy Assignment Operator**: Deleted to prevent assignment of `ThreadPool` objects.
- **Move Assignment Operator**: Deleted to prevent move assignment of `ThreadPool` objects.

#### Public Methods

- **void Start() noexcept**
  - Starts the thread pool by creating and starting worker threads.

- **void Push(Task task) noexcept**
  - Pushes a task into the thread pool for execution.

- **void Close() noexcept**
  - Closes the thread pool, preventing further tasks from being executed. Remaining tasks will not be executed.

### Private Members

#### Types

- **Task**: A type alias for `std::function<void()>`, representing a task that can be executed by the thread pool.

#### Member Variables

- **logger_**: A pointer to a logger used for logging messages.
- **mtx_**: A mutex used to synchronize access to shared resources.
- **closed_**: An atomic boolean indicating whether the thread pool is closed.
- **thread_count_**: The number of threads in the thread pool.
- **cond_**: A condition variable used to notify worker threads when tasks are available or when the thread pool is closing.
- **tasks_**: A list of tasks waiting to be executed.
- **threads_**: A list of worker threads managed by the thread pool.

#### Private Methods

- **void ExecProc() noexcept**
  - Continually pops and executes tasks from the task queue. Any exceptions raised in callbacks are caught, and exception messages are logged.

## Class Implementation: `ThreadPool`

### File Path

`src/containers/thread_pool/thread_pool.cpp`

### Constructor

- **ThreadPool(std::optional<std::size_t> thread_count, log::Logger::Ptr logger) noexcept**
  - Initializes the logger. If no logger is provided, it defaults to the global root logger.
  - Determines the number of threads based on the input parameter or hardware concurrency.

### Destructor

- **~ThreadPool() noexcept**
  - Closes the thread pool and joins all worker threads before destruction.

### Public Methods

- **void Start() noexcept**
  - Asserts that the thread pool is closed, sets it to open, and starts the specified number of worker threads.

- **void Push(Task task) noexcept**
  - Asserts that the thread pool is not closed, locks the mutex, adds the task to the queue, and notifies one waiting worker thread.

- **void Close() noexcept**
  - Locks the mutex, sets the `closed_` flag to true, and notifies all waiting worker threads.

### Private Methods

- **void ExecProc() noexcept**
  - Continually pops and executes tasks from the task queue. If an exception is raised during task execution, it logs the error message.

## Usage Example

The usage of the `ThreadPool` class can be found in the example file `tests/containers/thread_pool_test.cpp`.

## Conclusion

This design specification provides a comprehensive overview of the `ThreadPool` class, including its public and private interfaces, constructors, destructors, and methods. It also outlines the dependencies and usage examples to ensure that developers have all necessary information for implementing or maintaining this component.

---

**Note**: The identifiers `Fxx/Uxx` are preserved as per the guidelines provided. No assumptions were made about their meanings or purposes beyond what was explicitly stated in the input files.