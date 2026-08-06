#include "response.h"
#include <stdexcept>
#include <sstream>
#include <cassert>
#include <regex>

namespace ws::http {

Response::Response(std::filesystem::path root_dir) noexcept : root_dir_(std::move(root_dir)) {}

Response::~Response() noexcept {}

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
    return file_;
}

void Response::Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept {
    Clear();
    file_path_ = root_dir_ / html;
    CheckFile();
    if (status_code_ == StatusCode::OK)
        AddParamContent(buf, params);
    else
        AddPredefinedErrorContent(buf);
    code = status_code_;
}

void Response::Build(Buffer& buf, StatusCode code, std::string msg) noexcept {
    Clear();
    status_code_ = code;
    if (!msg.empty())
        AddPredefinedErrorContent(buf, msg);
    else
        Build(buf);
}

void Response::Clear() noexcept {
    file_path_.clear();
    file_.Close();
    keep_alive_ = false;
    status_code_ = StatusCode::OK;
}

void Response::Build(Buffer& buf, const Parameters* params) noexcept {
    AddStatusLine(buf);
    AddHeaders(buf);
    if (file_.Size() > 0)
        AddMappedContent(buf);
    else if (params)
        AddParamContent(buf, *params);
}

void Response::CheckFile() {
    if (!std::filesystem::exists(file_path_))
        status_code_ = StatusCode::NotFound;
    else if (!std::filesystem::is_regular_file(file_path_))
        status_code_ = StatusCode::Forbidden;
}

void Response::MapFile() {
    file_.Open(file_path_, MappedReadOnlyFile::AccessMode::Read);
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
    buf.Append("Content-Type: ");
    buf.Append(ContentTypeByFileName(file_path_.filename().string()));
    buf.Append(new_line);
}

void Response::AddMappedContent(Buffer& buf) noexcept {
    buf.Append("Content-Length: ");
    buf.Append(file_.Size());
    buf.Append(new_line);
    buf.Append(new_line);
}

void Response::AddParamContent(Buffer& buf, const Parameters& params) const noexcept {
    std::ifstream file(file_path_);
    if (!file)
        throw std::runtime_error("Failed to open HTML template");
    std::stringstream ss;
    ss << file.rdbuf();
    std::string html = PutParamIntoHTML(ss.str(), params);
    buf.Append(html);
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    std::string error_page = "<html><body><h1>";
    error_page += StatusCodeToInteger(status_code_);
    error_page += ' ';
    error_page += StatusCodeToMessage(status_code_);
    error_page += "</h1><p>";
    if (!msg.empty())
        error_page += msg;
    error_page += "</p></body></html>";
    buf.Append(error_page);
}

}  // namespace ws::http