## Design Specification for Buffer and IOBuffer Classes

This document details the design specification for the `ws::Buffer` and `ws::IOBuffer` classes, based on the provided C++ source code. It is intended to guide the re-implementation of these classes by another LLM without access to the original source.  It focuses solely on the information present in the given files (F01/U01 and F02/U02).

**1. Overview**

The `ws::Buffer` class provides an auto-expandable buffer for storing bytes and strings. It manages a circular buffer with separate read and write positions, allowing efficient appending and retrieval of data.  `ws::IOBuffer` inherits from `ws::Buffer` and adds functionality to interact with I/O streams via an interface defined in the reference-only namespace `ws::io`.

**2. Namespaces**

*   `ws`: The primary namespace for these classes.
*   `ws::io`:  Contains a reference-only class `IReadWriter`, which is not detailed here as it's outside the scope of replacement units.

**3. Enums**

*   `NewLine`: Defines newline character options:
    *   `LF`: Represents "\n".
    *   `CRLF`: Represents "\r\n".

**4. Class `ws::Buffer`**

**4.1. Data Members (Protected)**

*   `buf_`: A `std::vector<std::byte>` storing the buffer's data.
*   `read_pos_`: An `std::atomic<std::size_t>` representing the read position within the buffer.  Atomic for potential thread safety, though not explicitly demonstrated in provided code.
*   `write_pos_`: An `std::atomic<std::size_t>` representing the write position within the buffer. Atomic for potential thread safety.

**4.2. Constructors**

*   `Buffer(std::size_t size) noexcept`:  Constructs a `Buffer` with an initial capacity of `size` bytes.
*   `Buffer(std::span<const std::byte> bytes) noexcept`: Constructs a `Buffer` and appends the contents of the provided byte span.
*   `Buffer(std::initializer_list<std::byte> bytes) noexcept`: Constructs a `Buffer` and appends the elements from the initializer list.
*   `Buffer(std::string_view str) noexcept`: Constructs a `Buffer` and appends the given string view.
*   `Buffer(const Buffer&) noexcept`: Copy constructor.  Performs a deep copy of the buffer data, read position, and write position.
*   `Buffer(Buffer&&) noexcept`: Move constructor. Transfers ownership of the internal buffer and atomic positions.
*   `Buffer& operator=(const Buffer&) noexcept`: Copy assignment operator. Performs a deep copy.
*   `Buffer& operator=(Buffer&&) noexcept`: Move assignment operator.  Transfers ownership.

**4.3. Public Methods**

*   `WritableSize() const noexcept`: Returns the number of bytes available for writing without reallocation ( `buf_.size() - write_pos_`).
*   `ReadableSize() const noexcept`: Returns the number of readable bytes in the buffer (`write_pos_ - read_pos_`).
*   `Peek() const noexcept`:  Returns an `std::optional<std::byte>` containing the first byte without advancing the read position. Returns `std::nullopt` if the buffer is empty.
*   `ReadableBytes() const noexcept`: Returns a `std::span<const std::byte>` representing the readable portion of the buffer (from `read_pos_` to `write_pos_`).
*   `ReadableString() const noexcept`:  Returns a `std::string` containing the readable bytes, interpreted as a string. **Warning:** Assumes stored bytes are printable.
*   `WritableBytes() const noexcept`: Returns a `std::span<std::byte>` representing the writable portion of the buffer (from `write_pos_` to the end of `buf_`).
*   `Append(std::span<const std::byte> bytes) noexcept`: Appends the given byte span to the buffer, advancing the write position.
*   `Append(std::initializer_list<std::byte> bytes) noexcept`: Appends the elements of the initializer list to the buffer, advancing the write position.
*   `Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept`: Appends a string view to the buffer, optionally adding a newline character (`\n` for `NewLine::LF`, `\r\n` for `NewLine::CRLF`), and advancing the write position.
*   `Append(const void* data, std::size_t size) noexcept`: Appends `size` bytes from the given memory location to the buffer, advancing the write position.
*   `Append(const Buffer& buf) noexcept`: Appends another `Buffer`'s readable content to this buffer.
*   `EnsureWriteableSize(std::size_t size) noexcept`: Ensures that there is enough writable space in the buffer. If not, it calls `MakeSpace()` to allocate more space.
*   `HasWritten(std::size_t size) noexcept`: Advances the write position by `size`.  Assumes sufficient writable space exists.
*   `Retrieve(std::size_t size) noexcept`: Advances the read position by `size`. Assumes sufficient readable space exists.
*   `RetrieveUntil(const void* addr) noexcept`: Advances the read position until it reaches the given memory address.
*   `RetrieveAll() noexcept`: Advances the read position to the end of the buffer, effectively consuming all data. Returns the number of bytes retrieved.
*   `RetrieveAllToString() noexcept`: Retrieves all readable bytes as a string and clears the buffer. **Warning:** Assumes stored bytes are printable.
*   `Clear() noexcept`: Resets both read and write positions to 0, effectively emptying the buffer.
*   `Empty() const noexcept`: Returns `true` if the buffer is empty (readable size is 0), `false` otherwise.

**4.4. Protected Methods**

*   `PrependableSize() const noexcept`: Returns the number of bytes that can be prepended to the buffer (equal to `read_pos_`).
*   `MakeSpace(std::size_t size) noexcept`:  Allocates more space in the buffer if necessary. It either resizes the underlying vector or copies existing data to the beginning of the vector to create contiguous writable space.
*   `ReadIter() const noexcept`: Returns an iterator pointing to the current read position within `buf_`.
*   `WriteIter() const noexcept`: Returns an iterator pointing to the current write position within `buf_`.

**5. Class `ws::IOBuffer`**

**5.1. Inheritance:**  Inherits publicly from `ws::Buffer`.

**5.2. Methods:**

*   `ReadFrom(io::IReadWriter& io)`: Reads data from an `io::IReadWriter` object and appends it to the buffer. Returns the number of bytes read.
*   `WriteTo(io::IReadWriter& io)`: Writes the readable contents of the buffer to an `io::IReadWriter` object. Returns the number of bytes written.

**6. Operators (Free Functions)**

*   `operator<<(Buffer& buf, std::string_view str) noexcept`: Appends a string view to the given buffer.
*   `operator<<(Buffer& to, const Buffer& from) noexcept`: Appends the contents of one buffer to another.
*   `operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept`: Appends a byte span to the given buffer.
*   `operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept`: Appends an initializer list of bytes to the given buffer.

**7.  Important Considerations:**

*   **Thread Safety:** The use of `std::atomic` for `read_pos_` and `write_pos_` suggests potential thread safety considerations, although the provided code doesn't demonstrate explicit multi-threading usage.
*   **Error Handling:** The code does not include explicit error handling (e.g., exceptions) for memory allocation failures or invalid input parameters.  The use of `assert` indicates that these conditions are considered programming errors.
*   **Printable Bytes Assumption**: Several methods (`ReadableString`, `RetrieveAllToString`) assume the stored bytes represent printable characters, which could lead to undefined behavior if this assumption is violated.
*   **I/O Interface:** The functionality of `IOBuffer` relies on the external `ws::io::IReadWriter` interface, which is not defined in the provided code and therefore cannot be detailed further here.
