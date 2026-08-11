# Design Specification for Reimplementation of `util.h` and `util.cpp`

## Overview

This document provides a detailed design specification for the reimplementation of two target-owned files: `util.h` (header file) and `util.cpp` (source file). The goal is to ensure that the new implementation adheres strictly to the provided specifications, preserving all names, types, signatures, namespaces, and replacement boundaries.

## Target Files

### F01/U01 - `include/util.h`

#### Role
- Complete target-owned implementation/declaration file.
- Replacement required: true.

#### Dependencies
- `<fmt/format.h>`
- `<yaml-cpp/yaml.h>`
- `<sys/stat.h>`
- `<concepts>`
- `<functional>`
- `<initializer_list>`
- `<memory>`
- `<regex>`
- `<string>`
- `<string_view>`
- `<utility>`
- `<vector>`

#### Namespace
- `ws`

#### Constants and Types
- `FileDescriptor`: Alias for `int`.
- `invalid_file_descriptor`: Constant value `-1`.

#### Functions
1. **StringToLower**
   - Signature: `std::string StringToLower(std::string str) noexcept;`
   - Description: Converts a string to lowercase.

2. **StringToUpper**
   - Signature: `std::string StringToUpper(std::string str) noexcept;`
   - Description: Converts a string to uppercase.

3. **ReplaceAllSubstring**
   - Signature: `std::string ReplaceAllSubstring(std::string_view str, std::string_view from, std::string_view to) noexcept;`
   - Description: Replaces all occurrences of a substring within a string with another substring.

4. **SplitString**
   - Signature: `std::vector<std::string> SplitString(const std::string& str, const std::regex& pattern) noexcept;`
   - Description: Splits a string into substrings based on a regular expression pattern.

5. **SplitStringToLines**
   - Signature: `std::vector<std::string> SplitStringToLines(const std::string& str) noexcept;`
   - Description: Splits a string into lines.

6. **LoadYamlString**
   - Signature: `YAML::Node LoadYamlString(std::string_view str, std::initializer_list<std::string_view> required_fields = {});`
   - Description: Loads a YAML string and checks for required fields.

7. **ThrowIfYamlFieldIsNotScalar**
   - Signature: `void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node, std::string_view field);`
   - Description: Throws an exception if the specified YAML field is not scalar.

8. **IsValidFileDescriptor**
   - Signature: `constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept;`
   - Description: Checks if a file descriptor is valid.

9. **SetFileDescriptorAsNonblocking**
   - Signature: `void SetFileDescriptorAsNonblocking(FileDescriptor fd);`
   - Description: Sets a file descriptor to non-blocking mode.

10. **ThrowLastSystemError**
    - Signature: `[[noreturn]] void ThrowLastSystemError();`
    - Description: Throws the last system error as an exception.

11. **CurrentThreadId**
    - Signature: `std::uint32_t CurrentThreadId() noexcept;`
    - Description: Returns the current thread ID.

12. **Backtrace (Overloaded)**
    - Signature 1: `void Backtrace(std::vector<std::string>& stack, std::size_t size, std::size_t skip = 0) noexcept;`
      - Description: Captures a backtrace and stores it in a vector.
    - Signature 2: `std::string Backtrace(std::size_t size, std::size_t skip = 0, std::string_view prefix = "") noexcept;`
      - Description: Returns a formatted string of the backtrace.

#### Templates
1. **Singleton**
   - Template Parameters: `T`, `Args...`
   - Methods:
     - `Instance`: Provides a singleton instance of type `T`.

2. **SingletonPtr**
   - Template Parameters: `T`, `Args...`
   - Methods:
     - `Instance`: Provides a shared pointer to a singleton instance of type `T`.

3. **RAII**
   - Template Parameters: `T`, `Cleaner = std::function<void(T)>`
   - Requires: `std::is_invocable_v<Cleaner, T>`
   - Methods:
     - Constructor: Initializes the object and its cleaner.
     - Deleted Copy and Move Semantics
     - Destructor: Cleans up the object using the provided cleaner.
     - `Object`: Returns a constant reference to the managed object.

4. **MappedReadOnlyFile**
   - Methods:
     - Default Constructor
     - Deleted Copy Semantics
     - Move Constructor and Assignment Operator
     - Destructor
     - `Map`: Maps a file into memory.
     - `Unmap`: Unmaps the file from memory.
     - `Size`: Returns the size of the mapped file.
     - `Data`: Returns a pointer to the mapped data.
     - `Path`: Returns the path of the mapped file.

5. **Addable Concept**
   - Template Parameters: `T`, `U`, `Ret = T`
   - Requires: The expression `t + u` is convertible to type `Ret`.

### F02/U02 - `src/util/util.cpp`

#### Role
- Complete target-owned implementation/declaration file.
- Replacement required: true.

#### Dependencies
- `"util.h"`
- `<execinfo.h>`
- `<fcntl.h>`
- `<sys/mman.h>`
- `<sys/syscall.h>`
- `<unistd.h>`
- `<algorithm>`
- `<cassert>`
- `<cerrno>`
- `<iterator>`
- `<sstream>`
- `<system_error>`

#### Namespace
- `ws`

#### Function Implementations

1. **StringToLower**
   - Implementation: Uses `std::ranges::transform` to convert each character in the string to lowercase.

2. **StringToUpper**
   - Implementation: Uses `std::ranges::transform` to convert each character in the string to uppercase.

3. **ReplaceAllSubstring**
   - Implementation: Iterates through the input string, replacing all occurrences of a substring with another substring using an output stream.

4. **SplitString**
   - Implementation: Utilizes `std::sregex_token_iterator` to split the string based on a regular expression pattern and stores the results in a vector.

5. **SplitStringToLines**
   - Implementation: Calls `SplitString` with a predefined regex pattern that matches line breaks.

6. **LoadYamlString**
   - Implementation: Loads a YAML string using `YAML::Load`, checks for required fields, and throws an exception if any field is missing.

7. **ThrowIfYamlFieldIsNotScalar**
   - Implementation: Checks if the specified YAML field exists and is scalar; otherwise, throws an exception.

8. **SetFileDescriptorAsNonblocking**
   - Implementation: Uses `fcntl` to set the file descriptor to non-blocking mode and throws a system error if it fails.

9. **ThrowLastSystemError**
   - Implementation: Throws the last system error using `std::system_error`.

10. **CurrentThreadId**
    - Implementation: Retrieves the current thread ID using `syscall(SYS_gettid)`.

11. **Backtrace (Overloaded)**
    - Implementation 1: Captures a backtrace using `backtrace` and stores it in a vector.
    - Implementation 2: Calls the first implementation of `Backtrace`, formats the results, and returns them as a string.

#### Class Implementations

1. **MappedReadOnlyFile**
   - Methods:
     - Default Constructor
     - Move Constructor and Assignment Operator
     - Destructor: Ensures that the file is unmapped.
     - `Map`: Maps a file into memory using `mmap` and handles errors.
     - `Unmap`: Unmaps the file from memory using `munmap`.
     - `Size`, `Data`, `Path`: Accessor methods for the mapped file's size, data pointer, and path.

## Conclusion

This design specification provides a comprehensive guide for reimplementing the `util.h` and `util.cpp` files. It ensures that all necessary components are included while preserving the original structure, namespaces, and function signatures. The reimplementation should strictly adhere to this specification to maintain consistency with the target-owned codebase.