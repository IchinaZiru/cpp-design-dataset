## Design Specification for Thread Pool (Fxx/Uxx)

This document details the design specification for a thread pool implementation, based on the provided C++ source code. It is intended to guide the re-implementation of this functionality by another LLM without access to the original source.  It focuses solely on the information present in F01/U01 and F02/U02.

**1. Overview**

The `ws::ThreadPool` class provides a mechanism for managing a pool of worker threads that execute tasks submitted to it. It aims to improve performance by reusing threads instead of creating new ones for each task.  It includes logging capabilities for error handling within the tasks themselves.

**2. Class Definition: `ws::ThreadPool`**

*   **Namespace:** `ws`
*   **Purpose:** Manages a pool of worker threads and executes submitted tasks.

**3. Public Interface**

*   **`using Task = std::function<void()>;`**: Defines a type alias for task functions, which are callable objects that take no arguments and return void.

*   **`ThreadPool(std::optional<std::size_t> thread_count = std::nullopt, log::Logger::Ptr logger = log::RootLogger()) noexcept;` (Constructor)**
    *   **Parameters:**
        *   `thread_count`: An optional size representing the desired number of threads in the pool. If `std::nullopt` or 0 is provided, the thread count defaults to the hardware concurrency reported by `std::thread::hardware_concurrency()`.
        *   `logger`: A pointer to a logger object.  If null, it uses the global root logger (`log::RootLogger()`).
    *   **Behavior:** Initializes the thread pool with the specified number of threads and logger.

*   **`~ThreadPool() noexcept;` (Destructor)**
    *   **Behavior:** Closes the thread pool and joins all worker threads before destruction, ensuring proper cleanup.

*   **`ThreadPool(const ThreadPool&) = delete;`**: Disables copy construction.
*   **`ThreadPool(ThreadPool&&) = delete;`**: Disables move construction.
*   **`ThreadPool& operator=(const ThreadPool&) = delete;`**: Disables copy assignment.
*   **`ThreadPool& operator=(ThreadPool&&) = delete;`**: Disables move assignment.

*   **`void Start() noexcept;`**
    *   **Behavior:** Starts the worker threads, creating and launching them to begin processing tasks.  It asserts that the pool is not already closed before starting.

*   **`void Push(Task task) noexcept;`**
    *   **Parameters:** `task`: The function object representing the task to be executed.
    *   **Behavior:** Adds the given task to the queue of tasks and notifies a waiting worker thread (if any).  It asserts that the pool is not closed before pushing a task.

*   **`void Close() noexcept;`**
    *   **Behavior:** Signals all worker threads to exit their execution loops, preventing further task processing. It also notifies all waiting threads. Remaining tasks in the queue will *not* be executed.

**4. Private Members**

*   **`log::Logger::Ptr logger_;`**: A pointer to a logger object used for logging errors that occur during task execution.
*   **`mutable std::mutex mtx_;`**:  A mutex protecting access to the shared resources (task queue, thread list). `mutable` allows modification within const methods like `ExecProc`.
*   **`std::atomic_bool closed_ {true};`**: An atomic boolean flag indicating whether the thread pool is closed. Initialized to `true`, meaning it's initially closed.
*   **`std::size_t thread_count_;`**: The number of worker threads in the pool.
*   **`std::condition_variable cond_;`**: A condition variable used to signal worker threads when new tasks are available or when the pool is closing.
*   **`std::list<Task> tasks_;`**:  A list storing the tasks waiting to be executed.
*   **`std::list<std::thread> threads_;`**: A list containing the worker thread objects.

**5. Private Methods**

*   **`void ExecProc() noexcept;`**
    *   **Behavior:** This is the function executed by each worker thread. It continuously waits for tasks to become available, retrieves them from the queue, and executes them.  It handles exceptions that occur during task execution by logging an error message but *not* re-throwing the exception. The loop terminates when the `closed_` flag becomes true.
    *   **Important Note:** Includes a check within the wait condition to prevent permanent blocking if the pool is closed before threads start waiting on the condition variable.

**6. Thread Safety**

The thread pool uses a mutex (`mtx_`) and a condition variable (`cond_`) to ensure thread safety when accessing shared resources like the task queue (`tasks_`) and the list of threads (`threads_`).  `std::atomic_bool closed_` is used for atomic access to the `closed_` flag.

**7. Error Handling**

Exceptions thrown by tasks are caught within the `ExecProc()` method, logged using the logger, but not re-thrown. This prevents a single failing task from bringing down the entire thread pool.
