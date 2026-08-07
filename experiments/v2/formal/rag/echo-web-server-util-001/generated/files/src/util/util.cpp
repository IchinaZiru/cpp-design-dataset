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
    std::ranges::transform(str, str.begin(), [](unsigned char c) { return std::tolower(c); });
    return str;
}

std::string StringToUpper(std::string str) noexcept {
    std::ranges::transform(str, str.begin(), [](unsigned char c) { return std::toupper(c); });
    return str;
}

std::string ReplaceAllSubstring(std::string_view str, std::string_view from,
                                std::string_view to) noexcept {
    if (from.empty()) {
        return std::string{str};
    }
    std::ostringstream ss;
    std::size_t begin = 0;
    while (true) {
        auto pos = str.find(from, begin);
        if (pos == std::string_view::npos) {
            ss << str.substr(begin);
            break;
        }
        ss << str.substr(begin, pos - begin) << to;
        begin = pos + from.length();
    }
    return ss.str();
}

std::vector<std::string> SplitString(const std::string& str,
                                     const std::regex& pattern) noexcept {
    std::sregex_token_iterator iter{str.begin(), str.end(), pattern, -1};
    std::sregex_token_iterator end;
    return {iter, end};
}

std::vector<std::string> SplitStringToLines(const std::string& str) noexcept {
    static const std::regex line_pattern{"\r*\n"};
    return SplitString(str, line_pattern);
}

YAML::Node LoadYamlString(
    std::string_view str,
    std::initializer_list<std::string_view> required_fields) {
    YAML::Node node = YAML::Load(std::string{str});
    for (auto field : required_fields) {
        if (!node[field.data()]) {
            throw std::invalid_argument{
                fmt::format("The YAML node does not contain the required field: {}", field)};
        }
        if (!node[field.data()].IsScalar()) {
            throw std::invalid_argument{
                fmt::format("The YAML field is not a scalar: {}", field)};
        }
    }
    return node;
}

void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node,
                                 std::string_view field) {
    if (!node[field.data()]) {
        throw std::invalid_argument{
            fmt::format("The YAML node does not contain the required field: {}", field)};
    }
    if (!node[field.data()].IsScalar()) {
        throw std::invalid_argument{
            fmt::format("The YAML field is not a scalar: {}", field)};
    }
}

constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept {
    return fd >= 0;
}

void SetFileDescriptorAsNonblocking(FileDescriptor fd) {
    assert(IsValidFileDescriptor(fd));
    if (fcntl(fd, F_SETFL, fcntl(fd, F_GETFD) | O_NONBLOCK) < 0) {
        ThrowLastSystemError();
    }
}

[[noreturn]] void ThrowLastSystemError() {
    throw std::system_error{errno, std::system_category()};
}

std::uint32_t CurrentThreadId() noexcept {
    return syscall(SYS_gettid);
}

void Backtrace(std::vector<std::string>& stack, std::size_t size,
               std::size_t skip) noexcept {
    auto buffer = std::make_unique<void*[]>(size);
    auto ret_size = backtrace(buffer.get(), size);
    if (ret_size > 0) {
        auto stack_strs = backtrace_symbols(buffer.get(), ret_size);
        for (std::size_t i = skip; i < ret_size; ++i) {
            stack.push_back(stack_strs[i]);
        }
        free(stack_strs);
    }
}

std::string Backtrace(std::size_t size, std::size_t skip,
                      std::string_view prefix) noexcept {
    std::vector<std::string> stack;
    Backtrace(stack, size, skip);
    std::ostringstream ss;
    for (const auto& frame : stack) {
        ss << prefix << frame << "\n";
    }
    return ss.str();
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

MappedReadOnlyFile::MappedReadOnlyFile(MappedReadOnlyFile&& other) noexcept : path_{std::move(other.path_)},
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
    Unmap();
    path_ = std::move(path);
    Check();
    RAII<int, decltype(&close)> fd{open(path_.c_str(), O_RDONLY), close};
    if (!IsValidFileDescriptor(fd.Object())) {
        ThrowLastSystemError();
    }
    void* map_base = mmap(nullptr, stat_.st_size, PROT_READ, MAP_PRIVATE, fd.Object(), 0);
    if (map_base == MAP_FAILED) {
        ThrowLastSystemError();
    }
    data_ = static_cast<std::byte*>(map_base);
    return data_;
}

void MappedReadOnlyFile::Unmap() noexcept {
    if (data_) {
        munmap(data_, stat_.st_size);
        data_ = nullptr;
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
    if (stat(path_.c_str(), &stat_) < 0) {
        ThrowLastSystemError();
    }
    if (S_ISDIR(stat_.st_mode)) {
        throw std::invalid_argument{
            fmt::format("The path refers to a directory: {}", path_)};
    }
}

}  // namespace ws