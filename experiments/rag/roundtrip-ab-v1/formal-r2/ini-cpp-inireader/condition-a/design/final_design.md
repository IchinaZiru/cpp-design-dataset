# Design Specification for INIReader Class

## Overview

The `INIReader` class is designed to parse and manage INI files. It provides methods to read, insert, update, and retrieve values from an INI file. The class handles parsing errors and supports various data types including strings, booleans, and vectors.

## Namespace and File Location

- **Namespace**: Not explicitly defined in the provided code snippet.
- **File Path**: `ini/ini.h`

## Class Definition

### Class Name
`INIReader`

### Constructors

1. **Default Constructor**
   - **Signature**: `INIReader() = default;`
   - **Description**: Initializes an empty `INIReader` object.

2. **Constructor from File Name**
   - **Signature**: `INIReader(const std::string& filename)`
   - **Parameters**:
     - `filename`: The name of the INI file to parse.
   - **Exceptions**:
     - Throws `std::runtime_error` if there is an error parsing the INI file.

3. **Constructor from File Pointer**
   - **Signature**: `INIReader(std::FILE* file)`
   - **Parameters**:
     - `file`: A pointer to the INI file to parse.
   - **Exceptions**:
     - Throws `std::runtime_error` if there is an error parsing the INI file.

### Public Methods

1. **ParseError**
   - **Signature**: `int ParseError() const`
   - **Description**: Returns the result of the parse operation.
   - **Return Value**:
     - `0`: On success.
   - **Exceptions**:
     - Throws `std::runtime_error` on file open or parse error.

2. **Sections**
   - **Signature**: `std::set<std::string> Sections() const`
   - **Description**: Returns the list of sections found in the INI file.
   - **Return Value**:
     - A set of section names.

3. **Keys**
   - **Signature**: `std::set<std::string> Keys(const std::string& section) const`
   - **Parameters**:
     - `section`: The name of the section.
   - **Description**: Returns the list of keys in the specified section.
   - **Return Value**:
     - A set of key names.

4. **Get (Section Map)**
   - **Signature**: `std::unordered_map<std::string, std::string> Get(const std::string& section) const`
   - **Parameters**:
     - `section`: The name of the section.
   - **Description**: Returns a map representing the values in the specified section.
   - **Exceptions**:
     - Throws `std::runtime_error` if the section is not found.

5. **Get (Value by Key)**
   - **Signature**: `template <typename T = std::string> T Get(const std::string& section, const std::string& name) const`
   - **Parameters**:
     - `section`: The name of the section.
     - `name`: The key name.
   - **Description**: Returns the value of the specified key in the given section.
   - **Exceptions**:
     - Throws `std::runtime_error` if the section/key is not found or the value cannot be parsed to type `T`.

6. **Get with Default (Value by Key)**
   - **Signature**: `template <typename T> T Get(const std::string& section, const std::string& name, T&& default_v) const`
   - **Parameters**:
     - `section`: The name of the section.
     - `name`: The key name.
     - `default_v`: The default value to return if the key is not found.
   - **Description**: Returns the value of the specified key in the given section, or the default value if the key is not found.

7. **GetVector (Value Array by Key)**
   - **Signature**: `template <typename T = std::string> std::vector<T> GetVector(const std::string& section, const std::string& name) const`
   - **Parameters**:
     - `section`: The name of the section.
     - `name`: The key name.
   - **Description**: Returns a vector of values for the specified key in the given section.
   - **Exceptions**:
     - Throws `std::runtime_error` if the value cannot be parsed to a vector.

8. **GetVector with Default (Value Array by Key)**
   - **Signature**: `template <typename T> std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const`
   - **Parameters**:
     - `section`: The name of the section.
     - `name`: The key name.
     - `default_v`: The default vector to return if the key is not found.
   - **Description**: Returns a vector of values for the specified key in the given section, or the default vector if the key is not found.

9. **InsertEntry (Single Value)**
   - **Signature**: `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const T& v)`
   - **Parameters**:
     - `section`: The name of the section.
     - `name`: The key name.
     - `v`: The value to insert.
   - **Exceptions**:
     - Throws `std::runtime_error` if the key already exists in the section.

10. **InsertEntry (Vector of Values)**
    - **Signature**: `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`
    - **Parameters**:
      - `section`: The name of the section.
      - `name`: The key name.
      - `vs`: The vector of values to insert.
    - **Exceptions**:
      - Throws `std::runtime_error` if the key already exists in the section.

11. **UpdateEntry (Single Value)**
    - **Signature**: `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const T& v)`
    - **Parameters**:
      - `section`: The name of the section.
      - `name`: The key name.
      - `v`: The new value to set.
    - **Exceptions**:
      - Throws `std::runtime_error` if the key does not exist in the section.

12. **UpdateEntry (Vector of Values)**
    - **Signature**: `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`
    - **Parameters**:
      - `section`: The name of the section.
      - `name`: The key name.
      - `vs`: The new vector of values to set.
    - **Exceptions**:
      - Throws `std::runtime_error` if the key does not exist in the section.

### Protected Methods

1. **Converter**
   - **Signature**: `template <typename T> T Converter(const std::string& s) const`
   - **Parameters**:
     - `s`: The string to parse.
   - **Description**: Parses a string as a specified type `T`.
   - **Exceptions**:
     - Throws `std::runtime_error` on failure.

2. **BoolConverter**
   - **Signature**: `bool BoolConverter(std::string s) const`
   - **Parameters**:
     - `s`: The string to parse.
   - **Description**: Parses a boolean token from the string.
   - **Exceptions**:
     - Throws `std::runtime_error` if the string is not a valid boolean value.

3. **V2String**
   - **Signature**: `template <typename T> std::string V2String(const T& v) const`
   - **Parameters**:
     - `v`: The value to serialize.
   - **Description**: Serializes a value with the `operator<<`.

4. **Vec2String**
   - **Signature**: `template <typename T> std::string Vec2String(const std::vector<T>& v) const`
   - **Parameters**:
     - `v`: The vector of values to serialize.
   - **Description**: Serializes a vector as space-separated values.

### Private Methods

1. **GetSection**
   - **Signature**: `const std::unordered_map<std::string, std::string>& GetSection(const std::string& section) const`
   - **Parameters**:
     - `section`: The name of the section.
   - **Description**: Returns a reference to the map representing the values in the specified section.
   - **Exceptions**:
     - Throws `std::runtime_error` if the section is not found.

2. **FindEntry**
   - **Signature**: `std::string& FindEntry(const std::string& section, const std::string& name)`
   - **Parameters**:
     - `section`: The name of the section.
     - `name`: The key name.
   - **Description**: Finds and returns a reference to the value for the specified key in the given section.
   - **Exceptions**:
     - Throws `std::runtime_error` if the key does not exist in the section.

3. **Parse**
   - **Signature**: `void Parse(std::string_view content)`
   - **Parameters**:
     - `content`: The INI file content as a string view.
   - **Description**: Parses the whole INI content according to the specified grammar and records the first faulty line in `_error`.

### Member Variables

1. **_error**
   - **Type**: `int`
   - **Description**: Parse result: `0` on success, `-1` on file open error, otherwise the number of the first faulty line.

2. **_values**
   - **Type**: `std::unordered_map<std::string, std::unordered_map<std::string, std::string>>`
   - **Description**: Parsed content, as `_values[section][name] = value`.

## Detailed Design

### Parsing Logic

- The `Parse` method processes the INI file content line by line.
- It handles:
  - Blank lines and comments (lines starting with `;` or `#`).
  - Section headers (`[section]`).
  - Key-value pairs (`name = value` or `name : value`).
- The method trims whitespace, ignores inline comments, and records the first faulty line in `_error`.

### Error Handling

- The class throws `std::runtime_error` for various error conditions such as file open errors, parse errors, duplicate keys, missing sections/keys, and invalid boolean values.

### Data Conversion

- The `Converter` method handles parsing strings to specified types.
- The `BoolConverter` method parses boolean tokens in a case-insensitive manner.
- The `V2String` and `Vec2String` methods serialize values and vectors respectively using the `operator<<`.

## Conclusion

The `INIReader` class provides comprehensive functionality for reading, writing, and managing INI files. It ensures robust error handling and supports various data types, making it a versatile tool for configuration file management in C++ applications.