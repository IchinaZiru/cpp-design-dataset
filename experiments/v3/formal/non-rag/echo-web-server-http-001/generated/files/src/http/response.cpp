#include "response.h"
#include <cassert>
#include <fstream>
#include <sstream>

namespace ws::http {

Response::Response(std::filesystem::path root_dir) noexcept : root_dir_ {std::move(root_dir)} {}

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
    else if (std::filesystem::is_directory(file_path_))
        status_code_ = StatusCode::Forbidden;
}

void Response::MapFile() {
    file_.Open(file_path_);
    if (!file_.Valid())
        status_code_ = StatusCode::NotFound;
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
    buf.Append("Connection: ");
    buf.Append(keep_alive_ ? true_tag : false_tag);
    buf.Append(new_line);
    if (status_code_ == StatusCode::OK && file_.Valid()) {
        buf.Append("Content-Type: ");
        buf.Append(ContentTypeByFileName(file_path_.filename().string()));
        buf.Append(new_line);
        buf.Append("Content-Length: ");
        buf.Append(std::to_string(file_.Size()));
        buf.Append(new_line);
    }
    buf.Append(new_line);
}

void Response::AddMappedContent(Buffer& buf) noexcept {
    // Do nothing, because the file content will be sent after the response header.
}

void Response::AddParamContent(Buffer& buf, const Parameters& params) const noexcept {
    std::ifstream ifs {file_path_};
    if (!ifs)
        return;

    std::ostringstream oss;
    std::string line;
    while (std::getline(ifs, line)) {
        ReplaceAll(line, HTMLPlaceholder("user"), params.at("user"));
        ReplaceAll(line, HTMLPlaceholder("msg"), params.at("msg"));
        oss << line << "\n";
    }

    buf.Append(oss.str());
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    static const char* error_page = R"(
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Error</title>
</head>
<body>
<h1>Error</h1>
<p>{{msg}}</p>
</body>
</html>)";

    std::string content {error_page};
    ReplaceAll(content, HTMLPlaceholder("msg"), msg);
    buf.Append(content);
}

}  // namespace ws::http