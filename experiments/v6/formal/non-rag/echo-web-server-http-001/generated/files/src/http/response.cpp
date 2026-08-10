#include "response.h"
#include <cassert>
#include <sstream>
#include <stdexcept>

namespace ws::http {

Response::Response(std::filesystem::path root_dir) noexcept : root_dir_ {std::move(root_dir)} {}

Response::~Response() noexcept = default;

Response& Response::SetKeepAlive(bool set) noexcept {
    keep_alive_ = set;
    return *this;
}

std::optional<MappedReadOnlyFile> Response::Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept {
    Clear();
    status_code_ = StatusCode::OK;
    file_path_ = std::move(file);
    CheckFile();
    MapFile();
    if (!file_.Valid()) {
        status_code_ = StatusCode::NotFound;
        AddPredefinedErrorContent(buf);
        return std::nullopt;
    }
    AddStatusLine(buf);
    AddHeaders(buf);
    AddMappedContent(buf);
    code = status_code_;
    return file_;
}

void Response::Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept {
    Clear();
    status_code_ = StatusCode::OK;
    if (root_dir_.empty()) {
        status_code_ = StatusCode::BadRequest;
        AddPredefinedErrorContent(buf);
        return;
    }
    file_path_ = root_dir_ / html;
    CheckFile();
    MapFile();
    if (!file_.Valid()) {
        status_code_ = StatusCode::NotFound;
        AddPredefinedErrorContent(buf);
        return;
    }
    std::string content {reinterpret_cast<const char*>(file_.Data()), file_.Size()};
    const auto lines {SplitStringToLines(content)};
    std::size_t length {new_line.length() * (lines.size() - 1)};
    for (auto i {0}; i < lines.size(); ++i) {
        length += lines[i].size();
    }
    AddStatusLine(buf);
    AddHeaders(buf);
    buf.Append(fmt::format("Content-length: {}", length), NewLine::CRLF);
    for (auto i {0}; i < lines.size(); ++i) {
        if (i != 0) {
            buf.Append(new_line);
        }
        buf.Append(lines[i]);
    }
    AddParamContent(buf, params);
    code = status_code_;
}

void Response::Build(Buffer& buf, StatusCode code, std::string msg) noexcept {
    Clear();
    status_code_ = code;
    AddStatusLine(buf);
    AddHeaders(buf);
    if (!msg.empty()) {
        buf.Append(fmt::format("Content-type: text/html", NewLine::CRLF));
        const auto body {fmt::format("<p>{} : {}</p>", StatusCodeToInteger(status_code_), StatusCodeToMessage(status_code_))};
        buf.Append(fmt::format("Content-length: {}", body.size()), NewLine::CRLF);
        buf.Append(body);
    }
}

void Response::Clear() noexcept {
    file_path_.clear();
    if (file_.Valid()) {
        file_.Unmap();
    }
}

void Response::Build(Buffer& buf, const Parameters* params) noexcept {
    AddStatusLine(buf);
    AddHeaders(buf);
    if (params != nullptr) {
        AddParamContent(buf, *params);
    } else {
        AddMappedContent(buf);
    }
}

void Response::CheckFile() {
    if (!root_dir_.empty()) {
        file_path_ = root_dir_ / file_path_.relative_path();
    }
}

void Response::MapFile() {
    if (file_path_.empty()) {
        return;
    }
    try {
        file_.Map(file_path_);
    } catch (...) {
        status_code_ = StatusCode::BadRequest;
        throw;
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
    buf.Append(fmt::format("Content-type: text/html", NewLine::CRLF));
    buf.Append(fmt::format("Content-length: {}", content.size()), NewLine::CRLF);
    buf.Append(content);
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    if (root_dir_.empty()) {
        return;
    }
    file_path_ = root_dir_ / http_status_page;
    MapFile();
    if (!file_.Valid()) {
        AddStatusLine(buf);
        AddHeaders(buf);
        buf.Append(fmt::format("Content-type: text/html", NewLine::CRLF));
        const auto body {fmt::format("<p>{} : {}</p>", StatusCodeToInteger(status_code_), StatusCodeToMessage(status_code_))};
        if (!msg.empty()) {
            body += fmt::format("<p>{}</p>", msg);
        }
        buf.Append(fmt::format("Content-length: {}", body.size()), NewLine::CRLF);
        buf.Append(body);
    } else {
        std::string content {reinterpret_cast<const char*>(file_.Data()), file_.Size()};
        const Parameters params { {status_code_tag.data(), std::to_string(StatusCodeToInteger(status_code_))}, {status_tag.data(), StatusCodeToMessage(status_code_).data()}, {msg_tag.data(), std::move(msg)} };
        AddParamContent(buf, params);
    }
}

}  // namespace ws::http