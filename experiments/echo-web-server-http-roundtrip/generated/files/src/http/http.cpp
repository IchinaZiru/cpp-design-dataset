#include "http.h"
#include "io.h"
#include "util.h"
#include <cassert>
#include <sstream>
#include <stdexcept>

namespace ws::http {

std::string_view StatusCodeToMessage(StatusCode code) noexcept {
    switch (code) {
        case StatusCode::OK:
            return "OK";
        case StatusCode::BadRequest:
            return "Bad Request";
        case StatusCode::Forbidden:
            return "Forbidden";
        case StatusCode::NotFound:
            return "Not Found";
        default:
            assert(false);
            return "Unknown Status Code";
    }
}

std::uint32_t StatusCodeToInteger(StatusCode code) noexcept {
    return static_cast<std::uint32_t>(code);
}

std::ostream& operator<<(std::ostream& os, StatusCode code) noexcept {
    return os << StatusCodeToMessage(code);
}

std::string_view MethodToString(Method method) noexcept {
    switch (method) {
        case Method::Get:
            return "GET";
        case Method::Post:
            return "POST";
        case Method::Put:
            return "PUT";
        case Method::Patch:
            return "PATCH";
        case Method::Delete:
            return "DELETE";
        default:
            assert(false);
            return "Unknown Method";
    }
}

std::string to_string(Method method) noexcept {
    return std::string {MethodToString(method)};
}

Method StringToMethod(std::string str) {
    if (str == "GET")
        return Method::Get;
    else if (str == "POST")
        return Method::Post;
    else if (str == "PUT")
        return Method::Put;
    else if (str == "PATCH")
        return Method::Patch;
    else if (str == "DELETE")
        return Method::Delete;
    throw std::invalid_argument {"Invalid HTTP method"};
}

std::ostream& operator<<(std::ostream& os, Method method) noexcept {
    return os << to_string(method);
}

std::string_view ContentTypeByFileName(std::string_view name) noexcept {
    if (name.ends_with(".html") || name.ends_with(".htm"))
        return "text/html";
    else if (name.ends_with(".css"))
        return "text/css";
    else if (name.ends_with(".js"))
        return "application/javascript";
    else if (name.ends_with(".png"))
        return "image/png";
    else if (name.ends_with(".jpg") || name.ends_with(".jpeg"))
        return "image/jpeg";
    else
        return "application/octet-stream";
}

char DecodeURLEncodedCharacter(const std::string& str) {
    if (str.size() != 3 || str[0] != '%')
        throw std::invalid_argument {"Invalid URL-encoded character"};
    try {
        return static_cast<char>(std::stoi(str.substr(1), nullptr, 16));
    } catch (...) {
        throw std::invalid_argument {"Invalid URL-encoded character"};
    }
}

std::string DecodeURLEncodedString(const std::string& str) {
    std::ostringstream oss;
    for (std::size_t i = 0; i < str.size(); ++i) {
        if (str[i] == '%' && i + 2 < str.size()) {
            oss << DecodeURLEncodedCharacter(str.substr(i, 3));
            i += 2;
        } else {
            oss << str[i];
        }
    }
    return oss.str();
}

std::string HTMLPlaceholder(std::string_view key) noexcept {
    return "{{" + std::string {key} + "}}";
}

std::string PutParamIntoHTML(std::string html, const Parameters& params) {
    for (const auto& [key, value] : params) {
        const auto placeholder = HTMLPlaceholder(key);
        size_t pos = 0;
        while ((pos = html.find(placeholder, pos)) != std::string::npos) {
            html.replace(pos, placeholder.size(), value);
            pos += value.size();
        }
    }
    return html;
}

std::filesystem::path ConnectionImpl::root_dir_ {};

void ConnectionImpl::SetRootDirectory(std::filesystem::path dir) noexcept {
    root_dir_ = std::move(dir);
}

std::filesystem::path ConnectionImpl::GetRootDirectory() noexcept {
    return root_dir_;
}

ConnectionImpl::ConnectionImpl(FileDescriptor socket) noexcept : socket_ {socket} {}

ConnectionImpl::~ConnectionImpl() noexcept {
    Close();
}

void ConnectionImpl::Close() noexcept {
    if (Valid()) {
        io::Close(socket_);
        socket_ = invalid_file_descriptor;
    }
}

bool ConnectionImpl::Valid() const noexcept {
    return socket_ != invalid_file_descriptor;
}

FileDescriptor ConnectionImpl::Socket() const noexcept {
    return socket_;
}

std::size_t ConnectionImpl::Receive() {
    if (!Valid())
        throw std::runtime_error {"Invalid connection"};
    return io::Read(socket_, read_buf_.WriteBegin(), read_buf_.WritableBytes());
}

std::size_t ConnectionImpl::Send() {
    if (!Valid())
        throw std::runtime_error {"Invalid connection"};
    const auto bytes = write_buf_.ReadableBytes();
    const auto sent_bytes = io::Write(socket_, write_buf_.ReadBegin(), bytes);
    write_buf_.Retrieve(sent_bytes);
    return sent_bytes;
}

bool ConnectionImpl::KeepAlive() const noexcept {
    return keep_alive_;
}

void ConnectionImpl::SetState(std::unique_ptr<State> state) noexcept {
    state_ = std::move(state);
}

void ConnectionImpl::Clear() noexcept {
    method_ = Method::Get;
    version_.clear();
    path_.clear();
    headers_.clear();
    post_.clear();
}

bool ConnectionImpl::Process() noexcept {
    if (read_buf_.ReadableBytes() == 0)
        return false;
    try {
        Request request {read_buf_};
        Response response {root_dir_};
        StatusCode code;
        if (request.Method() == Method::Get) {
            response.Build(write_buf_, request.Path(), code);
        } else if (request.Method() == Method::Post) {
            response.Build(write_buf_, "form.html", request.Post(), code);
        }
        keep_alive_ = request.KeepAlive();
    } catch (...) {
        Response response {root_dir_};
        StatusCode code = StatusCode::BadRequest;
        response.Build(write_buf_, code);
    }
    read_buf_.RetrieveAll();
    return true;
}

std::string Connection<IPAddr>::IPAddress() const noexcept {
    return addr_.ToString();
}

std::uint16_t Connection<IPAddr>::Port() const noexcept {
    return addr_.Port();
}

}  // namespace ws::http