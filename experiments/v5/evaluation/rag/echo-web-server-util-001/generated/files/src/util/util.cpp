#include "util.h"
#include <execinfo.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <algorithm>
#include <cassert>
#include <cerrno>
#include <iterator>
#include <sstream>
#include <system_error>

namespace ws {

std::string StringToLower(std::string str) noexcept {
    std::transform(str.begin(), str.end(), str.begin(), ::tolower);
    return str;
}

std::string StringToUpper(std::string str) noexcept {
    std::transform(str.begin(), str.end(), str.begin(), ::toupper);
    return str;
}

std::string ReplaceAllSubstring(std::string_view str, std::string_view from,
                                std::string_view to) noexcept {
    if (from.empty()) return std::string{str};
    std::string result;
    size_t start = 0;
    while (true) {
        auto pos = str.find(from, start);
        if (pos == std::string_view::npos) break;
        result.append(str.substr(start, pos - start));
        result.append(to);
        start = pos + from.length();
    }
    result.append(str.substr(start));
    return result;
}

std::vector<std::string> SplitString(const std::string& str,
                                     const std::regex& pattern) noexcept {
    std::sregex_token_iterator iter{str.begin(), str.end(), pattern, -1};
    std::sregex_token_iterator end;
    return {iter, end};
}

std::vector<std::string> SplitStringToLines(const std::string& str) noexcept {
    std::istringstream iss{str};
    std::vector<std::string> lines;
    std::string line;
    while (std::getline(iss, line)) {
        lines.push_back(line);
    }
    return lines;
}

YAML::Node LoadYamlString(
    std::string_view str,
    std::initializer_list<std::string_view> required_fields) {
    YAML::Node node = YAML::Load(std::string{str});
    for (auto field : required_fields) {
        if (!node[field]) {
            throw std::invalid_argument{
                fmt::format("YAML node does not contain the required field: {}", field)};
        }
    }
    return node;
}

void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node,
                                 std::string_view field) {
    if (!node[field] || !node[field].IsScalar()) {
        throw std::invalid_argument{
            fmt::format("YAML field is not a scalar: {}", field)};
    }
}

constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept {
    return fd >= 0;
}

void SetFileDescriptorAsNonblocking(FileDescriptor fd) {
    int flags = fcntl(fd, F_GETFL);
    if (flags == -1) {
        throw std::system_error{errno, std::generic_category(),
                              "Failed to get file descriptor flags"};
    }
    if (fcntl(fd, F_SETFL, flags | O_NONBLOCK) == -1) {
        throw std::system_error{errno, std::generic_category(),
                              "Failed to set file descriptor as non-blocking"};
    }
}

[[noreturn]] void ThrowLastSystemError() {
    throw std::system_error{errno, std::generic_category(), strerror(errno)};
}

std::uint32_t CurrentThreadId() noexcept {
    return static_cast<std::uint32_t>(syscall(SYS_gettid));
}

void Backtrace(std::vector<std::string>& stack, std::size_t size,
               std::size_t skip) noexcept {
    void* buffer[size];
    int nptrs = backtrace(buffer, size);
    char** strings = backtrace_symbols(buffer, nptrs);
    if (strings == nullptr) return;
    for (int i = static_cast<int>(skip); i < nptrs; ++i) {
        stack.push_back(strings[i]);
    }
    free(strings);
}

std::string Backtrace(std::size_t size, std::size_t skip,
                      std::string_view prefix) noexcept {
    std::vector<std::string> stack;
    Backtrace(stack, size, skip);
    std::ostringstream oss;
    for (const auto& frame : stack) {
        oss << prefix << frame << "\n";
    }
    return oss.str();
}

template <typename T, typename... Args>
template <Args... args>
T& Singleton<T, Args...>::Instance() noexcept {
    static T instance{args...};
    return instance;
}

template <typename T, typename... Args>
template <Args... args>
std::shared_ptr<T> SingletonPtr<T, Args...>::Instance() noexcept {
    static std::shared_ptr<T> instance = std::make_shared<T>(args...);
    return instance;
}

template <typename T, typename Cleaner>
RAII<T, Cleaner>::~RAII() noexcept {
    cleaner_(obj_);
}

template <typename T, typename Cleaner>
const T& RAII<T, Cleaner>::Object() const noexcept {
    return obj_;
}

MappedReadOnlyFile::MappedReadOnlyFile() noexcept {}

MappedReadOnlyFile::MappedReadOnlyFile(MappedReadOnlyFile&& other) noexcept
    : path_{std::move(other.path_)},
      stat_{other.stat_},
      data_{std::exchange(other.data_, nullptr)} {}

MappedReadOnlyFile& MappedReadOnlyFile::operator=(MappedReadOnlyFile&& other) noexcept {
    if (this != &other) {
        Unmap();
        path_ = std::move(other.path_);
        stat_ = other.stat_;
        data_ = std::exchange(other.data_, nullptr);
    }
    return *this;
}

MappedReadOnlyFile::~MappedReadOnlyFile() noexcept {
    Unmap();
}

std::byte* MappedReadOnlyFile::Map(std::string path) {
    if (!path_.empty()) {
        throw std::invalid_argument{"File is already mapped"};
    }
    path_ = std::move(path);
    Check();
    int fd = open(path_.c_str(), O_RDONLY);
    if (fd == -1) {
        throw std::system_error{errno, std::generic_category(), "Failed to open file"};
    }
    RAII<int> raii_fd{fd, [](int fd) { close(fd); }};
    data_ = static_cast<std::byte*>(mmap(nullptr, stat_.st_size, PROT_READ, MAP_PRIVATE, fd, 0));
    if (data_ == MAP_FAILED) {
        throw std::system_error{errno, std::generic_category(), "Failed to map file"};
    }
    return data_;
}

void MappedReadOnlyFile::Unmap() noexcept {
    if (data_) {
        munmap(data_, stat_.st_size);
        data_ = nullptr;
        path_.clear();
        stat_ = {};
    }
}

std::size_t MappedReadOnlyFile::Size() const noexcept {
    return stat_.st_size;
}

std::byte* MappedReadOnlyFile::Data() const noexcept {
    return data_;
}

std::string_view MappedReadOnlyFile::Path() const noexcept {
    return path_;
}

void MappedReadOnlyFile::Check() {
    struct stat file_stat;
    if (stat(path_.c_str(), &file_stat) == -1) {
        throw std::system_error{errno, std::generic_category(), "Failed to get file status"};
    }
    if (S_ISDIR(file_stat.st_mode)) {
        throw std::invalid_argument{"The path refers to a directory"};
    }
    stat_ = file_stat;
}

}  // namespace ws