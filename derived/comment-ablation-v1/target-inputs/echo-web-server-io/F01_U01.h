   
             
                                                                  
  
                                                
                                              
              
                                 
               
                   
  
                             
   

#pragma once

#include "util.h"

#include <iostream>


namespace ws {

class Buffer;

namespace io {

                                                      
class IReader {
public:
    virtual ~IReader() noexcept = default;

                                
    virtual std::size_t ReadFrom(Buffer& buf) = 0;
};

                                                      
class IWriter {
public:
    virtual ~IWriter() noexcept = default;

                               
    virtual std::size_t WriteTo(Buffer& buf) = 0;
};

                                              
class IReadWriter : public virtual IReader, public virtual IWriter {};

   
                   
  
           
                                                                
                                       
   
class Null : public virtual IReadWriter {
public:
    std::size_t WriteTo(Buffer& buf) noexcept override;

    std::size_t ReadFrom(Buffer& buf) noexcept override;
};

                           
class StringStream : public virtual IReadWriter {
public:
       
                                                                 
      
                  
                                   
                                             
                   
                                   
                                                
      
               
                                                      
                                                                          
       
    explicit StringStream(std::istream& read, std::ostream& write) noexcept;

    StringStream(const StringStream&) = delete;

    StringStream(StringStream&&) = delete;

    StringStream& operator=(const StringStream&) = delete;

    StringStream& operator=(StringStream&&) = delete;

    std::size_t WriteTo(Buffer& buf) noexcept override;

    std::size_t ReadFrom(Buffer& buf) noexcept override;

private:
    std::istream& read_;
    std::ostream& write_;
};

                             
class FileDescriptor : public virtual IReadWriter {
public:
       
                                                         
      
                  
                                     
                                             
                   
                                     
                                                
      
            
                                                                      
                                                                                     
       
    explicit FileDescriptor(ws::FileDescriptor read,
                            ws::FileDescriptor write) noexcept;

    FileDescriptor(const FileDescriptor&) = delete;

    FileDescriptor(FileDescriptor&&) = delete;

    FileDescriptor& operator=(const FileDescriptor&) = delete;

    FileDescriptor& operator=(FileDescriptor&&) = delete;

    std::size_t WriteTo(Buffer& buf) override;

    std::size_t ReadFrom(Buffer& buf) override;

private:
    ws::FileDescriptor read_;
    ws::FileDescriptor write_;
};

}                 

}                 