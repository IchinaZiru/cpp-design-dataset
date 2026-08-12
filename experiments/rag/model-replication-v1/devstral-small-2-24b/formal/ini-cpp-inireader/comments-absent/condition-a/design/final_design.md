# INIReader Class Design Specification

## Overview
The `INIReader` class is designed to read and manipulate INI configuration files. It provides functionality to parse INI files, access sections and keys, retrieve values with type conversion, and modify the configuration data.

## Class Structure

### Public Interface

#### Constructors
1. **Default Constructor**
   - Initializes an empty `INIReader` instance
   - No parameters required

2. **File Path Constructor**
   - Parameters: `const std::string& filename`
   - Reads and parses the INI file at the specified path
   - Throws exceptions on file not found or parse errors

3. **FILE* Constructor**
   - Parameters: `std::FILE* file`
   - Reads and parses content from an open FILE pointer
   - Does not close the file handle

#### Core Methods

1. **Error Handling**
   - `int ParseError() const` - Throws exceptions based on parse errors:
     - `-1`: File not found
     - `-2`: Memory allocation error
     - Other values: Parse error with line number

2. **Section Management**
   - `std::set<std::string> Sections() const` - Returns all section names
   - `std::set<std::string> Keys(const std::string& section) const` - Returns keys in a specific section

3. **Value Retrieval**
   - `Get(section)` - Returns all key-value pairs in a section
   - `Get<T>(section, name)` - Template method to get typed values:
     - Supports string, bool, and other types via converter
     - Throws if key not found or conversion fails
   - `Get<T>(section, name, default_v)` - Version with default value fallback

4. **Vector Handling**
   - `GetVector<T>(section, name)` - Parses space-separated values into vector
   - `GetVector<T>(section, name, default_v)` - With default value fallback

5. **Modification Methods**
   - `InsertEntry<T>(section, name, v)` - Adds new key-value pair
   - `UpdateEntry<T>(section, name, v)` - Updates existing key-value pair
   - Both support single values and vectors

### Protected Members
- `_error` - Integer error code (0 = success)
- `_values` - Nested unordered_map storing section → key → value data

### Private Helper Methods
1. **Type Conversion**
   - `Converter<T>(s)` - Template method for string-to-type conversion
   - `BoolConverter(s)` - Specialized boolean conversion with case-insensitive matching
   - `V2String(v)` - Converts values to strings
   - `Vec2String(vs)` - Converts vectors to space-separated strings

2. **Data Access**
   - `GetSection(section)` - Returns section data or throws if not found
   - `FindEntry(section, name)` - Locates and returns reference to value

3. **Parsing**
   - `Parse(content)` - Main parsing logic:
     - Handles BOM removal
     - Processes sections and key-value pairs
     - Skips comments (lines starting with ; or #)
     - Tracks line numbers for error reporting

## Implementation Details

### Data Storage
- Uses nested unordered_maps: `_values[section][key] = value`
- All values stored as strings internally, converted on retrieval

### Error Handling Strategy
- Throws `std::runtime_error` for all error conditions
- Provides detailed error messages including line numbers where applicable

### Type Conversion System
- Template-based conversion system with specialization for:
  - String (identity)
  - Boolean (with multiple true/false representations)
  - Numeric types (via detail::parse_value)
  - Custom types (if detail::parse_value supports them)

## Dependencies
- Requires C++17 or later features
- Uses standard library components:
  - `<fstream>` for file I/O
  - `<unordered_map>`, `<set>`, `<vector>`
  - `<string_view>` for parsing efficiency
  - `<sstream>` for string conversion

## Assumptions and Notes
1. The `detail` namespace contains helper functions not shown in this specification:
   - `is_space()`
   - `trim()`, `rtrim()`
   - `find_char_or_comment()`
   - `parse_value()` for type conversion

2. The class maintains internal consistency by throwing on duplicate keys during parsing and modification.

3. All string operations are UTF-8 compatible (BOM handling, character processing).

4. The implementation is designed to be efficient with:
   - Memory-mapped file reading
   - String_view usage in parsing
   - Minimal copying of data

This specification provides all necessary information for a complete reimplementation while preserving the original behavior and interface.