   
                     
                                               
  
                                                
              
                                 
               
                   
  
                                                
   

#pragma once

#include "log.h"
#include "util.h"

#include <algorithm>
#include <cassert>
#include <chrono>
#include <compare>
#include <deque>
#include <functional>
#include <optional>
#include <stdexcept>
#include <unordered_map>


namespace ws {

   
         
                                        
  
           
                                                                  
                                                      
  
                                     
   
template <typename Key>
class HeapTimer {
public:
    using Clock = std::chrono::steady_clock;

    using TimeOutCallback = std::function<void(const Key&)>;

       
                                    
      
                    
                                                                                       
       
    explicit HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept;

    HeapTimer(HeapTimer&&) = delete;

    HeapTimer& operator=(HeapTimer&&) = delete;

    HeapTimer(const HeapTimer&) = delete;

    HeapTimer& operator=(const HeapTimer&) = delete;

       
                                              
      
                        
                                                                        
      
                                                                                                     
       
    void Adjust(const Key& key, Clock::duration expiration);

       
                                              
      
                        
                                               
      
                                                                                                     
       
    void Adjust(const Key& key, Clock::time_point expiration);

       
                                                
      
                        
                                                                    
                                                                                      
       
    void Push(const Key& key, Clock::duration expiration,
              TimeOutCallback callback) noexcept;

       
                                                
      
                        
                                            
                                                                                      
       
    void Push(const Key& key, Clock::time_point expiration,
              TimeOutCallback callback) noexcept;

       
                                                              
      
               
                                                               
                                                         
       
    void Tick() noexcept;

       
                                       
      
                                            
       
    bool Remove(const Key& key) noexcept;

       
                                                               
      
                                                                                                     
      
               
                                                               
                                                         
       
    void Invoke(const Key& key);

       
                                                  
      
                                                                                  
       
    Key Pop() noexcept;

                               
    void Clear() noexcept;

                                                                       
    bool Contain(const Key& key) const noexcept;

                                          
    bool Empty() const noexcept;

                                
    std::size_t Size() const noexcept;

       
             
                                                       
                                                                            
                                                     
      
               
                                                               
                                                         
       
    Clock::duration ToNextTick() noexcept;

private:
    struct Node {
                                      
        Key key;

                               
        Clock::time_point expiration;

                                                                            
        TimeOutCallback callback;

                                         
        bool Expired() const noexcept;

        void Swap(Node&) noexcept;

        friend std::weak_ordering operator<=>(const Node& lhs,
                                              const Node& rhs) noexcept {
            return lhs.expiration <=> rhs.expiration;
        }
    };

    void Swap(std::size_t idx1, std::size_t idx2) noexcept;

       
                            
      
                                                                                                     
       
    void Adjust(const Key& key, Clock::time_point expiration,
                std::optional<TimeOutCallback> callback);

                                         
    Key RemoveByIndex(std::size_t idx) noexcept;

       
             
                                                                                
      
               
                                                                                  
                                                                                     
       
    void ShiftUp(std::size_t idx) noexcept;

                                                                                       
    void ShiftDown(std::size_t idx) noexcept;

    bool ValidIndex(std::size_t idx) const noexcept;

                                                                                  
    std::optional<std::size_t> Parent(std::size_t idx) const noexcept;

       
             
                                                                          
                                               
       
    std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept;

    log::Logger::Ptr logger_;

                                                      
    std::unordered_map<Key, std::size_t> key_to_idx_;
    std::deque<Node> nodes_;
};

template <typename Key>
bool HeapTimer<Key>::Node::Expired() const noexcept {
    return Clock::now() >= expiration;
}

template <typename Key>
void HeapTimer<Key>::Node::Swap(Node& o) noexcept {
    using std::swap;
    swap(key, o.key);
    swap(expiration, o.expiration);
    swap(callback, o.callback);
}

template <typename Key>
HeapTimer<Key>::HeapTimer(log::Logger::Ptr logger) noexcept :
    logger_ {std::move(logger)} {
    if (!logger_) {
        logger_ = log::RootLogger();
    }
}

template <typename Key>
void HeapTimer<Key>::Clear() noexcept {
    nodes_.clear();
    key_to_idx_.clear();
}

template <typename Key>
bool HeapTimer<Key>::Remove(const Key& key) noexcept {
    if (Contain(key)) {
        RemoveByIndex(key_to_idx_[key]);
        return true;
    } else {
        return false;
    }
}

template <typename Key>
bool HeapTimer<Key>::ValidIndex(const std::size_t idx) const noexcept {
    return idx < Size();
}

template <typename Key>
bool HeapTimer<Key>::Contain(const Key& key) const noexcept {
    return key_to_idx_.contains(key);
}

template <typename Key>
void HeapTimer<Key>::Adjust(const Key& key, const Clock::duration expiration) {
    Adjust(key, Clock::now() + expiration);
}

template <typename Key>
void HeapTimer<Key>::Adjust(const Key& key,
                            const Clock::time_point expiration) {
    Adjust(key, expiration, std::nullopt);
}

template <typename Key>
void HeapTimer<Key>::Adjust(const Key& key, const Clock::time_point expiration,
                            const std::optional<TimeOutCallback> callback) {
    const auto idx {key_to_idx_.at(key)};
    if (callback.has_value()) {
        nodes_[idx].callback = *callback;
    }

    const auto shift_up {expiration < nodes_[idx].expiration};
    nodes_[idx].expiration = expiration;
    if (shift_up) {
        ShiftUp(idx);
    } else {
        ShiftDown(idx);
    }
}

template <typename Key>
void HeapTimer<Key>::Push(const Key& key, const Clock::duration expiration,
                          TimeOutCallback callback) noexcept {
    Push(key, Clock::now() + expiration, std::move(callback));
}

template <typename Key>
void HeapTimer<Key>::Push(const Key& key, const Clock::time_point expiration,
                          TimeOutCallback callback) noexcept {
    if (!Contain(key)) {
        const auto idx {Size()};
        key_to_idx_.emplace(key, idx);
        nodes_.push_back({key, expiration, std::move(callback)});
        ShiftUp(idx);
    } else {
        Adjust(key, expiration, std::move(callback));
    }
}

template <typename Key>
bool HeapTimer<Key>::Empty() const noexcept {
    assert(nodes_.empty() == key_to_idx_.empty());
    return nodes_.empty();
}

template <typename Key>
std::size_t HeapTimer<Key>::Size() const noexcept {
    assert(nodes_.size() == key_to_idx_.size());
    return nodes_.size();
}

template <typename Key>
void HeapTimer<Key>::ShiftUp(std::size_t idx) noexcept {
    assert(ValidIndex(idx));
    auto parent {Parent(idx)};
    while (parent.has_value()) {
        assert(*parent < idx);
        if (nodes_[*parent] >= nodes_[idx]) {
            Swap(*parent, idx);
            idx = *parent;
            parent = Parent(idx);
        } else {
            break;
        }
    }
}

template <typename Key>
void HeapTimer<Key>::ShiftDown(std::size_t idx) noexcept {
    assert(ValidIndex(idx));
    auto child {SmallChild(idx)};
    while (child.has_value()) {
        assert(*child > idx);
        if (nodes_[idx] > nodes_[*child]) {
            Swap(*child, idx);
            idx = *child;
            child = SmallChild(idx);
        } else {
            break;
        }
    }
}

template <typename Key>
std::optional<std::size_t> HeapTimer<Key>::Parent(
    const std::size_t idx) const noexcept {
    assert(ValidIndex(idx));
    return idx != 0 ? std::optional {(idx - 1) / 2} : std::nullopt;
}

template <typename Key>
std::optional<std::size_t> HeapTimer<Key>::SmallChild(
    const std::size_t idx) const noexcept {
    assert(ValidIndex(idx));

    const auto left {idx * 2 + 1};
    const auto right {left + 1};
    if (ValidIndex(left) && left > idx) {
        auto smaller {left};
        if (ValidIndex(right) && right > idx && nodes_[right] < nodes_[left]) {
            smaller = right;
        }
        return smaller;
    } else {
        return std::nullopt;
    }
}

template <typename Key>
void HeapTimer<Key>::Swap(const std::size_t idx1,
                          const std::size_t idx2) noexcept {
    assert(ValidIndex(idx1) && ValidIndex(idx2));
    if (idx1 != idx2) {
        nodes_[idx1].Swap(nodes_[idx2]);
        key_to_idx_[nodes_[idx1].key] = idx1;
        key_to_idx_[nodes_[idx2].key] = idx2;
    }
}

template <typename Key>
void HeapTimer<Key>::Tick() noexcept {
    while (!Empty()) {
        if (auto& node {nodes_.front()}; node.Expired()) {
            const auto callback {std::move(node.callback)};
            const auto key {node.key};
            Pop();

            try {
                assert(callback);
                callback(key);
            } catch (const std::exception& err) {
                logger_->Log(
                    log::Event::Create(log::Level::Error)
                    << fmt::format("Exception raised in timer's callback: {}",
                                   err.what()));
            }
        } else {
            break;
        }
    }
}

template <typename Key>
typename HeapTimer<Key>::Clock::duration HeapTimer<Key>::ToNextTick() noexcept {
    Tick();
    if (!Empty()) {
        const auto interval {nodes_.front().expiration - Clock::now()};
        if (interval > Clock::duration::zero()) {
            return interval;
        }
    }

    return Clock::duration::zero();
}

template <typename Key>
Key HeapTimer<Key>::Pop() noexcept {
    assert(!Empty());
    return RemoveByIndex(0);
}

template <typename Key>
void HeapTimer<Key>::Invoke(const Key& key) {
    const auto idx {key_to_idx_.at(key)};

    try {
        assert(nodes_[idx].callback);
        nodes_[idx].callback(key);
    } catch (const std::exception& err) {
        logger_->Log(log::Event::Create(log::Level::Error)
                     << fmt::format("Exception raised in timer's callback: {}",
                                    err.what()));
    }

    RemoveByIndex(idx);
    assert(!Contain(key));
}

   
        
                                                          
                                            
                                                                                          
   
template <typename Key>
Key HeapTimer<Key>::RemoveByIndex(const std::size_t idx) noexcept {
    assert(ValidIndex(idx));
    const auto key {nodes_[idx].key};
    if (Size() == 1) {
        Clear();
        return key;
    }

                                                  
    nodes_[idx].expiration = Clock::time_point {Clock::duration::zero()};
    ShiftUp(idx);

                                         
    assert(nodes_.front().key == key);

                                      
    nodes_.front().Swap(nodes_.back());
    std::swap(key_to_idx_[nodes_.front().key], key_to_idx_[nodes_.back().key]);

                             
    nodes_.pop_back();
    key_to_idx_.erase(key);

                                              
    ShiftDown(0);

    assert(key_to_idx_.size() == nodes_.size());
    return key;
}

}                 