#include "http.h"
#include "io.h"
#include <cassert>
#include <sstream>
#include <stdexcept>

namespace ws::http {

std::string_view StatusCodeToMessage(StatusCode code) noexcept {
    static const std::unordered_map<StatusCode, std::string_view> msgs { {StatusCode::OK, "OK"}, {StatusCode::BadRequest, "Bad Request"}, {StatusCode::Forbidden, "Forbidden"}, {StatusCode::NotFound, "Not Found"}};
    return msgs.at(code);
}

std::uint32_t StatusCodeToInteger(StatusCode code) noexcept {
    return static_cast<std::uint32_t>(code);
}

std::ostream& operator<<(std::ostream& os, StatusCode code) noexcept {
    return os << StatusCodeToMessage(code);
}

std::string_view MethodToString(Method method) noexcept {
    static const std::unordered_map<Method, std::string_view> methods { {Method::Get, "GET"}, {Method::Patch, "PATCH"}, {Method::Post, "POST"}, {Method::Delete, "DELETE"}, {Method::Put, "PUT"}};
    return methods.at(method);
}

std::string to_string(Method method) noexcept {
    return std::string {MethodToString(method)};
}

Method StringToMethod(std::string str) {
    static const std::unordered_map<std::string_view, Method> methods { {"GET", Method::Get}, {"PATCH", Method::Patch}, {"POST", Method::Post}, {"DELETE", Method::Delete}, {"PUT", Method::Put}};
    const auto method {methods.find(StringToUpper(str))};
    if (method == methods.cend()) {
        throw std::invalid_argument(fmt::format("Invalid HTTP method: '{}'", str));
    }
    return method->second;
}

std::ostream& operator<<(std::ostream& os, Method method) noexcept {
    return os << to_string(method);
}

std::string_view ContentTypeByFileName(std::string_view name) noexcept {
    static const std::unordered_map<std::string_view, std::string_view> types { {".html", "text/html"}, {".xml", "text/xml"}, {".xhtml", "application/xhtml+xml"}, {".txt", "text/plain"}, {".rtf", "application/rtf"}, {".pdf", "application/pdf"}, {".word", "application/nsword"}, {".png", "image/png"}, {".gif", "image/gif"}, {".jpg", "image/jpeg"}, {".jpeg", "image/jpeg"}, {".au", "audio/basic"}, {".mpeg", "video/mpeg"}, {".mpg", "video/mpeg"}, {".avi", "video/x-msvideo"}, {".gz", "application/x-gzip"}, {".tar", "application/x-tar"}, {".css", "text/css"}, {".js", "text/javascript"}, };
    const auto extension { StringToLower(std::filesystem::path {name}.extension())};
    if (types.contains(extension.c_str())) {
        return types.at(extension.c_str());
    }
    return "application/octet-stream";
}

char DecodeURLEncodedCharacter(const std::string& str) {
    static constexpr std::size_t encoded_length {3};
    if (str.length() != encoded_length || str.front() != '%') {
        throw std::invalid_argument(fmt::format("Invalid HTTP URL-encoding character: '{}'", str));
    }
    const auto ascii {std::stoi(str.substr(1), nullptr, 16)};
    if (ascii < 0 || ascii > 255) {
        throw std::invalid_argument(fmt::format("Invalid HTTP URL-encoding character: '{}'", str));
    }
    return static_cast<char>(ascii);
}

std::string DecodeURLEncodedString(const std::string& str) {
    std::ostringstream ss;
    for (std::size_t i {0}; i < str.size(); ) {
        if (str[i] == '%') {
            const auto encoded {str.substr(i, encoded_length)};
            if (encoded.length() != encoded_length) {
                throw std::invalid_argument(fmt::format("Invalid HTTP URL-encoding strings: '{}'", str));
            }
            ss << DecodeURLEncodedCharacter(encoded);
            i += encoded_length;
        } else {
            ss << str[i];
            ++i;
        }
    }
    return ss.str();
}

std::string HTMLPlaceholder(std::string_view key) noexcept {
    return fmt::format("<${}$>", key);
}

std::string PutParamIntoHTML(std::string html, const Parameters& params) {
    for (const auto& [key, val] : params) {
        html = ReplaceAllSubstring(html, HTMLPlaceholder(key), val);
    }
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
    return IsValidFileDescriptor(socket_);
}

FileDescriptor ConnectionImpl::Socket() const noexcept {
    return socket_;
}

std::size_t ConnectionImpl::Receive() {
    io::FileDescriptor io {socket_, socket_};
    std::size_t size {0};
    try {
        size = read_buf_.ReadFrom(io);
    } catch (const std::system_error& err) {
        Close();
        throw;
    }
    return size;
}

std::size_t ConnectionImpl::Send() {
    io::FileDescriptor io {socket_, socket_};
    if (write_buf_.Empty()) {
        return 0;
    }
    std::size_t size {0};
    try {
        size = write_buf_.WriteTo(io);
    } catch (const std::system_error& err) {
        Close();
        throw;
    }
    if (write_buf_.Empty()) {
        keep_alive_ = false;
    }
    return size;
}

bool ConnectionImpl::KeepAlive() const noexcept {
    return keep_alive_;
}

bool ConnectionImpl::Process() noexcept {
    if (read_buf_.ReadableSize() == 0) {
        return false;
    }
    Request request;
    try {
        request.Parse(read_buf_);
    } catch (const std::invalid_argument& err) {
        error_msg = err.what();
        status_code = StatusCode::BadRequest;
        goto build_response;
    }

    keep_alive_ = request.KeepAlive();
    path = request.Path();
    if (path.empty()) {
        params = ExtractUserMessage(request).value_or(Parameters {});
        params.insert({hide_msg_tag.data(), params.empty() ? true_tag.data() : false_tag.data()});
        response.Build(write_buf_, index_page, params, status_code);
    } else {
        file = response.Build(write_buf_, std::move(path), status_code);
        if (file.has_value()) {
            write(socket_, file_.Data(), file_.Size());
        }
    }

build_response:
    if (error_msg.has_value()) {
        response.Build(write_buf_, StatusCode::BadRequest, *error_msg);
    }
    return true;
}

std::string Connection<IPAddr>::IPAddress() const noexcept {
    return addr_.IPAddress();
}

std::uint16_t Connection<IPAddr>::Port() const noexcept {
    return addr_.Port();
}

}  // namespace ws::http