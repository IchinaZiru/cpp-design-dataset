# Design Specification for Reimplementation of `io.h` and `io.cpp`

## Overview

This document provides a detailed design specification for the reimplementation of two C++ source files: `include/io.h` and `src/io/io.cpp`. The primary goal is to ensure that the new implementation adheres strictly to the provided specifications, including namespaces, class hierarchies, method signatures, and other critical details.

## Target-Owned Inputs

### Identifiers
- **Fxx/Uxx identifiers**: These are opaque and must be preserved in their original form.
  - `F01/U01`: `include/io.h`
  - `F02/U02`: `src/io/io.cpp`

### Replacement Units
- **Replacement Required**:
  - `F01/U01` (`include/io.h`)
  - `F02/U02` (`src/io/io.cpp`)

## File: `include/io.h`

### Role
This file contains the declarations for I/O objects that support reading and writing from buffers.

### Namespace
- **Top-Level Namespace**: `ws`
- **Sub-Namespace**: `io`

### Classes

#### 1. `IReader`
- **Role**: An interface for reading data from a buffer.
- **Methods**:
  - `virtual ~IReader() noexcept = default;`
  - `virtual std::size_t ReadFrom(Buffer& buf) = 0;`

#### 2. `IWriter`
- **Role**: An interface for writing data to a buffer.
- **Methods**:
  - `virtual ~IWriter() noexcept = default;`
  - `virtual std::size_t WriteTo(Buffer& buf) = 0;`

#### 3. `IReadWriter`
- **Role**: A combined interface that inherits from both `IReader` and `IWriter`.
- **Inheritance**:
  - `public virtual IReader`
  - `public virtual IWriter`

#### 4. `Null`
- **Role**: A null I/O object that consumes all readable or writable space without performing any actual read/write operations.
- **Inheritance**:
  - `public virtual IReadWriter`
- **Methods**:
  - `std::size_t WriteTo(Buffer& buf) noexcept override;`
  - `std::size_t ReadFrom(Buffer& buf) noexcept override;`

#### 5. `StringStream`
- **Role**: An I/O object that interacts with string streams for reading and writing.
- **Inheritance**:
  - `public virtual IReadWriter`
- **Constructor**:
  - `explicit StringStream(std::istream& read, std::ostream& write) noexcept;`
- **Deleted Methods**:
  - Copy constructor
  - Move constructor
  - Copy assignment operator
  - Move assignment operator
- **Methods**:
  - `std::size_t WriteTo(Buffer& buf) noexcept override;`
  - `std::size_t ReadFrom(Buffer& buf) noexcept override;`

#### 6. `FileDescriptor`
- **Role**: An I/O object that interacts with file descriptors for reading and writing.
- **Inheritance**:
  - `public virtual IReadWriter`
- **Constructor**:
  - `explicit FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept;`
- **Deleted Methods**:
  - Copy constructor
  - Move constructor
  - Copy assignment operator
  - Move assignment operator
- **Methods**:
  - `std::size_t WriteTo(Buffer& buf) override;`
  - `std::size_t ReadFrom(Buffer& buf) override;`

## File: `src/io/io.cpp`

### Role
This file contains the implementations for the I/O objects declared in `include/io.h`.

### Namespace
- **Top-Level Namespace**: `ws`
- **Sub-Namespace**: `io`

### Implementations

#### 1. `Null::WriteTo(Buffer& buf) noexcept`
- **Description**: Consumes all writable space in the buffer without writing any data.
- **Implementation**:
  - Retrieve the writable size of the buffer.
  - Mark the entire writable space as written.
  - Return the size.

#### 2. `Null::ReadFrom(Buffer& buf) noexcept`
- **Description**: Consumes all readable space in the buffer without reading any data.
- **Implementation**:
  - Retrieve and return all readable data from the buffer.

#### 3. `StringStream::StringStream(std::istream& read, std::ostream& write) noexcept`
- **Description**: Initializes a `StringStream` object with references to input and output string streams.
- **Parameters**:
  - `std::istream& read`: The input stream for reading data.
  - `std::ostream& write`: The output stream for writing data.

#### 4. `StringStream::WriteTo(Buffer& buf) noexcept`
- **Description**: Writes data from the input string stream to the buffer.
- **Implementation**:
  - Read a string from the input stream.
  - Append the string to the buffer.
  - Return the length of the string.

#### 5. `StringStream::ReadFrom(Buffer& buf) noexcept`
- **Description**: Reads data from the buffer and writes it to the output string stream.
- **Implementation**:
  - Retrieve all readable data from the buffer as a string.
  - Write the string to the output stream.
  - Return the length of the string.

#### 6. `FileDescriptor::FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept`
- **Description**: Initializes a `FileDescriptor` object with file descriptors for reading and writing.
- **Parameters**:
  - `ws::FileDescriptor read`: The file descriptor for reading data.
  - `ws::FileDescriptor write`: The file descriptor for writing data.

#### 7. `FileDescriptor::WriteTo(Buffer& buf)`
- **Description**: Writes data from the buffer to the output file descriptor.
- **Implementation**:
  - Retrieve writable bytes from the buffer.
  - Use an additional buffer (`ext_bytes`) to handle cases where the writable size is small.
  - Use `readv` to read data into both buffers.
  - Handle errors and update the buffer accordingly.

#### 8. `FileDescriptor::ReadFrom(Buffer& buf)`
- **Description**: Reads data from the input file descriptor and writes it to the buffer.
- **Implementation**:
  - Retrieve readable bytes from the buffer.
  - Use `write` to write data from the buffer to the output file descriptor.
  - Handle errors and update the buffer accordingly.

## Conclusion

This design specification provides a comprehensive guide for reimplementing the provided C++ source files. It ensures that all necessary details, including namespaces, class hierarchies, method signatures, and specific behaviors, are preserved in the new implementation.