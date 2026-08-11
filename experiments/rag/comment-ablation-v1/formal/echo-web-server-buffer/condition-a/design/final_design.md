# Design Specification for Buffer and IOBuffer Classes

## Overview

This document provides a detailed design specification for the `Buffer` and `IOBuffer` classes, which are part of a container library. The primary purpose of these classes is to manage byte buffers efficiently, supporting operations such as reading, writing, appending, and clearing data.

## Namespace and Dependencies

- **Namespace**: `ws`
- **Dependencies**:
  - `<atomic>`
  - `<optional>`
  - `<span>`
  - `<string>`
  - `<string_view>`
  - `<vector>`
  - `"io.h"` (for `IOBuffer` class)

## Classes

### Buffer Class

#### Overview
The `Buffer` class provides a flexible and efficient way to manage byte buffers. It supports various operations such as appending data, reading data, and managing the buffer's internal state.

#### Constructors
- **Default Constructor**:
  ```cpp
  explicit Buffer(std::size_t size = 1000) noexcept;
  ```
  Initializes the buffer with a default or specified size.
  
- **Span Constructor**:
  ```cpp
  explicit Buffer(std::span<const std::byte> bytes) noexcept;
  ```
  Initializes the buffer with data from a span of bytes.
  
- **Initializer List Constructor**:
  ```cpp
  explicit Buffer(std::initializer_list<std::byte> bytes) noexcept;
  ```
  Initializes the buffer with data from an initializer list of bytes.
  
- **String View Constructor**:
  ```cpp
  explicit Buffer(std::string_view str) noexcept;
  ```
  Initializes the buffer with data from a string view.
  
- **Copy Constructor**:
  ```cpp
  Buffer(const Buffer&) noexcept;
  ```
  Creates a copy of another `Buffer` object.
  
- **Move Constructor**:
  ```cpp
  Buffer(Buffer&&) noexcept;
  ```
  Moves the contents of another `Buffer` object.

#### Assignment Operators
- **Copy Assignment Operator**:
  ```cpp
  Buffer& operator=(const Buffer&) noexcept;
  ```
  Assigns the contents of one `Buffer` to another.
  
- **Move Assignment Operator**:
  ```cpp
  Buffer& operator=(Buffer&&) noexcept;
  ```
  Moves the contents of one `Buffer` to another.

#### Public Methods

- **Writable Size**:
  ```cpp
  std::size_t WritableSize() const noexcept;
  ```
  Returns the number of writable bytes in the buffer.
  
- **Readable Size**:
  ```cpp
  std::size_t ReadableSize() const noexcept;
  ```
  Returns the number of readable bytes in the buffer.
  
- **Peek**:
  ```cpp
  std::optional<std::byte> Peek() const noexcept;
  ```
  Returns the first byte that can be read without removing it from the buffer, or `std::nullopt` if the buffer is empty.
  
- **Readable Bytes**:
  ```cpp
  std::span<const std::byte> ReadableBytes() const noexcept;
  ```
  Returns a span of the readable bytes in the buffer.
  
- **Readable String**:
  ```cpp
  std::string ReadableString() const noexcept;
  ```
  Returns a string representation of the readable bytes in the buffer.
  
- **Writable Bytes**:
  ```cpp
  std::span<std::byte> WritableBytes() const noexcept;
  ```
  Returns a span of the writable bytes in the buffer.
  
- **Append (Span)**:
  ```cpp
  void Append(std::span<const std::byte> bytes) noexcept;
  ```
  Appends data from a span of bytes to the buffer.
  
- **Append (Initializer List)**:
  ```cpp
  void Append(std::initializer_list<std::byte> bytes) noexcept;
  ```
  Appends data from an initializer list of bytes to the buffer.
  
- **Append (String View)**:
  ```cpp
  void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept;
  ```
  Appends a string view to the buffer, optionally adding a newline character.
  
- **Append (Void Pointer)**:
  ```cpp
  void Append(const void* data, std::size_t size) noexcept;
  ```
  Appends raw data from a pointer to the buffer.
  
- **Append (Buffer)**:
  ```cpp
  void Append(const Buffer& buf) noexcept;
  ```
  Appends another `Buffer`'s readable bytes to this buffer.
  
- **Ensure Writable Size**:
  ```cpp
  void EnsureWriteableSize(std::size_t size) noexcept;
  ```
  Ensures that the buffer has at least the specified number of writable bytes, resizing if necessary.
  
- **Has Written**:
  ```cpp
  void HasWritten(std::size_t size) noexcept;
  ```
  Marks a certain number of bytes as written.
  
- **Retrieve**:
  ```cpp
  void Retrieve(std::size_t size) noexcept;
  ```
  Removes a specified number of bytes from the beginning of the readable area.
  
- **Retrieve Until**:
  ```cpp
  std::size_t RetrieveUntil(const void* addr) noexcept;
  ```
  Retrieves all bytes up to a specified address.
  
- **Retrieve All**:
  ```cpp
  std::size_t RetrieveAll() noexcept;
  ```
  Removes all readable bytes from the buffer and returns their count.
  
- **Retrieve All To String**:
  ```cpp
  std::string RetrieveAllToString() noexcept;
  ```
  Retrieves all readable bytes as a string, then clears them from the buffer.
  
- **Clear**:
  ```cpp
  void Clear() noexcept;
  ```
  Clears all data in the buffer.
  
- **Empty**:
  ```cpp
  bool Empty() const noexcept;
  ```
  Checks if the buffer is empty.

#### Protected Methods

- **Prependable Size**:
  ```cpp
  std::size_t PrependableSize() const noexcept;
  ```
  Returns the number of bytes that can be prepended to the buffer.
  
- **Make Space**:
  ```cpp
  void MakeSpace(std::size_t size) noexcept;
  ```
  Ensures there is enough space for writing by either resizing or compacting the buffer.
  
- **Read Iterator**:
  ```cpp
  std::vector<std::byte>::iterator ReadIter() const noexcept;
  ```
  Returns an iterator to the beginning of the readable area.
  
- **Write Iterator**:
  ```cpp
  std::vector<std::byte>::iterator WriteIter() const noexcept;
  ```
  Returns an iterator to the beginning of the writable area.

#### Member Variables

- `buf_`: A vector of bytes that stores the buffer's data.
- `read_pos_`: An atomic size_t representing the current read position in the buffer.
- `write_pos_`: An atomic size_t representing the current write position in the buffer.

### IOBuffer Class

#### Overview
The `IOBuffer` class extends the `Buffer` class to provide additional functionality for reading from and writing to I/O streams using an `IReadWriter` interface.

#### Public Methods

- **Read From**:
  ```cpp
  std::size_t ReadFrom(io::IReadWriter& io);
  ```
  Reads data from an `IReadWriter` object into the buffer.
  
- **Write To**:
  ```cpp
  std::size_t WriteTo(io::IReadWriter& io);
  ```
  Writes data from the buffer to an `IReadWriter` object.

## Operators

### Stream Insertion Operator (String View)
```cpp
Buffer& operator<<(Buffer& buf, std::string_view str) noexcept;
```
Appends a string view to the buffer.

### Stream Insertion Operator (Buffer)
```cpp
Buffer& operator<<(Buffer& to, const Buffer& from) noexcept;
```
Appends another `Buffer`'s readable bytes to this buffer.

### Stream Insertion Operator (Span)
```cpp
Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept;
```
Appends data from a span of bytes to the buffer.

### Stream Insertion Operator (Initializer List)
```cpp
Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept;
```
Appends data from an initializer list of bytes to the buffer.

## Enumerations

### NewLine
```cpp
enum class NewLine {
    LF,
    CRLF
};
```
Defines newline characters for appending strings with newlines.

## Usage Example

```cpp
#include "buffer.h"
#include <iostream>

int main() {
    ws::Buffer buf(1024);
    buf << std::string_view("Hello, World!") << ws::NewLine::LF;
    
    std::cout << buf.ReadableString();
    return 0;
}
```

## Conclusion

This design specification provides a comprehensive overview of the `Buffer` and `IOBuffer` classes, including their constructors, methods, operators, and usage. The implementation should adhere to this specification to ensure consistency and functionality.