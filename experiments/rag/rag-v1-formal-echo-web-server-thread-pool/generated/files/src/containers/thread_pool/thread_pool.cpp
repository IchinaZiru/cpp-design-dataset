#include "../../include/containers/thread_pool.h"
#include <cassert>
#include <stdexcept>

namespace ws {

ThreadPool::ThreadPool(std::optional<std::size_t> thread_count,
                         log::Logger::Ptr logger) noexcept
    : logger_(std::move(logger)),
      thread_count_(thread_count.value_or(std::thread::hardware_concurrency())) {}

ThreadPool::~ThreadPool() noexcept {
    Close();
}

void ThreadPool::Start() noexcept {
    closed_ = false;
    for (std::size_t i = 0; i < thread_count_; ++i) {
        threads_.emplace_back(&ThreadPool::ExecProc, this);
    }
}

void ThreadPool::Push(Task task) noexcept {
    assert(!closed_ && "Cannot push tasks into a closed thread pool.");
    std::lock_guard<std::mutex> lock(mtx_);
    tasks_.push_back(std::move(task));
    cond_.notify_one();
}

void ThreadPool::Close() noexcept {
    {
        std::lock_guard<std::mutex> lock(mtx_);
        closed_ = true;
    }
    cond_.notify_all();
    for (auto& thread : threads_) {
        if (thread.joinable()) {
            thread.join();
        }
    }
}

void ThreadPool::ExecProc() noexcept {
    while (true) {
        Task task;
        {
            std::unique_lock<std::mutex> lock(mtx_);
            cond_.wait(lock, [this] { return closed_ || !tasks_.empty(); });
            if (closed_ && tasks_.empty()) {
                break;
            }
            task = std::move(tasks_.front());
            tasks_.pop_front();
        }
        try {
            task();
        } catch (const std::exception& e) {
            logger_->Log(log::LogLevel::Error, "Exception in thread pool: {}", e.what());
        } catch (...) {
            logger_->Log(log::LogLevel::Error, "Unknown exception in thread pool.");
        }
    }
}

}  // namespace ws
