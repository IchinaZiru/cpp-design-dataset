   
                      
                          
  
                                                
                                              
              
                                 
               
                   
  
                                                 
   

#pragma once

#include "log.h"

#include <condition_variable>
#include <functional>
#include <list>
#include <mutex>
#include <optional>
#include <thread>


namespace ws {

                    
class ThreadPool {
public:
    using Task = std::function<void()>;

       
                                   
      
                          
                                     
                                                                                                                         
                    
                                                                                      
       
    explicit ThreadPool(std::optional<std::size_t> thread_count = std::nullopt,
                        log::Logger::Ptr logger = log::RootLogger()) noexcept;

    ~ThreadPool() noexcept;

    ThreadPool(const ThreadPool&) = delete;

    ThreadPool(ThreadPool&&) = delete;

    ThreadPool& operator=(const ThreadPool&) = delete;

    ThreadPool& operator=(ThreadPool&&) = delete;

                            
    void Start() noexcept;

                                         
    void Push(Task task) noexcept;

       
                                    
      
               
                                                
       
    void Close() noexcept;

private:
       
                                                
      
               
                                                               
                                                         
       
    void ExecProc() noexcept;

    log::Logger::Ptr logger_;

    mutable std::mutex mtx_;
    std::atomic_bool closed_ {true};
    std::size_t thread_count_;
    std::condition_variable cond_;

    std::list<Task> tasks_;
    std::list<std::thread> threads_;
};

}                 