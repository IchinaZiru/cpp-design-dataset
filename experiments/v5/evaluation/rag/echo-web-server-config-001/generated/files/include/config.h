/**
 * @file config.h
 * @brief The configuration manager based on @p YAML.
 *
 * @author Chen Zhenshuo (chenzs108@outlook.com)
 * @par GitHub
 * https://github.com/Zhuagenborn
 * @version 1.0
 * @date 2022-05-10
 *
 * @example tests/config_test.cpp
 */

#pragma once

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


namespace ws {

namespace cfg {

/**
 * @brief
 * Convert a configuration variable into another type.
 * The default implementation is using @p static_cast.
 *
 * @tparam From The original type.
 * @tparam To A new type.
 *
 * @note
 * If a custom type needs to be saved to a configuration file,
 * it needs to be template-specialized to allow interconversion between it and strings.
 */
template <typename From, typename To>
class VarConverter {
public:
    To operator()(const From& val) const noexcept { return static_cast<To>(val); }
};

//! Convert a configuration variable into a string using @p to_string.
template <typename From>
class VarConverter<From, std::string> {
public:
    std::string operator()(const From& val) const noexcept { return std::to_string(val); }
};

//! Return the variable itself if it is a string.
template <>
class VarConverter<std::string, std::string> {
public:
    std::string operator()(const std::string_view val) const noexcept { return std::string(val); }
};

/**
 * @brief Convert a string into a configuration variable using @p std::istringstream.
 *
 * @exception std::invalid_argument The conversion failed.
 */
template <typename To>
class VarConverter<std::string, To> {
public:
    To operator()(const std::string_view str) const {
        std::istringstream iss(std::string(str));
        To val;
        if (!(iss >> val)) {
            throw std::invalid_argument("Conversion failed");
        }
        return val;
    }
};

/**
 * @brief Convert a string into a list of configuration variables.
 *
 * @exception std::invalid_argument The string does not represent a list.
 */
template <typename T>
class VarConverter<std::string, std::list<T>> {
public:
    std::list<T> operator()(const std::string_view str) const {
        std::istringstream iss(std::string(str));
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
};

//! Convert a list of configuration variables into a string.
template <typename T>
class VarConverter<std::list<T>, std::string> {
public:
    std::string operator()(const std::list<T>& vals) const noexcept {
        std::ostringstream oss;
        for (const auto& val : vals) {
            oss << val << " ";
        }
        return oss.str();
    }
};

//! Convert a string into an array of configuration variables.
template <typename T>
class VarConverter<std::string, std::vector<T>> {
public:
    std::vector<T> operator()(const std::string_view str) const {
        std::istringstream iss(std::string(str));
        std::vector<T> vals;
        T val;
        while (iss >> val) {
            vals.push_back(val);
        }
        if (vals.empty()) {
            throw std::invalid_argument("String does not represent a vector");
        }
        return vals;
    }
};

//! Convert an array of configuration variables into a string.
template <typename T>
class VarConverter<std::vector<T>, std::string> {
public:
    std::string operator()(const std::vector<T>& vals) const noexcept {
        std::ostringstream oss;
        for (const auto& val : vals) {
            oss << val << " ";
        }
        return oss.str();
    }
};

//! Convert a string into a set of configuration variables.
template <typename T>
class VarConverter<std::string, std::set<T>> {
public:
    std::set<T> operator()(const std::string_view str) const {
        std::istringstream iss(std::string(str));
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
};

//! Convert a set of configuration variables into a string.
template <typename T>
class VarConverter<std::set<T>, std::string> {
public:
    std::string operator()(const std::set<T>& vals) const noexcept {
        std::ostringstream oss;
        for (const auto& val : vals) {
            oss << val << " ";
        }
        return oss.str();
    }
};

//! Convert a string into an unordered set of configuration variables.
template <typename T>
class VarConverter<std::string, std::unordered_set<T>> {
public:
    std::unordered_set<T> operator()(const std::string_view str) const {
        std::istringstream iss(std::string(str));
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
};

//! Convert an unordered set of configuration variables into a string.
template <typename T>
class VarConverter<std::unordered_set<T>, std::string> {
public:
    std::string operator()(const std::unordered_set<T>& vals) const noexcept {
        std::ostringstream oss;
        for (const auto& val : vals) {
            oss << val << " ";
        }
        return oss.str();
    }
};

/**
 * @brief Convert a string into a map of configuration variables.
 *
 * @exception std::invalid_argument The string does not represent a map.
 */
template <typename T>
class VarConverter<std::string, std::map<std::string, T>> {
public:
    std::map<std::string, T> operator()(const std::string_view str) const {
        std::istringstream iss(std::string(str));
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
};

//! Convert a map of configuration variables into a string.
template <typename T>
class VarConverter<std::map<std::string, T>, std::string> {
public:
    std::string operator()(const std::map<std::string, T>& vals) const noexcept {
        std::ostringstream oss;
        for (const auto& [key, val] : vals) {
            oss << key << " " << val << " ";
        }
        return oss.str();
    }
};

//! Convert a string into an unordered map of configuration variables.
template <typename T>
class VarConverter<std::string, std::unordered_map<std::string, T>> {
public:
    std::unordered_map<std::string, T> operator()(const std::string_view str) const {
        std::istringstream iss(std::string(str));
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
};

//! Convert an unordered map of configuration variables into a string.
template <typename T>
class VarConverter<std::unordered_map<std::string, T>, std::string> {
public:
    std::string operator()(const std::unordered_map<std::string, T>& vals) const noexcept {
        std::ostringstream oss;
        for (const auto& [key, val] : vals) {
            oss << key << " " << val << " ";
        }
        return oss.str();
    }
};

//! Basic information about a configuration variable.
class VarBase {
public:
    using Ptr = std::shared_ptr<VarBase>;

    explicit VarBase(std::string_view name,
                     std::string_view description = "") noexcept : name_(name), description_(description) {}

    virtual ~VarBase() noexcept = default;

    //! Get the variable name.
    std::string_view Name() const noexcept { return name_; }

    //! Get the variable description.
    std::string_view Description() const noexcept { return description_; }

    //! Convert the variable into a string.
    virtual std::string ToString() const noexcept = 0;

    //! Set the variable from a string.
    virtual void FromString(std::string_view str) = 0;

protected:
    std::string name_;
    std::string description_;
};

/**
 * @brief The configuration variable.
 *
 * @tparam T The variable type.
 * @tparam FromStr A converter that can convert a string into a type-matching value.
 * @tparam ToStr A converter that can convert a type-matching value into a string.
 */
template <typename T, typename FromStr = VarConverter<std::string, T>,
          typename ToStr = VarConverter<T, std::string>>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
class Var : public VarBase {
public:
    using Ptr = std::shared_ptr<Var>;

    /**
     * @brief The listener for value change events.
     *
     * @param old_val The old value before changing.
     * @param new_val The new value after changing.
     */
    using OnChange = std::function<void(const T& old_val, const T& new_val)>;

    explicit Var(const std::string_view name, const T& default_val,
                 const std::string_view description = "") noexcept :
        VarBase {name, description}, val_ {default_val} {}

    Var(const Var&) = delete;

    Var(Var&&) = delete;

    Var& operator=(const Var&) = delete;

    Var& operator=(Var&&) = delete;

    std::string ToString() const noexcept override {
        ToStr converter;
        return converter(val_);
    }

    void FromString(const std::string_view str) override {
        FromStr converter;
        T new_val = converter(str);
        if (new_val != val_) {
            std::unique_lock lock(mtx_);
            auto old_val = val_;
            val_ = new_val;
            for (const auto& [key, listener] : listeners_) {
                listener(old_val, val_);
            }
        }
    }

    T GetValue() const noexcept {
        std::shared_lock lock(mtx_);
        return val_;
    }

    void SetValue(const T& val) noexcept {
        if (val != val_) {
            std::unique_lock lock(mtx_);
            auto old_val = val_;
            val_ = val;
            for (const auto& [key, listener] : listeners_) {
                listener(old_val, val_);
            }
        }
    }

    //! Get a unique string representing the variable type.
    std::string_view TypeName() const noexcept { return typeid(T).name(); }

    /**
     * @brief Remove a listener.
     *
     * @param key A unique key corresponding to the listener.
     */
    void RemoveListener(const std::uint64_t key) noexcept {
        std::unique_lock lock(mtx_);
        listeners_.erase(key);
    }

    /**
     * @brief Add a listener for value change events.
     *
     * @param listener A listener.
     * @return A unique key corresponding to the listener.
     */
    std::uint64_t AddListener(OnChange listener) noexcept {
        static std::atomic<std::uint64_t> next_key = 0;
        std::unique_lock lock(mtx_);
        auto key = next_key++;
        listeners_[key] = listener;
        return key;
    }

    //! Remove all listeners.
    void ClearListeners() noexcept {
        std::unique_lock lock(mtx_);
        listeners_.clear();
    }

private:
    mutable std::shared_mutex mtx_;

    T val_;
    std::unordered_map<std::uint64_t, OnChange> listeners_;
};

//! The configuration.
class Config {
public:
    using Ptr = std::shared_ptr<Config>;

    explicit Config(std::string_view name) noexcept : name_(name) {}

    Config(const Config&) = delete;

    Config(Config&&) = delete;

    Config& operator=(const Config&) = delete;

    Config& operator=(Config&&) = delete;

    std::string_view Name() const noexcept { return name_; }

    //! Lookup a variable by its name, creating it if it does not exist.
    template <typename T>
    typename Var<T>::Ptr Lookup(const std::string_view name,
                                const T& default_val,
                                const std::string_view description = "") {
        std::unique_lock lock(mtx_);
        auto it = vars_.find(name);
        if (it != vars_.end()) {
            auto var = std::dynamic_pointer_cast<Var<T>>(it->second);
            if (!var) {
                throw std::invalid_argument("Type mismatch");
            }
            return var;
        } else {
            auto var = std::make_shared<Var<T>>(name, default_val, description);
            vars_[name] = var;
            return var;
        }
    }

    /**
     * @brief Lookup a variable by its name.
     *
     * @tparam T A variable type.
     * @param name A variable name.
     * @return The found variable or @p nullptr.
     *
     * @exception std::invalid_argument The type of the found variable does not match @p T.
     */
    template <typename T>
    typename Var<T>::Ptr Lookup(const std::string_view name) const {
        std::shared_lock lock(mtx_);
        auto it = vars_.find(name);
        if (it != vars_.end()) {
            auto var = std::dynamic_pointer_cast<Var<T>>(it->second);
            if (!var) {
                throw std::invalid_argument("Type mismatch");
            }
            return var;
        } else {
            return nullptr;
        }
    }

    //! Lookup the basic information about a variable.
    VarBase::Ptr LookupBase(std::string_view name) const noexcept {
        std::shared_lock lock(mtx_);
        auto it = vars_.find(name);
        if (it != vars_.end()) {
            return it->second;
        } else {
            return nullptr;
        }
    }

    /**
     * @brief Set the values of existing variables from a @p YAML node.
     *
     * @warning
     * If a variable in the @p YAML node does not exist in the current configuration,
     * this method will not create it.
     */
    void LoadYaml(const YAML::Node& root) {
        for (const auto& [key, value] : root) {
            std::string name = key.as<std::string>();
            auto var_base = LookupBase(name);
            if (var_base) {
                var_base->FromString(value.as<std::string>());
            }
        }
    }

    //! Visit all variables.
    void Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept {
        std::shared_lock lock(mtx_);
        for (const auto& [name, var] : vars_) {
            visitor(var);
        }
    }

private:
    using VarMap = std::unordered_map<std::string, VarBase::Ptr>;

    mutable std::shared_mutex mtx_;
    std::string name_;
    VarMap vars_;
};

//! Get the root configuration.
Config::Ptr RootConfig() noexcept {
    static Config::Ptr config = std::make_shared<Config>("RootConfig");
    return config;
}

}  // namespace cfg

}  // namespace ws
