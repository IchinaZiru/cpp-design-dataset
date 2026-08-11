## Detailed Design Specification for Thread Pool (F01/U01 & F02/U02)

This document details the design of a thread pool implementation, based on the provided C++ source code (F01/U01 and F02/U02). It aims to provide sufficient information for another LLM to re-implement the functionality accurately.  The focus is on completeness and precision, prioritizing faithful reproduction over abstraction or optimization.

### 1. Accurate Definitions

| Symbol | Type | Description |
|---|---|---|
| `ws::ThreadPool` | `class` | The main thread pool class. |
| `ws::log::Logger::Ptr` | `std::shared_ptr<ws::log::Logger>` | A shared pointer to a logger object (from the `log` library). |
| `std::optional<std::size_t>` | `class` |  A container that may or may not contain a value of type `std::size_t`. Used for optional thread count. |
| `ws::ThreadPool::Task` | `std::function<void()>` | A function object representing a task to be executed by the thread pool. |
| `std::atomic_bool` | `class` | Atomic boolean type, used for thread-safe flag manipulation.|
| `std::mutex` | `class` | Mutex class for synchronization. |
| `std::condition_variable` | `class` | Condition variable for signaling between threads. |
| `std::list<ws::ThreadPool::Task>` | `class` | A list to store tasks waiting to be executed.|
| `std::list<std::thread>` | `class` | A list to store the worker threads.|

### 2. Direct Dependency Interfaces and Usage

The `ThreadPool` class directly depends on:

*   **`log::Logger` (from `include/log.h`)**: Used for logging errors within tasks.  A logger pointer is stored as a member variable (`logger_`). The `Log()` method of the logger is called to report exceptions.
*   **`<condition_variable>`**: Used for thread synchronization via `std::condition_variable cond_;`.  `notify_one()` and `wait()` are used to signal and wait for tasks.
*   **`<mutex>`**: Used for protecting shared resources (task list, closed flag) with `std::mutex mtx_;`.
*   **`<functional>`**: Provides `std::function` for the `Task` type.
*   **`<thread>`**:  Provides `std::thread` for creating and managing worker threads.
*   **`<atomic>`**: Provides `std::atomic_bool` for thread-safe flag manipulation (`closed_`).

### 3. Results Deciding Expressions/Concrete Values

*   **Thread Count:** If `thread_count` is `std::nullopt` or zero, the number of threads defaults to `std::thread::hardware_concurrency()`.
*   **Closed Flag:** The `closed_` flag starts as `true` and is set to `false` when the thread pool is started. It's used to signal worker threads to exit.
*   **Task Processing Loop Condition:** Worker threads continue processing tasks until `closed_` becomes true *and* the task list (`tasks_`) is empty. The condition variable wait predicate checks both conditions: `!tasks_.empty() || closed_`.

### 4. Used/Updated Data

| Data | Access Type | Description |
|---|---|---|
| `logger_` | Read-only after initialization | Logger instance for error reporting.|
| `mtx_` | Exclusive lock | Mutex protecting access to shared data (tasks_, closed_).|
| `closed_` | Atomic read/write | Flag indicating whether the thread pool is closed.  Accessed atomically.|
| `thread_count_` | Read-only after initialization | Number of worker threads in the pool.|
| `cond_` | Used with mutex | Condition variable for signaling task availability and shutdown.|
| `tasks_` | Protected read/write | List of tasks waiting to be executed.  Tasks are added at the back (`push_back`) and removed from the front (`pop_front`).|
| `threads_` | Read-only after initialization | List of worker threads. |

### 5. State, Side Effects, Invariants

*   **State:** The thread pool maintains an internal state consisting of the number of threads, a list of pending tasks, and a flag indicating whether it's closed.
*   **Side Effects:**  The primary side effect is executing user-provided `Task` objects in worker threads. Logging errors to the logger is another side effect.
*   **Invariants:**
    *   `closed_` is only modified while holding `mtx_`.
    *   Tasks are only added to `tasks_` when the pool is not closed (`!closed_`).
    *   Worker threads acquire `mtx_` before accessing or modifying `tasks_` and `closed_`.

### 6. Class Diagram

```mermaid
classDiagram
    class ws::ThreadPool {
        - log::Logger::Ptr logger_
        - std::mutex mtx_
        - std::atomic_bool closed_
        - std::size_t thread_count_
        - std::condition_variable cond_
        - std::list<Task> tasks_
        - std::list<std::thread> threads_
        + ThreadPool(std::optional<std::size_t>, log::Logger::Ptr)
        + ~ThreadPool()
        + Start()
        + Push(Task)
        + Close()
        - ExecProc()
    }

    class ws::log::Logger {
        + Log(Event::Ptr event)
    }

    ws::ThreadPool -- ws::log::Logger : uses >
```

### 7. Class, Method & Interface Details

| **Class/Method** | **Signature** | **Visibility** | **Description** |
|---|---|---|---|
| `ws::ThreadPool` | `class ThreadPool` | public | The main thread pool class.|
| `ThreadPool(std::optional<std::size_t> thread_count, log::Logger::Ptr logger)` |  public | Constructor. Initializes the thread count and logger. If `thread_count` is nullopt or 0, uses hardware concurrency. |
| `~ThreadPool()` | public | Destructor. Closes the pool and joins all threads.|
| `Start()` | public | Starts the worker threads.|
| `Push(Task task)` | public | Adds a task to the queue for execution.|
| `Close()` | public | Stops accepting new tasks and signals existing threads to exit.|
| `ExecProc()` | private | The main loop executed by each worker thread. Pops tasks from the queue and executes them, handling exceptions.|

### 8. Sequence Diagram (Task Submission & Execution)

```mermaid
sequenceDiagram
    participant Client
    participant ThreadPool
    participant WorkerThread
    participant Task

    Client->>ThreadPool: Push(task)
    activate ThreadPool
    ThreadPool->>ThreadPool: Lock mtx_
    ThreadPool->>tasks_: tasks_.push_back(task)
    ThreadPool->>cond_: cond_.notify_one()
    ThreadPool-->>Client: 
    deactivate ThreadPool

    WorkerThread->>ThreadPool: Wait on cond_ (mtx locked)
    activate WorkerThread
    ThreadPool->>WorkerThread: Signal from notify_one()
    WorkerThread->>ThreadPool: Lock mtx_
    WorkerThread->>tasks_: task = tasks_.front(); tasks_.pop_front()
    WorkerThread-->>ThreadPool: Unlock mtx_
    WorkerThread->>Task: Execute Task()
    activate Task
    Task-->>WorkerThread: 
    deactivate Task
```

### 9. Method Specifications (Push)

**Method:** `ws::ThreadPool::Push(Task task)`

*   **Purpose:** Adds a new task to the thread pool's queue for execution.
*   **Parameters:**
    *   `task`: A `std::function<void()>` representing the task to be executed.  Passed by value (moved).
*   **Return Value:** None (`void`).
*   **Behavior:**
    1.  Acquire a lock on `mtx_`.
    2.  Add the provided `task` to the back of the `tasks_` list using `push_back()`.
    3.  Notify one waiting worker thread via `cond_.notify_one()`.
    4.  Release the lock on `mtx_`.
*   **Exceptions:** None.
*   **Preconditions:** The thread pool must not be closed (`!closed_`).
*   **Postconditions:** The task has been added to the queue and a worker thread may eventually execute it.

This specification provides a detailed overview of the `ThreadPool` class, covering its structure, dependencies, behavior, and key methods. It is designed to enable accurate re-implementation by another LLM without requiring access to the original source code beyond what's provided in the input.
