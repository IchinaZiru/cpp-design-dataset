#include "request.h"
#include "util.h"

namespace ws::http {

Request::State::~State() noexcept {}

Request::NotStarted::NotStarted(Request& request) : request_(request) {}

void Request::NotStarted::Parse(std::string_view line) {
    std::istringstream iss(std::string(line));
    std::string method_str, path, version;
    if (!(iss >> method_str >> path >> version)) {
        throw std::invalid_argument("Invalid status line");
    }

    request_.method_ = StringToMethod(method_str);
    request_.path_ = path;
    request_.version_ = version;

    request_.SetState(std::make_unique<Header>(request_));
}

Request::Header::Header(Request& request) : request_(request) {}

void Request::Header::Parse(std::string_view line) {
    if (line.empty()) {
        request_.SetState(std::make_unique<Body>(request_));
        return;
    }

    std::size_t colon_pos = line.find(':');
    if (colon_pos == std::string_view::npos) {
        throw std::invalid_argument("Invalid header field");
    }

    std::string key(line.substr(0, colon_pos));
    std::string value(line.substr(colon_pos + 1));
    Trim(value);
    request_.headers_[std::move(key)] = std::move(value);
}

Request::Body::Body(Request& request) : request_(request) {}

void Request::Body::Parse(std::string_view line) {
    if (request_.method_ == http::Method::Post) {
        auto content_length_it = request_.headers_.find("Content-Length");
        if (content_length_it != request_.headers_.end()) {
            std::size_t content_length = std::stoul(content_length_it->second);
            if (request_.read_buf_.ReadableSize() < content_length) {
                return;
            }

            std::string body(request_.read_buf_.Read(content_length));
            request_.post_ = ParseURLEncodedString(body);
        }
    }

    request_.SetState(std::make_unique<Finished>(request_));
}

Request::Finished::Finished(Request& request) : request_(request) {}

void Request::Finished::Parse([[maybe_unused]] std::string_view line) {
    throw std::invalid_argument("Parsing is already finished");
}

Request::Request() noexcept : state_(std::make_unique<NotStarted>(*this)) {}

Request::Request(Buffer& buf) : Request() {
    Parse(buf);
}

Request::~Request() noexcept = default;

void Request::Parse(Buffer& buf) {
    Clear();
    std::string line;
    while (buf.ReadLine(line)) {
        state_->Parse(line);
        if (state_->IsFinished()) {
            break;
        }
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
    auto connection_it = headers_.find("Connection");
    if (connection_it != headers_.end()) {
        return connection_it->second == "keep-alive";
    }
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
