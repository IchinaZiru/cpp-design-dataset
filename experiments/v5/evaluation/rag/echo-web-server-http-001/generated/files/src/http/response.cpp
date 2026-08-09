#include "response.h"
#include <fstream>
#include <sstream>
#include <cassert>

namespace ws::http {

Response::Response(std::filesystem::path root_dir) noexcept : root_dir_(std::move(root_dir)) {}

Response::~Response() noexcept {
    Clear();
}

Response& Response::SetKeepAlive(bool set) noexcept {
    keep_alive_ = set;
    return *this;
}

std::optional<MappedReadOnlyFile> Response::Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept {
    Clear();
    file_path_ = root_dir_ / file;
    CheckFile();
    if (file_.IsValid()) {
        AddStatusLine(buf);
        AddHeaders(buf);
        AddMappedContent(buf);
        code = status_code_;
        return file_;
    }
    code = StatusCode::NotFound;
    AddPredefinedErrorContent(buf, "File not found");
    return std::nullopt;
}

void Response::Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept {
    Clear();
    file_path_ = root_dir_ / html;
    CheckFile();
    if (file_.IsValid()) {
        AddStatusLine(buf);
        AddHeaders(buf);
        std::ifstream ifs(file_path_);
        std::string content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
        content = PutParamIntoHTML(content, params);
        buf.Append(content);
        code = status_code_;
    } else {
        code = StatusCode::NotFound;
        AddPredefinedErrorContent(buf, "File not found");
    }
}

void Response::Build(Buffer& buf, StatusCode code, std::string msg) noexcept {
    Clear();
    status_code_ = code;
    AddStatusLine(buf);
    AddHeaders(buf);
    if (!msg.empty()) {
        buf.Append(msg);
    } else {
        AddPredefinedErrorContent(buf);
    }
}

void Response::Clear() noexcept {
    file_path_.clear();
    file_ = MappedReadOnlyFile();
    keep_alive_ = false;
    status_code_ = StatusCode::OK;
}

void Response::Build(Buffer& buf, const Parameters* params) noexcept {
    AddStatusLine(buf);
    AddHeaders(buf);
    if (params) {
        AddParamContent(buf, *params);
    }
}

void Response::CheckFile() {
    if (!std::filesystem::exists(file_path_)) {
        status_code_ = StatusCode::NotFound;
        return;
    }
    if (!std::filesystem::is_regular_file(file_path_)) {
        status_code_ = StatusCode::Forbidden;
        return;
    }
}

void Response::MapFile() {
    file_ = MappedReadOnlyFile(file_path_);
}

void Response::AddStatusLine(Buffer& buf) const noexcept {
    buf.Append(version);
    buf.Append(" ");
    buf.Append(std::to_string(StatusCodeToInteger(status_code_)));
    buf.Append(" ");
    buf.Append(StatusCodeToMessage(status_code_));
    buf.Append(new_line);
}

void Response::AddHeaders(Buffer& buf) const noexcept {
    buf.Append("Content-Type: ");
    buf.Append(ContentTypeByFileName(file_path_.filename().string()));
    buf.Append(new_line);
    if (keep_alive_) {
        buf.Append("Connection: keep-alive");
        buf.Append(new_line);
    }
    buf.Append(new_line); // End of headers
}

void Response::AddMappedContent(Buffer& buf) noexcept {
    MapFile();
    if (!file_.IsValid()) return;
    buf.Append("Content-Length: ");
    buf.Append(std::to_string(file_.Size()));
    buf.Append(new_line);
}

void Response::AddParamContent(Buffer& buf, const Parameters& params) const noexcept {
    // This method is intentionally left empty as the content is already added in Build with parameters.
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    buf.Append("<html><body>");
    if (!msg.empty()) {
        buf.Append(msg);
    } else {
        buf.Append(StatusCodeToMessage(status_code_));
    }
    buf.Append("</body></html>");
}

}