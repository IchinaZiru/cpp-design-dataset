   
                   
                            
  
                                                
                                              
              
                                 
               
                   
   

#pragma once

#include "containers/buffer.h"
#include "http.h"
#include "util.h"

#include <filesystem>
#include <optional>


namespace ws::http {

                              
class Response {
public:
       
                                              
      
                      
                        
                                                                      
                                                        
       
    explicit Response(std::filesystem::path root_dir) noexcept;

    ~Response() noexcept;

    Response(const Response&) = delete;

    Response(Response&&) = delete;

    Response& operator=(const Response&) = delete;

    Response& operator=(Response&&) = delete;

                                                 
    Response& SetKeepAlive(bool set) noexcept;

       
                                                         
      
                                                                                      
                                                                                                    
                                                                           
              
                                                                            
                                                  
                                                                                           
       
    std::optional<MappedReadOnlyFile> Build(Buffer& buf,
                                            std::filesystem::path file,
                                            StatusCode& code) noexcept;

       
                                                         
      
                                                                                      
                  
                                
                                                                           
                    
                       
                                                                                      
                                                                           
      
               
                                                                                                                
                                              
       
    void Build(Buffer& buf, std::filesystem::path html,
               const Parameters& params, StatusCode& code) noexcept;

       
                                                
      
                                                                                      
                                       
                                      
       
    void Build(Buffer& buf, StatusCode code, std::string msg = "") noexcept;

private:
                       
    void Clear() noexcept;

                                                         
    void Build(Buffer& buf, const Parameters* params = nullptr) noexcept;

                                                         
    void CheckFile();

                                                                  
    void MapFile();

                                
    void AddStatusLine(Buffer& buf) const noexcept;

                                                                              
    void AddHeaders(Buffer& buf) const noexcept;

       
                                                                              
      
            
                                                              
                                                                               
       
    void AddMappedContent(Buffer& buf) noexcept;

                                                                    
    void AddParamContent(Buffer& buf, const Parameters& params) const noexcept;

                                                                   
    void AddPredefinedErrorContent(Buffer& buf,
                                   std::string_view msg = "") noexcept;

    std::filesystem::path root_dir_;
    std::filesystem::path file_path_;

    MappedReadOnlyFile file_;

    bool keep_alive_ {false};
    StatusCode status_code_ {StatusCode::OK};
};

}                       