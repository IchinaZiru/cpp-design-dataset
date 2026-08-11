## Design Specification for I/O Classes (ws::io)

This document details the design of a set of I/O classes within the `ws` namespace, specifically under the `io` sub-namespace. These classes provide interfaces for reading and writing data to and from buffers. This specification is based on the provided C++ source code (`include/io.h` and `src/io/io.cpp`) and aims to enable re-implementation by another LLM without access to the original source.

**1. Overview**

The core concept revolves around abstracting I/O operations through interfaces that interact with a `Buffer` class (defined elsewhere - assumed to exist).  This allows for flexible I/O handling, supporting various sources and destinations like null streams, string streams, and file descriptors.

**2. Key Classes & Interfaces**

*   **`ws::io::IReader`**: Abstract interface for reading data from a buffer.
    *   **Methods:**
        *   `virtual ~IReader() noexcept = default;`: Virtual destructor.
        *   `virtual std::size_t ReadFrom(Buffer& buf) = 0;`:  Reads data from the provided `Buffer`. Returns the number of bytes read.

*   **`ws::io::IWriter`**: Abstract interface for writing data to a buffer.
    *   **Methods:**
        *   `virtual ~IWriter() noexcept = default;`: Virtual destructor.
        *   `virtual std::size_t WriteTo(Buffer& buf) = 0;`: Writes data to the provided `Buffer`. Returns the number of bytes written.

*   **`ws::io::IReadWriter`**:  Interface combining both reading and writing capabilities. Inherits from both `IReader` and `IWriter` (virtual inheritance).
    *   **Methods:** Inherited from `IReader` and `IWriter`.

*   **`ws::io::Null`**: Concrete class implementing `IReadWriter`.  Acts as a "no-op" I/O object, consuming buffer space without actually reading or writing data.
    *   **Methods:**
        *   `std::size_t WriteTo(Buffer& buf) noexcept override;`: Consumes all writable space in the `buf`, marking it as written. Returns the number of bytes "written" (equal to the buffer's original writable size).
        *   `std::size_t ReadFrom(Buffer& buf) noexcept override;`:  Retrieves and discards all readable data from the `buf`. Returns the number of bytes "read" (equal to the amount of data originally in the buffer).

*   **`ws::io::StringStream`**: Concrete class implementing `IReadWriter`. Reads from and writes to standard C++ streams (`std::istream`, `std::ostream`).
    *   **Members:**
        *   `std::istream& read_;`: Reference to the input stream.
        *   `std::ostream& write_;`: Reference to the output stream.
    *   **Methods:**
        *   `explicit StringStream(std::istream& read, std::ostream& write) noexcept;`: Constructor taking references to input and output streams.
        *   `StringStream(const StringStream&) = delete;`: Deleted copy constructor.
        *   `StringStream(StringStream&&) = delete;`: Deleted move constructor.
        *   `StringStream& operator=(const StringStream&) = delete;`: Deleted copy assignment operator.
        *   `StringStream& operator=(StringStream&&) = delete;`: Deleted move assignment operator.
        *   `std::size_t WriteTo(Buffer& buf) noexcept override;`: Reads a string from `read_` and appends it to the `buf`. Returns the length of the read string.
        *   `std::size_t ReadFrom(Buffer& buf) noexcept override;`: Retrieves all data from the `buf` as a string, writes it to `write_`, and returns the length of the written string.

*   **`ws::io::FileDescriptor`**: Concrete class implementing `IReadWriter`. Reads from and writes to file descriptors (`ws::FileDescriptor`).
    *   **Members:**
        *   `ws::FileDescriptor read_;`: File descriptor for reading.
        *   `ws::FileDescriptor write_;`: File descriptor for writing.
    *   **Methods:**
        *   `explicit FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept;`: Constructor taking file descriptors for reading and writing.
        *   `FileDescriptor(const FileDescriptor&) = delete;`: Deleted copy constructor.
        *   `FileDescriptor(FileDescriptor&&) = delete;`: Deleted move constructor.
        *   `FileDescriptor& operator=(const FileDescriptor&) = delete;`: Deleted copy assignment operator.
        *   `FileDescriptor& operator=(FileDescriptor&&) = delete;`: Deleted move assignment operator.
        *   `std::size_t WriteTo(Buffer& buf) override;`: Reads data from the `read_` file descriptor and writes it to the provided `buf`.  Handles potential overflow by using an auxiliary buffer if the input buffer is small. Returns the number of bytes written. Throws exception on error.
        *   `std::size_t ReadFrom(Buffer& buf) override;`: Writes data from the `buf` to the `write_` file descriptor.  Returns the number of bytes written. Throws exception on error.

**3. Dependencies**

*   `ws::Buffer`: The core buffer class used for I/O operations. Its interface is not defined here but assumed to exist and provide methods like:
    *   `ReadableBytes()`: Returns the number of readable bytes in the buffer.
    *   `WritableSize()`: Returns the number of writable bytes in the buffer.
    *   `Retrieve(size_t count)`: Retrieves `count` bytes from the beginning of the buffer, shifting subsequent data forward.
    *   `Append(const std::string& str)`: Appends a string to the end of the buffer.
    *   `HasWritten(std::size_t size)`: Marks `size` bytes as written in the buffer.
    *   `RetrieveAllToString()`: Returns all readable data from the buffer as a string.
    *   `WritableBytes()`: Returns a byte array representing writable space.

*   `ws::FileDescriptor`: Represents a file descriptor. Its interface is not defined here but assumed to exist.

*   Standard C++ library headers: `<iostream>`, `<string>`, `<array>`, `<sys/uio.h>`, `<unistd.h>`.

**4. Error Handling**

The `FileDescriptor` class uses the following error handling mechanism:

*   `ThrowLastSystemError()`:  A function (not defined in provided code, but assumed to exist) that throws an exception based on the last system error encountered (e.g., using `errno`). This is used after calls to `readv` and `write`.

**5. Design Considerations**

*   **Virtual Inheritance:** The use of virtual inheritance in `IReadWriter` allows for flexible class hierarchies and avoids multiple copies of base class members.
*   **Deleted Copy/Move Operations:**  The deleted copy and move constructors/assignment operators in `StringStream` and `FileDescriptor` prevent accidental copying or moving of objects that hold references to external resources (streams, file descriptors). This ensures resource safety.
*   **Auxiliary Buffer in FileDescriptor::WriteTo**: The use of an auxiliary buffer is a performance optimization to handle cases where the input buffer's writable size is small compared to the amount of data available from the file descriptor.

**6.  Assumptions**

*   The `ws::Buffer` class exists and provides the necessary methods for reading, writing, and managing buffer contents.
*   The `ws::FileDescriptor` class exists and represents a valid file descriptor.
*   A function named `ThrowLastSystemError()` is available to handle system errors.
