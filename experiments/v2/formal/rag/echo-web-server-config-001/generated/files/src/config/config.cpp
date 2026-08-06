#include "config.h"
#include <yaml-cpp/yaml.h>
#include <sstream>
#include <stdexcept>
#include <string_view>
#include <unordered_map>
#include <vector>

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
    std::istringstream iss(static_cast<std::string>(str));
    To val;
    if (!(iss >> val)) {
        throw std::invalid_argument("Conversion failed");
    }
    return val;
}

template <typename T>
std::list<T> VarConverter<std::string, std::list<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(static_cast<std::string>(str));
    std::list<T> vals;
    T val;
    while (iss >> val) {
        vals.push_back(val);
    }
    if (vals.empty()) {
        throw std::invalid_argument("String does not represent a list");
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::list<T>, std::string>::operator()(const std::list<T>& vals) const noexcept {
    std::ostringstream oss;
    for (const auto& val : vals) {
        oss << val << " ";
    }
    return oss.str();
}

template <typename T>
std::vector<T> VarConverter<std::string, std::vector<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(static_cast<std::string>(str));
    std::vector<T> vals;
    T val;
    while (iss >> val) {
        vals.push_back(val);
    }
    if (vals.empty()) {
        throw std::invalid_argument("String does not represent an array");
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::vector<T>, std::string>::operator()(const std::vector<T>& vals) const noexcept {
    std::ostringstream oss;
    for (const auto& val : vals) {
        oss << val << " ";
    }
    return oss.str();
}

template <typename T>
std::set<T> VarConverter<std::string, std::set<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(static_cast<std::string>(str));
    std::set<T> vals;
    T val;
    while (iss >> val) {
        vals.insert(val);
    }
    if (vals.empty()) {
        throw std::invalid_argument("String does not represent a set");
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::set<T>, std::string>::operator()(const std::set<T>& vals) const noexcept {
    std::ostringstream oss;
    for (const auto& val : vals) {
        oss << val << " ";
    }
    return oss.str();
}

template <typename T>
std::unordered_set<T> VarConverter<std::string, std::unordered_set<T>>::operator()(const std::string_view str) const {
    std::istringstream iss(static_cast<std::string>(str));
    std::unordered_set<T> vals;
    T val;
    while (iss >> val) {
        vals.insert(val);
    }
    if (vals.empty()) {
        throw std::invalid_argument("String does not represent an unordered set");
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::unordered_set<T>, std::string>::operator()(const std::unordered_set<T>& vals) const noexcept {
    std::ostringstream oss;
    for (const auto& val : vals) {
        oss << val << " ";
    }
    return oss.str();
}

template <typename T>
std::map<std::string, T> VarConverter<std::string, std::map<std::string, T>>::operator()(const std::string_view str) const {
    std::istringstream iss(static_cast<std::string>(str));
    std::map<std::string, T> vals;
    std::string key;
    T val;
    while (iss >> key >> val) {
        vals[key] = val;
    }
    if (vals.empty()) {
        throw std::invalid_argument("String does not represent a map");
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::map<std::string, T>, std::string>::operator()(const std::map<std::string, T>& vals) const noexcept {
    std::ostringstream oss;
    for (const auto& [key, val] : vals) {
        oss << key << " " << val << " ";
    }
    return oss.str();
}

template <typename T>
std::unordered_map<std::string, T> VarConverter<std::string, std::unordered_map<std::string, T>>::operator()(const std::string_view str) const {
    std::istringstream iss(static_cast<std::string>(str));
    std::unordered_map<std::string, T> vals;
    std::string key;
    T val;
    while (iss >> key >> val) {
        vals[key] = val;
    }
    if (vals.empty()) {
        throw std::invalid_argument("String does not represent an unordered map");
    }
    return vals;
}

template <typename T>
std::string VarConverter<std::unordered_map<std::string, T>, std::string>::operator()(const std::unordered_map<std::string, T>& vals) const noexcept {
    std::ostringstream oss;
    for (const auto& [key, val] : vals) {
        oss << key << " " << val << " ";
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
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
std::string Var<T, FromStr, ToStr>::ToString() const noexcept {
    return ToStr {}(GetValue());
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
void Var<T, FromStr, ToStr>::FromString(const std::string_view str) {
    SetValue(FromStr {}(str));
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
T Var<T, FromStr, ToStr>::GetValue() const noexcept {
    std::shared_lock lock(mtx_);
    return val_;
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
void Var<T, FromStr, ToStr>::SetValue(const T& val) noexcept {
    std::unique_lock lock(mtx_);
    const auto old_val = val_;
    val_ = val;
    for (const auto& [key, listener] : listeners_) {
        listener(old_val, val);
    }
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
std::string_view Var<T, FromStr, ToStr>::TypeName() const noexcept {
    return typeid(T).name();
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
void Var<T, FromStr, ToStr>::RemoveListener(const std::uint64_t key) noexcept {
    std::unique_lock lock(mtx_);
    listeners_.erase(key);
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
std::uint64_t Var<T, FromStr, ToStr>::AddListener(OnChange listener) noexcept {
    static std::atomic<std::uint64_t> key_counter = 0;
    const auto key = ++key_counter;
    std::unique_lock lock(mtx_);
    listeners_[key] = listener;
    return key;
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
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
    vars_[name] = var;
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
    for (const auto& [key, value] : root) {
        if (!key.as<std::string>().empty()) {
            auto var = LookupBase(key.as<std::string>());
            if (var != nullptr) {
                std::ostringstream ss;
                ss << value;
                var->FromString(ss.str());
            }
        }
    }
}

void Config::Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept {
    std::shared_lock lock(mtx_);
    for (const auto& [name, var] : vars_) {
        visitor(var);
    }
}

Config::Ptr RootConfig() noexcept {
    static Config root_config("Root");
    return std::make_shared<Config>(root_config);
}

}  // namespace cfg

}  // namespace ws
