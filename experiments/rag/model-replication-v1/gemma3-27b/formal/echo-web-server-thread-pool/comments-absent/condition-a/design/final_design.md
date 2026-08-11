## Design Specification for Thread Pool

This document details the design of a thread pool implementation in C++. It is intended to guide the re-implementation of the provided source code (F01/U01 and F02/U02) by another LLM.  The specification focuses solely on the information available within the given files, avoiding any assumptions or external knowledge.

**1. Overview**

The `ws::ThreadPool` class manages a pool of threads to execute tasks concurrently. It provides methods for starting the thread pool, submitting tasks, and shutting down the pool. The implementation uses a condition variable to signal worker threads when new tasks are available.  Error handling within tasks is implemented with logging.

**2. Namespaces**

*   `ws`: All classes and functions related to the thread pool reside in the `ws` namespace.

**3. Classes & Structures**

*   **`ws::ThreadPool`**: The core class representing the thread pool.
    *   **Members:**
        *   `logger_`: A pointer to a logger object (`log::Logger::Ptr`). Used for logging errors that occur within tasks.
        *   `mtx_`:  A `std::mutex` used to protect access to shared resources (e.g., the task queue).
        *   `closed_`: An `std::atomic_bool` indicating whether the thread pool is closed. Initialized to `true`.
        *   `thread_count_`: A `std::size_t` representing the number of threads in the pool.
        *   `cond_`: A `std::condition_variable` used to signal worker threads when tasks are available or the pool is closing.
        *   `tasks_`: A `std::list<Task>` holding the tasks to be executed.  Tasks are stored as function objects.
        *   `threads_`: A `std::list<std::thread>` storing the active threads in the pool.
    *   **Methods:**
        *   `ThreadPool(std::optional<std::size_t> thread_count = std::nullopt, log::Logger::Ptr logger = log::RootLogger()) noexcept`: Constructor. Initializes the thread pool with an optional number of threads and a logger. If `thread_count` is not provided, it defaults to the hardware concurrency.
        *   `~ThreadPool() noexcept`: Destructor. Closes the thread pool and joins all worker threads.
        *   `ThreadPool(const ThreadPool&) = delete;`: Copy constructor deleted.
        *   `ThreadPool(ThreadPool&&) = delete;`: Move constructor deleted.
        *   `ThreadPool& operator=(const ThreadPool&) = delete;`: Copy assignment operator deleted.
        *   `ThreadPool& operator=(ThreadPool&&) = delete;`: Move assignment operator deleted.
        *   `Start() noexcept`: Starts the thread pool by creating and launching worker threads. Sets `closed_` to `false`.
        *   `Push(Task task) noexcept`: Adds a new task to the task queue. Notifies one waiting worker thread.  Requires that the pool is not closed.
        *   `Close() noexcept`: Closes the thread pool by setting `closed_` to `true` and notifying all waiting worker threads.
        *   `ExecProc() noexcept`: The function executed by each worker thread. It waits for tasks, executes them, and handles exceptions.  Exits when the pool is closed.
    *   **Type Alias:**
        *   `Task = std::function<void()>`: Defines a task as a callable object (e.g., a function or lambda) that takes no arguments and returns void.

**4. Functionality Details**

*   **Thread Creation & Management**: The `Start()` method creates `thread_count_` number of threads, each executing the `ExecProc()` function.
*   **Task Submission**:  The `Push()` method adds tasks to the `tasks_` list and signals a waiting thread via `cond_.notify_one()`.
*   **Worker Thread Logic (`ExecProc`)**: Each worker thread:
    1.  Waits on the condition variable `cond_` until either there are tasks in the queue or the pool is closed. The wait is protected by a `std::unique_lock`.
    2.  If not closed, retrieves and executes the first task from the `tasks_` list.
    3.  Handles any exceptions thrown during task execution by logging an error message using the `logger_`.
    4.  Repeats steps 1-3 until the pool is closed.
*   **Shutdown**: The `Close()` method sets the `closed_` flag to true and notifies all waiting threads via `cond_.notify_all()`, causing them to exit their wait loop and terminate. The destructor joins all worker threads before exiting.

**5. Error Handling**

*   Exceptions thrown during task execution are caught within `ExecProc()` and logged using the `logger_`.  The exception does not cause the thread pool to crash, but is reported via logging.

**6. Dependencies**

*   `log.h`: Provides the `log::Logger` class for logging.
*   `<condition_variable>`: For condition variable synchronization.
*   `<functional>`: For `std::function`.
*   `<list>`: For `std::list`.
*   `<mutex>`: For `std::mutex` and `std::lock_guard`/`std::unique_lock`.
*   `<optional>`: For `std::optional`.
*   `<thread>`: For `std::thread` and `std::thread::hardware_concurrency()`.
*   `util.h`: Used by the format string in logging (fmt library).

**7.  Assumptions & Constraints**

*   The provided code assumes that the `log` namespace and its associated classes are defined elsewhere.
*   Tasks submitted to the thread pool should be thread-safe, as they may be executed concurrently by multiple threads.
*   The destructor ensures all threads are joined before exiting, preventing resource leaks.
