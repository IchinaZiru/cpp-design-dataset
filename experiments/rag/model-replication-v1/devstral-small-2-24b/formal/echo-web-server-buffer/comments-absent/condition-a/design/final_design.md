# Buffer Class Design Specification

## Overview
This document specifies the design of a buffer class system for efficient byte manipulation and I/O operations. The implementation consists of two main components: the `Buffer` base class and its derived `IOBuffer` class.

## Core Components

### 1. Buffer Class

#### Purpose
The `Buffer` class provides a circular buffer implementation for storing and manipulating binary data with thread-safe read/write position tracking.

#### Key Features
- Circular buffer implementation using a vector of bytes
- Thread-safe read/write position management via atomic variables
- Support for various input types (bytes, strings, spans)
- Efficient memory management with space optimization

#### Public Interface

##### Constructors
```cpp
// Default constructor with optional initial size
explicit Buffer(std::size_t size = 1000) noexcept;

// Constructor from byte span
explicit Buffer(std::span<const std::byte> bytes) noexcept;

// Constructor from initializer list of bytes
explicit Buffer(std::initializer_list<std::byte> bytes) noexcept;

// Constructor from string view
explicit Buffer(std::string_view str) noexcept;
```

##### Copy/Move Semantics
- Full support for copy and move operations (both constructors and assignment operators)
- Atomic variables are properly handled during copying

##### Size Information Methods
```cpp
// Returns available writable space
std::size_t WritableSize() const noexcept;

// Returns available readable data size
std::size_t ReadableSize() const noexcept;

// Checks if buffer is empty
bool Empty() const noexcept;
```

##### Data Access Methods
```cpp
// Peek at next byte without consuming it
std::optional<std::byte> Peek() const noexcept;

// Get span of readable bytes
std::span<const std::byte> ReadableBytes() const noexcept;

// Convert readable bytes to string
std::string ReadableString() const noexcept;

// Get span of writable bytes
std::span<std::byte> WritableBytes() const noexcept;
```

##### Data Manipulation Methods
```cpp
// Append various data types
void Append(std::span<const std::byte> bytes) noexcept;
void Append(std::initializer_list<std::byte> bytes) noexcept;
void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept;
void Append(const void* data, std::size_t size) noexcept;
void Append(const Buffer& buf) noexcept;

// Ensure minimum writable space
void EnsureWriteableSize(std::size_t size) noexcept;

// Update write position after writing
void HasWritten(std::size_t size) noexcept;

// Consume readable data
void Retrieve(std::size_t size) noexcept;
std::size_t RetrieveUntil(const void* addr) noexcept;
std::size_t RetrieveAll() noexcept;
std::string RetrieveAllToString() noexcept;

// Clear buffer contents
void Clear() noexcept;
```

#### Protected Interface

##### Internal Management Methods
```cpp
// Get prependable space (bytes before read position)
std::size_t PrependableSize() const noexcept;

// Ensure space for writing, may compact buffer
void MakeSpace(std::size_t size) noexcept;

// Get iterators for current read/write positions
std::vector<std::byte>::iterator ReadIter() const noexcept;
std::vector<std::byte>::iterator WriteIter() const noexcept;
```

##### Internal State
```cpp
// Storage vector
std::vector<std::byte> buf_;

// Atomic read/write positions
std::atomic<std::size_t> read_pos_;
std::atomic<std::size_t> write_pos_;
```

### 2. IOBuffer Class

#### Purpose
Derived class that adds I/O capabilities to the base Buffer class.

#### Public Interface
```cpp
// Inherits all constructors from Buffer
using Buffer::Buffer;

// Read data from IReadWriter into buffer
std::size_t ReadFrom(io::IReadWriter& io);

// Write buffer contents to IReadWriter
std::size_t WriteTo(io::IReadWriter& io);
```

### 3. Operator Overloads

#### Stream-like Operators
```cpp
// String output operator
Buffer& operator<<(Buffer& buf, std::string_view str) noexcept;

// Buffer-to-buffer copy operator
Buffer& operator<<(Buffer& to, const Buffer& from) noexcept;

// Byte span output operator
Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept;

// Initializer list output operator
Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept;
```

## Implementation Details

### Memory Management Strategy
1. **Initial Allocation**: Buffer starts with default size (1000 bytes) or specified size
2. **Growth Policy**:
   - When writable space is insufficient, buffer either:
     - Expands by resizing the underlying vector
     - Compacts existing data to free up space at the beginning
3. **Compaction**: When prependable + writable space is insufficient for requested write size

### Thread Safety Considerations
- Read and write positions are protected with atomic variables
- All position updates are atomic operations
- No locking mechanism required as atomic operations provide sufficient synchronization

### Error Handling
- Assertions used internally to verify invariants (disabled in release builds)
- No exceptions thrown from any method (all marked noexcept)

## Usage Patterns

### Basic Buffer Operations
```cpp
Buffer buf;
// Write data
buf.Append("Hello", 5);
// Read data
auto readable = buf.ReadableBytes();
// Consume data
buf.Retrieve(2);
```

### I/O Operations
```cpp
IOBuffer ioBuf;
ioBuf.WriteTo(someWriter); // Write buffer contents
ioBuf.ReadFrom(someReader); // Read into buffer
```

### Stream-like Interface
```cpp
Buffer buf;
buf << "Hello" << std::byte{0x0A} << anotherBuffer;
```

## Dependencies

### Required Headers
- `<atomic>` for thread-safe position tracking
- `<optional>` for Peek() return type
- `<span>` for byte span operations
- `<string>` and `<string_view>` for string handling
- `<vector>` for underlying storage
- `<algorithm>` for memory operations
- `<cassert>` for internal assertions

### External Dependencies
- `io::IReadWriter` interface (used by IOBuffer)

## Design Constraints

1. **No Allocations During Normal Operations**: Buffer should avoid dynamic allocations when possible
2. **Thread Safety**: Must support concurrent read/write operations from different threads
3. **No Exceptions**: All methods must be noexcept
4. **Preserve Input Types**: Maintain exact type signatures and namespaces as specified

## Performance Considerations

1. **Memory Efficiency**: Circular buffer implementation minimizes memory usage by reusing space
2. **Atomic Operations**: Minimal overhead for thread safety
3. **Bulk Operations**: Optimized for appending/reading large chunks of data

This specification provides all necessary information for a complete reimplementation of the buffer system while maintaining the exact same interface and behavior as the original implementation.