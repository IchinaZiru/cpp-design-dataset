## Design Specification: INIReader Class

**Document Version:** 1.0
**Date:** October 26, 2023
**Author:** LLM Assistant

This document details the design specification for the `INIReader` class based on the provided C++ source code (`ini/ini.h`).  It is intended to guide the re-implementation of this class by another Large Language Model (LLM). This specification focuses solely on the information available within the given input and avoids making any assumptions or inferences beyond it.

**1. Overview**

The `INIReader` class parses INI files and provides access to their contents. It supports reading from a filename, file pointer, or string content.  It handles basic error checking during parsing and provides methods for retrieving values as strings, booleans, numbers, vectors of strings, and other types using template-based conversion.

**2. Class Definition**

```cpp
class INIReader {
   public:
    INIReader() = default;

    INIReader(const std::string& filename);
    INIReader(std::FILE* file);

    int ParseError() const;

    std::set<std::string> Sections() const;
    std::set<std::string> Keys(const std::string& section) const;
    std::unordered_map<std::string, std::string> Get(
        const std::string& section) const;

    template <typename T = std::string>
    T Get(const std::string& section, const std::string& name) const;

    template <typename T>
    T Get(const std::string& section, const std::string& name,
          T&& default_v) const;

    template <typename T = std::string>
    std::vector<T> GetVector(const std::string& section,
                             const std::string& name) const;

    template <typename T>
    std::vector<T> GetVector(const std::string& section,
                             const std::string& name,
                             const std::vector<T>& default_v) const;

    template <typename T = std::string>
    void InsertEntry(const std::string& section, const std::string& name,
                     const T& v);

    template <typename T = std::string>
    void InsertEntry(const std::string& section, const std::string& name,
                     const std::vector<T>& vs);

    template <typename T = std::string>
    void UpdateEntry(const std::string& section, const std::string& name,
                     const T& v);

    template <typename T = std::string>
    void UpdateEntry(const std::string& section, const std::string& name,
                     const std::vector<T>& vs);

   protected:
    int _error;
    std::unordered_map<std::string,
                       std::unordered_map<std::string, std::string>>
        _values;

    template <typename T>
    T Converter(const std::string& s) const;

    bool BoolConverter(std::string s) const;

    template <typename T>
    std::string V2String(const T& v) const;

    template <typename T>
    std::string Vec2String(const std::vector<T>& v) const;

   private:
    const std::unordered_map<std::string, std::string>& GetSection(
        const std::string& section) const;

    std::string& FindEntry(const std::string& section,
                           const std::string& name);

    void Parse(std::string_view content);
};
```

**3. Member Variables**

*   `_error`:  An integer representing the error state of the parser. Values: 0 (no error), -1 (file not found), -2 (memory allocation error), and a positive value indicating the line number where an error occurred during parsing.
*   `_values`: A nested `std::unordered_map` storing the parsed INI data. The outer map's key is the section name (string).  The inner map's key is the key name within that section (string), and its value is the corresponding string value.

**4. Constructors**

*   `INIReader()`: Default constructor. Initializes `_error` to 0.
*   `INIReader(const std::string& filename)`: Constructor taking a filename as input.  It attempts to open the file, read its contents into a string, and then parse the content using the `Parse` method. Sets `_error` appropriately if the file cannot be opened or parsing fails.
*   `INIReader(std::FILE* file)`: Constructor taking a file pointer as input. It reads the entire file content into a string and parses it using the `Parse` method.  Sets `_error` appropriately if reading fails or parsing fails.

**5. Methods**

*   `int ParseError() const`: Throws a `std::runtime_error` based on the value of `_error`. The error messages are:
    *   `-1`: "ini file not found."
    *   `-2`: "memory alloc error"
    *   Otherwise: "parse error on line no: [line number]"
    Returns 0.

*   `std::set<std::string> Sections() const`: Returns a set of all section names present in the INI file.  Iterates through the outer map (`_values`) and extracts the keys (section names).

*   `std::set<std::string> Keys(const std::string& section) const`: Returns a set of all key names within a given section. Retrieves the inner map for the specified section using `GetSection()` and then iterates through its keys.

*   `std::unordered_map<std::string, std::string> Get(const std::string& section) const`:  Returns a copy of the inner map (key-value pairs as strings) for the given section. Uses `GetSection()` to retrieve the map and returns it.

*   `template <typename T = std::string> T Get(const std::string& section, const std::string& name) const`: Retrieves a value from the specified section with the given key.  It converts the string value to the template parameter type `T`.
    *   If `T` is `std::string`, it returns the string directly.
    *   If `T` is `bool`, it uses `BoolConverter()` to convert the string to a boolean.
    *   Otherwise, it uses `Converter<T>()` to perform the conversion.
    Throws a `std::runtime_error` if the key is not found in the section.

*   `template <typename T> T Get(const std::string& section, const std::string& name, T&& default_v) const`:  Attempts to retrieve a value using `Get<T>(section, name)`. If a `std::runtime_error` is caught (key not found), it returns the provided `default_v`.

*   `template <typename T = std::string> std::vector<T> GetVector(const std::string& section, const std::string& name) const`: Retrieves a string value from the specified section and key, then attempts to parse it as a vector of type `T`.  It splits the string by spaces. Throws a `std::runtime_error` if parsing fails.

*   `template <typename T> std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const`: Attempts to retrieve a vector using `GetVector<T>(section, name)`. If a `std::runtime_error` is caught, it returns the provided `default_v`.

*   `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const T& v)`: Inserts a new key-value pair into the specified section.  Throws a `std::runtime_error` if the key already exists in that section.

*   `template <typename T = std::string> void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: Inserts a new key-value pair (key mapped to vector) into the specified section. Throws a `std::runtime_error` if the key already exists in that section.

*   `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const T& v)`: Updates the value associated with an existing key in the specified section.

*   `template <typename T = std::string> void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: Updates the vector value associated with an existing key in the specified section.

**6. Protected Methods**

*   `template <typename T> T Converter(const std::string& s) const`: Converts a string to type `T`. If `T` is `std::string`, it returns the input string directly. Otherwise, it calls `detail::parse_value()` (not defined in provided code but assumed to exist and handle general parsing). Throws an error if parsing fails.
*   `bool BoolConverter(std::string s) const`: Converts a string to a boolean value. It converts the input string to lowercase and checks against predefined strings ("1", "true", "yes", "on", "0", "false", "no", "off"). Throws an error if the string is not a valid boolean representation.
*   `template <typename T> std::string V2String(const T& v) const`: Converts a value of type `T` to a string using an `std::ostringstream`.
*   `template <typename T> std::string Vec2String(const std::vector<T>& v) const`: Converts a vector of type `T` to a space-separated string.

**7. Private Methods**

*   `const std::unordered_map<std::string, std::string>& GetSection(const std::string& section) const`: Retrieves the inner map (section data) for the given section name. Throws an error if the section is not found.
*   `std::string& FindEntry(const std::string& section, const std::string& name)`: Finds and returns a reference to the string value associated with the given key in the specified section.  Throws an error if either the section or the key does not exist.
*   `void Parse(std::string_view content)`: Parses the INI file content (provided as a `std::string_view`). It handles comments, sections, and key-value pairs. The parsing logic includes:
    *   Removing Byte Order Mark (BOM) if present.
    *   Iterating through lines of the input string.
    *   Ignoring empty lines and comment lines (starting with ';' or '#').
    *   Identifying section headers (lines starting with '[').
    *   Extracting key-value pairs, splitting them at '=' or ':'.
    *   Storing the values in the `_values` map.

**8. Dependencies**

*   `<iostream>`
*   `<fstream>`
*   `<string>`
*   `<set>`
*   `<unordered_map>`
*   `<sstream>`
*   `<vector>`
*   `<type_traits>` (for `std::is_same_v`)

**9.  Assumptions & Notes**

* The code relies on a `detail` namespace containing helper functions like `trim`, `find_char_or_comment`, and `parse_value`. These are not defined in the provided snippet but are essential for parsing.
* Error handling is done through exceptions (`std::runtime_error`).
* The implementation uses `std::string_view` to avoid unnecessary string copies during parsing.
