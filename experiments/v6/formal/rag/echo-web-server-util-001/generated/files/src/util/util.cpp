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
    std::ranges::transform(str.begin(), str.end(), str.begin(), [](const unsigned char c) noexcept { return std::tolower(c); });
    return str;
}

std::string StringToUpper(std::string str) noexcept {
    std::ranges::transform(str.begin(), str.end(), str.begin(), [](const unsigned char c) noexcept { return std::toupper(c); });
    return str;
}

std::string ReplaceAllSubstring(std::string_view str, std::string_view from,
                                std::string_view to) noexcept {
    if (from.empty()) {
        return std::string{str};
    }
    std::string result;
    const auto begin {str.find(from)};
    while (begin != std::string_view::npos) {
        result.append(str.substr(0, begin));
        result.append(to);
        str.remove_prefix(begin + from.length());
        begin = str.find(from);
    }
    result.append(str);
    return result;
}

std::vector<std::string> SplitString(const std::string& str,
                                     const std::regex& pattern) noexcept {
    std::vector<std::string> strs;
    const std::sregex_token_iterator begin {str.cbegin(), str.cend(), pattern, -1};
    std::copy(begin, std::sregex_token_iterator {}, std::back_inserter(strs));
    return strs;
}

std::vector<std::string> SplitStringToLines(const std::string& str) noexcept {
    static const std::regex pattern {"\r*\n"};
    return SplitString(str, pattern);
}

YAML::Node LoadYamlString(
    std::string_view str,
    std::initializer_list<std::string_view> required_fields) {
    const YAML::Node node {YAML::Load(str.data())};
    std::ranges::for_each(required_fields, [&node, &str](const std::string_view field) {
        if (!node[field.data()]) {
            throw std::invalid_argument {fmt::format("Invalid YAML value: '{}'", str)};
        }
    });
    return node;
}

void ThrowIfYamlFieldIsNotScalar(const YAML::Node& node,
                                 std::string_view field) {
    if (!node[field.data()].IsScalar()) {
        throw std::invalid_argument {fmt::format("Invalid YAML field: '{}'", field)};
    }
}

constexpr bool IsValidFileDescriptor(FileDescriptor fd) noexcept {
    return fd >= 0;
}

void SetFileDescriptorAsNonblocking(FileDescriptor fd) {
    assert(IsValidFileDescriptor(fd));
    if (fcntl(fd, F_SETFL, fcntl(fd, F_GETFD) | O_NONBLOCK) == -1) {
        ThrowLastSystemError();
    }
}

[[noreturn]] void ThrowLastSystemError() {
    throw std::system_error {errno, std::system_category()};
}

std::uint32_t CurrentThreadId() noexcept {
    return static_cast<std::uint32_t>(syscall(SYS_gettid));
}

void Backtrace(std::vector<std::string>& stack, std::size_t size,
               std::size_t skip) noexcept {
    if (size == 0) {
        return;
    }
    std::unique_ptr<VoidPtr[]> buffer {new VoidPtr[size] {}};
    const auto ret_size {backtrace(buffer.get(), static_cast<int>(size))};
    char** const stack_strs {backtrace_symbols(buffer.get(), ret_size)};
    for (auto i {skip}; i < ret_size; ++i) {
        stack.push_back(stack_strs[i]);
    }
    free(stack_strs);
}

std::string Backtrace(std::size_t size, std::size_t skip,
                      std::string_view prefix) noexcept {
    std::vector<std::string> stack;
    Backtrace(stack, size, skip);
    std::ostringstream backtrace;
    std::ranges::for_each(stack, [&backtrace, &prefix](const auto& call) noexcept {
        backtrace << prefix << call << "\n";
    });
    return backtrace.str();
}

template <typename T, typename... Args>
template <Args... args>
T& Singleton<T, Args...>::Instance() noexcept {
    static T ins {std::move(args)...};
    return ins;
}

template <typename T, typename... Args>
template <Args... args>
std::shared_ptr<T> SingletonPtr<T, Args...>::Instance() noexcept {
    static const std::shared_ptr<T> ins { std::make_shared<T>(std::move(args)...)};
    return ins;
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

MappedReadOnlyFile::MappedReadOnlyFile(MappedReadOnlyFile&& o) noexcept : path_ {std::move(o.path_)}, stat_ {std::move(o.stat_)}, data_ {o.data_} {
    o.data_ = nullptr;
}

MappedReadOnlyFile& MappedReadOnlyFile::operator=(MappedReadOnlyFile&& o) noexcept {
    if (this != &o) {
        Unmap();
        path_ = std::move(o.path_);
        stat_ = std::move(o.stat_);
        data_ = o.data_;
        o.data_ = nullptr;
    }
    return *this;
}

MappedReadOnlyFile::~MappedReadOnlyFile() noexcept {
    Unmap();
}

std::byte* MappedReadOnlyFile::Map(std::string path) {
    if (!path_.empty()) {
        Unmap();
    }
    path_ = std::move(path);
    Check();
    const RAII fd {open(path_.c_str(), O_RDONLY), [](const auto fd) noexcept { if (IsValidFileDescriptor(fd)) { close(fd); } }};
    const auto map_base {mmap(nullptr, stat_.st_size, PROT_READ, MAP_PRIVATE, fd.Object(), 0)};
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
    assert(!path_.empty());
    if (stat(path_.data(), &stat_) == -1) {
        ThrowLastSystemError();
    }
    if (S_ISDIR(stat_.st_mode)) {
        throw std::invalid_argument {fmt::format("'{}' is a directory", path_)};
    }
}

}  // namespace ws
