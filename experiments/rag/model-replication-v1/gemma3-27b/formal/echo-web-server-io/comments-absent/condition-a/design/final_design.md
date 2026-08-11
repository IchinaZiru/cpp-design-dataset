## Design Specification for ws::io Namespace

This document details the design specification for the `ws::io` namespace, based on the provided C++ source code. It is intended to guide the re-implementation of this functionality in another LLM without access to the original source.  It focuses solely on the information present within the given files (F01/U01 and F02/U02).

**1. Overview**

The `ws::io` namespace provides an abstraction for reading from and writing to various sources, using interfaces defined by `IReader`, `IWriter`, and `IReadWriter`.  It includes concrete implementations like `Null`, `StringStream`, and `FileDescriptor`. The core concept revolves around transferring data between a `Buffer` (defined in `containers/buffer.h` - reference only) and the underlying source or destination.

**2. Namespaces & Classes**

*   **Namespace:** `ws::io`
*   **Classes:**
    *   `IReader`: Abstract base class for readers.
    *   `IWriter`: Abstract base class for writers.
    *   `IReadWriter`: Virtual inheritance from both `IReader` and `IWriter`.  Represents a component capable of both reading and writing.
    *   `Null`: A concrete implementation of `IReadWriter` that effectively does nothing (writes all data to nowhere, reads all data from nowhere).
    *   `StringStream`: A concrete implementation of `IReadWriter` that uses `std::istream` for reading and `std::ostream` for writing.
    *   `FileDescriptor`: A concrete implementation of `IReadWriter` that utilizes file descriptors (`ws::FileDescriptor` - opaque type) for read/write operations.

**3. Class Details & Functionality**

**3.1 IReader**

*   **Purpose:** Defines the interface for reading data.
*   **Methods:**
    *   `virtual ~IReader() noexcept = default;`: Virtual destructor.
    *   `virtual std::size_t ReadFrom(Buffer& buf) = 0;`:  Reads data from the source and appends it to the provided `Buffer`. Returns the number of bytes read.

**3.2 IWriter**

*   **Purpose:** Defines the interface for writing data.
*   **Methods:**
    *   `virtual ~IWriter() noexcept = default;`: Virtual destructor.
    *   `virtual std::size_t WriteTo(Buffer& buf) = 0;`: Writes data from the provided `Buffer` to the destination. Returns the number of bytes written.

**3.3 IReadWriter**

*   **Purpose:** Combines the functionality of both `IReader` and `IWriter`.
*   **Inheritance:** Publicly inherits virtually from both `IReader` and `IWriter`.
*   **Methods:** Inherits all methods from `IReader` and `IWriter`.

**3.4 Null**

*   **Purpose:** A no-op implementation of `IReadWriter`. Useful for testing or as a placeholder.
*   **Implementation Details:**
    *   `WriteTo(Buffer& buf) noexcept override;`:  Writes all data currently available in the buffer (determined by `buf.WritableSize()`) and marks it as written. Returns the number of bytes "written" which is equal to the writable size of the buffer.
    *   `ReadFrom(Buffer& buf) noexcept override;`: Retrieves all data from the buffer (determined by `buf.RetrieveAll()`) and effectively discards it.  Returns the number of bytes "read", which is equal to the amount retrieved.

**3.5 StringStream**

*   **Purpose:** Adapts standard input/output streams (`std::istream`, `std::ostream`) into `IReadWriter` interfaces.
*   **Constructor:**
    *   `explicit StringStream(std::istream& read, std::ostream& write) noexcept;`: Initializes the internal references to the provided `std::istream` and `std::ostream`.
*   **Implementation Details:**
    *   `WriteTo(Buffer& buf) noexcept override;`: Reads a string from the associated `std::istream`, appends it to the provided `Buffer`, and returns the length of the string.
    *   `ReadFrom(Buffer& buf) noexcept override;`: Retrieves all data from the buffer as a string, writes it to the associated `std::ostream`, and returns the length of the string.

**3.6 FileDescriptor**

*   **Purpose:** Adapts file descriptors (`ws::FileDescriptor` - opaque type) into `IReadWriter` interfaces.
*   **Constructor:**
    *   `explicit FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept;`: Initializes the internal references to the provided read and write file descriptors.
*   **Implementation Details:**
    *   `WriteTo(Buffer& buf) override;`:  Writes data from the buffer to the associated write file descriptor using `readv`. Handles potential errors by throwing an exception (implementation detail: `ThrowLastSystemError()`). Returns the number of bytes written. It uses a fixed-size array (`std::array<std::byte, 0x10000>`) as an intermediate buffer for writing and potentially appends any extra data to the provided Buffer if more data is read than fits in the initial buffer.
    *   `ReadFrom(Buffer& buf) override;`: Reads data from the associated read file descriptor using `write`. Returns the number of bytes read, or throws an exception on error (implementation detail: `ThrowLastSystemError()`).

**4. Dependencies**

*   `util.h`:  Likely contains utility functions used throughout the code. Not further specified in provided files.
*   `containers/buffer.h`: Defines the `Buffer` class, which is crucial for data transfer. The internal implementation of `Buffer` is not visible from these source files but it provides methods like:
    *   `WritableSize()`: Returns the amount of space available to write into the buffer.
    *   `HasWritten(std::size_t size)`: Marks a portion of the buffer as written.
    *   `RetrieveAll()`: Retrieves all data from the buffer and removes it.
    *   `WritableBytes()`: Returns a pointer to the writable bytes in the buffer.
    *   `ReadableBytes()`: Returns a pointer to the readable bytes in the buffer.
    *   `size_bytes()`: Returns the size of the buffer in bytes.
    *   `Append(const std::byte* data, const std::byte* end)`: Appends data from the given range to the buffer.
    *   `Retrieve(std::size_t size)`: Retrieves a specified number of bytes from the buffer and removes them.
    *   `RetrieveAllToString()`: Returns all content in the buffer as a string.

*   `<sys/uio.h>`: Used for `readv` system call in `FileDescriptor::WriteTo`.
*   `<unistd.h>`:  Used for `write` and `readv` system calls in `FileDescriptor`.
*   `<array>`: Used for fixed-size arrays, specifically in `FileDescriptor::WriteTo`.

**5. Error Handling**

The `FileDescriptor` class uses a function called `ThrowLastSystemError()` (implementation not provided) to handle errors encountered during file I/O operations (`readv`, `write`).  This suggests that the system's last error code is used for exception handling.
