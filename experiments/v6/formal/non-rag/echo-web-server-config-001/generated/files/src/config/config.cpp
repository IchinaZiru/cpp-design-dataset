#include "config.h"
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

namespace ws {

namespace cfg {

template <typename From, typename To>
To VarConverter<From, To>::operator()(const From& val) const noexcept {
    return static_cast<To>(val);
}

template <typename From>
std::string VarConverter<From, std::string>::operator()(const From& val) const noexcept {
    return to_string(val);
}

std::string VarConverter<std::string, std::string>::operator()(const std::string_view val) const noexcept {
    return {val};
}

template <typename To>
To VarConverter<std::string, To>::operator()(const std::string_view str) const {
    To val {};
    std::istringstream ss {str.data()};
    if (!(ss >> val)) {
        throw std::invalid_argument(fmt::format("Invalid value: '{}'", str));
    }
    return val;
}

template <typename T>
std::list<T> VarConverter<std::string, std::list<T>>::operator()(const std::string_view str) const {
    const auto node {LoadYamlString(str)};
    if (!node.IsSequence()) {
        throw std::invalid_argument(fmt::format("Invalid value: '{}'", str));
    }
    std::list<T> vals;
    std::ranges::for_each(node, [&vals](const YAML::Node& child) {
        std::ostringstream ss;
        ss << child;
        vals.emplace_back(VarConverter<std::string, T> {}(ss.str()));
    });
    return vals;
}

template <typename T>
std::string VarConverter<std::list<T>, std::string>::operator()(const std::list<T>& vals) const noexcept {
    YAML::Node node;
    std::ranges::for_each(vals, [&node](const T& val) {
        node.push_back(LoadYamlString(VarConverter<T, std::string> {}(val)));
    });
    return SaveYamlString(node);
}

template <typename T>
std::vector<T> VarConverter<std::string, std::vector<T>>::operator()(const std::string_view str) const {
    const auto node {LoadYamlString(str)};
    if (!node.IsSequence()) {
        throw std::invalid_argument(fmt::format("Invalid value: '{}'", str));
    }
    std::vector<T> vals;
    std::ranges::for_each(node, [&vals](const YAML::Node& child) {
        std::ostringstream ss;
        ss << child;
        vals.emplace_back(VarConverter<std::string, T> {}(ss.str()));
    });
    return vals;
}

template <typename T>
std::string VarConverter<std::vector<T>, std::string>::operator()(const std::vector<T>& vals) const noexcept {
    YAML::Node node;
    std::ranges::for_each(vals, [&node](const T& val) {
        node.push_back(LoadYamlString(VarConverter<T, std::string> {}(val)));
    });
    return SaveYamlString(node);
}

template <typename T>
std::set<T> VarConverter<std::string, std::set<T>>::operator()(const std::string_view str) const {
    const auto node {LoadYamlString(str)};
    if (!node.IsSequence()) {
        throw std::invalid_argument(fmt::format("Invalid value: '{}'", str));
    }
    std::set<T> vals;
    std::ranges::for_each(node, [&vals](const YAML::Node& child) {
        std::ostringstream ss;
        ss << child;
        vals.emplace(VarConverter<std::string, T> {}(ss.str()));
    });
    return vals;
}

template <typename T>
std::string VarConverter<std::set<T>, std::string>::operator()(const std::set<T>& vals) const noexcept {
    YAML::Node node;
    std::ranges::for_each(vals, [&node](const T& val) {
        node.push_back(LoadYamlString(VarConverter<T, std::string> {}(val)));
    });
    return SaveYamlString(node);
}

template <typename T>
std::unordered_set<T> VarConverter<std::string, std::unordered_set<T>>::operator()(const std::string_view str) const {
    const auto node {LoadYamlString(str)};
    if (!node.IsSequence()) {
        throw std::invalid_argument(fmt::format("Invalid value: '{}'", str));
    }
    std::unordered_set<T> vals;
    std::ranges::for_each(node, [&vals](const YAML::Node& child) {
        std::ostringstream ss;
        ss << child;
        vals.emplace(VarConverter<std::string, T> {}(ss.str()));
    });
    return vals;
}

template <typename T>
std::string VarConverter<std::unordered_set<T>, std::string>::operator()(const std::unordered_set<T>& vals) const noexcept {
    YAML::Node node;
    std::ranges::for_each(vals, [&node](const T& val) {
        node.push_back(LoadYamlString(VarConverter<T, std::string> {}(val)));
    });
    return SaveYamlString(node);
}

template <typename T>
std::map<std::string, T> VarConverter<std::string, std::map<std::string, T>>::operator()(const std::string_view str) const {
    const auto node {LoadYamlString(str)};
    if (!node.IsMap()) {
        throw std::invalid_argument(fmt::format("Invalid value: '{}'", str));
    }
    std::map<std::string, T> vals;
    std::ranges::for_each(node, [&vals](const std::pair<YAML::Node, YAML::Node>& child) {
        std::ostringstream key;
        key << child.first;
        std::ostringstream val;
        val << child.second;
        vals.emplace(key.str(), VarConverter<std::string, T> {}(val.str()));
    });
    return vals;
}

template <typename T>
std::string VarConverter<std::map<std::string, T>, std::string>::operator()(const std::map<std::string, T>& vals) const noexcept {
    YAML::Node node;
    std::ranges::for_each(vals, [&node](const std::pair<std::string, T>& val) {
        node[val.first] = LoadYamlString(VarConverter<T, std::string> {}(val.second));
    });
    return SaveYamlString(node);
}

template <typename T>
std::unordered_map<std::string, T> VarConverter<std::string, std::unordered_map<std::string, T>>::operator()(const std::string_view str) const {
    const auto node {LoadYamlString(str)};
    if (!node.IsMap()) {
        throw std::invalid_argument(fmt::format("Invalid value: '{}'", str));
    }
    std::unordered_map<std::string, T> vals;
    std::ranges::for_each(node, [&vals](const std::pair<YAML::Node, YAML::Node>& child) {
        std::ostringstream key;
        key << child.first;
        std::ostringstream val;
        val << child.second;
        vals.emplace(key.str(), VarConverter<std::string, T> {}(val.str()));
    });
    return vals;
}

template <typename T>
std::string VarConverter<std::unordered_map<std::string, T>, std::string>::operator()(const std::unordered_map<std::string, T>& vals) const noexcept {
    YAML::Node node;
    std::ranges::for_each(vals, [&node](const std::pair<std::string, T>& val) {
        node[val.first] = LoadYamlString(VarConverter<T, std::string> {}(val.second));
    });
    return SaveYamlString(node);
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
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
std::string Var<T, FromStr, ToStr>::ToString() const noexcept {
    return ToStr {}(GetValue());
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
void Var<T, FromStr, ToStr>::FromString(const std::string_view str) {
    const auto old_val {GetValue()};
    SetValue(FromStr {}(str));
    if (old_val != GetValue()) {
        std::ranges::for_each(listeners_, [&val = GetValue(), this](const auto& listener) noexcept {
            try {
                listener.second(old_val, val);
            } catch (const std::exception& err) {
                std::osyncstream {std::cerr} << err.what() << std::endl;
            }
        });
    }
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
T Var<T, FromStr, ToStr>::GetValue() const noexcept {
    const std::shared_lock locker {mtx_};
    return val_;
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
void Var<T, FromStr, ToStr>::SetValue(const T& val) noexcept {
    const std::unique_lock locker {mtx_};
    val_ = val;
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
    const std::unique_lock locker {mtx_};
    listeners_.erase(key);
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
std::uint64_t Var<T, FromStr, ToStr>::AddListener(OnChange listener) noexcept {
    static std::uint64_t key {0};
    const std::unique_lock locker {mtx_};
    return listeners_.emplace(++key, std::move(listener)).first->first;
}

template <typename T, typename FromStr, typename ToStr>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
void Var<T, FromStr, ToStr>::ClearListeners() noexcept {
    const std::unique_lock locker {mtx_};
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
    const auto var {Lookup<T>(name)};
    if (var == nullptr) {
        const auto new_var { std::make_shared<Var<T>>(name, default_val, description)};
        const std::unique_lock locker {mtx_};
        vars_.emplace(name, new_var);
        return new_var;
    }
    return var;
}

template <typename T>
typename Var<T>::Ptr Config::Lookup(const std::string_view name) const {
    const auto base {LookupBase(name)};
    if (base == nullptr) {
        return nullptr;
    }
    const auto var {std::dynamic_pointer_cast<Var<T>>(base)};
    if (!var) {
        throw std::invalid_argument(fmt::format("Mismatched type: '{}'", name));
    }
    return var;
}

VarBase::Ptr Config::LookupBase(std::string_view name) const noexcept {
    const std::shared_lock locker {mtx_};
    const auto var {vars_.find(name.data())};
    if (var == vars_.cend()) {
        return nullptr;
    }
    return var->second;
}

void Config::LoadYaml(const YAML::Node& root) {
    std::list<std::pair<std::string, YAML::Node>> members;
    ExtractMembers(root).merge(members, [](const std::pair<std::string, YAML::Node>& lhs, const std::pair<std::string, YAML::Node>& rhs) noexcept {
        return lhs.first < rhs.first;
    });
    for (const auto& [key, node] : members) {
        if (auto var {LookupBase(key)}) {
            try {
                var->FromString(node.as<std::string>());
            } catch (const std::exception& err) {
                std::osyncstream {std::cerr} << err.what() << std::endl;
            }
        }
    }
}

void Config::Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept {
    for (const auto& var : vars_) {
        try {
            visitor(var.second);
        } catch (const std::exception& err) {
            std::osyncstream {std::cerr} << err.what() << std::endl;
        }
    }
}

Config::Ptr RootConfig() noexcept {
    static const auto ins {std::make_shared<Config>("root")};
    return ins;
}

}  // namespace cfg

}  // namespace ws
