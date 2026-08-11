## Design Specification for Buffer and IOBuffer Classes

This document details the design specification for the `Buffer` and `IOBuffer` classes, based on the provided C++ source code.  It is intended to be used by another LLM to reimplement these classes without access to the original source.

**1. Overview**

The `Buffer` class provides a dynamic byte buffer with read/write positions for efficient data handling. The `IOBuffer` class inherits from `Buffer` and adds functionality related to reading from and writing to an `IReadWriter` interface (which is not defined in the provided code, so its behavior remains unspecified).

**2. Namespaces**

*   `ws`:  The top-level namespace for this component.
*   `ws::io`: A nested namespace containing the `IReadWriter` interface (implementation details are outside of scope).

**3. Enumeration: NewLine**

This enumeration defines possible newline characters to be appended when writing strings to the buffer.

*   `LF`: Line Feed (`\n`)
*   `CRLF`: Carriage Return and Line Feed (`\r\n`)

**4. Class: Buffer**

### 4.1. Members

*   `buf_`: `std::vector<std::byte>` - The underlying byte vector storing the buffer's data.
*   `read_pos_`: `std::atomic<std::size_t>` -  Atomic variable representing the read position within the buffer. Initialized to 0.
*   `write_pos_`: `std::atomic<std::size_t>` - Atomic variable representing the write position within the buffer. Initialized to 0.

### 4.2. Constructors

*   `Buffer(std::size_t size = 1000) noexcept;`:  Constructs a `Buffer` with an initial capacity of `size`.
*   `Buffer(std::span<const std::byte> bytes) noexcept;`: Constructs a `Buffer` and appends the contents of the provided span.
*   `Buffer(std::initializer_list<std::byte> bytes) noexcept;`: Constructs a `Buffer` and appends the elements from the initializer list.
*   `Buffer(std::string_view str) noexcept;`: Constructs a `Buffer` and appends the contents of the string view.
*   `Buffer(const Buffer&) noexcept;`: Copy constructor. Performs a deep copy of the buffer data, read position, and write position.
*   `Buffer(Buffer&&) noexcept;`: Move constructor. Transfers ownership of the underlying `std::vector<std::byte>` and atomic positions.
*   `Buffer& operator=(const Buffer&) noexcept;`: Copy assignment operator. Performs a deep copy. Returns a reference to *this*.
*   `Buffer& operator=(Buffer&&) noexcept;`: Move assignment operator. Transfers ownership of the underlying `std::vector<std::byte>` and atomic positions.  Returns a reference to *this*.

### 4.3. Public Methods

*   `std::size_t WritableSize() const noexcept;`: Returns the number of bytes that can be written to the buffer without reallocating.
*   `std::size_t ReadableSize() const noexcept;`: Returns the number of bytes currently available for reading in the buffer.
*   `std::optional<std::byte> Peek() const noexcept;`:  Returns an `std::optional<std::byte>` containing the first byte that can be read, or `std::nullopt` if the buffer is empty. Does not modify the read position.
*   `std::span<const std::byte> ReadableBytes() const noexcept;`: Returns a `std::span` representing the readable portion of the buffer (from `read_pos_` to `write_pos_`).
*   `std::string ReadableString() const noexcept;`:  Returns a `std::string` containing the readable data in the buffer. Assumes the bytes represent valid UTF-8 characters.
*   `std::span<std::byte> WritableBytes() const noexcept;`: Returns a `std::span` representing the writable portion of the buffer (from `write_pos_` to the end of the underlying vector).
*   `void Append(std::span<const std::byte> bytes) noexcept;`: Appends the contents of the provided span to the buffer.
*   `void Append(std::initializer_list<std::byte> bytes) noexcept;`: Appends the elements from the initializer list to the buffer.
*   `void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept;`: Appends a string view to the buffer, optionally adding a newline character (LF or CRLF).
*   `void Append(const void* data, std::size_t size) noexcept;`: Appends `size` bytes from the provided memory location (`data`) to the buffer.
*   `void Append(const Buffer& buf) noexcept;`: Appends the contents of another `Buffer` object to this buffer.
*   `void EnsureWriteableSize(std::size_t size) noexcept;`:  Ensures that there is enough writable space in the buffer for at least `size` bytes. If not, it resizes or shifts existing data as needed.
*   `void HasWritten(std::size_t size) noexcept;`: Advances the write position by `size`. Assumes sufficient writable space exists.
*   `void Retrieve(std::size_t size) noexcept;`:  Advances the read position by `size`, effectively discarding the first `size` bytes of readable data.
*   `std::size_t RetrieveUntil(const void* addr) noexcept;`: Retrieves (discards) all bytes up to and including the byte at the given address (`addr`). Returns the number of bytes retrieved.
*   `std::size_t RetrieveAll() noexcept;`:  Retrieves (discards) all readable data in the buffer. Returns the number of bytes retrieved.
*   `std::string RetrieveAllToString() noexcept;`: Retrieves all readable data as a `std::string`, then clears the buffer.
*   `void Clear() noexcept;`: Resets both read and write positions to 0, effectively clearing the readable portion of the buffer.
*   `bool Empty() const noexcept;`: Returns true if the buffer is empty (readable size is 0), false otherwise.

### 4.4. Protected Methods

*   `std::size_t PrependableSize() const noexcept;`:  Returns the number of bytes that can be prepended to the buffer without reallocating. This is equivalent to `read_pos_`.
*   `void MakeSpace(std::size_t size) noexcept;`: Internal helper function to ensure sufficient writable space, potentially by shifting existing data or resizing the underlying vector.
*   `std::vector<std::byte>::iterator ReadIter() const noexcept;`: Returns an iterator pointing to the current read position within the buffer.
*   `std::vector<std::byte>::iterator WriteIter() const noexcept;`: Returns an iterator pointing to the current write position within the buffer.

**5. Class: IOBuffer**

### 5.1. Inheritance

*   `IOBuffer : public Buffer` - Inherits all members and methods from `Buffer`.

### 5.2. Public Methods

*   `std::size_t ReadFrom(io::IReadWriter& io);`: Reads data from the provided `io::IReadWriter` object and appends it to the buffer. Returns the number of bytes read.
*   `std::size_t WriteTo(io::IReadWriter& io);`: Writes data from the buffer to the provided `io::IReadWriter` object.  Returns the number of bytes written.

**6. Free Operators**

*   `Buffer& operator<<(Buffer& buf, std::string_view str) noexcept;`: Appends a string view to the buffer using the `Append` method. Returns a reference to the buffer.
*   `Buffer& operator<<(Buffer& to, const Buffer& from) noexcept;`: Appends another buffer's contents to this buffer using the `Append` method. Returns a reference to the destination buffer.
*   `Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept;`: Appends a span of bytes to the buffer using the `Append` method. Returns a reference to the buffer.
*   `Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept;`: Appends an initializer list of bytes to the buffer using the `Append` method. Returns a reference to the buffer.

**7.  Important Considerations:**

*   The `io::IReadWriter` interface is not defined in the provided code and its behavior is unknown.
*   Error handling (e.g., for memory allocation failures) is not explicitly specified in the source code, so it can be implemented as appropriate by the reimplementing LLM.  Consider throwing exceptions or returning error codes.
*   The `noexcept` specifier indicates that these functions will not throw exceptions. The implementation should adhere to this constraint.
*   Atomic operations are used for `read_pos_` and `write_pos_`, suggesting potential multi-threaded access. Ensure thread safety if the buffer is accessed from multiple threads.
