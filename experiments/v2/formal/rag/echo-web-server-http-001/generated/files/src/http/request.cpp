#include "request.h"
#include <stdexcept>
#include <sstream>
#include <cassert>
#include <regex>

namespace ws::http {

Request::Request() noexcept {}

Request::Request(Buffer& buf) {
    Parse(buf);
}

Request::~Request() noexcept {}

void Request::Parse(Buffer& buf) {
    if (buf.Empty())
        throw std::invalid_argument("Empty buffer");
    SetState(std::make_unique<NotStarted>(*this));
    while (!state_->Finished()) {
        state_->Execute(buf);
    }
}

std::optional<std::string_view> Request::Header(std::string_view key) const noexcept {
    auto it = headers_.find(key);
    if (it != headers_.end())
        return it->second;
    return std::nullopt;
}

std::optional<std::string_view> Request::Post(std::string_view key) const noexcept {
    auto it = post_.find(key);
    if (it != post_.end())
        return it->second;
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
    auto keep_alive_header = Header("Connection");
    if (keep_alive_header && *keep_alive_header == "keep-alive")
        return true;
    return false;
}

void Request::SetState(std::unique_ptr<State> state) noexcept {
    state_ = std::move(state);
}

void Request::Clear() noexcept {
    method_ = Method::Get;
    version_.clear();
    path_.clear();
    headers_.clear();
    post_.clear();
}

}  // namespace ws::http