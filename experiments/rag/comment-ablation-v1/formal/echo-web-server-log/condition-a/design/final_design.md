### Design Specification for Log System Implementation

#### Overview
This document provides a detailed design specification for the logging system implementation. The system includes classes and functions to handle logging events, formatting messages, appending logs to different destinations (stdout or file), managing loggers, and configuring loggers via YAML configuration files.

#### Namespaces and Classes
The primary namespace is `ws::log`. Within this namespace, several key classes are defined:

- **Logger**: Manages the logging process, including adding/removing appenders, setting log levels, and formatting messages.
- **Event**: Represents a single log event with details such as level, timestamp, file name, line number, thread ID, and message.
- **Formatter**: Formats log events according to a specified pattern. It includes fields like `Message`, `Level`, `ThreadId`, `DateTime`, etc.
- **Appender**: Appends formatted log messages to destinations (stdout or files).
  - **StdOutAppender**: Appends logs to stdout.
  - **FileAppender**: Appends logs to a file.
- **Manager**: Manages multiple loggers and their configurations.

#### Enumerations
- **Level**: Represents the severity of log messages (`Debug`, `Info`, `Warn`, `Error`, `Fatal`).
- **AppenderType**: Specifies the type of appender (`StdOut`, `File`).

#### Functions
- Conversion functions between enumerations and strings.
- Utility functions for parsing patterns, creating events, and managing logger configurations.

### Detailed Design

#### Logger Class
- **Attributes**:
  - `name_`: Name of the logger.
  - `level_`: Minimum log level to be logged.
  - `capacity_`: Capacity of the event queue (0 means synchronous logging).
  - `async_`: Flag indicating whether asynchronous logging is enabled.
  - `writer_thread_`: Thread for handling asynchronous logging.
  - `event_deque_`: Queue for storing events in asynchronous mode.
  - `appenders_`: List of appenders attached to the logger.
  - `formatter_`: Default formatter used by the logger.

- **Methods**:
  - Constructors and destructors handle initialization and cleanup, including starting/stopping the writer thread.
  - `Log(Event::Ptr event)`: Logs an event based on its level.
  - `AddAppender(Appender::Ptr appender)`, `RemoveAppender(Appender::Ptr appender)`, `ClearAppenders()`: Manage appenders.
  - `GetLevel()`, `SetLevel(Level level)`: Get/set the log level.
  - `GetDefaultFormatter()`, `SetDefaultFormatter(Formatter::Ptr formatter)`, `SetDefaultFormatter(std::string_view pattern)`: Get/set the default formatter.
  - `Name()`, `Capacity()`: Return logger name and capacity.
  - `ToYamlString()`: Convert logger configuration to YAML string.

#### Event Class
- **Attributes**:
  - `level_`: Log level of the event.
  - `file_name_`: File name where the log was generated.
  - `line_num_`: Line number in the file.
  - `thread_id_`: Thread ID that generated the log.
  - `time_`: Timestamp of the log.
  - `msg_`: Message stream for constructing the log message.

- **Methods**:
  - Static method `Create` to create an event with specified details.
  - Getters for all attributes.
  - `MessageStream()`: Return a reference to the message stream.
  - Overloaded operator `<<` to append messages to the event.

#### Formatter Class
- **Attributes**:
  - `pattern_`: Pattern string defining the format of log messages.
  - `fields_`: List of fields that make up the pattern.

- **Methods**:
  - Static method `Default()` returns a default formatter.
  - Constructor initializes the formatter with a given pattern.
  - `Format(const Logger& logger, const Event& event)`: Formats an event according to the pattern.
  - `Pattern()`: Returns the pattern string.

#### Appender Class
- **Attributes**:
  - `formatter_`: Formatter used by the appender.
  - `mtx_`: Mutex for thread-safe operations.

- **Methods**:
  - Constructors initialize the appender with a formatter or pattern.
  - `Log(const Logger& logger, const Event& event)`: Logs an event to the destination (stdout or file).
  - `ToYamlString()`: Convert appender configuration to YAML string.
  - `GetFormatter()`, `SetFormatter(Formatter::Ptr formatter)`, `SetFormatter(std::string_view pattern)`: Get/set the formatter.

#### StdOutAppender and FileAppender Classes
- **StdOutAppender**:
  - Logs messages to stdout using a synchronized stream (`std::osyncstream`).

- **FileAppender**:
  - Logs messages to a file. The file is opened in append mode.
  - `ToYamlString()`: Convert appender configuration to YAML string.

#### Manager Class
- **Attributes**:
  - `name_`: Name of the manager.
  - `loggers_`: Map of logger names to logger pointers.

- **Methods**:
  - Constructor initializes the manager with a name.
  - `FindLogger(std::string_view name, log::Level level, std::optional<std::size_t> capacity)`: Finds or creates a logger with specified parameters.
  - `RemoveLogger(std::string_view name)`: Removes a logger by name.
  - `ToYamlString()`: Convert manager configuration to YAML string.

#### Utility Functions
- **Conversion functions**:
  - `LevelToString(Level level)`, `to_string(Level level)`, `StringToLevel(std::string str)`.
  - `AppenderTypeToString(AppenderType type)`, `to_string(AppenderType type)`, `StringToAppenderType(std::string str)`.

- **Pattern parsing**:
  - `ParsePattern(std::string_view pattern)`: Parses a format pattern into raw fields.
  - `RawFieldsToFormatFields(const std::list<RawField>& raw_fields)`: Converts raw fields to formatter fields.

#### Configuration Initialization
- **AppenderConfig and LoggerConfig Structures**:
  - Define the configuration for appenders and loggers, respectively.
  - Overloaded operators `==` and `!=` for comparison.

- **VarConverter Templates**:
  - Convert between YAML strings and `AppenderConfig`/`LoggerConfig` objects.
  - Specialize `std::hash<ws::log::LoggerConfig>` to hash logger configurations by name.

- **SetListener Function**:
  - Sets a listener on the configuration variable to update loggers based on changes in the configuration.

### Implementation Details

#### File: include/log.h
- Contains declarations for all classes and functions.
- Includes necessary headers (`config.h`, `containers/block_deque.h`, etc.).

#### File: src/log/log.cpp
- Implements methods for `Logger`, `Event`, `Formatter`, `Appender`, `StdOutAppender`, `FileAppender`, `Manager`, and utility functions.

#### File: src/log/appender.cpp
- Implements methods specific to `Appender`, `StdOutAppender`, and `FileAppender`.

#### File: src/log/field.h
- Declares classes for different log fields (`Message`, `Level`, `ThreadId`, etc.).

#### File: src/log/field.cpp
- Implements methods for all field classes.

#### File: src/log/config_init.h
- Declares structures and templates for configuration initialization.

#### File: src/log/config_init.cpp
- Implements functions for configuration initialization, including `SetListener`.

### Conclusion
This design specification provides a comprehensive overview of the logging system's architecture, including class definitions, methods, and utility functions. It ensures that the system is modular, extensible, and easy to maintain. The provided specifications should enable another developer to re-implement the system accurately without needing access to the original source code.