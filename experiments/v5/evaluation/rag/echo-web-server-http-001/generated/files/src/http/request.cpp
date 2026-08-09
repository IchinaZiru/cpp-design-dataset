#include "request.h"
#include <stdexcept>
#include <sstream>
#include <cassert>

namespace ws::http {

Request::State::~State() noexcept {}

class NotStarted : public Request::State {
public:
    void Parse(Request& request, Buffer& buf) override {
        std::string line;
        if (!buf.ReadLine(line)) throw std::invalid_argument("Invalid HTTP request");

        std::istringstream iss(line);
        std::string method_str, path, version;
        iss >> method_str >> path >> version;

        request.method_ = StringToMethod(method_str);
        request.path_ = DecodeURLEncodedString(path);
        request.version_ = version;

        request.SetState(std::make_unique<Header>());
    }
};

class Header : public Request::State {
public:
    void Parse(Request& request, Buffer& buf) override {
        std::string line;
        while (buf.ReadLine(line)) {
            if (line.empty()) {
                request.SetState(std::make_unique<Body>());
                return;
            }

            auto colon_pos = line.find(':');
            if (colon_pos == std::string::npos) throw std::invalid_argument("Invalid HTTP header");

            std::string key = line.substr(0, colon_pos);
            std::string value = line.substr(colon_pos + 2); // Skip the colon and space
            request.headers_[key] = value;
        }
    }
};

class Body : public Request::State {
public:
    void Parse(Request& request, Buffer& buf) override {
        if (request.method_ == http::Method::Post) {
            std::string body(buf.ReadableData(), buf.ReadableSize());
            buf.ConsumeReadableBytes(buf.ReadableSize());

            std::istringstream iss(body);
            std::string key, value;
            while (iss >> key >> value) {
                request.post_[key] = value;
            }
        }
    }
};

Request::Request() noexcept {}

Request::Request(Buffer& buf) {
    SetState(std::make_unique<NotStarted>());
    Parse(buf);
}

Request::~Request() noexcept {}

void Request::Parse(Buffer& buf) {
    while (state_) {
        state_->Parse(*this, buf);
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
    headers_.clear();
    post_.clear();
}

}