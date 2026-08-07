#include "thread_pool.h"
#include "util.h"
#include <cassert>

namespace ws {

ThreadPool::ThreadPool(std::optional<std::size_t> thread_count, log::Logger::Ptr logger) noexcept
    : logger_(std::move(logger)),
      closed_(true),
      thread_count_(thread_count.value_or(std::thread::hardware_concurrency())) {}

ThreadPool::~ThreadPool() noexcept {
    Close();
    for (auto& thread : threads_) {
        if (thread.joinable()) {
            thread.join();
        }
    }
}

void ThreadPool::Start() noexcept {
    assert(closed_);
    closed_ = false;
    for (std::size_t i = 0; i < thread_count_; ++i) {
        threads_.emplace_back(&ThreadPool::ExecProc, this);
    }
}

void ThreadPool::Push(Task task) noexcept {
    assert(!closed_);
    std::lock_guard<std::mutex> locker(mtx_);
    tasks_.push_back(std::move(task));
    cond_.notify_one();
}

void ThreadPool::Close() noexcept {
    {
        std::lock_guard<std::mutex> locker(mtx_);
        closed_ = true;
    }
    cond_.notify_all();
}

void ThreadPool::ExecProc() noexcept {
    auto not_empty_or_closed = [this]() noexcept {
        return !tasks_.empty() || closed_;
    };
    while (true) {
        std::unique_lock<std::mutex> locker(mtx_);
        cond_.wait(locker, not_empty_or_closed);
        if (closed_) {
            return;
        }
        Task task = std::move(tasks_.front());
        tasks_.pop_front();
        try {
            task();
        } catch (const std::exception& err) {
            logger_->Log(log::Event::Create(fmt::format("Exception in thread pool: {}", err.what())));
        }
    }
}

}  // namespace ws