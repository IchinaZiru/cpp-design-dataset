#include "request.h"
#include "util.h"

#include <cassert>
#include <regex>
#include <stdexcept>

namespace ws::http {

class Request::State {
public:
    virtual ~State() noexcept {}
    virtual void Parse(Request& request, Buffer& buf) = 0;
};

class NotStarted : public State {
public:
    void Parse(Request& request, Buffer& buf) override {
        std::string line;
        if (!buf.ReadLine(line))
            throw std::invalid_argument{"Invalid HTTP request"};
        std::regex re(R"((GET|POST|PUT|PATCH|DELETE) (\S+) HTTP/1\.1)");
        std::smatch match;
        if (!std::regex_match(line, match, re))
            throw std::invalid_argument{"Invalid HTTP request"};
        request.method_ = StringToMethod(match[1]);
        request.path_ = match[2];
        request.version_ = "1.1";
        request.SetState(std::make_unique<Header>());
    }
};

class Header : public State {
public:
    void Parse(Request& request, Buffer& buf) override {
        std::string line;
        while (buf.ReadLine(line)) {
            if (line.empty()) {
                request.SetState(std::make_unique<Body>());
                return;
            }
            auto colon_pos = line.find(':');
            if (colon_pos == std::string::npos)
                throw std::invalid_argument{"Invalid HTTP header"};
            std::string key = line.substr(0, colon_pos);
            std::string value = line.substr(colon_pos + 1);
            util::Trim(key);
            util::Trim(value);
            request.headers_[key] = value;
        }
    }
};

class Body : public State {
public:
    void Parse(Request& request, Buffer& buf) override {
        if (request.method_ == http::Method::Post) {
            std::string content_length_str = request.Header("Content-Length").value_or("");
            if (content_length_str.empty())
                throw std::invalid_argument{"Invalid HTTP request"};
            std::size_t content_length = std::stoul(content_length_str);
            std::string body;
            buf.Read(body, content_length);
            std::regex re(R"(([^&=]+)=([^&]*))");
            std::smatch match;
            while (std::regex_search(body, match, re)) {
                request.post_[match[1]] = match[2];
                body = match.suffix();
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
    auto connection = Header("Connection");
    if (connection && *connection == "keep-alive")
        return true;
    return false;
}

void Request::SetState(std::unique_ptr<State> state) noexcept {
    state_ = std::move(state);
}

void Request::Clear() noexcept {
    headers_.clear();
    post_.clear();
}

}  // namespace ws::http
