#include "util.h"

#include <fmt/format.h>
#include <yaml-cpp/yaml.h>
#include <sys/stat.h>
#include <concepts>
#include <functional>
#include <initializer_list>
#include <memory>
#include <regex>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
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
    if (from.empty())
        return std::string{str};

    std::string result;
    size_t start = 0;
    while (true) {
        auto pos = str.find(from, start);
        if (pos == std::string_view::npos)
            break;
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
    return SplitString(str, std::regex{"\r?\n"});
}

YAML::Node LoadYamlString(
    std::string_view str,
    std::initializer_list<std::string_view> required_fields) {
    YAML::Node node = YAML::Load(std::string{str});
    for (auto field : required_fields) {
        if (!node[field])
            throw std::invalid_argument{
                fmt::format("Missing required field: {}", field)};
    }
    return node;
}

void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node,
                                 std::string_view field) {
    if (!node[field] || !node[field].IsScalar())
        throw std::invalid_argument{
            fmt::format("Field is not a scalar: {}", field)};
}

constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept {
    return fd >= 0;
}

void SetFileDescriptorAsNonblocking(FileDescriptor fd) {
    int flags = fcntl(fd, F_GETFL);
    if (flags == -1)
        ThrowLastSystemError();

    if (fcntl(fd, F_SETFL, flags | O_NONBLOCK) == -1)
        ThrowLastSystemError();
}

[[noreturn]] void ThrowLastSystemError() {
    throw std::system_error{errno, std::generic_category()};
}

std::uint32_t CurrentThreadId() noexcept {
    return static_cast<std::uint32_t>(syscall(SYS_gettid));
}

void Backtrace(std::vector<std::string>& stack, std::size_t size,
               std::size_t skip) noexcept {
    void* buffer[size];
    auto count = backtrace(buffer, size);
    if (count <= skip)
        return;

    char** symbols = backtrace_symbols(buffer + skip, count - skip);
    if (!symbols)
        return;

    for (std::size_t i = 0; i < count - skip; ++i) {
        stack.emplace_back(symbols[i]);
    }
    free(symbols);
}

std::string Backtrace(std::size_t size, std::size_t skip,
                      std::string_view prefix) noexcept {
    std::vector<std::string> stack;
    Backtrace(stack, size, skip);
    std::ostringstream oss;
    for (const auto& frame : stack)
        oss << prefix << frame << "\n";
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
    if (data_)
        throw std::runtime_error{"Already mapped a file."};

    path_ = std::move(path);
    Check();

    data_ = static_cast<std::byte*>(mmap(nullptr, stat_.st_size, PROT_READ,
                                         MAP_PRIVATE, open(path_.c_str(), O_RDONLY), 0));
    if (data_ == MAP_FAILED)
        ThrowLastSystemError();

    return data_;
}

void MappedReadOnlyFile::Unmap() noexcept {
    if (!data_)
        return;

    munmap(data_, stat_.st_size);
    data_ = nullptr;
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
    if (stat(path_.c_str(), &stat_) == -1)
        ThrowLastSystemError();

    if (S_ISDIR(stat_.st_mode))
        throw std::invalid_argument{"The path refers to a directory."};
}

}  // namespace ws
