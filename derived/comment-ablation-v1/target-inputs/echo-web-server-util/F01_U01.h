   
               
                                  
  
                                                
              
                                 
               
                   
  
                               
  
                                             
   

#pragma once

#include <fmt/format.h>
#include <yaml-cpp/yaml.h>

#include <sys/stat.h>

#include <concepts>
#include <functional>
#include <initializer_list>
#include <memory>
#include <regex>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

                             
namespace ws {

                                            
using FileDescriptor = int;

                                                           
inline constexpr FileDescriptor invalid_file_descriptor {-1};

                                     
std::string StringToLower(std::string str) noexcept;

                                     
std::string StringToUpper(std::string str) noexcept;

                                                        
std::string ReplaceAllSubstring(std::string_view str, std::string_view from,
                                std::string_view to) noexcept;

                                      
std::vector<std::string> SplitString(const std::string& str,
                                     const std::regex& pattern) noexcept;

                              
std::vector<std::string> SplitStringToLines(const std::string& str) noexcept;

   
                                            
  
                               
                                          
  
                                                                                  
   
YAML::Node LoadYamlString(
    std::string_view str,
    std::initializer_list<std::string_view> required_fields = {});

                                                                                                                
void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node,
                                 std::string_view field);

   
                                             
  
                                                                                         
   
constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept {
    return fd >= 0;
}

   
                                                
  
                                                                  
   
void SetFileDescriptorAsNonblocking(FileDescriptor fd);

                                                                     
[[noreturn]] void ThrowLastSystemError();

                                     
std::uint32_t CurrentThreadId() noexcept;

   
                                                  
  
                                      
                                               
                                                 
   
void Backtrace(std::vector<std::string>& stack, std::size_t size,
               std::size_t skip = 0) noexcept;

   
                                                  
  
                                               
                                                 
                                             
   
std::string Backtrace(std::size_t size, std::size_t skip = 0,
                      std::string_view prefix = "") noexcept;

   
                                                         
  
                                                
                                                                                              
   
template <typename T, typename... Args>
class Singleton {
public:
       
                                         
      
                                               
       
    template <Args... args>
    static T& Instance() noexcept {
        static T ins {std::move(args)...};
        return ins;
    }
};

   
                                                           
  
                                                
                                                                                                   
   
template <typename T, typename... Args>
class SingletonPtr {
public:
       
                                         
      
                                               
       
    template <Args... args>
    static std::shared_ptr<T> Instance() noexcept {
        static const std::shared_ptr<T> ins {
            std::make_shared<T>(std::move(args)...)};
        return ins;
    }
};

template <typename T, typename Cleaner = std::function<void(T)>>
requires std::is_invocable_v<Cleaner, T>
class RAII {
public:
       
                                          
      
                                                  
                                
       
    explicit RAII(T obj, Cleaner cleaner) noexcept :
        obj_ {std::move(obj)}, cleaner_ {std::move(cleaner)} {}

    RAII(const RAII&) = delete;

    RAII(RAII&&) = delete;

    RAII& operator=(const RAII&) = delete;

    RAII& operator=(RAII&&) = delete;

    ~RAII() noexcept {
        cleaner_(obj_);
    }

    const T& Object() const noexcept {
        return obj_;
    }

private:
    T obj_;
    Cleaner cleaner_;
};

   
         
                                                              
  
           
                                                                  
   
class MappedReadOnlyFile {
public:
    MappedReadOnlyFile() noexcept;

    MappedReadOnlyFile(const MappedReadOnlyFile&) = delete;

    MappedReadOnlyFile(MappedReadOnlyFile&&) noexcept;

    MappedReadOnlyFile& operator=(const MappedReadOnlyFile&) = delete;

    MappedReadOnlyFile& operator=(MappedReadOnlyFile&&) noexcept;

    ~MappedReadOnlyFile() noexcept;

       
                                     
      
                                                                       
                                                                      
                                                           
       
    std::byte* Map(std::string path);

                       
    void Unmap() noexcept;

                          
    std::size_t Size() const noexcept;

                          
    std::byte* Data() const noexcept;

                          
    std::string_view Path() const noexcept;

private:
       
                             
      
                                                                       
                                                                      
                                                        
       
    void Check();

    std::string path_;
    struct stat stat_ {};
    std::byte* data_ {nullptr};
};

template <typename T, typename U, typename Ret = T>
concept Addable = requires(T t, U u) {
    { t + u } -> std::convertible_to<Ret>;
};

}                 