#include "config.h"
#include <fmt/core.h>
#include <yaml-cpp/yaml.h>
#include <algorithm>
#include <sstream>
#include <stdexcept>
#include <string_view>

namespace ws {

namespace cfg {

template <typename From, typename To>
To VarConverter<From, To>::operator()(const From& val) const noexcept {
    return static_cast<To>(val);
}

template <typename From>
std::string VarConverter<From, std::string>::operator()(const From& val) const noexcept {
    return std::to_string(val);
}

std::string VarConverter<std::string, std::string>::operator()(const std::string_view val) const noexcept {
    return static_cast<std::string>(val);
}

template <typename To>
To VarConverter<std::string, To>::operator()(const std::string_view str) const {
    std::istringstream iss {static_cast<std::string>(str)};
    To val;
    if (!(iss >> val)) {
        throw std::invalid_argument(fmt::format("Cannot convert string \"{}\" to type {}", str, typeid(To).name()));
    }
    return val;
}

template <typename T>
std::list<T> VarConverter<std::string, std::list<T>>::operator()(const std::string_view str) const {
    if (str.front() != '[' || str.back() != ']') {
        throw std::invalid_argument(fmt::format("String \"{}\" does not represent a list", str));
    }
    std::istringstream iss {static_cast<std::string>(str).substr(1, str.size() - 2)};
    std::list<T> vals;
    T val;
    while (iss >> val) {
        vals.push_back(val);
        if (iss.peek() == ',') {
            iss.ignore();
        }
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::list<T>, std::string>::operator()(const std::list<T>& vals) const noexcept {
    std::ostringstream oss;
    oss << '[';
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ',';
        }
        oss << *it;
    }
    oss << ']';
    return oss.str();
}

template <typename T>
std::vector<T> VarConverter<std::string, std::vector<T>>::operator()(const std::string_view str) const {
    if (str.front() != '[' || str.back() != ']') {
        throw std::invalid_argument(fmt::format("String \"{}\" does not represent a list", str));
    }
    std::istringstream iss {static_cast<std::string>(str).substr(1, str.size() - 2)};
    std::vector<T> vals;
    T val;
    while (iss >> val) {
        vals.push_back(val);
        if (iss.peek() == ',') {
            iss.ignore();
        }
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::vector<T>, std::string>::operator()(const std::vector<T>& vals) const noexcept {
    std::ostringstream oss;
    oss << '[';
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ',';
        }
        oss << *it;
    }
    oss << ']';
    return oss.str();
}

template <typename T>
std::set<T> VarConverter<std::string, std::set<T>>::operator()(const std::string_view str) const {
    if (str.front() != '{' || str.back() != '}') {
        throw std::invalid_argument(fmt::format("String \"{}\" does not represent a set", str));
    }
    std::istringstream iss {static_cast<std::string>(str).substr(1, str.size() - 2)};
    std::set<T> vals;
    T val;
    while (iss >> val) {
        vals.insert(val);
        if (iss.peek() == ',') {
            iss.ignore();
        }
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::set<T>, std::string>::operator()(const std::set<T>& vals) const noexcept {
    std::ostringstream oss;
    oss << '{';
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ',';
        }
        oss << *it;
    }
    oss << '}';
    return oss.str();
}

template <typename T>
std::unordered_set<T> VarConverter<std::string, std::unordered_set<T>>::operator()(const std::string_view str) const {
    if (str.front() != '{' || str.back() != '}') {
        throw std::invalid_argument(fmt::format("String \"{}\" does not represent a set", str));
    }
    std::istringstream iss {static_cast<std::string>(str).substr(1, str.size() - 2)};
    std::unordered_set<T> vals;
    T val;
    while (iss >> val) {
        vals.insert(val);
        if (iss.peek() == ',') {
            iss.ignore();
        }
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::unordered_set<T>, std::string>::operator()(const std::unordered_set<T>& vals) const noexcept {
    std::ostringstream oss;
    oss << '{';
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ',';
        }
        oss << *it;
    }
    oss << '}';
    return oss.str();
}

template <typename T>
std::map<std::string, T> VarConverter<std::string, std::map<std::string, T>>::operator()(const std::string_view str) const {
    if (str.front() != '{' || str.back() != '}') {
        throw std::invalid_argument(fmt::format("String \"{}\" does not represent a map", str));
    }
    std::istringstream iss {static_cast<std::string>(str).substr(1, str.size() - 2)};
    std::map<std::string, T> vals;
    std::string key;
    T val;
    while (iss >> key) {
        if (iss.peek() != ':') {
            throw std::invalid_argument(fmt::format("String \"{}\" does not represent a map", str));
        }
        iss.ignore();
        iss >> val;
        vals[key] = val;
        if (iss.peek() == ',') {
            iss.ignore();
        }
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::map<std::string, T>, std::string>::operator()(const std::map<std::string, T>& vals) const noexcept {
    std::ostringstream oss;
    oss << '{';
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ',';
        }
        oss << it->first << ':' << it->second;
    }
    oss << '}';
    return oss.str();
}

template <typename T>
std::unordered_map<std::string, T> VarConverter<std::string, std::unordered_map<std::string, T>>::operator()(const std::string_view str) const {
    if (str.front() != '{' || str.back() != '}') {
        throw std::invalid_argument(fmt::format("String \"{}\" does not represent a map", str));
    }
    std::istringstream iss {static_cast<std::string>(str).substr(1, str.size() - 2)};
    std::unordered_map<std::string, T> vals;
    std::string key;
    T val;
    while (iss >> key) {
        if (iss.peek() != ':') {
            throw std::invalid_argument(fmt::format("String \"{}\" does not represent a map", str));
        }
        iss.ignore();
        iss >> val;
        vals[key] = val;
        if (iss.peek() == ',') {
            iss.ignore();
        }
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::unordered_map<std::string, T>, std::string>::operator()(const std::unordered_map<std::string, T>& vals) const noexcept {
    std::ostringstream oss;
    oss << '{';
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ',';
        }
        oss << it->first << ':' << it->second;
    }
    oss << '}';
    return oss.str();
}

VarBase::VarBase(std::string_view name,
                 std::string_view description) noexcept : name_ {name}, description_ {description} {}

std::string_view VarBase::Name() const noexcept {
    return name_;
}

std::string_view VarBase::Description() const noexcept {
    return description_;
}

template <typename T, typename FromStr, typename ToStr>
std::string Var<T, FromStr, ToStr>::ToString() const noexcept {
    std::shared_lock lock {mtx_};
    return ToStr {}(val_);
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::FromString(const std::string_view str) {
    std::lock_guard lock {mtx_};
    const auto old_val = val_;
    val_ = FromStr {}(str);
    for (const auto& [key, listener] : listeners_) {
        listener(old_val, val_);
    }
}

template <typename T, typename FromStr, typename ToStr>
T Var<T, FromStr, ToStr>::GetValue() const noexcept {
    std::shared_lock lock {mtx_};
    return val_;
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::SetValue(const T& val) noexcept {
    std::lock_guard lock {mtx_};
    const auto old_val = val_;
    val_ = val;
    for (const auto& [key, listener] : listeners_) {
        listener(old_val, val_);
    }
}

template <typename T, typename FromStr, typename ToStr>
std::string_view Var<T, FromStr, ToStr>::TypeName() const noexcept {
    return typeid(T).name();
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::RemoveListener(const std::uint64_t key) noexcept {
    std::lock_guard lock {mtx_};
    listeners_.erase(key);
}

template <typename T, typename FromStr, typename ToStr>
std::uint64_t Var<T, FromStr, ToStr>::AddListener(OnChange listener) noexcept {
    static std::atomic<std::uint64_t> key_counter {0};
    const auto key = ++key_counter;
    std::lock_guard lock {mtx_};
    listeners_.emplace(key, std::move(listener));
    return key;
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::ClearListeners() noexcept {
    std::lock_guard lock {mtx_};
    listeners_.clear();
}

Config::Config(std::string_view name) noexcept : name_ {name} {}

std::string_view Config::Name() const noexcept {
    return name_;
}

template <typename T>
typename Var<T>::Ptr Config::Lookup(const std::string_view name,
                                  const T& default_val,
                                  const std::string_view description) {
    std::lock_guard lock {mtx_};
    if (auto it = vars_.find(name); it != vars_.end()) {
        auto var = std::dynamic_pointer_cast<Var<T>>(it->second);
        if (!var) {
            throw std::invalid_argument(fmt::format("Variable \"{}\" is not of type {}", name, typeid(T).name()));
        }
        return var;
    } else {
        auto var = std::make_shared<Var<T>>(name, default_val, description);
        vars_.emplace(name, var);
        return var;
    }
}

template <typename T>
typename Var<T>::Ptr Config::Lookup(const std::string_view name) const {
    std::shared_lock lock {mtx_};
    if (auto it = vars_.find(name); it != vars_.end()) {
        auto var = std::dynamic_pointer_cast<Var<T>>(it->second);
        if (!var) {
            throw std::invalid_argument(fmt::format("Variable \"{}\" is not of type {}", name, typeid(T).name()));
        }
        return var;
    } else {
        return nullptr;
    }
}

VarBase::Ptr Config::LookupBase(std::string_view name) const noexcept {
    std::shared_lock lock {mtx_};
    if (auto it = vars_.find(name); it != vars_.end()) {
        return it->second;
    } else {
        return nullptr;
    }
}

void Config::LoadYaml(const YAML::Node& root) {
    std::lock_guard lock {mtx_};
    for (const auto& [key, value] : root.as<std::map<std::string, YAML::Node>>()) {
        if (auto var = LookupBase(key)) {
            var->FromString(value.as<std::string>());
        }
    }
}

void Config::Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept {
    std::shared_lock lock {mtx_};
    for (const auto& [name, var] : vars_) {
        visitor(var);
    }
}

Config::Ptr RootConfig() noexcept {
    static Config::Ptr root_config = std::make_shared<Config>("root");
    return root_config;
}

}  // namespace cfg

}  // namespace ws
