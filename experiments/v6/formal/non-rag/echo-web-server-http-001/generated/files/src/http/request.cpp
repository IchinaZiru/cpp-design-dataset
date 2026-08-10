#include "request.h"
#include <cassert>
#include <regex>
#include <stdexcept>

namespace ws::http {

Request::Request() noexcept : state_ {std::make_unique<NotStarted>(*this)} {}

Request::Request(Buffer& buf) : Request {} {
    Parse(buf);
}

Request::~Request() noexcept = default;

void Request::Parse(Buffer& buf) {
    Clear();
    SetState(std::make_unique<NotStarted>(*this));
    while (!buf.Empty()) {
        assert(state_);
        state_->Parse(buf);
    }
}

std::optional<std::string_view> Request::Header(std::string_view key) const noexcept {
    const auto val {headers_.find(key.data())};
    if (val == headers_.cend()) {
        return std::nullopt;
    }
    return val->second;
}

std::optional<std::string_view> Request::Post(std::string_view key) const noexcept {
    const auto val {post_.find(key.data())};
    if (val == post_.cend()) {
        return std::nullopt;
    }
    return val->second;
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
    const auto conn {headers_.find("Connection")};
    if (conn == headers_.cend()) {
        return false;
    }
    return StringToUpper(conn->second) == "KEEP-ALIVE";
}

void Request::SetState(std::unique_ptr<State> state) noexcept {
    state_ = std::move(state);
}

void Request::Clear() noexcept {
    version_.clear();
    path_.clear();
    headers_.clear();
    post_.clear();
}

}  // namespace ws::http