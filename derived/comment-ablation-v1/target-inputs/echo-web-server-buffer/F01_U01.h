   
                 
                                                                           
  
                                                
                                              
              
                                 
               
                   
  
                                            
   

#pragma once

#include <atomic>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace ws {

namespace io {

class IReadWriter;

}

                       
enum class NewLine {
             
    LF,

               
    CRLF
};

   
                                                                          
  
           
        
                                         
                                         
                                         
                                         
                                                          
                                                          
                                                          
           
  
                                   
   
class Buffer {
public:
                                             
    explicit Buffer(std::size_t size = 1000) noexcept;

                                   
    explicit Buffer(std::span<const std::byte> bytes) noexcept;

                                   
    explicit Buffer(std::initializer_list<std::byte> bytes) noexcept;

                                      
    explicit Buffer(std::string_view str) noexcept;

    Buffer(const Buffer&) noexcept;

    Buffer(Buffer&&) noexcept;

    Buffer& operator=(const Buffer&) noexcept;

    Buffer& operator=(Buffer&&) noexcept;

                                                        
    std::size_t WritableSize() const noexcept;

                              
    std::size_t ReadableSize() const noexcept;

                                                              
    std::optional<std::byte> Peek() const noexcept;

                                                             
    std::span<const std::byte> ReadableBytes() const noexcept;

       
                                                                      
      
                                                                             
       
    std::string ReadableString() const noexcept;

       
                                             
      
               
                                                                                  
                                                                       
       
    std::span<std::byte> WritableBytes() const noexcept;

                                                                       
    void Append(std::span<const std::byte> bytes) noexcept;

                                                                       
    void Append(std::initializer_list<std::byte> bytes) noexcept;

                                                                                                             
    void Append(std::string_view str,
                std::optional<NewLine> new_line = std::nullopt) noexcept;

                                                                      
    void Append(const void* data, std::size_t size) noexcept;

                                                                                
    void Append(const Buffer& buf) noexcept;

                                                    
    void EnsureWriteableSize(std::size_t size) noexcept;

                                                                    
    void HasWritten(std::size_t size) noexcept;

                                                                    
    void Retrieve(std::size_t size) noexcept;

                                                                                  
    std::size_t RetrieveUntil(const void* addr) noexcept;

                                                            
    std::size_t RetrieveAll() noexcept;

       
                                                                                                     
      
                                                                             
       
    std::string RetrieveAllToString() noexcept;

                         
    void Clear() noexcept;

                                    
    bool Empty() const noexcept;

protected:
                                                     
    std::size_t PrependableSize() const noexcept;

                                                   
    void MakeSpace(std::size_t size) noexcept;

                               
    std::vector<std::byte>::iterator ReadIter() const noexcept;

                               
    std::vector<std::byte>::iterator WriteIter() const noexcept;

    std::vector<std::byte> buf_;
    std::atomic<std::size_t> read_pos_ {0};
    std::atomic<std::size_t> write_pos_ {0};
};

                                                          
class IOBuffer : public Buffer {
public:
    using Buffer::Buffer;

                                     
    std::size_t ReadFrom(io::IReadWriter& io);

                                    
    std::size_t WriteTo(io::IReadWriter& io);
};

                               
Buffer& operator<<(Buffer& buf, std::string_view str) noexcept;

                                     
Buffer& operator<<(Buffer& to, const Buffer& from) noexcept;

                            
Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept;

                            
Buffer& operator<<(Buffer& buf,
                   std::initializer_list<std::byte> bytes) noexcept;

}                 