   
                 
                                                     
  
                                                
              
                                 
               
                   
  
                                 
   

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

   
         
                                                      
                                                      
  
                                  
                         
  
        
                                                              
                                                                                       
   
template <typename From, typename To>
class VarConverter {
public:
    To operator()(const From& val) const noexcept {
        return static_cast<To>(val);
    }
};

                                                                      
template <typename From>
class VarConverter<From, std::string> {
public:
    std::string operator()(const From& val) const noexcept {
        using std::to_string;
        return to_string(val);
    }
};

                                                 
template <>
class VarConverter<std::string, std::string> {
public:
    std::string operator()(const std::string_view val) const noexcept {
        return val.data();
    }
};

   
                                                                                     
  
                                                          
   
template <typename To>
class VarConverter<std::string, To> {
public:
    To operator()(const std::string_view str) const {
        To val {};
        std::istringstream ss {str.data()};
        ss >> val;
        if (ss.fail()) {
            throw std::invalid_argument {
                fmt::format("Invalid value: '{}'", str)};
        } else {
            return val;
        }
    }
};

   
                                                                  
  
                                                                         
   
template <typename T>
class VarConverter<std::string, std::list<T>> {
public:
    std::list<T> operator()(const std::string_view str) const {
        const auto node {LoadYamlString(str)};
        if (!node.IsSequence()) {
            throw std::invalid_argument {
                fmt::format("Mismatched type: '{}'", str)};
        }

        std::list<T> vals;
        std::ranges::for_each(node, [&vals](const YAML::Node& child) {
            std::ostringstream ss;
            ss << child;
            vals.emplace_back(VarConverter<std::string, T> {}(ss.str()));
        });

        return vals;
    }
};

                                                            
template <typename T>
class VarConverter<std::list<T>, std::string> {
public:
    std::string operator()(const std::list<T>& vals) const noexcept {
        YAML::Node node;
        std::ranges::for_each(vals, [&node](const T& val) {
            node.push_back(
                LoadYamlString(VarConverter<T, std::string> {}(val)));
        });

        std::ostringstream ss;
        ss << node;
        return ss.str();
    }
};

                                                              
template <typename T>
class VarConverter<std::string, std::vector<T>> {
public:
    std::vector<T> operator()(const std::string_view str) const {
        std::vector<T> vals;
        std::ranges::move(VarConverter<std::string, std::list<T>> {}(str),
                          std::back_inserter(vals));
        return vals;
    }
};

                                                              
template <typename T>
class VarConverter<std::vector<T>, std::string> {
public:
    std::string operator()(const std::vector<T>& vals) const noexcept {
        return VarConverter<std::list<T>, std::string> {}(
            {vals.cbegin(), vals.cend()});
    }
};

                                                           
template <typename T>
class VarConverter<std::string, std::set<T>> {
public:
    std::set<T> operator()(const std::string_view str) const {
        std::set<T> vals;
        std::ranges::move(VarConverter<std::string, std::list<T>> {}(str),
                          std::inserter(vals, vals.end()));
        return vals;
    }
};

                                                           
template <typename T>
class VarConverter<std::set<T>, std::string> {
public:
    std::string operator()(const std::set<T>& vals) const noexcept {
        return VarConverter<std::list<T>, std::string> {}(
            {vals.cbegin(), vals.cend()});
    }
};

                                                                      
template <typename T>
class VarConverter<std::string, std::unordered_set<T>> {
public:
    std::unordered_set<T> operator()(const std::string_view str) const {
        std::unordered_set<T> vals;
        std::ranges::move(VarConverter<std::string, std::list<T>> {}(str),
                          std::inserter(vals, vals.end()));
        return vals;
    }
};

                                                                      
template <typename T>
class VarConverter<std::unordered_set<T>, std::string> {
public:
    std::string operator()(const std::unordered_set<T>& vals) const noexcept {
        return VarConverter<std::list<T>, std::string> {}(
            {vals.cbegin(), vals.cend()});
    }
};

   
                                                                 
  
                                                                        
   
template <typename T>
class VarConverter<std::string, std::map<std::string, T>> {
public:
    std::map<std::string, T> operator()(const std::string_view str) const {
        const auto node {LoadYamlString(str)};
        if (!node.IsMap()) {
            throw std::invalid_argument {
                fmt::format("Mismatched type: '{}'", str)};
        }

        std::map<std::string, T> vals;
        std::ranges::for_each(
            node, [&vals](const std::pair<YAML::Node, YAML::Node>& child) {
                std::ostringstream key;
                key << child.first;
                std::ostringstream val;
                val << child.second;
                vals.emplace(key.str(),
                             VarConverter<std::string, T> {}(val.str()));
            });

        return vals;
    }
};

                                                           
template <typename T>
class VarConverter<std::map<std::string, T>, std::string> {
public:
    std::string operator()(
        const std::map<std::string, T>& vals) const noexcept {
        YAML::Node node;
        std::ranges::for_each(
            vals, [&node](const std::pair<std::string, T>& val) {
                node[val.first] =
                    LoadYamlString(VarConverter<T, std::string> {}(val.second));
            });

        std::ostringstream ss;
        ss << node;
        return ss.str();
    }
};

                                                                      
template <typename T>
class VarConverter<std::string, std::unordered_map<std::string, T>> {
public:
    std::unordered_map<std::string, T> operator()(
        const std::string_view str) const {
        std::unordered_map<std::string, T> vals;
        std::ranges::move(
            VarConverter<std::string, std::map<std::string, T>> {}(str),
            std::inserter(vals, vals.end()));
        return vals;
    }
};

                                                                      
template <typename T>
class VarConverter<std::unordered_map<std::string, T>, std::string> {
public:
    std::string operator()(
        const std::unordered_map<std::string, T>& vals) const noexcept {
        return VarConverter<std::map<std::string, T>, std::string> {}(
            {vals.cbegin(), vals.cend()});
    }
};

                                                     
class VarBase {
public:
    using Ptr = std::shared_ptr<VarBase>;

    explicit VarBase(std::string_view name,
                     std::string_view description = "") noexcept;

    virtual ~VarBase() noexcept = default;

                              
    std::string_view Name() const noexcept;

                                     
    std::string_view Description() const noexcept;

                                           
    virtual std::string ToString() const noexcept = 0;

                                       
    virtual void FromString(std::string_view str) = 0;

protected:
    std::string name_;
    std::string description_;
};

   
                                     
  
                               
                                                                                    
                                                                                  
   
template <typename T, typename FromStr = VarConverter<std::string, T>,
          typename ToStr = VarConverter<T, std::string>>
requires std::is_invocable_r_v<T, FromStr, std::string> && std::
    is_nothrow_invocable_r_v<std::string, ToStr, T>
class Var : public VarBase {
public:
    using Ptr = std::shared_ptr<Var>;

       
                                                   
      
                                                    
                                                   
       
    using OnChange = std::function<void(const T& old_val, const T& new_val)>;

    explicit Var(const std::string_view name, const T& default_val,
                 const std::string_view description = "") noexcept :
        VarBase {name, description}, val_ {default_val} {}

    Var(const Var&) = delete;

    Var(Var&&) = delete;

    Var& operator=(const Var&) = delete;

    Var& operator=(Var&&) = delete;

    std::string ToString() const noexcept override {
        return ToStr {}(GetValue());
    }

    void FromString(const std::string_view str) override {
        SetValue(FromStr {}(str));
    }

    T GetValue() const noexcept {
        const std::shared_lock locker {mtx_};
        return val_;
    }

    void SetValue(const T& val) noexcept {
        {
            const std::shared_lock locker {mtx_};
            if (val != val_) {
                std::ranges::for_each(
                    listeners_, [&val, this](const auto& listener) noexcept {
                        try {
                            listener.second(val_, val);
                        } catch (const std::exception& err) {
                            std::osyncstream {std::cerr} << err.what()
                                                         << std::endl;
                        }
                    });
            }
        }

        const std::unique_lock locker {mtx_};
        val_ = val;
    }

                                                           
    std::string_view TypeName() const noexcept {
        return typeid(T).name();
    }

       
                                
      
                                                             
       
    void RemoveListener(const std::uint64_t key) noexcept {
        const std::unique_lock locker {mtx_};
        listeners_.erase(key);
    }

       
                                                     
      
                                  
                                                          
       
    std::uint64_t AddListener(OnChange listener) noexcept {
        const std::unique_lock locker {mtx_};
        static std::uint64_t key {0};
        listeners_[key] = std::move(listener);
        return key++;
    }

                             
    void ClearListeners() noexcept {
        const std::unique_lock locker {mtx_};
        listeners_.clear();
    }

private:
    mutable std::shared_mutex mtx_;

    T val_;
    std::unordered_map<std::uint64_t, OnChange> listeners_;
};

                      
class Config {
public:
    using Ptr = std::shared_ptr<Config>;

    explicit Config(std::string_view name) noexcept;

    Config(const Config&) = delete;

    Config(Config&&) = delete;

    Config& operator=(const Config&) = delete;

    Config& operator=(Config&&) = delete;

    std::string_view Name() const noexcept;

                                                                        
    template <typename T>
    typename Var<T>::Ptr Lookup(const std::string_view name,
                                const T& default_val,
                                const std::string_view description = "") {
        if (const auto var {Lookup<T>(name)}; !var) {
            const auto new_var {
                std::make_shared<Var<T>>(name, default_val, description)};
            const std::unique_lock locker {mtx_};
            vars_.emplace(name, new_var);
            return new_var;
        } else {
            return var;
        }
    }

       
                                            
      
                                 
                                   
                                                
      
                                                                                           
       
    template <typename T>
    typename Var<T>::Ptr Lookup(const std::string_view name) const {
        if (const auto base {LookupBase(name)}; base) {
            if (const auto var {std::dynamic_pointer_cast<Var<T>>(base)}; var) {
                return var;
            } else {
                throw std::invalid_argument {
                    fmt::format("Mismatched type: '{}'", name)};
            }
        } else {
            return nullptr;
        }
    }

                                                      
    VarBase::Ptr LookupBase(std::string_view name) const noexcept;

       
                                                                       
      
               
                                                                                     
                                      
       
    void LoadYaml(const YAML::Node& root);

                            
    void Visit(std::function<void(VarBase::Ptr)> visitor) const noexcept;

private:
    using VarMap = std::unordered_map<std::string, VarBase::Ptr>;

    mutable std::shared_mutex mtx_;
    std::string name_;
    VarMap vars_;
};

                               
Config::Ptr RootConfig() noexcept;

}                  

}                 