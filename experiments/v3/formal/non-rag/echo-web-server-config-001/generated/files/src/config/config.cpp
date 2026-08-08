#include "config.h"
#include <yaml-cpp/yaml.h>
#include <fmt/core.h>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <typeinfo>

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
    return std::string(val);
}

template <typename To>
To VarConverter<std::string, To>::operator()(const std::string_view str) const {
    std::istringstream iss(std::string(str));
    To result;
    if (!(iss >> result)) {
        throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type {}", str, typeid(To).name()));
    }
    return result;
}

template <typename T>
std::list<T> VarConverter<std::string, std::list<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(std::string(str));
    std::list<T> result;
    std::string item;
    while (std::getline(iss, item, ',')) {
        std::istringstream itemStream(item);
        T value;
        if (!(itemStream >> value)) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type {}", str, typeid(T).name()));
        }
        result.push_back(value);
    }
    return result;
}

template <typename T>
std::string VarConverter<std::list<T>, std::string>::operator()(const std::list<T>& vals) const noexcept {
    std::ostringstream oss;
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ",";
        }
        oss << *it;
    }
    return oss.str();
}

template <typename T>
std::vector<T> VarConverter<std::string, std::vector<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(std::string(str));
    std::vector<T> result;
    std::string item;
    while (std::getline(iss, item, ',')) {
        std::istringstream itemStream(item);
        T value;
        if (!(itemStream >> value)) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type {}", str, typeid(T).name()));
        }
        result.push_back(value);
    }
    return result;
}

template <typename T>
std::string VarConverter<std::vector<T>, std::string>::operator()(const std::vector<T>& vals) const noexcept {
    std::ostringstream oss;
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ",";
        }
        oss << *it;
    }
    return oss.str();
}

template <typename T>
std::set<T> VarConverter<std::string, std::set<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(std::string(str));
    std::set<T> result;
    std::string item;
    while (std::getline(iss, item, ',')) {
        std::istringstream itemStream(item);
        T value;
        if (!(itemStream >> value)) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type {}", str, typeid(T).name()));
        }
        result.insert(value);
    }
    return result;
}

template <typename T>
std::string VarConverter<std::set<T>, std::string>::operator()(const std::set<T>& vals) const noexcept {
    std::ostringstream oss;
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ",";
        }
        oss << *it;
    }
    return oss.str();
}

template <typename T>
std::unordered_set<T> VarConverter<std::string, std::unordered_set<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(std::string(str));
    std::unordered_set<T> result;
    std::string item;
    while (std::getline(iss, item, ',')) {
        std::istringstream itemStream(item);
        T value;
        if (!(itemStream >> value)) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type {}", str, typeid(T).name()));
        }
        result.insert(value);
    }
    return result;
}

template <typename T>
std::string VarConverter<std::unordered_set<T>, std::string>::operator()(const std::unordered_set<T>& vals) const noexcept {
    std::ostringstream oss;
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ",";
        }
        oss << *it;
    }
    return oss.str();
}

template <typename T>
std::map<std::string, T> VarConverter<std::string, std::map<std::string, T>>::operator()(const std::string_view str) const {
    std::istringstream iss(std::string(str));
    std::map<std::string, T> result;
    std::string item;
    while (std::getline(iss, item, ';')) {
        size_t pos = item.find('=');
        if (pos == std::string::npos) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type map", str));
        }
        std::string key = item.substr(0, pos);
        std::istringstream valueStream(item.substr(pos + 1));
        T value;
        if (!(valueStream >> value)) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type {}", str, typeid(T).name()));
        }
        result[key] = value;
    }
    return result;
}

template <typename T>
std::string VarConverter<std::map<std::string, T>, std::string>::operator()(const std::map<std::string, T>& vals) const noexcept {
    std::ostringstream oss;
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ";";
        }
        oss << it->first << "=" << it->second;
    }
    return oss.str();
}

template <typename T>
std::unordered_map<std::string, T> VarConverter<std::string, std::unordered_map<std::string, T>>::operator()(const std::string_view str) const {
    std::istringstream iss(std::string(str));
    std::unordered_map<std::string, T> result;
    std::string item;
    while (std::getline(iss, item, ';')) {
        size_t pos = item.find('=');
        if (pos == std::string::npos) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type unordered_map", str));
        }
        std::string key = item.substr(0, pos);
        std::istringstream valueStream(item.substr(pos + 1));
        T value;
        if (!(valueStream >> value)) {
            throw std::invalid_argument(fmt::format("Failed to convert string \"{}\" to type {}", str, typeid(T).name()));
        }
        result[key] = value;
    }
    return result;
}

template <typename T>
std::string VarConverter<std::unordered_map<std::string, T>, std::string>::operator()(const std::unordered_map<std::string, T>& vals) const noexcept {
    std::ostringstream oss;
    for (auto it = vals.begin(); it != vals.end(); ++it) {
        if (it != vals.begin()) {
            oss << ";";
        }
        oss << it->first << "=" << it->second;
    }
    return oss.str();
}

VarBase::VarBase(std::string_view name,
                 std::string_view description) noexcept : name_(name), description_(description) {}

std::string_view VarBase::Name() const noexcept {
    return name_;
}

std::string_view VarBase::Description() const noexcept {
    return description_;
}

template <typename T, typename FromStr, typename ToStr>
std::string Var<T, FromStr, ToStr>::ToString() const noexcept {
    std::shared_lock lock(mtx_);
    return ToStr()(val_);
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::FromString(const std::string_view str) {
    std::unique_lock lock(mtx_);
    T new_val = FromStr()(str);
    if (new_val != val_) {
        auto old_val = val_;
        val_ = new_val;
        for (auto& [key, listener] : listeners_) {
            listener(old_val, val_);
        }
    }
}

template <typename T, typename FromStr, typename ToStr>
T Var<T, FromStr, ToStr>::GetValue() const noexcept {
    std::shared_lock lock(mtx_);
    return val_;
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::SetValue(const T& val) noexcept {
    std::unique_lock lock(mtx_);
    if (val != val_) {
        auto old_val = val_;
        val_ = val;
        for (auto& [key, listener] : listeners_) {
            listener(old_val, val_);
        }
    }
}

template <typename T, typename FromStr, typename ToStr>
std::string_view Var<T, FromStr, ToStr>::TypeName() const noexcept {
    return typeid(T).name();
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::RemoveListener(const std::uint64_t key) noexcept {
    std::unique_lock lock(mtx_);
    listeners_.erase(key);
}

template <typename T, typename FromStr, typename ToStr>
std::uint64_t Var<T, FromStr, ToStr>::AddListener(OnChange listener) noexcept {
    static std::atomic<std::uint64_t> next_key = 0;
    std::unique_lock lock(mtx_);
    auto key = next_key++;
    listeners_[key] = listener;
    return key;
}

template <typename T, typename FromStr, typename ToStr>
void Var<T, FromStr, ToStr>::ClearListeners() noexcept {
    std::unique_lock lock(mtx_);
    listeners_.clear();
}

Config::Config(std::string_view name) noexcept : name_(name) {}

std::string_view Config::Name() const noexcept {
    return name_;
}

template <typename T>
typename Var<T>::Ptr Config::Lookup(const std::string_view name,
                                  const T& default_val,
                                  const std::string_view description) {
    std::unique_lock lock(mtx_);
    auto it = vars_.find(name);
    if (it != vars_.end()) {
        return std::dynamic_pointer_cast<Var<T>>(it->second);
    }
    auto var = std::make_shared<Var<T>>(name, default_val, description);
    vars_[std::string(name)] = var;
    return var;
}

template <typename T>
typename Var<T>::Ptr Config::Lookup(const std::string_view name) const {
    std::shared_lock lock(mtx_);
    auto it = vars_.find(name);
    if (it != vars_.end()) {
        return std::dynamic_pointer_cast<Var<T>>(it->second);
    }
    return nullptr;
}

VarBase::Ptr Config::LookupBase(std::string_view name) const noexcept {
    std::shared_lock lock(mtx_);
    auto it = vars_.find(name);
    if (it != vars_.end()) {
        return it->second;
    }
    return nullptr;
}

void Config::LoadYaml(const YAML::Node& root) {
    std::unique_lock lock(mtx_);
    for (auto&& [key, value] : root) {
        auto var = LookupBase(key.as<std::string>());
        if (var) {
            var->FromString(value.as<std::string>());
        }
    }
}

void Config::Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept {
    std::shared_lock lock(mtx_);
    for (auto&& [key, value] : vars_) {
        visitor(value);
    }
}

Config::Ptr RootConfig() noexcept {
    static Config root("Root");
    return std::make_shared<Config>(root);
}

}  // namespace cfg

}  // namespace ws
