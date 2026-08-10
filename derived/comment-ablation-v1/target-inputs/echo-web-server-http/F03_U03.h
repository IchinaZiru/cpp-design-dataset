   
                  
                                  
  
                                                
                                              
              
                                 
               
                   
   

#pragma once

#include "containers/buffer.h"
#include "http.h"

#include <memory>
#include <optional>


namespace ws::http {

                            
class Request {
public:
    class State;

    Request() noexcept;

       
                                                        
      
                                                                    
       
    explicit Request(Buffer& buf);

    ~Request() noexcept;

       
                                    
      
                                                                    
       
    void Parse(Buffer& buf);

       
                                            
      
                                            
       
    std::optional<std::string_view> Header(std::string_view key) const noexcept;

       
                                                      
      
                                            
       
    std::optional<std::string_view> Post(std::string_view key) const noexcept;

                                                 
    std::size_t PostSize() const noexcept;

                            
    http::Method Method() const noexcept;

                     
    std::string_view Path() const noexcept;

                             
    std::string_view Version() const noexcept;

                                        
    bool KeepAlive() const noexcept;

private:
    friend class NotStarted;
    friend class Header;
    friend class Body;

                                
    void SetState(std::unique_ptr<State> state) noexcept;

                        
    void Clear() noexcept;

    std::unique_ptr<State> state_;

    http::Method method_ {Method::Get};
    std::string version_;
    std::string path_;

    Parameters headers_;
    Parameters post_;
};

}                       