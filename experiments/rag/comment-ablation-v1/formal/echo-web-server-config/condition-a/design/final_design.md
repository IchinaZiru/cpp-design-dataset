### Design Specification for Reimplementation of C++ Source Code

#### Overview
This document provides a detailed design specification for reimplementing the given C++ source code. The target-owned identifiers (Fxx/Uxx) are to be preserved, and only the units marked with `replacement_required: true` will be regenerated.

#### Target Files
1. **include/config.h**
2. **src/config/config.cpp**

### File: include/config.h

#### Role
Complete target-owned implementation/declaration file.

#### Namespace
- `ws::cfg`

#### Included Headers
```cpp
#include "util.h"
#include <algorithm>
#include <initializer_list>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <shared_mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <syncstream>
#include <typeinfo>
#include <unordered_map>
#include <unordered_set>
#include <vector>
```

#### Classes and Templates

1. **VarConverter**
   - Template Class: `template <typename From, typename To>`
     - Method: `To operator()(const From& val) const noexcept`
   - Specialization: `template <typename From>`
     - Method: `std::string operator()(const From& val) const noexcept`
   - Specialization: `template <>`
     - Method: `std::string operator()(const std::string_view val) const noexcept`
   - Template Class: `template <typename To>`
     - Method: `To operator()(const std::string_view str) const`
   - Template Class: `template <typename T>`
     - Methods:
       - `std::list<T> operator()(const std::string_view str) const`
       - `std::string operator()(const std::list<T>& vals) const noexcept`
       - `std::vector<T> operator()(const std::string_view str) const`
       - `std::string operator()(const std::vector<T>& vals) const noexcept`
       - `std::set<T> operator()(const std::string_view str) const`
       - `std::string operator()(const std::set<T>& vals) const noexcept`
       - `std::unordered_set<T> operator()(const std::string_view str) const`
       - `std::string operator()(const std::unordered_set<T>& vals) const noexcept`
       - `std::map<std::string, T> operator()(const std::string_view str) const`
       - `std::string operator()(const std::map<std::string, T>& vals) const noexcept`
       - `std::unordered_map<std::string, T> operator()(const std::string_view str) const`
       - `std::string operator()(const std::unordered_map<std::string, T>& vals) const noexcept`

2. **VarBase**
   - Methods:
     - `explicit VarBase(std::string_view name, std::string_view description = "") noexcept`
     - `virtual ~VarBase() noexcept = default`
     - `std::string_view Name() const noexcept`
     - `std::string_view Description() const noexcept`
     - `virtual std::string ToString() const noexcept = 0`
     - `virtual void FromString(std::string_view str) = 0`

3. **Var**
   - Template Class: `template <typename T, typename FromStr = VarConverter<std::string, T>, typename ToStr = VarConverter<T, std::string>>`
   - Requires:
     - `std::is_invocable_r_v<T, FromStr, std::string>`
     - `std::is_nothrow_invocable_r_v<std::string, ToStr, T>`
   - Methods:
     - `explicit Var(const std::string_view name, const T& default_val, const std::string_view description = "") noexcept`
     - `Var(const Var&) = delete`
     - `Var(Var&&) = delete`
     - `Var& operator=(const Var&) = delete`
     - `Var& operator=(Var&&) = delete`
     - `std::string ToString() const noexcept override`
     - `void FromString(const std::string_view str) override`
     - `T GetValue() const noexcept`
     - `void SetValue(const T& val) noexcept`
     - `std::string_view TypeName() const noexcept`
     - `void RemoveListener(const std::uint64_t key) noexcept`
     - `std::uint64_t AddListener(OnChange listener) noexcept`
     - `void ClearListeners() noexcept`

4. **Config**
   - Methods:
     - `explicit Config(std::string_view name) noexcept`
     - `Config(const Config&) = delete`
     - `Config(Config&&) = delete`
     - `Config& operator=(const Config&) = delete`
     - `Config& operator=(Config&&) = delete`
     - `std::string_view Name() const noexcept`
     - `template <typename T> typename Var<T>::Ptr Lookup(const std::string_view name, const T& default_val, const std::string_view description = "")`
     - `template <typename T> typename Var<T>::Ptr Lookup(const std::string_view name) const`
     - `VarBase::Ptr LookupBase(std::string_view name) const noexcept`
     - `void LoadYaml(const YAML::Node& root)`
     - `void Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept`

5. **RootConfig**
   - Function: `Config::Ptr RootConfig() noexcept`

### File: src/config/config.cpp

#### Role
Complete target-owned implementation/declaration file.

#### Namespace
- `ws::cfg`

#### Included Headers
```cpp
#include "config.h"
```

#### Functions and Methods

1. **ExtractMembers**
   - Function: `std::list<std::pair<std::string, YAML::Node>> ExtractMembers(const YAML::Node& node, const std::string& prefix = "")`
     - Description: Recursively extracts members from a YAML node.

2. **VarBase Constructor and Methods**
   - Constructor: `VarBase::VarBase(const std::string_view name, const std::string_view description) noexcept`
   - Method: `std::string_view VarBase::Name() const noexcept`
   - Method: `std::string_view VarBase::Description() const noexcept`

3. **Config Constructor and Methods**
   - Constructor: `Config::Config(const std::string_view name) noexcept`
   - Method: `std::string_view Config::Name() const noexcept`
   - Method: `VarBase::Ptr Config::LookupBase(std::string_view name) const noexcept`
   - Method: `void Config::LoadYaml(const YAML::Node& root)`
   - Method: `void Config::Visit(const std::function<void(VarBase::Ptr)> visitor) const noexcept`

4. **RootConfig**
   - Function: `Config::Ptr RootConfig() noexcept`

### Summary
This design specification provides a detailed breakdown of the classes, templates, and functions present in the given C++ source code. The reimplementation should strictly adhere to this structure while preserving all target-owned identifiers (Fxx/Uxx).