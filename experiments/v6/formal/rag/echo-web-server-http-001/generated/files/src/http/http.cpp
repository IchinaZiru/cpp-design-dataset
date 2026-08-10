#include "http.h"
#include "request.h"
#include "response.h"
#include "io.h"
#include "util.h"
#include <cassert>
#include <sstream>
#include <optional>
#include <regex>
#include <stdexcept>

namespace ws::http {

std::filesystem::path ConnectionImpl::root_dir_;

void ConnectionImpl::SetRootDirectory(std::filesystem::path dir) noexcept {
    root_dir_ = std::move(dir);
}

std::filesystem::path ConnectionImpl::GetRootDirectory() noexcept {
    return root_dir_;
}

ConnectionImpl::ConnectionImpl(FileDescriptor socket) noexcept : socket_(socket) {}

ConnectionImpl::~ConnectionImpl() noexcept {
    Close();
}

void ConnectionImpl::Close() noexcept {
    if (IsValidFileDescriptor(socket_)) {
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
    std::size_t size {read_buf_.ReadFrom(io)};
    if (size == 0) {
        ThrowLastSystemError();
    }
    return size;
}

std::size_t ConnectionImpl::Send() {
    io::FileDescriptor io {socket_, socket_};
    std::size_t header_size {write_buf_.WriteTo(io)};
    if (!file_.Data()) {
        return header_size;
    }
    std::size_t file_size {0};
    while (file_size < file_.Size()) {
        const auto size {write(socket_, file_.Data() + file_size, file_.Size() - file_size)};
        if (size == 0) {
            ThrowLastSystemError();
        }
        file_size += size;
    }
    return header_size + file_size;
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
        std::cerr << "Invalid HTTP request: " << err.what() << std::endl;
        Response response {root_dir_};
        response.Build(write_buf_, StatusCode::BadRequest, err.what());
        return true;
    }
    keep_alive_ = request.KeepAlive();
    Response response {root_dir_};
    response.SetKeepAlive(keep_alive_);
    std::optional<std::string> error_msg;
    std::string path {request.Path()};
    StatusCode status_code {StatusCode::OK};
    if (path.empty()) {
        path = index_page;
    } else {
        auto params {ExtractUserMessage(request).value_or(Parameters {})};
        params.insert({hide_msg_tag.data(), params.empty() ? true_tag.data() : false_tag.data()});
        response.Build(write_buf_, std::move(path), params, status_code);
    }
    auto file {response.Build(write_buf_, std::move(path), status_code)};
    if (file.has_value()) {
        file_ = std::move(*file);
    } else {
        Response error_response {root_dir_};
        error_response.Build(write_buf_, StatusCode::NotFound, "File not found.");
    }
    return true;
}

std::string Connection<ValidIPAddr>::IPAddress() const noexcept {
    return addr_.IPAddress();
}

std::uint16_t Connection<ValidIPAddr>::Port() const noexcept {
    return addr_.Port();
}

}  // namespace ws::http