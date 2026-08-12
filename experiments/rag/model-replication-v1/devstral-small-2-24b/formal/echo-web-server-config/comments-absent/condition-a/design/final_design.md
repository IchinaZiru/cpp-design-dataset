# Configuration System Design Specification

## Overview
This document specifies the design of a configuration system implemented in C++ that provides type-safe configuration variables with change notification capabilities. The system is designed to be thread-safe and supports various data types including primitive types, collections, and nested maps.

## Core Components

### 1. VarConverter Template Class
**Purpose**: Provides conversion between different types, particularly between string representations and actual values.

**Template Parameters**:
- `From`: Source type
- `To`: Target type

**Specializations**:
1. **Generic Conversion**: Uses `static_cast` for numeric conversions
2. **String to Primitive**: Uses `std::to_string` for conversion from primitive types to string
3. **String to String**: Direct copy of the string data
4. **Primitive to String**: Uses `std::istringstream` with error handling
5. **Collection Types**:
   - Supports `std::list`, `std::vector`, `std::set`, `std::unordered_set`
   - Converts between string (YAML format) and collection types
6. **Map Types**:
   - Supports `std::map` and `std::unordered_map` with string keys
   - Converts between string (YAML format) and map types

**Error Handling**: Throws `std::invalid_argument` for conversion failures with descriptive messages.

### 2. VarBase Abstract Class
**Purpose**: Base class for all configuration variables providing common interface.

**Key Methods**:
- `Name()`: Returns the variable name
- `Description()`: Returns the variable description
- `ToString()`: Pure virtual method to convert value to string
- `FromString()`: Pure virtual method to parse string into value

### 3. Var Template Class
**Purpose**: Concrete implementation of configuration variables with change notification.

**Template Parameters**:
- `T`: The type of the configuration value
- `FromStr`: Converter from string to T (defaults to `VarConverter<std::string, T>`)
- `ToStr`: Converter from T to string (defaults to `VarConverter<T, std::string>`)

**Key Features**:
1. **Thread Safety**: Uses `std::shared_mutex` for concurrent access
2. **Change Notification**: Supports adding/removing listeners that are called when value changes
3. **Value Access**:
   - `GetValue()`: Returns current value (thread-safe read)
   - `SetValue()`: Updates value and notifies listeners (thread-safe write)

**Listener Management**:
- Listeners are identified by unique 64-bit keys
- Each listener receives old and new values when called
- Exceptions in listeners are caught and logged to stderr

### 4. Config Class
**Purpose**: Manages a collection of configuration variables.

**Key Features**:
1. **Variable Lookup**:
   - `Lookup<T>(name, default_val)`: Creates or retrieves variable with type T
   - `Lookup<T>(name)`: Retrieves existing variable (throws if wrong type)
2. **YAML Loading**: `LoadYaml()` method loads configuration from YAML node
3. **Iteration**: `Visit()` method applies visitor to all variables

**Thread Safety**: Uses `std::shared_mutex` for concurrent access.

### 5. Root Configuration Singleton
**Purpose**: Provides global access to the root configuration instance.

**Function**:
- `RootConfig()`: Returns shared pointer to the singleton root config

## Implementation Details

### YAML Integration
The system uses YAML-CPP library for:
1. Parsing string representations of complex types (lists, maps)
2. Serializing values back to YAML format

**Helper Function**:
- `ExtractMembers()`: Recursively extracts all key-value pairs from a YAML node with dot notation for nested structures.

### Error Handling
1. **Conversion Errors**: Throws `std::invalid_argument` with formatted error messages
2. **Type Mismatches**: Throws when attempting to access variable with wrong type
3. **Listener Exceptions**: Caught and logged to stderr without affecting system operation

## Thread Safety Guarantees
1. All public methods are thread-safe
2. Read operations use shared locks (`std::shared_lock`)
3. Write operations use exclusive locks (`std::unique_lock`)
4. Listener callbacks are called under lock protection

## Usage Pattern
```cpp
// Get root config
auto config = ws::cfg::RootConfig();

// Create a variable
auto intVar = config->Lookup<int>("timeout", 30);

// Add change listener
intVar->AddListener([](const int& oldVal, const int& newVal) {
    std::cout << "Changed from " << oldVal << " to " << newVal << "\n";
});

// Load YAML configuration
YAML::Node yaml = YAML::Load("timeout: 60");
config->LoadYaml(yaml);
```

## Dependencies
- C++20 features (concepts, ranges)
- YAML-CPP library for YAML parsing
- fmt library for formatted error messages

This specification provides all necessary information for a complete reimplementation of the configuration system while preserving all target-owned identifiers and interfaces.