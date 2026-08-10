# Design Specification for Configuration Management System

## Overview

This document provides a detailed design specification for the configuration management system based on YAML. The system includes classes and functions to manage configuration variables, convert between types, and handle events when configuration values change.

## Namespaces and Classes

### Namespace: `ws::cfg`

#### Class: `VarConverter<From, To>`

**Description:**  
A template class that converts a variable from one type to another. The default implementation uses `static_cast`.

**Template Parameters:**
- `From`: The original type.
- `To`: A new type.

**Methods:**
- `operator()(const From& val) const noexcept`: Converts the value from `From` to `To`.

#### Specializations of `VarConverter`

1. **`VarConverter<From, std::string>`**
   - Converts a variable into a string using `std::to_string`.
   
2. **`VarConverter<std::string, std::string>`**
   - Returns the variable itself if it is a string.
   
3. **`VarConverter<std::string, To>`**
   - Converts a string into a configuration variable using `std::istringstream`. Throws `std::invalid_argument` on failure.

4. **`VarConverter<std::string, std::list<T>>`, `VarConverter<std::list<T>, std::string>`**
   - Convert between a string and a list of configuration variables.
   
5. **`VarConverter<std::string, std::vector<T>>`, `VarConverter<std::vector<T>, std::string>`**
   - Convert between a string and an array of configuration variables.
   
6. **`VarConverter<std::string, std::set<T>>`, `VarConverter<std::set<T>, std::string>`**
   - Convert between a string and a set of configuration variables.
   
7. **`VarConverter<std::string, std::unordered_set<T>>`, `VarConverter<std::unordered_set<T>, std::string>`**
   - Convert between a string and an unordered set of configuration variables.
   
8. **`VarConverter<std::string, std::map<std::string, T>>`, `VarConverter<std::map<std::string, T>, std::string>`**
   - Convert between a string and a map of configuration variables.
   
9. **`VarConverter<std::string, std::unordered_map<std::string, T>>`, `VarConverter<std::unordered_map<std::string, T>, std::string>`**
   - Convert between a string and an unordered map of configuration variables.

#### Class: `VarBase`

**Description:**  
Basic information about a configuration variable.

**Methods:**
- `Name() const noexcept`: Get the variable name.
- `Description() const noexcept`: Get the variable description.
- `ToString() const noexcept = 0`: Convert the variable into a string (pure virtual).
- `FromString(std::string_view str) = 0`: Set the variable from a string (pure virtual).

**Protected Members:**
- `name_`: The name of the variable.
- `description_`: The description of the variable.

#### Class Template: `Var<T, FromStr, ToStr>`

**Description:**  
The configuration variable.

**Template Parameters:**
- `T`: The variable type.
- `FromStr`: A converter that can convert a string into a type-matching value.
- `ToStr`: A converter that can convert a type-matching value into a string.

**Methods:**
- `ToString() const noexcept override`: Convert the variable into a string using `ToStr`.
- `FromString(std::string_view str) override`: Set the variable from a string using `FromStr`.
- `GetValue() const noexcept`: Get the current value of the variable.
- `SetValue(const T& val) noexcept`: Set the value of the variable and notify listeners if it changes.
- `TypeName() const noexcept`: Get a unique string representing the variable type.
- `RemoveListener(const std::uint64_t key) noexcept`: Remove a listener.
- `AddListener(OnChange listener) noexcept`: Add a listener for value change events.
- `ClearListeners() noexcept`: Remove all listeners.

**Protected Members:**
- `mtx_`: A shared mutex to protect the variable and its listeners.
- `val_`: The current value of the variable.
- `listeners_`: A map of listeners with unique keys.

#### Class: `Config`

**Description:**  
The configuration manager.

**Methods:**
- `Name() const noexcept`: Get the name of the configuration.
- `Lookup(const std::string_view name, const T& default_val, const std::string_view description = "")`: Lookup a variable by its name, creating it if it does not exist.
- `Lookup(const std::string_view name) const`: Lookup a variable by its name. Throws `std::invalid_argument` on type mismatch.
- `LookupBase(std::string_view name) const noexcept`: Lookup the basic information about a variable.
- `LoadYaml(const YAML::Node& root)`: Set the values of existing variables from a YAML node.
- `Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept`: Visit all variables.

**Protected Members:**
- `mtx_`: A shared mutex to protect the configuration variables.
- `name_`: The name of the configuration.
- `vars_`: A map of variable names to their corresponding `VarBase` pointers.

#### Function: `RootConfig()`

**Description:**  
Get the root configuration.

**Return Value:**
- `Config::Ptr`: A shared pointer to the root configuration.

## Implementation Details

### File: `include/config.h`

This file contains the declarations for all classes and functions in the `ws::cfg` namespace. It includes necessary headers such as `<algorithm>`, `<initializer_list>`, `<iostream>`, etc., and defines the template classes and functions described above.

### File: `src/config/config.cpp`

This file contains the implementations of the methods declared in `include/config.h`. It includes a helper function `ExtractMembers` that recursively extracts members from a YAML node, which is used by `Config::LoadYaml`.

## Usage Example

```cpp
#include "config.h"
#include <iostream>

int main() {
    auto config = ws::cfg::RootConfig();
    
    // Create and lookup variables
    auto port_var = config->Lookup<int>("system.port", 80, "Port number");
    auto ip_var = config->Lookup<std::string>("system.ip", "127.0.0.1", "IP address");

    // Set values from YAML node
    YAML::Node yaml_node;
    yaml_node["system"]["port"] = 8080;
    yaml_node["system"]["ip"] = "192.168.1.1";
    config->LoadYaml(yaml_node);

    // Print values
    std::cout << "Port: " << port_var->GetValue() << std::endl;
    std::cout << "IP: " << ip_var->GetValue() << std::endl;

    return 0;
}
```

## Conclusion

This design specification provides a comprehensive overview of the configuration management system, including its classes, methods, and usage. The system is designed to be flexible and extensible, allowing for easy conversion between different types and handling of value change events.