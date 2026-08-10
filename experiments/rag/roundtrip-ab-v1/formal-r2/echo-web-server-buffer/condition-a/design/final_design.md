# Design Specification for Buffer and IOBuffer Classes

## Overview

This document provides a detailed design specification for the `Buffer` and `IOBuffer` classes, which are part of an auto-expandable buffer system designed to store bytes and strings. The primary goal is to ensure that another developer can accurately re-implement these classes based on this specification without needing access to the original source code.

## Target Audience

This document is intended for developers who need to implement or maintain the `Buffer` and `IOBuffer` classes in a C++ environment.

## Key Components

### Namespaces
- **ws::io**: Contains the `IReadWriter` interface, which is referenced but not included in this specification.
- **ws**: Contains the `Buffer` and `IOBuffer` classes.

### Enumerations
- **NewLine**: Represents newline characters (`LF` for `\n`, `CRLF` for `\r\n`).

### Classes

#### Buffer Class

**Role**: An auto-expandable buffer that supports storing bytes and strings. It includes methods to manage reading and writing offsets, append data, ensure writable space, and clear the buffer.

**Constructors:**
- **Buffer(std::size_t size = 1000) noexcept**: Initializes a buffer with an initial size.
- **Buffer(std::span<const std::byte> bytes) noexcept**: Initializes a buffer with given bytes.
- **Buffer(std::initializer_list<std::byte> bytes) noexcept**: Initializes a buffer with given bytes using an initializer list.
- **Buffer(std::string_view str) noexcept**: Initializes a buffer with a string.
- **Buffer(const Buffer&) noexcept**: Copy constructor.
- **Buffer(Buffer&&) noexcept**: Move constructor.

**Operators:**
- **operator=(const Buffer&) noexcept**: Copy assignment operator.
- **operator=(Buffer&&) noexcept**: Move assignment operator.

**Public Methods:**
- **WritableSize() const noexcept**: Returns the current writable size without expanding.
- **ReadableSize() const noexcept**: Returns the readable size.
- **Peek() const noexcept**: Peeks the first byte without moving the reading offset.
- **ReadableBytes() const noexcept**: Returns readable bytes without moving the reading offset.
- **ReadableString() const noexcept**: Returns a readable string without moving the reading offset. Developers should ensure that the stored bytes are printable.
- **WritableBytes() const noexcept**: Returns writable space for editing. Developers must manually adjust the writing offset with `HasWritten` if they directly write data using the base address of writable space.
- **Append(std::span<const std::byte> bytes) noexcept**: Appends bytes to the buffer and moves forward the writing offset.
- **Append(std::initializer_list<std::byte> bytes) noexcept**: Appends bytes to the buffer using an initializer list and moves forward the writing offset.
- **Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept**: Appends a string and an optional newline character to the buffer and moves forward the writing offset.
- **Append(const void* data, std::size_t size) noexcept**: Appends data to the buffer and moves forward the writing offset.
- **Append(const Buffer& buf) noexcept**: Appends another buffer to the buffer and moves forward the writing offset.
- **EnsureWriteableSize(std::size_t size) noexcept**: Ensures the buffer has enough writable space.
- **HasWritten(std::size_t size) noexcept**: Manually moves forward the writing offset by a specific size.
- **Retrieve(std::size_t size) noexcept**: Manually moves forward the reading offset by a specific size.
- **RetrieveUntil(const void* addr) noexcept**: Manually moves forward the reading offset until it reaches the destination.
- **RetrieveAll() noexcept**: Manually moves forward the reading offset to the end and returns the number of bytes retrieved.
- **RetrieveAllToString() noexcept**: Manually moves forward the reading offset to the end, extracts a string from the rest, and returns it. Developers should ensure that the stored bytes are printable.
- **Clear() noexcept**: Clears the buffer.
- **Empty() const noexcept**: Checks if the buffer is empty.

**Protected Methods:**
- **PrependableSize() const noexcept**: Returns the prependable size which can be reused.
- **MakeSpace(std::size_t size) noexcept**: Makes the buffer have enough writable space.
- **ReadIter() const noexcept**: Returns the reading offset iterator.
- **WriteIter() const noexcept**: Returns the writing offset iterator.

**Member Variables:**
- **buf_**: A vector of bytes that stores the data.
- **read_pos_**: An atomic size_t representing the current reading position.
- **write_pos_**: An atomic size_t representing the current writing position.

#### IOBuffer Class

**Role**: An enhanced buffer supporting I/O reading and writing. Inherits from `Buffer`.

**Public Methods:**
- **ReadFrom(io::IReadWriter& io)**: Reads data from an I/O object.
- **WriteTo(io::IReadWriter& io)**: Writes data to an I/O object.

### Operators

#### Buffer Insertion Operators
- **operator<<(Buffer& buf, std::string_view str) noexcept**: Writes a string to a buffer.
- **operator<<(Buffer& to, const Buffer& from) noexcept**: Writes a buffer to another buffer.
- **operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept**: Writes bytes to a buffer.
- **operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept**: Writes bytes to a buffer using an initializer list.

## Implementation Details

### Buffer Class

**Constructors:**
- The default constructor initializes the buffer with a specified size (default is 1000).
- Constructors that take `std::span<const std::byte>`, `std::initializer_list<std::byte>`, and `std::string_view` initialize the buffer with the provided data.

**Operators:**
- Copy and move constructors and assignment operators ensure proper copying and moving of buffer contents, including reading and writing positions.

**Public Methods:**
- **WritableSize()**: Returns the remaining writable space in the buffer.
- **ReadableSize()**: Returns the number of bytes that can be read from the buffer.
- **Peek()**: Returns the first byte without advancing the reading position.
- **ReadableBytes()**: Returns a span of readable bytes.
- **ReadableString()**: Converts readable bytes to a string. Developers should ensure the data is printable.
- **WritableBytes()**: Returns a span of writable bytes, allowing direct writing. Manual adjustment of the writing offset is required if writing directly.
- **Append()**: Appends various types of data (bytes, strings) to the buffer and advances the writing position accordingly.
- **EnsureWriteableSize()**: Ensures there is enough space for writing by expanding the buffer if necessary.
- **HasWritten()**: Advances the writing position after direct writes.
- **Retrieve()**: Advances the reading position by a specified number of bytes.
- **RetrieveUntil()**: Advances the reading position until it reaches a specified address.
- **RetrieveAll()**: Clears the buffer and returns the number of bytes read.
- **RetrieveAllToString()**: Clears the buffer, converts the readable data to a string, and returns it. Developers should ensure the data is printable.
- **Clear()**: Resets the buffer, clearing all data and resetting reading and writing positions.
- **Empty()**: Checks if there are no readable bytes in the buffer.

**Protected Methods:**
- **PrependableSize()**: Returns the size of the prependable space that can be reused.
- **MakeSpace()**: Ensures there is enough writable space by either resizing the buffer or shifting existing data to make room.
- **ReadIter()**: Returns an iterator pointing to the current reading position.
- **WriteIter()**: Returns an iterator pointing to the current writing position.

**Member Variables:**
- **buf_**: A vector of bytes that stores the actual data.
- **read_pos_**: An atomic size_t representing the current reading position.
- **write_pos_**: An atomic size_t representing the current writing position.

### IOBuffer Class

**Public Methods:**
- **ReadFrom(io::IReadWriter& io)**: Reads data from an I/O object and appends it to the buffer.
- **WriteTo(io::IReadWriter& io)**: Writes data from the buffer to an I/O object.

### Buffer Insertion Operators

These operators provide a convenient way to append various types of data to a `Buffer` instance using the `<<` operator.

## Conclusion

This design specification provides a comprehensive overview of the `Buffer` and `IOBuffer` classes, including their constructors, methods, and usage. It ensures that another developer can accurately re-implement these classes based on this document without needing access to the original source code.