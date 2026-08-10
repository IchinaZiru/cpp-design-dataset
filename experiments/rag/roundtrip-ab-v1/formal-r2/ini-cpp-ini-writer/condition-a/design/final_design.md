# Design Specification for INIWriter Class

## Overview
This document provides a detailed design specification for the `INIWriter` class. The purpose of this class is to write the contents of an INI file to a new file based on data provided by an `INIReader` object.

## Namespace and File Location
- **Namespace**: Not explicitly defined in the given code snippet.
- **File Path**: `ini/ini.h`

## Class Definition

### Class Name
- **Class Name**: `INIWriter`

### Constructors
- **Default Constructor**:
  - **Signature**: `INIWriter() = default;`
  - **Description**: Initializes an instance of the `INIWriter` class with default values.

### Static Methods
- **Method Name**: `write`
  - **Role**: Writes the contents of an INI file to a new file.
  - **Signature**: 
    ```cpp
    inline static void write(const std::string& filepath, const INIReader& reader, const bool overwrite = false);
    ```
  - **Parameters**:
    - `filepath`: A string representing the path of the output file.
    - `reader`: An instance of the `INIReader` class containing the data to be written.
    - `overwrite`: A boolean indicating whether to overwrite an existing file. Defaults to `false`.
  - **Exceptions**:
    - Throws a `std::runtime_error` if the output file already exists and `overwrite` is `false`.
    - Throws a `std::runtime_error` if the output file cannot be opened.
  - **Functionality**:
    - Checks if the file already exists and throws an exception if it does and `overwrite` is `false`.
    - Opens the output file for writing. If the file cannot be opened, throws an exception.
    - Iterates through each section in the `INIReader` object.
    - Writes each section header to the file.
    - Iterates through each key in the current section and writes the key-value pair to the file.

## Dependencies
- **External Libraries**: 
  - `<string>` for string handling.
  - `<fstream>` for file input/output operations.
  - `<stdexcept>` for exception handling (`std::runtime_error`).
- **Internal Classes**:
  - `INIReader`: This class is referenced in the method signature but not defined within this unit. It must be available and properly implemented elsewhere.

## Usage Example
```cpp
#include "ini/ini.h"
#include <iostream>

int main() {
    INIReader reader("input.ini");
    try {
        INIWriter::write("output.ini", reader, true);
        std::cout << "INI file written successfully." << std::endl;
    } catch (const std::runtime_error& e) {
        std::cerr << "Error: " << e.what() << std::endl;
    }
    return 0;
}
```

## Notes
- The `Fxx/Uxx` identifiers (`F01/U01`) and their associated metadata are preserved as per the requirements.
- No reference-only inputs were provided, so no additional design considerations based on such inputs are included.

This specification is intended to guide the reimplementation of the `INIWriter` class in a separate codebase while adhering strictly to the provided details.