### Design Specification for Reimplementation of C++ Source Code

#### Overview
This document provides a detailed design specification for reimplementing the given C++ source code. The target-owned identifiers (Fxx/Uxx) are to be preserved, and only the units marked with `replacement_required: true` will be regenerated.

#### Target Units
- **F01/U01**: Header file (`include/io.h`)
- **F02/U02**: Source file (`src/io/io.cpp`)

### F01/U01: include/io.h

**Path:** `include/io.h`

**Role:** Complete target-owned implementation/declaration file.

#### Namespaces
- **ws::io**

#### Classes and Interfaces

1. **IReader**
   - **Description**: Interface for reading data into a buffer.
   - **Methods**:
     - `virtual ~IReader() noexcept = default;`
     - `virtual std::size_t ReadFrom(Buffer& buf) = 0;`

2. **IWriter**
   - **Description**: Interface for writing data from a buffer.
   - **Methods**:
     - `virtual ~IWriter() noexcept = default;`
     - `virtual std::size_t WriteTo(Buffer& buf) = 0;`

3. **IReadWriter**
   - **Description**: Interface combining both reading and writing capabilities.
   - **Inheritance**: Inherits from `IReader` and `IWriter` virtually.

4. **Null**
   - **Description**: A null implementation of `IReadWriter`.
   - **Methods**:
     - `std::size_t WriteTo(Buffer& buf) noexcept override;`
     - `std::size_t ReadFrom(Buffer& buf) noexcept override;`

5. **StringStream**
   - **Description**: Implementation of `IReadWriter` using standard input and output streams.
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

6. **FileDescriptor**
   - **Description**: Implementation of `IReadWriter` using file descriptors.
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

### F02/U02: src/io/io.cpp

**Path:** `src/io/io.cpp`

**Role:** Complete target-owned implementation/declaration file.

#### Included Headers
- `"io.h"`
- `"containers/buffer.h"`
- `<sys/uio.h>`
- `<unistd.h>`
- `<array>`

#### Implementation Details

1. **Null Class**
   - **Methods**:
     - `std::size_t WriteTo(Buffer& buf) noexcept;`
       - Marks the entire writable size of the buffer as written.
     - `std::size_t ReadFrom(Buffer& buf) noexcept;`
       - Retrieves all data from the buffer.

2. **StringStream Class**
   - **Constructor**:
     - Initializes with input and output streams.
   - **Methods**:
     - `std::size_t WriteTo(Buffer& buf) noexcept;`
       - Reads a string from the input stream and appends it to the buffer.
     - `std::size_t ReadFrom(Buffer& buf) noexcept;`
       - Retrieves all data from the buffer as a string and writes it to the output stream.

3. **FileDescriptor Class**
   - **Constructor**:
     - Initializes with read and write file descriptors.
   - **Methods**:
     - `std::size_t WriteTo(Buffer& buf);`
       - Reads data from the file descriptor into the buffer using `readv`.
     - `std::size_t ReadFrom(Buffer& buf);`
       - Writes data from the buffer to the file descriptor using `write`.

### Conclusion
This design specification provides a comprehensive guide for reimplementing the given C++ source code while preserving the target-owned identifiers and maintaining the structure and functionality of the original units.