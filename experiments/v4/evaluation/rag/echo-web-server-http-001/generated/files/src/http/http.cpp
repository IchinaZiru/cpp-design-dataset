#include "http.h"
#include "request.h"
#include "response.h"
#include <sstream>
#include <stdexcept>

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
        default: return "Unknown Method";
    }
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
    auto pos = name.rfind(".");
    if (pos == std::string_view::npos) return "application/octet-stream";
    auto ext = name.substr(pos + 1);
    if (ext == "html") return "text/html";
    if (ext == "css") return "text/css";
    if (ext == "js") return "application/javascript";
    if (ext == "png") return "image/png";
    if (ext == "jpg" || ext == "jpeg") return "image/jpeg";
    return "application/octet-stream";
}

char DecodeURLEncodedCharacter(const std::string& str) {
    if (str.size() != 3 || str[0] != '%') throw std::invalid_argument("Invalid URL-encoded character");
    int value = std::stoi(str.substr(1), nullptr, 16);
    return static_cast<char>(value);
}

std::string DecodeURLEncodedString(const std::string& str) {
    std::string result;
    for (std::size_t i = 0; i < str.size(); ++i) {
        if (str[i] == '%' && i + 2 < str.size()) {
            result += DecodeURLEncodedCharacter(str.substr(i, 3));
            i += 2;
        } else {
            result += str[i];
        }
    }
    return result;
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
    if (socket_ != invalid_file_descriptor) {
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
    if (!Valid()) throw std::runtime_error("Invalid connection");
    return read_buf_.Read(socket_);
}

std::size_t ConnectionImpl::Send() {
    if (!Valid()) throw std::runtime_error("Invalid connection");
    return write_buf_.Write(socket_);
}

bool ConnectionImpl::KeepAlive() const noexcept {
    return keep_alive_;
}

bool ConnectionImpl::Process() noexcept {
    if (read_buf_.Empty()) return false;
    try {
        Request request(read_buf_);
        Response response(root_dir_);
        StatusCode code;
        if (request.Method() == Method::Get) {
            response.Build(write_buf_, request.Path(), code);
        } else if (request.Method() == Method::Post) {
            response.Build(write_buf_, "form.html", request.Post(), code);
        }
        keep_alive_ = request.KeepAlive();
    } catch (...) {
        StatusCode code = StatusCode::BadRequest;
        Response response(root_dir_);
        response.Build(write_buf_, code, "Invalid request");
        return false;
    }
    return true;
}

std::string Connection<IPAddr>::IPAddress() const noexcept {
    return addr_.ToString();
}

std::uint16_t Connection<IPAddr>::Port() const noexcept {
    return addr_.Port();
}

}  // namespace ws::http