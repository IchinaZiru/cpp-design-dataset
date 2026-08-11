## Design Specification for ws::util.h and src/util/util.cpp

This document details the design specification for the `ws::util` namespace, based on the provided C++ source code. It is intended to guide a re-implementation of this functionality without access to the original source.  The specification focuses solely on the exposed API and behavior as defined in the given files.

**Overall Namespace:** `ws`

**File Dependencies:** The implementation relies on:
*   `<fmt/format.h>` (for formatted output)
*   `<yaml-cpp/yaml.h>` (for YAML parsing)
*   `<sys/stat.h>` (for file status information)
*   `<execinfo.h>`, `<fcntl.h>`, `<sys/mman.h>`, `<sys/syscall.h>`, `<unistd.h>` (system calls for backtrace and memory mapping)
*   Standard library headers: `<algorithm>`, `<cassert>`, `<cerrno>`, `<initializer_list>`, `<iostream>`, `<iterator>`, `<memory>`, `<regex>`, `<sstream>`, `<string>`, `<string_view>`, `<utility>`, `<vector>`.

**Note:** This specification only covers the provided code. Any implicit behavior or assumptions not explicitly stated are outside the scope of this document.

---

### 1. `FileDescriptor` Type and Constants (F01/U01)

*   **Type Definition:**  `typedef int FileDescriptor;`
*   **Constant:** `constexpr FileDescriptor invalid_file_descriptor = -1;`
*   **Purpose:** Represents a file descriptor as an integer. The constant represents an invalid file descriptor value.

### 2. String Manipulation Functions (F01/U01, F02/U02)

*   **`StringToLower(std::string str) noexcept;`**:
    *   **Input:** A `std::string`.
    *   **Output:** A lowercase version of the input string.
    *   **Behavior:** Converts all characters in the input string to lowercase using `std::tolower()`.  The function is marked `noexcept`, indicating it will not throw exceptions.
*   **`StringToUpper(std::string str) noexcept;`**:
    *   **Input:** A `std::string`.
    *   **Output:** An uppercase version of the input string.
    *   **Behavior:** Converts all characters in the input string to uppercase using `std::toupper()`. The function is marked `noexcept`.
*   **`ReplaceAllSubstring(std::string_view str, std::string_view from, std::string_view to) noexcept;`**:
    *   **Input:** A source string (`str`), a substring to replace (`from`), and the replacement string (`to`). All inputs are `std::string_view`.
    *   **Output:** A new `std::string` with all occurrences of `from` replaced by `to`.
    *   **Behavior:** Iterates through the source string, finding all instances of the substring to replace.  The function is marked `noexcept`.
*   **`SplitString(const std::string& str, const std::regex& pattern) noexcept;`**:
    *   **Input:** A string (`str`) and a regular expression (`pattern`).
    *   **Output:** A `std::vector<std::string>` containing substrings of the input string separated by matches to the provided regex.
    *   **Behavior:** Uses `std::sregex_token_iterator` to split the string based on the given regular expression. The function is marked `noexcept`.
*   **`SplitStringToLines(const std::string& str) noexcept;`**:
    *   **Input:** A string (`str`).
    *   **Output:** A `std::vector<std::string>` containing lines of the input string.
    *   **Behavior:** Splits the string into lines based on newline characters (`\r*\n`) using a regular expression. The function is marked `noexcept`.

### 3. YAML Handling Functions (F01/U01, F02/U02)

*   **`LoadYamlString(std::string_view str, std::initializer_list<std::string_view> required_fields = {});`**:
    *   **Input:** A YAML string (`str`) and an optional list of required fields.
    *   **Output:** A `YAML::Node` representing the parsed YAML data.
    *   **Behavior:** Parses the input YAML string using `YAML::Load()`.  It then checks if all specified `required_fields` exist in the loaded YAML node, throwing a `std::invalid_argument` exception if any are missing.
*   **`ThrowIfYamlFieldIsNotScalar(const YAML::Node& node, std::string_view field);`**:
    *   **Input:** A YAML node (`node`) and a field name (`field`).
    *   **Output:** None (throws an exception).
    *   **Behavior:** Checks if the specified `field` exists in the YAML node and is a scalar value. If not, it throws a `std::invalid_argument` exception.

### 4. File Descriptor Utility Functions (F01/U01, F02/U02)

*   **`IsValidFileDescriptor(FileDescriptor fd) noexcept;`**:
    *   **Input:** A `FileDescriptor`.
    *   **Output:**  A `bool` indicating whether the file descriptor is valid (non-negative). The function is marked `noexcept`.
*   **`SetFileDescriptorAsNonblocking(FileDescriptor fd);`**:
    *   **Input:** A `FileDescriptor`.
    *   **Output:** None.
    *   **Behavior:** Sets the file descriptor to non-blocking mode using `fcntl()`. Throws a `std::system_error` if the operation fails. Requires that the input is a valid file descriptor.
*   **`ThrowLastSystemError();`**:
    *   **Input:** None.
    *   **Output:** None (throws an exception).
    *   **Behavior:** Throws a `std::system_error` exception containing information about the last system error that occurred (obtained from `errno`).

### 5. Thread and Backtrace Functions (F01/U01, F02/U02)

*   **`CurrentThreadId() noexcept;`**:
    *   **Input:** None.
    *   **Output:** A `std::uint32_t` representing the ID of the current thread. The function is marked `noexcept`.
*   **`Backtrace(std::vector<std::string>& stack, std::size_t size, std::size_t skip = 0) noexcept;`**:
    *   **Input:** A reference to a vector of strings (`stack`), the maximum number of frames to capture (`size`), and an optional number of frames to skip (`skip`).
    *   **Output:** None (modifies the input `stack` vector).
    *   **Behavior:** Captures a backtrace using `backtrace()` and `backtrace_symbols()`, storing the stack trace strings in the provided vector. The function is marked `noexcept`.
*   **`Backtrace(std::size_t size, std::size_t skip = 0, std::string_view prefix = "") noexcept;`**:
    *   **Input:** The maximum number of frames to capture (`size`), an optional number of frames to skip (`skip`), and an optional prefix string.
    *   **Output:** A `std::string` containing the formatted backtrace.
    *   **Behavior:** Captures a backtrace (using the other `Backtrace` function) and formats it into a single string, prepending each line with the provided `prefix`. The function is marked `noexcept`.

### 6. Smart Pointers & RAII Helpers (F01/U01)

*   **`Singleton<T, Args...>`**: A template class providing a simple singleton pattern implementation.
    *   **`Instance()`:** Returns a reference to the single instance of type `T`, creating it on first use with the provided arguments (`Args...`).  The function is marked `noexcept`.
*   **`SingletonPtr<T, Args...>`**: A template class providing a singleton pattern implementation using `std::shared_ptr`.
    *   **`Instance()`:** Returns a `std::shared_ptr` to the single instance of type `T`, creating it on first use with the provided arguments (`Args...`). The function is marked `noexcept`.
*   **`RAII<T, Cleaner>`**: A template class implementing Resource Acquisition Is Initialization (RAII).
    *   **Constructor:** Takes an object `obj` and a cleaner function `cleaner`, storing them.
    *   **Destructor:** Calls the `cleaner` function with the stored `obj`.
    *   **`Object()`:** Returns a const reference to the managed object.
    *   Requires that the provided `Cleaner` is callable with an argument of type `T`.

### 7. MappedReadOnlyFile Class (F01/U01, F02/U02)

*   **Purpose:** Provides a way to memory-map a file for read-only access.
*   **Constructor:** Default constructor and move constructor. Copy constructor and assignment operator are deleted.
*   **Destructor:** Unmaps the file if it was mapped.
*   **`Map(std::string path)`**:
    *   **Input:** The path to the file.
    *   **Output:** A `std::byte*` pointer to the beginning of the mapped region.
    *   **Behavior:** Opens the specified file in read-only mode, checks its permissions and type (must be a regular file), memory maps it using `mmap()`, and returns a pointer to the mapped data. Throws exceptions on error.
*   **`Unmap() noexcept;`**: Unmaps the file if it is currently mapped.
*   **`Size() const noexcept;`**: Returns the size of the mapped file in bytes.
*   **`Data() const noexcept;`**: Returns a pointer to the beginning of the mapped data.
*   **`Path() const noexcept;`**: Returns a `std::string_view` representing the path to the mapped file.
*   **`Check()`:** Internal helper function that validates the file path and permissions before mapping.

### 8. Type Concept (F01/U01)

* **`Addable<T, U, Ret>`**: A concept that checks if types `T` and `U` can be added together to produce a result convertible to type `Ret`.
