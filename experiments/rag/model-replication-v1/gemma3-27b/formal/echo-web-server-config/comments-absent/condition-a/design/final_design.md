## Design Specification for Config System

This document details the design of a configuration system implemented in C++. It is based on the provided source code (F01/U01 and F02/U02) and aims to provide sufficient information for re-implementation without access to the original code.  The specification focuses solely on the functionality exposed by the given files, making no assumptions about external dependencies or broader system context beyond what is explicitly defined.

**1. Overview**

The configuration system allows defining and managing configurable variables of various types (string, integer, list, vector, set, map) using a YAML-based approach. It provides type conversion capabilities between strings and other data types for loading configurations from YAML files or string representations.  It also supports listeners that are notified when variable values change.

**2. Key Components**

*   **`VarBase`**: Abstract base class for all configurable variables.
    *   Stores the name and description of a variable.
    *   Provides virtual methods `ToString()` (to convert to string) and `FromString()` (to parse from string).
*   **`Var<T>`**: Template class derived from `VarBase`, representing a specific type of configurable variable (`T`).
    *   Stores the actual value of the variable.
    *   Implements `ToString()` and `FromString()` using `VarConverter` specializations for type conversion.
    *   Provides methods to get/set the value, register listeners for change notifications, and clear listeners.
*   **`Config`**:  Manages a collection of `VarBase` objects (variables).
    *   Stores variables in an unordered map (`vars_`) keyed by their names.
    *   Provides methods to lookup variables by name and type, load configurations from YAML nodes, and visit all variables with a given function.
*   **`VarConverter<From, To>`**: Template class providing conversion between types `From` and `To`.  Specializations exist for common conversions (e.g., string to int, string to vector).

**3. Detailed Component Specifications**

### 3.1. `VarBase`

*   **Members:**
    *   `name_`: `std::string` - The name of the variable.
    *   `description_`: `std::string` - A description of the variable.
*   **Methods:**
    *   `VarBase(const std::string_view name, const std::string_view description) noexcept;`: Constructor. Initializes `name_` and `description_`.
    *   `virtual ~VarBase() noexcept = default;`: Virtual destructor.
    *   `std::string_view Name() const noexcept;`: Returns the variable's name.
    *   `std::string_view Description() const noexcept;`: Returns the variable's description.
    *   `virtual std::string ToString() const noexcept = 0;`:  Pure virtual method to convert the variable’s value to a string representation. Must be implemented by derived classes.
    *   `virtual void FromString(std::string_view str) = 0;`: Pure virtual method to parse a string and set the variable's value. Must be implemented by derived classes.

### 3.2. `Var<T>`

*   **Template Parameters:**
    *   `T`: The data type of the variable.
    *   `FromStr`:  The `VarConverter` specialization used to convert from string to `T`. Defaults to `VarConverter<std::string, T>`.
    *   `ToStr`: The `VarConverter` specialization used to convert from `T` to string. Defaults to `VarConverter<T, std::string>`.
*   **Members:**
    *   Inherits members from `VarBase`.
    *   `val_`: `T` -  The actual value of the variable.
    *   `mtx_`: `std::shared_mutex` – Mutex for thread-safe access to `val_` and listeners.
    *   `listeners_`: `std::unordered_map<std::uint64_t, OnChange>` - Map storing listener functions keyed by a unique identifier.
*   **Methods:**
    *   `Var(const std::string_view name, const T& default_val, const std::string_view description = "") noexcept;`: Constructor. Initializes `VarBase`, sets the initial value of `val_`.
    *   Deleted copy constructor and assignment operator to prevent copying.
    *   Deleted move constructor and assignment operator to prevent moving.
    *   `std::string ToString() const noexcept override;`:  Returns the string representation of `val_` using `ToStr {}(GetValue())`.
    *   `void FromString(const std::string_view str) override;`: Parses `str` using `FromStr {}` and sets `val_`.
    *   `T GetValue() const noexcept;`: Returns the current value of `val_`, protected by a shared lock.
    *   `void SetValue(const T& val) noexcept;`: Sets the value of `val_`, protected by a unique lock.  Notifies registered listeners if the value has changed.
    *   `std::string_view TypeName() const noexcept;`: Returns the name of the type `T` using `typeid(T).name()`.
    *   `void RemoveListener(const std::uint64_t key) noexcept;`: Removes a listener identified by its key. Protected by a unique lock.
    *   `std::uint64_t AddListener(OnChange listener) noexcept;`: Adds a new listener and returns a unique key for it.  Protected by a unique lock.
    *   `void ClearListeners() noexcept;`: Removes all listeners. Protected by a unique lock.

### 3.3. `Config`

*   **Members:**
    *   `name_`: `std::string` - The name of the configuration.
    *   `mtx_`: `std::shared_mutex` – Mutex for thread-safe access to `vars_`.
    *   `vars_`: `std::unordered_map<std::string, VarBase::Ptr>` - Map storing variables keyed by their names.
*   **Methods:**
    *   `Config(const std::string_view name) noexcept;`: Constructor. Initializes `name_`.
    *   Deleted copy constructor and assignment operator to prevent copying.
    *   Deleted move constructor and assignment operator to prevent moving.
    *   `std::string_view Name() const noexcept;`: Returns the configuration's name.
    *   `template <typename T> typename Var<T>::Ptr Lookup(const std::string_view name, const T& default_val, const std::string_view description = "");`:  Looks up a variable by name. If not found, creates a new `Var<T>` with the given default value and description, adds it to the map, and returns its pointer.
    *   `template <typename T> typename Var<T>::Ptr Lookup(const std::string_view name) const;`: Looks up a variable by name and type. Throws an exception if the found variable is not of the requested type. Returns `nullptr` if not found.
    *   `VarBase::Ptr LookupBase(std::string_view name) const noexcept;`:  Looks up a variable by name, returning a `VarBase::Ptr`. Returns `nullptr` if not found.
    *   `void LoadYaml(const YAML::Node& root);`: Loads configuration values from a YAML node. Iterates through the members of the YAML node and calls `FromString()` on corresponding variables.
    *   `void Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept;`:  Iterates through all registered variables and calls the provided visitor function for each one.
    *   Static method: `Config::Ptr RootConfig() noexcept;`: Returns a singleton instance of the root configuration object.

### 3.4. `VarConverter<From, To>`

*   **Template Parameters:**
    *   `From`: The source type.
    *   `To`: The destination type.
*   **Methods:**
    *   `To operator()(const From& val) const noexcept;`:  Virtual function that performs the conversion from `From` to `To`.
*   **Specializations:**
    *   `VarConverter<From, std::string>`: Converts any type `From` to a string using `std::to_string`.
    *   `VarConverter<std::string, std::string>`: Returns the input string view as a C-style string.
    *   `VarConverter<std::string, To>`:  Converts a string to type `To` by parsing it from an `std::istringstream`. Throws `std::invalid_argument` if parsing fails.
    *   `VarConverter<std::string, std::list<T>>`: Converts a YAML string to a list of type `T`.  Uses `LoadYamlString()` (not defined in the provided code but assumed to exist) to parse the YAML and then converts each element using another `VarConverter` specialization.
    *   `VarConverter<std::list<T>, std::string>`: Converts a list of type `T` to a YAML string. Uses `LoadYamlString()` (not defined in the provided code but assumed to exist) for each element and combines them into a YAML node, then converts it to a string.
    *   Similar specializations exist for converting between strings and vectors, sets, unordered sets, maps, and unordered maps using lists as an intermediate representation.

**4.  Assumptions & External Dependencies**

*   **YAML Library:** The code relies on a YAML parsing library (likely `YAML::Node` from a third-party library). The exact API of this library is not defined in the provided source code, but its existence and basic functionality are assumed. Specifically, `LoadYamlString()` function is used which takes string view as input and returns `YAML::Node`.
*   **fmt Library:**  The code uses the `fmt` library for formatted output (e.g., `fmt::format`).
*   **Standard C++ Libraries:** The code utilizes standard C++ libraries such as `<string>`, `<vector>`, `<map>`, `<iostream>`, etc.

**5. Thread Safety**

The `Config` and `Var<T>` classes use `std::shared_mutex` to provide thread-safe access to their internal data structures (variables and listeners).  This allows multiple readers or a single writer at any given time.

**6. Error Handling**

*   Parsing errors during `FromString()` are handled by throwing `std::invalid_argument`.
*   Exceptions thrown within listener callbacks are caught and printed to `std::cerr` to prevent program termination, but the specific exception is not re-thrown.

This specification provides a comprehensive overview of the configuration system based on the provided source code. It should be sufficient for implementing a functionally equivalent system without access to the original implementation details.
