   
               
                              
  
                                                
                                              
              
                                 
               
                   
   

#pragma once

#include "containers/buffer.h"
#include "ip.h"
#include "util.h"

#include <filesystem>
#include <iostream>
#include <memory>
#include <string>
#include <string_view>
#include <unordered_map>


namespace ws::http {

                     
inline constexpr std::string_view version {"1.1"};

                                                  
using Parameters = std::unordered_map<std::string, std::string>;

                      
enum class StatusCode : std::uint32_t {
    OK = 200,
    BadRequest = 400,
    Forbidden = 403,
    NotFound = 404
};

                                               
std::string_view StatusCodeToMessage(StatusCode code) noexcept;

                                                
std::uint32_t StatusCodeToInteger(StatusCode code) noexcept;

std::ostream& operator<<(std::ostream& os, StatusCode code) noexcept;

                 
enum class Method { Get, Post, Put, Patch, Delete };

                                         
std::string_view MethodToString(Method method) noexcept;

std::string to_string(Method method) noexcept;

   
                                               
  
                                                                                 
   
Method StringToMethod(std::string str);

std::ostream& operator<<(std::ostream& os, Method method) noexcept;

                                            
inline constexpr std::string_view new_line {"\r\n"};

   
         
                             
                                                                                              
   
std::string_view ContentTypeByFileName(std::string_view name) noexcept;

   
         
                                   
                                                                    
  
                                                                                           
   
char DecodeURLEncodedCharacter(const std::string& str);

   
         
                                
                                                                                      
  
                                                                                       
   
std::string DecodeURLEncodedString(const std::string& str);

   
         
                                                  
                                                          
   
std::string HTMLPlaceholder(std::string_view key) noexcept;

   
         
                                                                                        
  
           
                                                                                                   
   
std::string PutParamIntoHTML(std::string html, const Parameters& params);

   
                                                     
  
           
                                                                          
                          
                       
  
           
                                                  
                                                       
   
class ConnectionImpl {
public:
    using Ptr = std::shared_ptr<ConnectionImpl>;

                               
    static void SetRootDirectory(std::filesystem::path dir) noexcept;

                               
    static std::filesystem::path GetRootDirectory() noexcept;

    ConnectionImpl(const ConnectionImpl&) = delete;

    ConnectionImpl(ConnectionImpl&&) = delete;

    ConnectionImpl& operator=(const ConnectionImpl&) = delete;

    ConnectionImpl& operator=(ConnectionImpl&&) = delete;

                             
    void Close() noexcept;

                                        
    bool Valid() const noexcept;

                       
    FileDescriptor Socket() const noexcept;

                                
    std::size_t Receive();

                              
    std::size_t Send();

                                           
    bool KeepAlive() const noexcept;

       
                                       
      
               
                                                                  
                                                
                                                                                      
      
                                                                                      
       
    bool Process() noexcept;

protected:
    static constexpr std::string_view true_tag {"true"};

    static constexpr std::string_view false_tag {"false"};

    explicit ConnectionImpl(FileDescriptor socket) noexcept;

    virtual ~ConnectionImpl() noexcept;

    static std::filesystem::path root_dir_;

    FileDescriptor socket_ {invalid_file_descriptor};
    bool keep_alive_ {false};

    IOBuffer read_buf_;
    IOBuffer write_buf_;

                           
    MappedReadOnlyFile file_;
};

                        
template <ValidIPAddr IPAddr>
class Connection : public ConnectionImpl {
public:
    using Ptr = std::shared_ptr<Connection>;

    explicit Connection(const FileDescriptor socket, IPAddr addr) noexcept :
        ConnectionImpl {socket}, addr_ {std::move(addr)} {}

    std::string IPAddress() const noexcept {
        return addr_.IPAddress();
    }

    std::uint16_t Port() const noexcept {
        return addr_.Port();
    }

private:
    IPAddr addr_;
};

}                       