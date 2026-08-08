#include "response.h"
#include <cassert>
#include <fstream>
#include <sstream>

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
    if (status_code_ == StatusCode::OK)
        MapFile();
    Build(buf);
    code = status_code_;
    return file_ ? std::optional<MappedReadOnlyFile>(file_) : std::nullopt;
}

void Response::Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept {
    Clear();
    file_path_ = root_dir_ / html;
    CheckFile();
    if (status_code_ == StatusCode::OK)
        Build(buf, &params);
    else
        AddPredefinedErrorContent(buf);
    code = status_code_;
}

void Response::Build(Buffer& buf, StatusCode code, std::string msg) noexcept {
    Clear();
    status_code_ = code;
    AddStatusLine(buf);
    AddHeaders(buf);
    if (!msg.empty())
        buf.Append(msg);
}

void Response::Clear() noexcept {
    file_path_.clear();
    file_.Close();
    keep_alive_ = false;
    status_code_ = StatusCode::OK;
}

void Response::Build(Buffer& buf, const Parameters* params) noexcept {
    AddStatusLine(buf);
    if (params)
        AddParamContent(buf, *params);
    else
        AddMappedContent(buf);
    AddHeaders(buf);
}

void Response::CheckFile() {
    if (!std::filesystem::exists(file_path_))
        status_code_ = StatusCode::NotFound;
}

void Response::MapFile() {
    file_.Open(file_path_);
    if (!file_.Valid())
        status_code_ = StatusCode::Forbidden;
}

void Response::AddStatusLine(Buffer& buf) const noexcept {
    buf.Append("HTTP/1.1 ");
    buf.Append(StatusCodeToInteger(status_code_));
    buf.Append(' ');
    buf.Append(StatusCodeToMessage(status_code_));
    buf.Append(new_line);
}

void Response::AddHeaders(Buffer& buf) const noexcept {
    if (keep_alive_) {
        buf.Append("Connection: keep-alive");
        buf.Append(new_line);
    }
    buf.Append(new_line);
}

void Response::AddMappedContent(Buffer& buf) noexcept {
    if (!file_.Valid())
        return;
    auto content_type = ContentTypeByFileName(file_path_.filename().string());
    buf.Append("Content-Type: ");
    buf.Append(content_type);
    buf.Append(new_line);
}

void Response::AddParamContent(Buffer& buf, const Parameters& params) const noexcept {
    std::ifstream file(file_path_);
    if (!file.is_open())
        return;
    std::stringstream ss;
    ss << file.rdbuf();
    std::string html = PutParamIntoHTML(ss.str(), params);
    buf.Append(html);
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    static const char* error_page_template = "<html><body><h1>Error</h1><p>${message}</p></body></html>";
    Parameters params {{"message", std::string(msg)}};
    AddParamContent(buf, params);
}

}  // namespace ws::http