### Design Specification for Logging System

#### Overview
This document provides a detailed design specification for the logging system implemented in C++. The system supports various features such as different event levels, custom formatters, and multiple appenders (standard output and file). It also includes configuration management through YAML files.

#### Components

1. **Logger**
2. **Event**
3. **Formatter**
4. **Appender** (StdOutAppender, FileAppender)
5. **Manager**
6. **Field Formatters**

### Detailed Design

#### 1. Logger
- **Role**: The central component that manages logging operations.
- **Attributes**:
  - `name`: Name of the logger.
  - `level`: Minimum level of events to log.
  - `capacity`: Capacity of the event queue (0 for synchronous operation).
  - `appenders`: List of appenders attached to the logger.
  - `formatter_`: Default formatter used by the logger.

- **Methods**:
  - `Log(Event::Ptr event)`: Logs an event if its level is above or equal to the logger's level.
  - `AddAppender(Appender::Ptr appender)`: Adds an appender to the logger.
  - `RemoveAppender(Appender::Ptr appender)`: Removes an appender from the logger.
  - `ClearAppenders()`: Clears all appenders.
  - `GetLevel()`, `SetLevel(Level level)`: Get and set the logging level.
  - `GetDefaultFormatter()`, `SetDefaultFormatter(Formatter::Ptr formatter)`: Get and set the default formatter.
  - `ToYamlString()`: Converts logger configuration to a YAML string.

#### 2. Event
- **Role**: Represents a log event with metadata such as level, location, thread ID, time, and message.
- **Attributes**:
  - `level_`: Level of the event.
  - `file_name_`, `line_num_`, `thread_id_`, `time_`: Metadata about where and when the event occurred.
  - `msg_`: Message stream for user messages.

- **Methods**:
  - `Create(...)`: Static method to create an event.
  - `Level()`, `FileName()`, `LineNum()`, `ThreadId()`, `Time()`: Getters for metadata.
  - `Message()`, `MessageStream()`: Get and modify the message stream.

#### 3. Formatter
- **Role**: Formats log events into strings based on a pattern.
- **Attributes**:
  - `pattern_`: Pattern string defining the format.
  - `fields_`: List of field formatters derived from the pattern.

- **Methods**:
  - `Default()`: Returns a default formatter instance.
  - `Format(const Logger& logger, const Event& event)`: Formats an event into a string using the defined fields.

#### 4. Appender
- **Role**: Writes formatted log events to a specific destination (e.g., standard output or file).
- **Attributes**:
  - `formatter_`: Formatter used by the appender.
  
- **Methods**:
  - `Log(const Logger& logger, const Event& event)`: Logs an event using the formatter.
  - `ToYamlString()`: Converts appender configuration to a YAML string.

#### 5. StdOutAppender
- **Role**: Appends log events to standard output.
- **Methods**:
  - `Log(...)`: Writes formatted log events to stdout.

#### 6. FileAppender
- **Role**: Appends log events to a file.
- **Attributes**:
  - `file_name_`: Name of the file where logs are written.
  - `file_`: Output stream for the file.

- **Methods**:
  - `Log(...)`: Writes formatted log events to the specified file.

#### 7. Manager
- **Role**: Manages a collection of loggers.
- **Attributes**:
  - `name_`: Name of the manager.
  - `loggers_`: Map of logger names to logger instances.

- **Methods**:
  - `FindLogger(...)`: Finds or creates a logger by name.
  - `RemoveLogger(...)`: Removes a logger by name.
  - `ToYamlString()`: Converts manager configuration to a YAML string.
  - `InitConfig()`: Initializes the configuration management for loggers.

#### 8. Field Formatters
- **Role**: Sub-formatters for different event fields (e.g., message, level, thread ID).
- **Classes**:
  - `Message`, `Level`, `ThreadId`, `DateTime`, `FileName`, `LineNum`, `NewLine`, `Tab`, `RawString`, `LoggerName`.

- **Methods**:
  - `Format(...)`: Formats the respective field into a string.
  - `Tag()`: Returns the tag representing the field.

### Configuration Management
- **Role**: Manages logger configurations through YAML files.
- **Structs**:
  - `AppenderConfig`: Configuration for an appender.
  - `LoggerConfig`: Configuration for a logger.

- **Methods**:
  - `SetListener(...)`: Sets a listener callback to adjust loggers when the configuration changes.

### Implementation Details
- **Namespaces**: All components are encapsulated within the `ws::log` namespace.
- **Thread Safety**: Mutexes (`std::mutex`) are used for thread-safe operations on shared resources.
- **Error Handling**: Exceptions are thrown for invalid configurations or system errors.

### Conclusion
This design specification provides a comprehensive overview of the logging system's components, their roles, and methods. It ensures that the system is flexible, extensible, and easy to maintain. The provided interfaces allow for easy integration with other parts of an application and support advanced features like asynchronous logging and custom formatters.