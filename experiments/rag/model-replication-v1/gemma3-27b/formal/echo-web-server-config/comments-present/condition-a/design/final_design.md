## Design Specification for Configuration Manager (ws::cfg)

This document details the design of a configuration manager based on YAML, as defined by the provided C++ source code. It is intended to guide the re-implementation of this functionality in another LLM without access to the original code.  The specification focuses solely on the public interface and core logic exposed by the given files (F01/U01 & F02/U02).

**1. Overview**

The `ws::cfg` namespace provides a mechanism for managing configuration variables loaded from YAML files. It allows defining variables with specific types, providing default values, and converting between strings and variable types.  It also supports listeners that are notified when a variable's value changes. The system is designed to be thread-safe using shared mutexes.

**2. Key Components**

*   **`VarConverter<From, To>`:** A template class responsible for converting configuration values from one type (`From`) to another (`To`).  Specializations exist for common conversions (e.g., `string` to `int`, `list` to `vector`).
*   **`VarBase`:** An abstract base class representing a configuration variable. It stores the name and description of the variable and provides methods to access these attributes.
*   **`Var<T, FromStr, ToStr>`:** A template class derived from `VarBase`, representing a typed configuration variable.  It holds the actual value (`T`) and uses provided converters (`FromStr`, `ToStr`) for string conversions. It also manages change listeners.
*   **`Config`:** A class that manages a collection of `VarBase` objects (configuration variables). It provides methods to lookup, create, and load configuration values from YAML data.

**3. Detailed Component Specifications**

### 3.1. `VarConverter<From, To>`

*   **Purpose:**  Handles conversion between different types for configuration values.
*   **Template Parameters:**
    *   `From`: The source type of the value (e.g., `std::string`).
    *   `To`: The destination type of the value (e.g., `int`).
*   **Methods:**
    *   `operator()(const From& val) const noexcept -> To`:  Performs the conversion from `From` to `To`. The default implementation uses `static_cast`.
*   **Specializations:**
    *   `VarConverter<From, std::string>`: Converts any type `From` to a string using `std::to_string`.
    *   `VarConverter<std::string, std::string>`: Returns the input string directly.
    *   `VarConverter<std::string, To>`: Parses a string into a value of type `To` using `std::istringstream`. Throws `std::invalid_argument` if parsing fails.
    *   `VarConverter<std::string, std::list<T>>`: Loads a YAML string and converts it to a list of type T.  Throws `std::invalid_argument` if the input is not a sequence (YAML list).
    *   `VarConverter<std::list<T>, std::string>`: Converts a list of type T into a YAML formatted string.
    *   `VarConverter<std::string, std::vector<T>>`: Converts a YAML string to a vector of type T.
    *   `VarConverter<std::vector<T>, std::string>`: Converts a vector of type T to a YAML formatted string.
    *   `VarConverter<std::string, std::set<T>>`: Converts a YAML string to a set of type T.
    *   `VarConverter<std::set<T>, std::string>`: Converts a set of type T to a YAML formatted string.
    *   `VarConverter<std::string, std::unordered_set<T>>`: Converts a YAML string to an unordered set of type T.
    *   `VarConverter<std::unordered_set<T>, std::string>`: Converts an unordered set of type T to a YAML formatted string.
    *   `VarConverter<std::string, std::map<std::string, T>>`: Loads a YAML string and converts it into a map with string keys and values of type T. Throws `std::invalid_argument` if the input is not a mapping (YAML dictionary).
    *   `VarConverter<std::map<std::string, T>, std::string>`: Converts a map to a YAML formatted string.

### 3.2. `VarBase`

*   **Purpose:** Base class for configuration variables.
*   **Members:**
    *   `name_`:  A `std::string` storing the name of the variable.
    *   `description_`: A `std::string` storing a description of the variable.
*   **Methods:**
    *   `VarBase(const std::string_view name, const std::string_view description) noexcept`: Constructor.
    *   `~VarBase() noexcept = default`: Virtual destructor.
    *   `Name() const noexcept -> std::string_view`: Returns the variable's name.
    *   `Description() const noexcept -> std::string_view`: Returns the variable's description.
    *   `ToString() const noexcept = 0 -> std::string`:  Abstract method to convert the variable value to a string. Must be implemented by derived classes.
    *   `FromString(std::string_view str) = 0`: Abstract method to set the variable's value from a string. Must be implemented by derived classes.

### 3.3. `Var<T, FromStr, ToStr>`

*   **Purpose:** Represents a typed configuration variable.
*   **Template Parameters:**
    *   `T`: The type of the variable (e.g., `int`, `bool`).
    *   `FromStr`:  The converter to use for converting strings *to* type `T`. Defaults to `VarConverter<std::string, T>`.
    *   `ToStr`: The converter to use for converting type `T` *to* strings. Defaults to `VarConverter<T, std::string>`.
*   **Members:**
    *   `val_`:  The variable's value of type `T`.
    *   `mtx_`: A `std::shared_mutex` for thread-safe access to the variable.
    *   `listeners_`: An `std::unordered_map` storing change listeners (function objects). The key is a unique identifier assigned when adding the listener.
*   **Methods:**
    *   `Var(const std::string_view name, const T& default_val, const std::string_view description = "") noexcept`: Constructor. Initializes with a default value.
    *   `ToString() const noexcept override -> std::string`:  Returns the string representation of `val_` using `ToStr`.
    *   `FromString(const std::string_view str) override`: Sets `val_` from the input string using `FromStr`.
    *   `GetValue() const noexcept -> T`: Returns the current value of `val_` in a thread-safe manner.
    *   `SetValue(const T& val) noexcept`:  Sets the value of `val_`, notifies listeners if the value has changed, and ensures thread safety.
    *   `TypeName() const noexcept -> std::string_view`: Returns the name of the type `T`.
    *   `RemoveListener(const std::uint64_t key) noexcept`: Removes a listener identified by its unique key.
    *   `AddListener(OnChange listener) noexcept -> std::uint64_t`: Adds a new change listener and returns a unique key for it.
    *   `ClearListeners() noexcept`: Removes all registered listeners.

### 3.4. `Config`

*   **Purpose:** Manages a collection of configuration variables.
*   **Members:**
    *   `name_`: A `std::string` storing the name of the configuration.
    *   `vars_`: An `std::unordered_map` storing `VarBase` pointers, keyed by variable name.
    *   `mtx_`: A `std::shared_mutex` for thread-safe access to the variables map.
*   **Methods:**
    *   `Config(const std::string_view name) noexcept`: Constructor.
    *   `Name() const noexcept -> std::string_view`: Returns the configuration's name.
    *   `Lookup<T>(const std::string_view name, const T& default_val, const std::string_view description = "") -> typename Var<T>::Ptr`:  Looks up a variable by name. If not found, creates a new `Var<T>` with the given default value and description, adds it to the map, and returns a shared pointer to it.
    *   `Lookup<T>(const std::string_view name) const -> typename Var<T>::Ptr`: Looks up a variable by name. Returns a shared pointer if found; otherwise, returns `nullptr`. Throws `std::invalid_argument` if the type of the found variable does not match the requested type `T`.
    *   `LookupBase(const std::string_view name) const noexcept -> VarBase::Ptr`: Looks up a variable by name and returns a raw pointer to its base class. Returns `nullptr` if not found.
    *   `LoadYaml(const YAML::Node& root)`: Loads configuration values from a YAML node, applying them to existing variables. Uses the `ExtractMembers` helper function to traverse the YAML structure.
    *   `Visit(const std::function<void(VarBase::Ptr)> visitor) const noexcept`: Iterates through all registered variables and calls the provided visitor function on each one.
*   **Static Method:**
    *   `RootConfig() noexcept -> Config::Ptr`: Returns a singleton instance of the root configuration object.

**4. Helper Function: `ExtractMembers`**

*   **Purpose:** Recursively extracts members from a YAML node, creating a list of name-node pairs representing the hierarchical structure.
*   **Parameters:**
    *   `node`: The YAML node to extract members from.
    *   `prefix`: A string prefix representing the current level in the hierarchy (used for constructing fully qualified names).
*   **Return Value:**  A `std::list` of `std::pair<std::string, YAML::Node>`, where each pair represents a member and its corresponding node.

**5. Thread Safety**

The `Config` and `Var` classes use `std::shared_mutex` to provide thread-safe access to their internal data.  Readers can acquire shared locks, while writers (e.g., `SetValue`) require exclusive locks. This allows multiple readers to access the configuration concurrently without blocking each other.

**6. Error Handling**

*   The `VarConverter<std::string, To>` specialization throws `std::invalid_argument` if string parsing fails.
*   Type mismatches during variable lookup (using `Lookup<T>`) also throw `std::invalid_argument`.
*   Exceptions thrown within listener callbacks are caught and logged to `std::cerr`.

**7. YAML Dependency**

This design relies on a YAML library (`YAML`). The specific implementation details of the YAML library are not defined in this specification, but it is assumed that the library provides functionality for parsing YAML strings into node structures and traversing those structures.
