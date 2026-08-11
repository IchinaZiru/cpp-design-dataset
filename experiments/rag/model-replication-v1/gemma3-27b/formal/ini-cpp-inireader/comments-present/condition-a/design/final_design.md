## Design Specification for INIReader Class

This document details the design specification for the `INIReader` class, based on the provided C++ source code.  It is intended to guide the re-implementation of this class in another language or environment.

**1. Overview**

The `INIReader` class parses INI (Initialization) files and provides access to their contents. It supports retrieving values by section and key, converting them to various data types, and handling potential errors during parsing.

**2. Class Definition**

```c++
class INIReader {
   public:
    // Constructors & Destructor
    INIReader() = default;
    INIReader(const std::string& filename);
    INIReader(std::FILE* file);

    // Error Handling
    int ParseError() const;

    // Section and Key Accessors
    std::set<std::string> Sections() const;
    std::set<std::string> Keys(const std::string& section) const;
    std::unordered_map<std::string, std::string> Get(const std::string& section) const;

    // Value Retrieval with Type Conversion
    template <typename T = std::string>
    T Get(const std::string& section, const std::string& name) const;

    template <typename T>
    T Get(const std::string& section, const std::string& name, T&& default_v) const;

    // Vector Retrieval
    template <typename T = std::string>
    std::vector<T> GetVector(const std::string& section, const std::string& name) const;

    template <typename T>
    std::vector<T> GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const;

    // Insertion and Update (Modification of INI data in memory)
    template <typename T = std::string>
    void InsertEntry(const std::string& section, const std::string& name, const T& v);

    template <typename T = std::string>
    void InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs);

    template <typename T = std::string>
    void UpdateEntry(const std::string& section, const std::string& name, const T& v);

    template <typename T = std::string>
    void UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs);

   protected:
    // Internal data members (implementation details)
    int _error;
    std::unordered_map<std::string, std::unordered_map<std::string, std::string>> _values;

    // Helper functions for type conversion and string manipulation.  These are not part of the public API.
    template <typename T>
    T Converter(const std::string& s) const;

    bool BoolConverter(std::string s) const;

    template <typename T>
    std::string V2String(const T& v) const;

    template <typename T>
    std::string Vec2String(const std::vector<T>& v) const;

   private:
    // Private helper functions for internal use.  Not part of the public API.
    const std::unordered_map<std::string, std::string>& GetSection(const std::string& section) const;
    std::string& FindEntry(const std::string& section, const std::string& name);

    void Parse(std::string_view content);
};
```

**3. Data Members**

*   `_error`: An integer representing the parsing error status. 0 indicates success. Negative values indicate errors (see `ParseError()` for details).
*   `_values`: A nested unordered map storing the parsed INI data. The outer map keys are section names, and the inner map keys are key names within each section.  The inner map's values are strings representing the corresponding values from the INI file.

**4. Constructors**

*   `INIReader()`: Default constructor. Initializes `_error` to 0 and leaves `_values` empty.
*   `INIReader(const std::string& filename)`: Constructor that takes a filename as input. It opens the file, reads its content, parses it using the `Parse()` method, and calls `ParseError()` to check for errors.  Handles potential file open failures by setting `_error = -1`.
*   `INIReader(std::FILE* file)`: Constructor that takes a file pointer as input. It reads the entire file content into a string, parses it using the `Parse()` method, and calls `ParseError()` to check for errors.

**5. Methods**

*   `ParseError() const`:  Checks the value of `_error`. Throws a `std::runtime_error` exception based on its value:
    *   0: No error (returns 0).
    *   -1: File not found.
    *   -2: Memory allocation error.
    *   Other negative values: Parse error on the corresponding line number.

*   `Sections() const`: Returns a `std::set<std::string>` containing all section names found in the INI file.  Iterates through the outer map of `_values`.

*   `Keys(const std::string& section) const`: Returns a `std::set<std::string>` containing all key names within the specified section. Retrieves the inner map for the given section from `_values` and iterates through its keys.

*   `Get(const std::string& section) const`:  Returns an `std::unordered_map<std::string, std::string>` representing the values in the specified section. This is essentially a copy of the inner map for that section within `_values`. Throws a `std::runtime_error` if the section does not exist.

*   `Get(const std::string& section, const std::string& name) const`: Returns the value associated with the given key in the specified section, converted to type `T` (defaulting to `std::string`). Throws a `std::runtime_error` if the section or key does not exist.  Uses template specialization for type conversion:
    *   If `T` is `std::string`, returns the string value directly.
    *   If `T` is `bool`, uses `BoolConverter()` to parse the string as a boolean.
    *   Otherwise, uses `Converter<T>()` to perform generic type conversion.

*   `Get(const std::string& section, const std::string& name, T&& default_v) const`:  Similar to the previous `Get()` method, but returns a default value of type `T` if the key is not found in the specified section. Uses perfect forwarding (`T&&`) for the default value.

*   `GetVector(const std::string& section, const std::string& name) const`: Returns a `std::vector<T>` containing values associated with the given key in the specified section. The string value is split by spaces to create the vector elements.  Uses template specialization for type conversion of each element. Throws a `std::runtime_error` if parsing fails or the key/section doesn't exist.

*   `GetVector(const std::string& section, const std::string& name, const std::vector<T>& default_v) const`: Similar to the previous `GetVector()` method, but returns a default vector of type `T` if the key is not found in the specified section.

*   `InsertEntry(const std::string& section, const std::string& name, const T& v)`: Inserts a new key-value pair into the INI data (in memory). Throws a `std::runtime_error` if the key already exists within the section.

*   `InsertEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: Inserts a new key-vector pair into the INI data (in memory). Throws a `std::runtime_error` if the key already exists within the section.

*   `UpdateEntry(const std::string& section, const std::string& name, const T& v)`: Updates the value associated with an existing key in the specified section.  Throws a `std::runtime_error` if the key does not exist.

*   `UpdateEntry(const std::string& section, const std::string& name, const std::vector<T>& vs)`: Updates the vector of values associated with an existing key in the specified section. Throws a `std::runtime_error` if the key does not exist.

**6. Helper Functions (Protected/Private)**

These functions are internal implementation details and should not be exposed to external users.

*   `Converter<T>(const std::string& s) const`: Converts a string value to type `T`.  Handles `std::string` directly, otherwise uses a generic parsing mechanism (`detail::parse_value`, which is not defined in the provided code and would need to be implemented).
*   `BoolConverter(std::string s) const`: Parses a string as a boolean (case-insensitive comparison with "1", "0", "true", "false", "yes", "no", "on", "off").
*   `V2String(const T& v) const`: Converts a value of type `T` to a string using an output string stream.
*   `Vec2String(const std::vector<T>& v) const`: Converts a vector of values to a space-separated string.
*   `GetSection(const std::string& section) const`: Retrieves the inner map for the given section from `_values`. Throws an exception if the section is not found.
*   `FindEntry(const std::string& section, const std::string& name)`: Finds a specific entry (key-value pair) within a section.  Throws an exception if the key does not exist in the specified section.
*   `Parse(std::string_view content)`: Parses the INI file content and populates the `_values` map. This is the core parsing logic, handling sections, keys, values, comments, and errors.

**7. Error Handling**

The class uses exceptions (`std::runtime_error`) to signal errors during parsing or access. The `ParseError()` method provides a way to check for and retrieve specific error information based on the value of the `_error` member variable.

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

* The code uses a custom namespace called `detail` for helper functions like `trim`, `find_char_or_comment`, and `parse_value`. These are not defined in the provided snippet and must be implemented during re-implementation.
*   The parsing logic assumes a specific INI file format (see comments within the `Parse()` method).  It handles sections, key-value pairs, comments, and whitespace trimming.
* The code uses `std::string_view` for efficient string handling in the `Parse` function.

This specification provides a comprehensive overview of the `INIReader` class based on the provided C++ source code. It should be sufficient to guide the re-implementation of this class in another language or environment while preserving its functionality and behavior.
