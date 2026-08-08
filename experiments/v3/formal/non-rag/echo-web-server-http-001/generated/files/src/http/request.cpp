#include "request.h"
#include <cassert>
#include <sstream>
#include <stdexcept>
#include <string_view>

namespace ws::http {

Request::State::~State() noexcept {}

class NotStarted : public Request::State {
public:
    void Parse(Request& request, Buffer& buf) override {
        std::string line;
        if (!buf.ReadLine(line))
            throw std::invalid_argument {"Invalid HTTP request"};

        std::istringstream iss {line};
        std::string method_str, path, version;
        if (!(iss >> method_str >> path >> version) || !version.starts_with("HTTP/"))
            throw std::invalid_argument {"Invalid HTTP request"};

        request.method_ = StringToMethod(method_str);
        request.path_ = path;
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
            if (colon_pos == std::string_view::npos)
                throw std::invalid_argument {"Invalid HTTP header"};

            std::string key = Trim(line.substr(0, colon_pos));
            std::string value = Trim(line.substr(colon_pos + 1));
            request.headers_[std::move(key)] = std::move(value);
        }
    }
};

class Body : public Request::State {
public:
    void Parse(Request& request, Buffer& buf) override {
        if (request.method_ == http::Method::Post) {
            auto content_length_it = request.headers_.find("Content-Length");
            if (content_length_it != request.headers_.end()) {
                std::size_t content_length;
                try {
                    content_length = std::stoul(content_length_it->second);
                } catch (...) {
                    throw std::invalid_argument {"Invalid Content-Length header"};
                }

                if (buf.ReadableSize() < content_length)
                    return;

                std::string body(buf.Peek(), content_length);
                buf.Retrieve(content_length);

                std::istringstream iss {body};
                std::string key, value;
                while (std::getline(iss, key, '&')) {
                    auto eq_pos = key.find('=');
                    if (eq_pos != std::string_view::npos) {
                        value = key.substr(eq_pos + 1);
                        key.resize(eq_pos);
                        request.post_[DecodeURLEncodedString(key)] = DecodeURLEncodedString(value);
                    }
                }
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
    while (state_)
        state_->Parse(*this, buf);
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
    auto connection_it = headers_.find("Connection");
    if (connection_it != headers_.end())
        return connection_it->second == true_tag;
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