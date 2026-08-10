   
              
                             
  
           
                                               
                                     
                                   
                                 
                             
                                   
                                  
                                 
                                   
                                  
  
                                                
              
                                 
               
                   
  
                              
   

#pragma once

#include "config.h"
#include "containers/block_deque.h"
#include "util.h"

#include <chrono>
#include <experimental/source_location>
#include <fstream>
#include <iostream>
#include <list>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <thread>
#include <unordered_map>


namespace ws::log {

class Logger;

enum class Level { Debug = 0, Info = 1, Warn = 2, Error = 3, Fatal = 4 };

                                  
std::string_view LevelToString(Level level) noexcept;

std::string to_string(Level level) noexcept;

std::ostream& operator<<(std::ostream& os, Level level) noexcept;

   
                                        
  
                                                                          
   
Level StringToLevel(std::string str);

enum class AppenderType { StdOut = 0, File = 1 };

                                           
std::string_view AppenderTypeToString(AppenderType type) noexcept;

std::string to_string(AppenderType type) noexcept;

std::ostream& operator<<(std::ostream& os, AppenderType type) noexcept;

   
                                                 
  
                                                                                   
   
AppenderType StringToAppenderType(std::string str);

                  
class Event {
public:
    using Ptr = std::shared_ptr<Event>;

    using Clock = std::chrono::system_clock;

       
                              
      
                                    
                                          
                                                                      
                                  
      
                                                                                        
       
    static Ptr Create(log::Level level,
                      std::experimental::source_location location =
                          std::experimental::source_location::current(),
                      std::uint32_t thread_id = CurrentThreadId(),
                      Clock::time_point time = Clock::now()) noexcept;

    Event(const Event&) = delete;

    Event(Event&&) = delete;

    Event& operator=(const Event&) = delete;

    Event& operator=(Event&&) = delete;

    log::Level Level() const noexcept;

    std::string_view FileName() const noexcept;

    std::size_t LineNum() const noexcept;

    std::uint32_t ThreadId() const noexcept;

    Clock::time_point Time() const noexcept;

                                            
    std::string Message() const noexcept;

                                                                  
    std::ostringstream& MessageStream() noexcept;

protected:
    explicit Event(log::Level level,
                   std::experimental::source_location location,
                   std::uint32_t thread_id, Clock::time_point time) noexcept;

private:
    log::Level level_;
    std::string_view file_name_;
    std::size_t line_num_;
    std::uint32_t thread_id_;
    Clock::time_point time_;

    std::ostringstream msg_;
};

Event::Ptr operator<<(Event::Ptr event, std::string_view msg) noexcept;

                        
class Formatter {
public:
    using Ptr = std::shared_ptr<Formatter>;

    static Formatter::Ptr Default() noexcept;

       
             
                                                     
                                                                                           
      
                           
       
    class Field {
    public:
        using Ptr = std::shared_ptr<Field>;

           
                                           
          
                                                                     
           
        explicit Field(std::string_view format = "") noexcept;

        virtual ~Field() noexcept = default;

                                         
        virtual void Format(std::ostream& out, const Logger& logger,
                            const Event& event) noexcept = 0;

           
                 
                                            
                                                              
           
        virtual std::string_view Tag() const noexcept = 0;
    };

       
                                 
      
                                                                                       
      
                                                               
       
    explicit Formatter(std::string_view pattern);

                                      
    std::string Format(const Logger& logger, const Event& event) const noexcept;

    std::string_view Pattern() const noexcept;

private:
    std::string pattern_;
    std::list<Field::Ptr> fields_;
};

                                                        
class Appender {
public:
    using Ptr = std::shared_ptr<Appender>;

       
                                                       
      
                                                               
       
    explicit Appender(std::string_view pattern);

    explicit Appender(Formatter::Ptr formatter = Formatter::Default()) noexcept;

    Appender(const Appender&) = delete;

    Appender(Appender&&) = delete;

    Appender& operator=(const Appender&) = delete;

    Appender& operator=(Appender&&) = delete;

    virtual ~Appender() noexcept = default;

                                             
    virtual void Log(const Logger& logger, const Event& event) noexcept = 0;

                                                                             
    virtual std::string ToYamlString() const noexcept = 0;

    Formatter::Ptr GetFormatter() const noexcept;

    void SetFormatter(Formatter::Ptr formatter) noexcept;

       
                                  
      
                                                                      
       
    void SetFormatter(std::string_view pattern);

protected:
    mutable std::mutex mtx_;
    Formatter::Ptr formatter_;
};

                                                                  
class StdOutAppender : public Appender {
public:
    using Ptr = std::shared_ptr<StdOutAppender>;

    using Appender::Appender;

    void Log(const Logger& logger, const Event& event) noexcept override;

    std::string ToYamlString() const noexcept override;
};

                                              
class FileAppender : public Appender {
public:
    using Ptr = std::shared_ptr<FileAppender>;

       
                                     
      
                                    
                                    
      
                                                              
       
    explicit FileAppender(std::string_view file_name,
                          Formatter::Ptr formatter = Formatter::Default());

    void Log(const Logger& logger, const Event& event) noexcept override;

    std::string ToYamlString() const noexcept override;

private:
    std::string file_name_;
    std::ofstream file_;
};

   
         
                                              
                                               
   
class Logger {
public:
    using Ptr = std::shared_ptr<Logger>;

       
                              
      
                          
                   
                              
                                                                  
                      
                                   
                                                                                        
                                                                             
       
    explicit Logger(
        std::string_view name, log::Level level = Level::Info,
        std::optional<std::size_t> capacity = std::nullopt) noexcept;

    ~Logger() noexcept;

    Logger(const Logger&) = delete;

    Logger(Logger&&) = delete;

    Logger& operator=(const Logger&) = delete;

    Logger& operator=(Logger&&) = delete;

    void Log(Event::Ptr event) noexcept;

    void AddAppender(Appender::Ptr appender) noexcept;

    void RemoveAppender(Appender::Ptr appender) noexcept;

    void ClearAppenders() noexcept;

    log::Level GetLevel() const noexcept;

    void SetLevel(log::Level level) noexcept;

    Formatter::Ptr GetDefaultFormatter() const noexcept;

       
             
                               
      
               
                                                              
                                          
       
    void SetDefaultFormatter(Formatter::Ptr formatter) noexcept;

       
                                      
      
                                                                      
       
    void SetDefaultFormatter(std::string_view pattern);

    std::string_view Name() const noexcept;

    std::size_t Capacity() const noexcept;

                                                                           
    std::string ToYamlString() const noexcept;

private:
                                                                             
    void AsyncLogProc() noexcept;

    void SyncLog(const Event& event) noexcept;

    mutable std::mutex mtx_;
    bool async_;
    std::unique_ptr<std::thread> writer_thread_;

    std::string name_;
    std::size_t capacity_;
    log::Level level_;
    std::list<Appender::Ptr> appenders_;
    std::unique_ptr<BlockDeque<Event::Ptr>> event_deque_;
    Formatter::Ptr formatter_ {Formatter::Default()};
};

void Log(Logger::Ptr logger, Event::Ptr event) noexcept;

Logger::Ptr operator<<(Logger::Ptr logger, Event::Ptr event) noexcept;

   
         
                              
                                                              
  
           
                             
  
               
                                                              
           
   
class EventWriter {
public:
    explicit EventWriter(Logger& logger, Event::Ptr event) noexcept;

    EventWriter(const EventWriter&) = delete;

    EventWriter(EventWriter&&) = delete;

    EventWriter& operator=(const EventWriter&) = delete;

    EventWriter& operator=(EventWriter&&) = delete;

    ~EventWriter() noexcept;

    std::ostringstream& MessageStream() noexcept;

private:
    Logger& logger_;
    Event::Ptr event_;
};

                                                            
class Manager {
public:
       
                                                                  
      
                                                                               
       
    static void InitConfig() noexcept;

    using Ptr = std::shared_ptr<Manager>;

    explicit Manager(std::string_view name) noexcept;

    Manager(const Manager&) = delete;

    Manager(Manager&&) = delete;

    Manager& operator=(const Manager&) = delete;

    Manager& operator=(Manager&&) = delete;

    std::string_view Name() const noexcept;

                                                                   
    Logger::Ptr FindLogger(
        std::string_view name, log::Level level = Level::Info,
        std::optional<std::size_t> capacity = std::nullopt) noexcept;

    void RemoveLogger(std::string_view name) noexcept;

                                                                            
    std::string ToYamlString() const noexcept;

private:
    mutable std::mutex mtx_;
    std::string name_;
    std::unordered_map<std::string, Logger::Ptr> loggers_;
};

Manager::Ptr RootManager() noexcept;

Logger::Ptr RootLogger() noexcept;

Logger::Ptr FindLogger(std::string_view name) noexcept;

}                      