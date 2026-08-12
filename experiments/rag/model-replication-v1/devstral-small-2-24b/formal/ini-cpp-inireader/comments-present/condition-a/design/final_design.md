# INIReader Class Design Specification

## Overview
The `INIReader` class is a C++ utility for parsing and manipulating INI configuration files. It provides methods to read sections, keys, and values from an INI file, as well as methods to insert and update entries.

## Class Structure

### Public Interface

#### Constructors
1. **Default Constructor**
   - `INIReader() = default;`
   - Creates an empty INI reader instance

2. **File Constructor**
   - `INIReader(const std::string& filename)`
   - Parameters:
     - `filename`: Path to the INI file
   - Throws: `std::runtime_error` if file cannot be opened or parsed
   - Behavior:
     - Reads entire file content into memory
     - Parses content using internal `Parse()` method
     - Sets error state via `ParseError()`

3. **File Pointer Constructor**
   - `INIReader(std::FILE* file)`
   - Parameters:
     - `file`: Pointer to an open file stream
   - Throws: `std::runtime_error` if parsing fails
   - Behavior:
     - Reads content in chunks using `fread()`
     - Parses content using internal `Parse()` method

#### Error Handling
- `int ParseError() const`
  - Returns: 0 on success
  - Throws: `std::runtime_error` with specific error message based on `_error` value:
    - `-1`: "ini file not found."
    - `-2`: "memory alloc error"
    - Other negative values: "parse error on line no: X"

#### Data Access Methods
- `std::set<std::string> Sections() const`
  - Returns all section names in the INI file

- `std::set<std::string> Keys(const std::string& section) const`
  - Parameters:
    - `section`: Name of section to query
  - Returns: All key names in specified section
  - Throws: `std::runtime_error` if section not found

- `std::unordered_map<std::string, std::string> Get(const std::string& section) const`
  - Parameters:
    - `section`: Name of section to retrieve
  - Returns: Map of all key-value pairs in section
  - Throws: `std::runtime_error` if section not found

- Template method `T Get(const std::string& section, const std::string& name) const`
  - Parameters:
    - `section`: Section containing the key
    - `name`: Key to retrieve
    - `T`: Type to convert value to (defaults to `std::string`)
  - Returns: Value converted to type T
  - Throws: `std::runtime_error` if section/key not found or conversion fails

- Template method `T Get(const std::string& section, const std::string& name, T&& default_v) const`
  - Overload with default value
  - Returns: Value converted to type T, or default_v if key not found

#### Vector Operations
- Template method `std::vector<T> GetVector(const std::string& section, const std::string& name) const`
  - Parses space-separated values into vector
  - Example: "1 2 3" → {1, 2, 3}
  - Throws: `std::runtime_error` if parsing fails

- Template method `std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const`
  - Overload with default vector value

#### Modification Methods
- Template method `void InsertEntry(const std::string& section, const std::string& name, const T& v)`
  - Adds new key-value pair to section
  - Throws: `std::runtime_error` if key already exists

- Template method `void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`
  - Overload for vector values

- Template method `void UpdateEntry(const std::string& section, const std::string& name, const T& v)`
  - Updates existing key-value pair
  - Throws: `std::runtime_error` if key doesn't exist

- Template method `void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`
  - Overload for vector values

### Protected Members
- `_error`: Integer flag indicating parse status (0=success, negative=error)
- `_values`: Nested unordered_map storing parsed data as `section → key → value`

### Private Helper Methods
1. **Type Conversion**
   - `T Converter(const std::string& s) const`
     - Uses `detail::parse_value()` helper (not shown in code)
     - Throws on conversion failure

2. **Boolean Conversion**
   - `bool BoolConverter(std::string s) const`
     - Case-insensitive parsing of: 1/0, true/false, yes/no, on/off
     - Throws for invalid values

3. **Serialization**
   - `std::string V2String(const T& v) const`
     - Converts value to string using `operator<<`
   - `std::string Vec2String(const std::vector<T>& v) const`
     - Serializes vector as space-separated values

4. **Data Access**
   - `const std::unordered_map<std::string, std::string>& GetSection(const std::string& section) const`
     - Retrieves section map
     - Throws if section not found
   - `std::string& FindEntry(const std::string& section, const std::string& name)`
     - Finds and returns reference to value
     - Throws if key not found

5. **Parsing**
   - `void Parse(std::string_view content)`
     - Main parsing logic with these rules:
       - `[section]` lines define sections (text after ']' ignored)
       - `name = value` or `name : value` pairs
       - Lines starting with ';' or '#' are comments
       - ';' preceded by whitespace starts inline comment
     - Handles UTF-8 BOM
     - Tracks first faulty line in `_error`
     - Throws on duplicate keys

## Implementation Notes

1. **String Handling**
   - Uses `std::string_view` for efficient parsing
   - Relies on `detail::trim()` and `detail::is_space()` helpers (not shown)

2. **Error Handling Strategy**
   - Immediate throw for critical errors (file not found, memory issues)
   - Deferred throw via `ParseError()` for parse errors

3. **Template Specialization**
   - Default template parameter allows type deduction
   - Explicit specialization for string and bool types

4. **Memory Management**
   - Reads entire file into memory for parsing
   - Uses efficient chunked reading for FILE* constructor

5. **INI Format Support**
   - Supports both `=` and `:` as value separators
   - Handles inline comments (semicolon after whitespace)
   - Case-sensitive section/key names

## Dependencies

1. Standard Library Components:
   - `<fstream>` for file I/O
   - `<unordered_map>` for data storage
   - `<set>` for ordered key/section lists
   - `<sstream>` for string conversion
   - `<stdexcept>` for exceptions
   - `<string_view>` for efficient parsing

2. External Helpers (not shown in code):
   - `detail::parse_value()`: Type conversion utility
   - `detail::trim()`: String trimming
   - `detail::is_space()`: Whitespace checking
   - `detail::find_char_or_comment()`: Position finding with comment awareness

## Usage Examples

```cpp
// Reading values
INIReader reader("config.ini");
int value = reader.Get<int>("section", "key");
std::vector<float> vec = reader.GetVector<float>("section", "vec_key");

// Modifying data
reader.InsertEntry("new_section", "new_key", 42);
reader.UpdateEntry("existing_section", "existing_key", true);

// Error handling
try {
    auto val = reader.Get<int>("missing_section", "key");
} catch (const std::runtime_error& e) {
    // Handle error
}
```

This specification provides all necessary information for a complete reimplementation of the `INIReader` class while preserving all original functionality and behavior.