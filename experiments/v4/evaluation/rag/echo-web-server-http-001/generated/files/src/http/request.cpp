#include "request.h"
#include <sstream>
#include <stdexcept>

namespace ws::http {

Request::State::~State() noexcept {}

Request::Request() noexcept : state_(std::make_unique<NotStarted>()) {}

Request::Request(Buffer& buf) : Request() {
    Parse(buf);
}

Request::~Request() noexcept {
    Clear();
}

void Request::Parse(Buffer& buf) {
    while (!buf.Empty()) {
        state_->Parse(*this, buf);
    }
    if (method_ == http::Method::Get && post_.empty()) {
        throw std::invalid_argument("Invalid GET request");
    }
}

std::optional<std::string_view> Request::Header(std::string_view key) const noexcept {
    auto it = headers_.find(key);
    if (it != headers_.end()) return it->second;
    return std::nullopt;
}

std::optional<std::string_view> Request::Post(std::string_view key) const noexcept {
    auto it = post_.find(key);
    if (it != post_.end()) return it->second;
    return std::nullopt;
}

std::size_t Request::PostSize() const noexcept {
    return post_.size();
}

http::Method Request::Method() const noexcept {
    return method_;
}

std::string_view Request::Path() const noexcept {
    return path_;
}

std::string_view Request::Version() const noexcept {
    return version_;
}

bool Request::KeepAlive() const noexcept {
    auto connection = Header("Connection");
    if (connection && *connection == "keep-alive") return true;
    return false;
}

void Request::SetState(std::unique_ptr<State> state) noexcept {
    state_ = std::move(state);
}

void Request::Clear() noexcept {
    method_ = http::Method::Get;
    version_.clear();
    path_.clear();
    headers_.clear();
    post_.clear();
}

}  // namespace ws::http