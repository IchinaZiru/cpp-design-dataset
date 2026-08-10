#include "request.h"
#include <cassert>
#include <sstream>
#include <optional>
#include <regex>
#include <stdexcept>

namespace ws::http {

Request::Request() noexcept {}

Request::Request(Buffer& buf) {
    Parse(buf);
}

Request::~Request() noexcept {
    Clear();
}

void Request::Parse(Buffer& buf) {
    if (state_) {
        state_->Clear();
    }
    SetState(std::make_unique<NotStarted>(*this));
    while (!buf.Empty()) {
        const auto content {buf.ReadableString()};
        if (content.empty()) {
            break;
        }
        const auto line_end {content.find(new_line)};
        const auto line {content.substr(0, line_end)};
        state_->Parse(line);
        buf.Retrieve(line.length());
        if (line_end == std::string_view::npos) {
            break;
        }
        buf.Retrieve(new_line.length());
    }
}

std::optional<std::string_view> Request::Header(std::string_view key) const noexcept {
    auto val {headers_.find(key.data())};
    if (val == headers_.cend()) {
        return std::nullopt;
    }
    return val->second;
}

std::optional<std::string_view> Request::Post(std::string_view key) const noexcept {
    auto val {post_.find(key.data())};
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
    auto conn {headers_.find("Connection")};
    if (conn == headers_.cend()) {
        return false;
    }
    return StringToUpper(conn->second) == "KEEP-ALIVE";
}

void Request::SetState(std::unique_ptr<State> state) noexcept {
    assert(state);
    state_ = std::move(state);
}

void Request::Clear() noexcept {
    if (state_) {
        state_->Clear();
    }
    method_ = http::Method::Get;
    version_.clear();
    path_.clear();
    headers_.clear();
    post_.clear();
}

}  // namespace ws::http