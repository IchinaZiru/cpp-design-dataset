#include "request.h"
#include <cassert>
#include <stdexcept>
#include <sstream>

namespace ws::http {

Request::State::~State() noexcept {}

Request::Request() noexcept : state_ {std::make_unique<NotStarted>()} {}

Request::Request(Buffer& buf) : Request {} {
    Parse(buf);
}

Request::~Request() noexcept {}

void Request::Parse(Buffer& buf) {
    while (state_) {
        if (!state_->Parse(*this, buf))
            break;
    }
}

std::optional<std::string_view> Request::Header(std::string_view key) const noexcept {
    auto it = headers_.find(key);
    return it != headers_.end() ? std::make_optional(it->second) : std::nullopt;
}

std::optional<std::string_view> Request::Post(std::string_view key) const noexcept {
    auto it = post_.find(key);
    return it != post_.end() ? std::make_optional(it->second) : std::nullopt;
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
    return connection && *connection == "keep-alive";
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