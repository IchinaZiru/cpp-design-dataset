# Parser Class Design Specification

## Overview
The `Parser` class is a utility class for parsing hexadecimal data from input streams into memory. It provides two main parsing methods: one for byte-level parsing and another for word-level (32-bit) parsing.

## Class Structure

### Namespace
- The class is defined in the global namespace (no explicit namespace declaration)

### Dependencies
- `<string>` - For string operations
- `<sstream>` - For string stream operations
- `<iostream>` - For input/output stream operations
- `Memory` class (external dependency) - For memory access

## Public Interface

### Static Methods

#### 1. `parse_hex`
```cpp
static unsigned parse_hex(const std::string &hex)
```
- **Purpose**: Converts a hexadecimal string to an unsigned integer
- **Parameters**:
  - `hex`: Input string containing hexadecimal value (e.g., "A3", "1F")
- **Returns**: Unsigned integer representation of the hex string
- **Implementation Details**:
  - Uses `strtol` with base 16 for conversion
  - Returns 0 on error (default behavior of `strtol`)

#### 2. `parse`
```cpp
static void parse(std::istream &in, Memory &mem)
```
- **Purpose**: Parses hexadecimal data from input stream into memory byte by byte
- **Parameters**:
  - `in`: Input stream containing hex data (one value per line or space-separated)
  - `mem`: Memory object to write parsed data to
- **Behavior**:
  - Lines starting with '@' set the base address (hexadecimal value after '@')
  - Other lines contain space-separated hex values to be written to memory
  - Each hex value is converted and stored as a byte in memory
  - Base address increments by 1 for each byte written

#### 3. `parse_hex`
```cpp
static void parse_hex(std::istream &in, Memory &mem)
```
- **Purpose**: Parses hexadecimal data from input stream into memory word by word (32-bit)
- **Parameters**:
  - `in`: Input stream containing hex data (one value per line or space-separated)
  - `mem`: Memory object to write parsed data to
- **Behavior**:
  - Reads all hex values from the stream
  - Each hex value is converted and written as a 32-bit word to memory
  - Base address increments by 4 for each word written

## Error Handling
- Both parsing methods check if the input stream is valid at the start
- Invalid streams result in an error message printed to `std::cerr`
- No exceptions are thrown; errors are reported via `std::cerr`

## Implementation Notes
1. The class uses only static methods, making it a utility/class without state
2. Memory access is delegated to the `Memory` class through its interface
3. The parser assumes:
   - Hex strings are properly formatted (no validation)
   - Input stream contains valid hexadecimal data
   - Memory object can handle the requested write operations

## Example Usage
```cpp
// Byte-level parsing
Parser::parse(std::cin, memory);

// Word-level parsing
Parser::parse_hex(std::cin, memory);
```

This specification provides all necessary information for a different LLM to reimplement the `Parser` class while maintaining identical functionality and interface.