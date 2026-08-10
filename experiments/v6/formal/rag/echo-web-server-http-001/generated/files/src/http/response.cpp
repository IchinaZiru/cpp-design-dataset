#include "response.h"
#include <cassert>
#include <sstream>
#include <optional>
#include <regex>
#include <stdexcept>

namespace ws::http {

Response::Response(std::filesystem::path root_dir) noexcept : root_dir_(std::move(root_dir)) {}

Response::~Response() noexcept {
    file_.Unmap();
}

Response& Response::SetKeepAlive(bool set) noexcept {
    keep_alive_ = set;
    return *this;
}

std::optional<MappedReadOnlyFile> Response::Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept {
    Clear();
    file_path_ = root_dir_ / file.relative_path();
    CheckFile();
    if (status_code_ != StatusCode::OK) {
        code = status_code_;
        return std::nullopt;
    }
    MapFile();
    Build(buf);
    code = status_code_;
    return file_;
}

void Response::Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept {
    Clear();
    file_path_ = root_dir_ / html.relative_path();
    CheckFile();
    if (status_code_ != StatusCode::OK) {
        code = status_code_;
        return;
    }
    Build(buf, &params);
    code = status_code_;
}

void Response::Build(Buffer& buf, StatusCode code, std::string msg) noexcept {
    Clear();
    status_code_ = code;
    AddStatusLine(buf);
    AddHeaders(buf);
    if (!msg.empty()) {
        AddPredefinedErrorContent(buf, msg);
    }
}

void Response::Clear() noexcept {
    file_path_.clear();
    file_.Unmap();
    keep_alive_ = false;
    status_code_ = StatusCode::OK;
}

void Response::Build(Buffer& buf, const Parameters* params) noexcept {
    AddStatusLine(buf);
    AddHeaders(buf);
    if (file_path_.empty()) {
        return;
    }
    if (params) {
        AddParamContent(buf, *params);
    } else {
        AddMappedContent(buf);
    }
}

void Response::CheckFile() {
    if (!std::filesystem::exists(file_path_)) {
        status_code_ = StatusCode::NotFound;
        return;
    }
    if (std::filesystem::is_directory(file_path_)) {
        file_path_ /= index_page;
    }
}

void Response::MapFile() {
    if (!file_.Map(file_path_)) {
        status_code_ = StatusCode::Forbidden;
        return;
    }
}

void Response::AddStatusLine(Buffer& buf) const noexcept {
    buf.Append(fmt::format("HTTP/{} {} {}", version, StatusCodeToInteger(status_code_), StatusCodeToMessage(status_code_)), NewLine::CRLF);
}

void Response::AddHeaders(Buffer& buf) const noexcept {
    buf.Append("Connection: ");
    if (keep_alive_) {
        buf.Append("keep-alive", NewLine::CRLF);
        buf.Append("keep-alive: max=6, timeout=120", NewLine::CRLF);
    } else {
        buf.Append("close", NewLine::CRLF);
    }
}

void Response::AddMappedContent(Buffer& buf) noexcept {
    assert(file_.Data());
    buf.Append(fmt::format("Content-type: {}", ContentTypeByFileName(file_path_.c_str())), NewLine::CRLF);
    buf.Append(fmt::format("Content-length: {}", file_.Size()), NewLine::CRLF);
    buf.Append(new_line);
}

void Response::AddParamContent(Buffer& buf, const Parameters& params) const noexcept {
    std::string content {reinterpret_cast<const char*>(file_.Data()), file_.Size()};
    for (const auto& [key, val] : params) {
        content = ReplaceAllSubstring(content, HTMLPlaceholder(key), val);
    }
    buf.Append(fmt::format("Content-type: text/html"), NewLine::CRLF);
    buf.Append(fmt::format("Content-length: {}", content.size()), NewLine::CRLF);
    buf.Append(new_line);
    buf.Append(content);
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    std::ifstream file {root_dir_ / http_status_page};
    if (!file.is_open()) {
        return;
    }
    std::ostringstream ss;
    ss << file.rdbuf();
    std::string content {ss.str()};
    const Parameters params {
        {status_code_tag.data(), std::to_string(StatusCodeToInteger(status_code_))},
        {status_tag.data(), StatusCodeToMessage(status_code_).data()},
        {msg_tag.data(), msg}
    };
    for (const auto& [key, val] : params) {
        content = ReplaceAllSubstring(content, HTMLPlaceholder(key), val);
    }
    buf.Append(fmt::format("Content-type: text/html"), NewLine::CRLF);
    buf.Append(fmt::format("Content-length: {}", content.size()), NewLine::CRLF);
    buf.Append(new_line);
    buf.Append(content);
}

}  // namespace ws::http