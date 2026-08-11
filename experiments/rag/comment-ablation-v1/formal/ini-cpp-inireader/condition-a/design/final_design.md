# Design Specification for Reimplementation of INIReader Class

## Overview
This document provides a detailed design specification for the `INIReader` class, which is responsible for parsing and managing INI configuration files. The goal is to ensure that another developer can accurately reimplement this class without needing access to the original source code.

## Target Audience
- Developers tasked with reimplementing the `INIReader` class.
- Reviewers who need to verify the correctness of the reimplementation.

## Class Definition

### Namespace and File Path
- **Namespace**: Not explicitly defined in the provided snippet, but should be preserved if present.
- **File Path**: `ini/ini.h`

### Class Name
- **Class Name**: `INIReader`

### Public Members

#### Constructors
1. **Default Constructor**
   - **Signature**: `INIReader() = default;`
   - **Description**: Initializes an empty `INIReader` object.

2. **Filename Constructor**
   - **Signature**: `INIReader(const std::string& filename);`
   - **Description**: Opens and reads the specified INI file, parsing its contents into memory.
   - **Error Handling**: Throws a `std::runtime_error` if the file cannot be opened or read.

3. **File Pointer Constructor**
   - **Signature**: `INIReader(std::FILE* file);`
   - **Description**: Reads from the provided file pointer, parsing the INI content into memory.
   - **Error Handling**: None specified in the snippet.

#### Methods
1. **ParseError Method**
   - **Signature**: `int ParseError() const;`
   - **Description**: Checks for and reports any errors encountered during parsing.
   - **Return Value**: Returns 0 if no error, otherwise throws a `std::runtime_error` with an appropriate message.

2. **Sections Method**
   - **Signature**: `std::set<std::string> Sections() const;`
   - **Description**: Retrieves all section names from the parsed INI file.
   - **Return Value**: A set of strings representing the section names.

3. **Keys Method**
   - **Signature**: `std::set<std::string> Keys(const std::string& section) const;`
   - **Description**: Retrieves all key names within a specified section.
   - **Parameters**:
     - `section`: The name of the section to query.
   - **Return Value**: A set of strings representing the keys in the specified section.

4. **Get Method (Overloaded)**
   - **Signature 1**: `std::unordered_map<std::string, std::string> Get(const std::string& section) const;`
     - **Description**: Retrieves all key-value pairs within a specified section.
     - **Parameters**:
       - `section`: The name of the section to query.
     - **Return Value**: A map of strings representing the keys and values in the specified section.

   - **Signature 2**: `template <typename T = std::string> T Get(const std::string& section, const std::string& name) const;`
     - **Description**: Retrieves a value for a specific key within a section.
     - **Parameters**:
       - `section`: The name of the section to query.
       - `name`: The name of the key to retrieve.
     - **Return Value**: The value associated with the specified key, converted to type `T`.
     - **Error Handling**: Throws a `std::runtime_error` if the key is not found.

   - **Signature 3**: `template <typename T> T Get(const std::string& section, const std::string& name, T&& default_v) const;`
     - **Description**: Retrieves a value for a specific key within a section, with a default value.
     - **Parameters**:
       - `section`: The name of the section to query.
       - `name`: The name of the key to retrieve.
       - `default_v`: The default value to return if the key is not found.
     - **Return Value**: The value associated with the specified key, or the default value if the key is not found.

5. **GetVector Method (Overloaded)**
   - **Signature 1**: `template <typename T = std::string> std::vector<T> GetVector(const std::string& section, const std::string& name) const;`
     - **Description**: Retrieves a vector of values for a specific key within a section.
     - **Parameters**:
       - `section`: The name of the section to query.
       - `name`: The name of the key to retrieve.
     - **Return Value**: A vector of type `T` containing the parsed values.
     - **Error Handling**: Throws a `std::runtime_error` if parsing fails.

   - **Signature 2**: `template <typename T> std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const;`
     - **Description**: Retrieves a vector of values for a specific key within a section, with a default value.
     - **Parameters**:
       - `section`: The name of the section to query.
       - `name`: The name of the key to retrieve.
       - `default_v`: The default vector to return if parsing fails.
     - **Return Value**: A vector of type `T` containing the parsed values, or the default vector if parsing fails.

6. **InsertEntry Method (Overloaded)**
   - **Signature 1**: `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const T& v);`
     - **Description**: Inserts a new key-value pair into the specified section.
     - **Parameters**:
       - `section`: The name of the section to modify.
       - `name`: The name of the key to insert.
       - `v`: The value to associate with the key.
     - **Error Handling**: Throws a `std::runtime_error` if the key already exists.

   - **Signature 2**: `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs);`
     - **Description**: Inserts a new key-vector pair into the specified section.
     - **Parameters**:
       - `section`: The name of the section to modify.
       - `name`: The name of the key to insert.
       - `vs`: The vector of values to associate with the key.
     - **Error Handling**: Throws a `std::runtime_error` if the key already exists.

7. **UpdateEntry Method (Overloaded)**
   - **Signature 1**: `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const T& v);`
     - **Description**: Updates an existing key-value pair in the specified section.
     - **Parameters**:
       - `section`: The name of the section to modify.
       - `name`: The name of the key to update.
       - `v`: The new value to associate with the key.

   - **Signature 2**: `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs);`
     - **Description**: Updates an existing key-vector pair in the specified section.
     - **Parameters**:
       - `section`: The name of the section to modify.
       - `name`: The name of the key to update.
       - `vs`: The new vector of values to associate with the key.

### Protected Members

#### Member Variables
1. **_error**
   - **Type**: `int`
   - **Description**: Stores error codes encountered during parsing.

2. **_values**
   - **Type**: `std::unordered_map<std::string, std::unordered_map<std::string, std::string>>`
   - **Description**: Maps section names to key-value pairs within those sections.

#### Methods
1. **Converter Method (Template)**
   - **Signature**: `template <typename T> T Converter(const std::string& s) const;`
   - **Description**: Converts a string to the specified type.
   - **Parameters**:
     - `s`: The string to convert.
   - **Return Value**: The converted value of type `T`.
   - **Error Handling**: Throws a `std::runtime_error` if conversion fails.

2. **BoolConverter Method**
   - **Signature**: `bool BoolConverter(std::string s) const;`
   - **Description**: Converts a string to a boolean value.
   - **Parameters**:
     - `s`: The string to convert.
   - **Return Value**: A boolean value.
   - **Error Handling**: Throws a `std::runtime_error` if the string is not a valid boolean.

3. **V2String Method (Template)**
   - **Signature**: `template <typename T> std::string V2String(const T& v) const;`
   - **Description**: Converts a value to a string.
   - **Parameters**:
     - `v`: The value to convert.
   - **Return Value**: A string representation of the value.

4. **Vec2String Method (Template)**
   - **Signature**: `template <typename T> std::string Vec2String(const std::vector<T>& v) const;`
   - **Description**: Converts a vector of values to a space-separated string.
   - **Parameters**:
     - `v`: The vector to convert.
   - **Return Value**: A string representation of the vector.

### Private Members

#### Methods
1. **GetSection Method**
   - **Signature**: `const std::unordered_map<std::string, std::string>& GetSection(const std::string& section) const;`
   - **Description**: Retrieves a reference to the key-value pairs within a specified section.
   - **Parameters**:
     - `section`: The name of the section to query.
   - **Return Value**: A constant reference to the map of keys and values in the specified section.
   - **Error Handling**: Throws a `std::runtime_error` if the section is not found.

2. **FindEntry Method**
   - **Signature**: `std::string& FindEntry(const std::string& section, const std::string& name);`
   - **Description**: Retrieves a reference to the value associated with a specific key within a section.
   - **Parameters**:
     - `section`: The name of the section to query.
     - `name`: The name of the key to retrieve.
   - **Return Value**: A reference to the string value associated with the specified key.
   - **Error Handling**: Throws a `std::runtime_error` if the key does not exist.

3. **Parse Method**
   - **Signature**: `void Parse(std::string_view content);`
   - **Description**: Parses the provided INI content into memory.
   - **Parameters**:
     - `content`: The string view containing the INI content to parse.
   - **Error Handling**: Sets `_error` to a non-zero value and breaks parsing if an error is encountered.

## Implementation Notes
- Ensure that all methods handle errors appropriately, throwing exceptions as specified.
- Preserve the use of templates for type conversion and vector handling.
- Maintain the structure and logic of the original class, including the use of helper functions like `detail::trim`, `detail::find_char_or_comment`, and `detail::is_space`.
- Ensure that all member variables are properly initialized and managed.

## Conclusion
This design specification provides a comprehensive guide for reimplementing the `INIReader` class. By following this document, developers can create an equivalent implementation without needing access to the original source code.