#include "http.h"
#include <stdexcept>
#include <sstream>
#include <cassert>

namespace ws::http {

std::string_view StatusCodeToMessage(StatusCode code) noexcept {
    switch (code) {
        case StatusCode::OK: return "OK";
        case StatusCode::BadRequest: return "Bad Request";
        case StatusCode::Forbidden: return "Forbidden";
        case StatusCode::NotFound: return "Not Found";
        default: return "Unknown Status Code";
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
        case Method::Get: return "GET";
        case Method::Post: return "POST";
        case Method::Put: return "PUT";
        case Method::Patch: return "PATCH";
        case Method::Delete: return "DELETE";
    }
    return "UNKNOWN";
}

std::string to_string(Method method) noexcept {
    return std::string(MethodToString(method));
}

Method StringToMethod(std::string str) {
    if (str == "GET") return Method::Get;
    if (str == "POST") return Method::Post;
    if (str == "PUT") return Method::Put;
    if (str == "PATCH") return Method::Patch;
    if (str == "DELETE") return Method::Delete;
    throw std::invalid_argument("Invalid HTTP method");
}

std::ostream& operator<<(std::ostream& os, Method method) noexcept {
    return os << to_string(method);
}

std::string_view ContentTypeByFileName(std::string_view name) noexcept {
    if (name.ends_with(".html")) return "text/html";
    if (name.ends_with(".css")) return "text/css";
    if (name.ends_with(".js")) return "application/javascript";
    if (name.ends_with(".png")) return "image/png";
    if (name.ends_with(".jpg") || name.ends_with(".jpeg")) return "image/jpeg";
    return "application/octet-stream";
}

char DecodeURLEncodedCharacter(const std::string& str) {
    if (str.size() != 3 || str[0] != '%')
        throw std::invalid_argument("Invalid URL-encoded character");
    int value = std::stoi(str.substr(1), nullptr, 16);
    return static_cast<char>(value);
}

std::string DecodeURLEncodedString(const std::string& str) {
    std::string decoded;
    for (size_t i = 0; i < str.size(); ++i) {
        if (str[i] == '%' && i + 2 < str.size()) {
            decoded += DecodeURLEncodedCharacter(str.substr(i, 3));
            i += 2;
        } else {
            decoded += str[i];
        }
    }
    return decoded;
}

std::string HTMLPlaceholder(std::string_view key) noexcept {
    return "{{" + std::string(key) + "}}";
}

std::string PutParamIntoHTML(std::string html, const Parameters& params) {
    for (const auto& [key, value] : params) {
        std::regex placeholder(HTMLPlaceholder(key));
        html = std::regex_replace(html, placeholder, value);
    }
    return html;
}

std::filesystem::path ConnectionImpl::root_dir_;

ConnectionImpl::ConnectionImpl(FileDescriptor socket) noexcept : socket_(socket) {}

ConnectionImpl::~ConnectionImpl() noexcept {
    Close();
}

void ConnectionImpl::SetRootDirectory(std::filesystem::path dir) noexcept {
    root_dir_ = std::move(dir);
}

std::filesystem::path ConnectionImpl::GetRootDirectory() noexcept {
    return root_dir_;
}

void ConnectionImpl::Close() noexcept {
    if (socket_.Valid()) {
        socket_.Close();
    }
}

bool ConnectionImpl::Valid() const noexcept {
    return socket_.Valid();
}

FileDescriptor ConnectionImpl::Socket() const noexcept {
    return socket_;
}

std::size_t ConnectionImpl::Receive() {
    if (!socket_.Valid()) throw std::runtime_error("Invalid socket");
    return read_buf_.ReadFrom(socket_);
}

std::size_t ConnectionImpl::Send() {
    if (!socket_.Valid()) throw std::runtime_error("Invalid socket");
    auto bytes_sent = write_buf_.WriteTo(socket_);
    if (file_.IsValid()) {
        bytes_sent += file_.WriteTo(socket_, write_buf_.WritableSize());
    }
    return bytes_sent;
}

bool ConnectionImpl::KeepAlive() const noexcept {
    return keep_alive_;
}

bool ConnectionImpl::Process() noexcept {
    if (read_buf_.ReadableSize() == 0) return false;
    try {
        Request request(read_buf_);
        Response response(root_dir_);
        StatusCode status_code;
        if (request.Method() == Method::Get) {
            auto file = root_dir_ / request.Path();
            response.Build(write_buf_, file, status_code);
        } else {
            Parameters params;
            for (const auto& [key, value] : request.Post()) {
                params[key] = std::string(value);
            }
            response.Build(write_buf_, "form.html", params, status_code);
        }
        keep_alive_ = request.KeepAlive();
    } catch (...) {
        StatusCode status_code = StatusCode::BadRequest;
        Response(root_dir_).Build(write_buf_, status_code);
    }
    return true;
}

std::string Connection<ValidIPAddr>::IPAddress() const noexcept {
    return addr_.ToString();
}

std::uint16_t Connection<ValidIPAddr>::Port() const noexcept {
    return addr_.Port();
}

}