#include "response.h"
#include "util.h"

#include <cassert>
#include <sstream>

namespace ws::http {

Response::Response(std::filesystem::path root_dir) noexcept : root_dir_{std::move(root_dir)} {}

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
    return file_;
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
        buf.Write(msg);
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
    file_.Open(file_path_, std::ios::in | std::ios::binary);
    if (!file_.IsValid())
        status_code_ = StatusCode::NotFound;
}

void Response::AddStatusLine(Buffer& buf) const noexcept {
    buf.Write("HTTP/1.1 ");
    buf.Write(StatusCodeToInteger(status_code_));
    buf.Write(' ');
    buf.Write(StatusCodeToMessage(status_code_));
    buf.Write(new_line);
}

void Response::AddHeaders(Buffer& buf) const noexcept {
    buf.Write("Connection: ");
    if (keep_alive_)
        buf.Write(true_tag);
    else
        buf.Write(false_tag);
    buf.Write(new_line);
    buf.Write(new_line);
}

void Response::AddMappedContent(Buffer& buf) noexcept {
    buf.Write("Content-Type: ");
    buf.Write(ContentTypeByFileName(file_path_.filename().string()));
    buf.Write(new_line);
    buf.Write("Content-Length: ");
    buf.Write(std::to_string(file_.Size()));
    buf.Write(new_line);
}

void Response::AddParamContent(Buffer& buf, const Parameters& params) const noexcept {
    std::ifstream html_file{file_path_};
    if (!html_file.is_open()) {
        status_code_ = StatusCode::NotFound;
        return;
    }
    std::stringstream ss;
    ss << html_file.rdbuf();
    std::string content = PutParamIntoHTML(ss.str(), params);
    buf.Write(content);
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    static const std::string error_page = R"(
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Error</title>
</head>
<body>
<h1>Error {{code}}</h1>
<p>{{message}}</p>
</body>
</html>)";
    Parameters params{
        {"code", std::to_string(StatusCodeToInteger(status_code_))},
        {"message", msg}
    };
    AddParamContent(buf, params);
}

}  // namespace ws::http
