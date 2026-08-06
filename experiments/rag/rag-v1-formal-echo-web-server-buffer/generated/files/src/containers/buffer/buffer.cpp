#include "buffer.h"
#include <cassert>
#include <cstring>

namespace ws {

Buffer::Buffer(std::size_t size) noexcept : buf_(size) {}

Buffer::Buffer(std::span<const std::byte> bytes) noexcept : buf_(bytes.begin(), bytes.end()) {}

Buffer::Buffer(std::initializer_list<std::byte> bytes) noexcept : buf_(bytes) {}

Buffer::Buffer(std::string_view str) noexcept {
    buf_.assign(str.begin(), str.end());
}

Buffer::Buffer(const Buffer& other) noexcept : buf_(other.buf_), read_pos_(other.read_pos_.load()), write_pos_(other.write_pos_.load()) {}

Buffer::Buffer(Buffer&& other) noexcept : buf_(std::move(other.buf_)), read_pos_(other.read_pos_.exchange(0)), write_pos_(other.write_pos_.exchange(0)) {}

Buffer& Buffer::operator=(const Buffer& other) noexcept {
    if (this != &other) {
        buf_ = other.buf_;
        read_pos_.store(other.read_pos_.load());
        write_pos_.store(other.write_pos_.load());
    }
    return *this;
}

Buffer& Buffer::operator=(Buffer&& other) noexcept {
    if (this != &other) {
        buf_ = std::move(other.buf_);
        read_pos_.store(other.read_pos_.exchange(0));
        write_pos_.store(other.write_pos_.exchange(0));
    }
    return *this;
}

std::size_t Buffer::WritableSize() const noexcept {
    return buf_.size() - write_pos_;
}

std::size_t Buffer::ReadableSize() const noexcept {
    return write_pos_ - read_pos_;
}

std::optional<std::byte> Buffer::Peek() const noexcept {
    if (read_pos_ < write_pos_) {
        return buf_[read_pos_];
    }
    return std::nullopt;
}

std::span<const std::byte> Buffer::ReadableBytes() const noexcept {
    return {buf_.data() + read_pos_, ReadableSize()};
}

std::string Buffer::ReadableString() const noexcept {
    return {reinterpret_cast<const char*>(buf_.data()) + read_pos_, ReadableSize()};
}

std::span<std::byte> Buffer::WritableBytes() const noexcept {
    return {buf_.data() + write_pos_, WritableSize()};
}

void Buffer::Append(std::span<const std::byte> bytes) noexcept {
    EnsureWriteableSize(bytes.size());
    std::memcpy(buf_.data() + write_pos_, bytes.data(), bytes.size());
    HasWritten(bytes.size());
}

void Buffer::Append(std::initializer_list<std::byte> bytes) noexcept {
    Append({bytes.begin(), bytes.end()});
}

void Buffer::Append(std::string_view str, std::optional<NewLine> new_line) noexcept {
    EnsureWriteableSize(str.size() + (new_line ? 2 : 0));
    std::memcpy(buf_.data() + write_pos_, str.data(), str.size());
    HasWritten(str.size());

    if (new_line) {
        switch (*new_line) {
            case NewLine::LF:
                Append({static_cast<std::byte>(10)});
                break;
            case NewLine::CRLF:
                Append({static_cast<std::byte>(13), static_cast<std::byte>(10)});
                break;
        }
    }
}

void Buffer::Append(const void* data, std::size_t size) noexcept {
    EnsureWriteableSize(size);
    std::memcpy(buf_.data() + write_pos_, data, size);
    HasWritten(size);
}

void Buffer::Append(const Buffer& buf) noexcept {
    Append(buf.ReadableBytes());
}

void Buffer::EnsureWriteableSize(std::size_t size) noexcept {
    if (WritableSize() < size) {
        MakeSpace(size);
    }
}

void Buffer::HasWritten(std::size_t size) noexcept {
    assert(write_pos_ + size <= buf_.size());
    write_pos_ += size;
}

void Buffer::Retrieve(std::size_t size) noexcept {
    assert(read_pos_ + size <= write_pos_);
    read_pos_ += size;
}

std::size_t Buffer::RetrieveUntil(const void* addr) noexcept {
    auto offset = static_cast<const std::byte*>(addr) - buf_.data();
    assert(offset >= 0 && static_cast<std::size_t>(offset) <= write_pos_);
    Retrieve(static_cast<std::size_t>(offset));
    return ReadableSize();
}

std::size_t Buffer::RetrieveAll() noexcept {
    auto size = ReadableSize();
    read_pos_ = 0;
    write_pos_ = 0;
    return size;
}

std::string Buffer::RetrieveAllToString() noexcept {
    std::string result = ReadableString();
    RetrieveAll();
    return result;
}

void Buffer::Clear() noexcept {
    read_pos_ = 0;
    write_pos_ = 0;
}

bool Buffer::Empty() const noexcept {
    return read_pos_ == write_pos_;
}

std::size_t Buffer::PrependableSize() const noexcept {
    return read_pos_;
}

void Buffer::MakeSpace(std::size_t size) noexcept {
    if (WritableSize() + PrependableSize() < size) {
        buf_.resize(write_pos_ + size);
    } else {
        std::size_t readable = ReadableSize();
        std::memmove(buf_.data(), buf_.data() + read_pos_, readable);
        read_pos_ = 0;
        write_pos_ = readable;
    }
}

std::vector<std::byte>::iterator Buffer::ReadIter() const noexcept {
    return buf_.begin() + read_pos_;
}

std::vector<std::byte>::iterator Buffer::WriteIter() const noexcept {
    return buf_.begin() + write_pos_;
}

Buffer& operator<<(Buffer& buf, std::string_view str) noexcept {
    buf.Append(str);
    return buf;
}

Buffer& operator<<(Buffer& to, const Buffer& from) noexcept {
    to.Append(from);
    return to;
}

Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept {
    buf.Append(bytes);
    return buf;
}

Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept {
    buf.Append(bytes);
    return buf;
}

}  // namespace ws
