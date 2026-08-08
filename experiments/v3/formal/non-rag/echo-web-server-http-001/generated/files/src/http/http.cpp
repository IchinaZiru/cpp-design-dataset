#include "http.h"
#include "io.h"
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
    for (const auto& [key, value] : params)
        ReplaceAll(html, HTMLPlaceholder(key), value);
    return html;
}

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
        close(socket_);
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
        throw std::system_error {errno, std::generic_category(), "Invalid socket"};
    return read_buf_.Read(socket_);
}

std::size_t ConnectionImpl::Send() {
    if (!Valid())
        throw std::system_error {errno, std::generic_category(), "Invalid socket"};
    return write_buf_.Write(socket_);
}

bool ConnectionImpl::KeepAlive() const noexcept {
    return keep_alive_;
}

bool ConnectionImpl::Process() noexcept {
    if (read_buf_.Empty())
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
        read_buf_.Clear();
        write_buf_.Clear();
        return false;
    }
    return true;
}

std::string Connection<IPv4>::IPAddress() const noexcept {
    return addr_.ToString();
}

std::uint16_t Connection<IPv4>::Port() const noexcept {
    return addr_.Port();
}

std::string Connection<IPv6>::IPAddress() const noexcept {
    return addr_.ToString();
}

std::uint16_t Connection<IPv6>::Port() const noexcept {
    return addr_.Port();
}

}  // namespace ws::http