#include "response.h"
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
    if (!file_.Valid()) {
        status_code_ = StatusCode::NotFound;
        AddPredefinedErrorContent(buf);
        return std::nullopt;
    }
    MapFile();
    status_code_ = StatusCode::OK;
    Build(buf);
    return file_;
}

void Response::Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept {
    Clear();
    file_path_ = root_dir_ / html;
    CheckFile();
    if (!file_.Valid()) {
        status_code_ = StatusCode::NotFound;
        AddPredefinedErrorContent(buf);
        return;
    }
    MapFile();
    status_code_ = StatusCode::OK;
    Build(buf, &params);
}

void Response::Build(Buffer& buf, StatusCode code, std::string msg) noexcept {
    Clear();
    status_code_ = code;
    AddPredefinedErrorContent(buf, msg);
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
    if (file_.Valid()) {
        AddMappedContent(buf);
    } else if (params) {
        AddParamContent(buf, *params);
    }
}

void Response::CheckFile() {
    if (!std::filesystem::exists(file_path_)) return;
    if (!std::filesystem::is_regular_file(file_path_)) {
        file_.Close();
        return;
    }
    file_ = MappedReadOnlyFile(file_path_);
}

void Response::MapFile() {
    if (file_.Valid()) {
        file_ = MappedReadOnlyFile(file_path_);
    }
}

void Response::AddStatusLine(Buffer& buf) const noexcept {
    std::ostringstream oss;
    oss << "HTTP/" << version << ' ' << StatusCodeToInteger(status_code_) << ' ' << StatusCodeToMessage(status_code_) << new_line;
    buf.Write(oss.str());
}

void Response::AddHeaders(Buffer& buf) const noexcept {
    std::ostringstream oss;
    if (keep_alive_) {
        oss << "Connection: keep-alive" << new_line;
    } else {
        oss << "Connection: close" << new_line;
    }
    buf.Write(oss.str());
}

void Response::AddMappedContent(Buffer& buf) noexcept {
    std::ostringstream oss;
    oss << "Content-Type: " << ContentTypeByFileName(file_path_.filename().string()) << new_line;
    oss << "Content-Length: " << file_.Size() << new_line;
    oss << new_line;
    buf.Write(oss.str());
}

void Response::AddParamContent(Buffer& buf, const Parameters& params) const noexcept {
    std::ifstream ifs(file_path_);
    if (!ifs.is_open()) return;
    std::string content((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    content = PutParamIntoHTML(content, params);
    buf.Write(content);
}

void Response::AddPredefinedErrorContent(Buffer& buf, std::string_view msg) noexcept {
    std::ostringstream oss;
    oss << "Content-Type: text/html" << new_line;
    oss << "Content-Length: 135" << new_line;
    oss << new_line;
    oss << "<html><body><h1>" << StatusCodeToInteger(status_code_) << ' ' << StatusCodeToMessage(status_code_) << "</h1><p>" << msg << "</p></body></html>";
    buf.Write(oss.str());
}

}  // namespace ws::http