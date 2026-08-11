## Design Specification for Logging System

This document details the design of a logging system based on the provided C++ source code. It aims to provide sufficient information for another LLM to reimplement the system without access to the original code.  The specification focuses solely on the public interface and behavior as defined by the given files, avoiding any assumptions beyond what is explicitly stated.

**1. Overview**

The logging system provides a flexible way to record events with varying levels of severity (Debug, Info, Warn, Error, Fatal). It supports multiple appenders that can write log messages to different destinations (e.g., standard output, files).  Configuration is handled externally and loaded via YAML format. The system offers both synchronous and asynchronous logging capabilities.

**2. Core Components & Classes**

*   **`ws::log::Level`**: An enumeration representing the severity of a log event.
    *   Values: `Debug`, `Info`, `Warn`, `Error`, `Fatal`.
    *   Provides string conversion functions (`LevelToString`, `to_string`) and parsing from strings (`StringToLevel`).

*   **`ws::log::AppenderType`**: An enumeration representing the type of appender.
    *   Values: `StdOut`, `File`.
    *   Provides string conversion functions (`AppenderTypeToString`, `to_string`) and parsing from strings (`StringToAppenderType`).

*   **`ws::log::Event`**: Represents a single log event.
    *   Contains information like level, timestamp, thread ID, file name, line number, and message.
    *   Provides static factory method `Create()` to construct events.  The constructor is private; use the factory.
    *   Offers accessors for all data members (e.g., `Level()`, `FileName()`, `Message()`).
    *   `MessageStream()` returns an `std::ostringstream&` allowing users to build messages incrementally before finalizing the event.

*   **`ws::log::Formatter`**:  Responsible for formatting log events into strings.
    *   Uses a pattern string to define the output format (e.g., `%d{%Y-%m-%d %H:%M:%S}%T%t%T[%p]%T[%c]%T<%f:%l>%T%m%n`).
    *   `Default()` returns a pre-configured formatter with a standard pattern.
    *   `Format()` takes a `Logger` and an `Event` and returns the formatted string.

*   **`ws::log::Formatter::Field`**: An abstract base class for individual field formatters within a `Formatter`.  Derived classes implement specific formatting logic (e.g., formatting timestamps, thread IDs).
    *   `Format()`: Abstract method to format the field into an output stream.
    *   `Tag()`: Returns a string representing the tag used in the formatter pattern for this field.

*   **`ws::log::Appender`**: An abstract base class for appenders that write log events to specific destinations.
    *   `Log()`: Abstract method to write an event.  Subclasses must implement this.
    *   `ToYamlString()`: Returns a YAML string representing the appender's configuration.
    *   Holds a `Formatter::Ptr` which is used for formatting events before writing them.

*   **`ws::log::StdOutAppender`**: An implementation of `Appender` that writes log messages to standard output (`std::cout`).

*   **`ws::log::FileAppender`**: An implementation of `Appender` that writes log messages to a file.
    *   Requires a filename during construction.

*   **`ws::log::Logger`**: The central logging component.
    *   Manages a list of appenders.
    *   Provides the `Log()` method to write events.
    *   Supports both synchronous and asynchronous logging based on an optional capacity parameter in the constructor.  If capacity > 0, it uses an internal queue and thread for asynchronous logging.
    *   Allows adding and removing appenders dynamically (`AddAppender()`, `RemoveAppender()`).
    *   Provides methods to set the log level (`SetLevel()`) and default formatter (`SetDefaultFormatter()`).

*   **`ws::log::Manager`**: Manages a collection of named loggers.
    *   `FindLogger()`: Retrieves an existing logger by name or creates a new one if it doesn't exist.
    *   `RemoveLogger()`: Removes a logger by name.
    *   Configuration is loaded via YAML and applied to the managed loggers.

**3.  Data Structures & Types**

*   `Event::Ptr`: `std::shared_ptr<Event>` - Used for shared ownership of event objects.
*   `Formatter::Ptr`: `std::shared_ptr<Formatter>` - Used for shared ownership of formatter objects.
*   `Appender::Ptr`: `std::shared_ptr<Appender>` - Used for shared ownership of appender objects.
*   `Logger::Ptr`: `std::shared_ptr<Logger>` - Used for shared ownership of logger objects.
*   `Manager::Ptr`: `std::shared_ptr<Manager>` - Used for shared ownership of manager objects.
*   `BlockDeque<Event::Ptr>`: A thread-safe queue used in asynchronous logging to buffer events.

**4.  Key Interactions & Workflow**

1.  A client creates a `Logger` (typically obtained through the `Manager`).
2.  The client constructs an `Event` using the `Event::Create()` factory method.
3.  The client populates the event with data, potentially using `MessageStream()`.
4.  The client calls `Log()` on the logger, passing in the event.
5.  The logger iterates through its appenders and calls `Log()` on each one, providing the event.
6.  Each appender formats the event (using its formatter) and writes it to its destination.

**5. Configuration**

The logging system is configured using YAML files. The configuration specifies:

*   Logger names
*   Logging levels for each logger
*   Appenders associated with each logger
*   Formatter patterns for appenders or default loggers.

Configuration parsing and application are handled by the `cfg` namespace (details not fully provided in the source, but assumed to be a configuration management system).  The `LoggerConfig` and `AppenderConfig` structs define the structure of the YAML data.

**6. Thread Safety**

*   The `BlockDeque` is thread-safe.
*   Access to internal logger state (appenders, level) is protected by a `std::mutex`.
*   The asynchronous logging thread uses its own mutex for synchronization.

**7. Error Handling**

*   Invalid log levels or appender types will throw `std::invalid_argument` exceptions.
*   File creation errors in `FileAppender` may throw `std::system_error`.
*   YAML parsing errors are handled by the underlying configuration system (`cfg`).

**8.  Assumptions & Limitations**

*   The implementation of the `cfg` namespace is not provided and must be assumed to exist and function as described in the comments.
*   The exact details of YAML parsing are not specified, only that it's used for configuration.
*   No information about external dependencies beyond those included in the source code is available.

**9.  Future Considerations (Not Implemented)**

*   Rolling log files (e.g., rotating logs based on size or time).
*   More advanced filtering and routing of log events.
*   Support for different output formats (e.g., JSON, XML).
