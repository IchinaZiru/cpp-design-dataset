#include "http.h"
#include <stdexcept>
#include <sstream>
#include <cassert>
#include <regex>

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
    else if (str == "POST") return Method::Post;
    else if (str == "PUT") return Method::Put;
    else if (str == "PATCH") return Method::Patch;
    else if (str == "DELETE") return Method::Delete;
    throw std::invalid_argument("Invalid HTTP method");
}

std::ostream& operator<<(std::ostream& os, Method method) noexcept {
    return os << to_string(method);
}

std::string_view ContentTypeByFileName(std::string_view name) noexcept {
    if (name.ends_with(".html")) return "text/html";
    else if (name.ends_with(".css")) return "text/css";
    else if (name.ends_with(".js")) return "application/javascript";
    else if (name.ends_with(".png")) return "image/png";
    else if (name.ends_with(".jpg") || name.ends_with(".jpeg")) return "image/jpeg";
    else return "application/octet-stream";
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

void ConnectionImpl::SetRootDirectory(std::filesystem::path dir) noexcept {
    root_dir_ = std::move(dir);
}

std::filesystem::path ConnectionImpl::GetRootDirectory() noexcept {
    return root_dir_;
}

ConnectionImpl::ConnectionImpl(FileDescriptor socket) noexcept : socket_(socket) {}

ConnectionImpl::~ConnectionImpl() noexcept {}

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
        throw std::runtime_error("Invalid connection");
    std::size_t size = 0;
    try {
        while (read_buf_.ReadableSize() > 0) {
            size += read_buf_.ReadFrom(socket_);
        }
    } catch (const std::system_error& err) {
        if (err.code() != std::errc::resource_unavailable_try_again)
            throw;
    }
    return size;
}

std::size_t ConnectionImpl::Send() {
    if (!Valid())
        throw std::runtime_error("Invalid connection");
    std::size_t header_size = 0, file_size = 0;
    while (!write_buf_.Empty()) {
        header_size += write_buf_.WriteTo(socket_);
    }
    if (file_.Size() > 0) {
        while (file_size < file_.Size()) {
            ssize_t size = write(socket_, file_.Data() + file_size, file_.Size() - file_size);
            if (size >= 0)
                file_size += size;
            else
                ThrowLastSystemError();
        }
    }
    return header_size + file_size;
}

bool ConnectionImpl::KeepAlive() const noexcept {
    return keep_alive_;
}

bool ConnectionImpl::Process() noexcept {
    if (read_buf_.ReadableSize() == 0)
        return false;
    try {
        Request request(read_buf_);
        keep_alive_ = request.KeepAlive();
        Response response(root_dir_);
        response.SetKeepAlive(keep_alive_);
        std::string path = request.Path();
        if (path.empty() || path == "/")
            path = "index.html";
        StatusCode status_code {StatusCode::OK};
        if (path == "index.html") {
            auto params {ExtractUserMessage(request).value_or(Parameters {})};
            params.insert({hide_msg_tag.data(), params.empty() ? true_tag.data() : false_tag.data()});
            response.Build(write_buf_, path, params, status_code);
        } else {
            auto file {response.Build(write_buf_, std::move(path), status_code)};
            if (file.has_value())
                file_ = std::move(*file);
        }
    } catch (const std::exception& err) {
        Response response(root_dir_);
        response.SetKeepAlive(keep_alive_);
        response.Build(write_buf_, StatusCode::BadRequest, err.what());
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