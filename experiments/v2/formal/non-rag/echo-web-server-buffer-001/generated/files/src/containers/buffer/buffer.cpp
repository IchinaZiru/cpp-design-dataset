#include "buffer.h"
#include "io.h"
#include <algorithm>
#include <cassert>

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
    std::copy(bytes.begin(), bytes.end(), WriteIter());
    HasWritten(bytes.size());
}

void Buffer::Append(std::initializer_list<std::byte> bytes) noexcept {
    Append({bytes.begin(), bytes.end()});
}

void Buffer::Append(std::string_view str, std::optional<NewLine> new_line) noexcept {
    EnsureWriteableSize(str.size() + (new_line ? 2 : 0));
    auto write_iter = WriteIter();
    std::copy(str.begin(), str.end(), write_iter);
    if (new_line) {
        switch (*new_line) {
            case NewLine::LF:
                *write_iter++ = static_cast<std::byte>('\n');
                break;
            case NewLine::CRLF:
                *write_iter++ = static_cast<std::byte>('\r');
                *write_iter++ = static_cast<std::byte>('\n');
                break;
        }
    }
    HasWritten(str.size() + (new_line ? 2 : 0));
}

void Buffer::Append(const void* data, std::size_t size) noexcept {
    Append({static_cast<const std::byte*>(data), size});
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
    if (offset > 0 && read_pos_ + offset <= write_pos_) {
        Retrieve(offset);
        return offset;
    }
    return 0;
}

std::size_t Buffer::RetrieveAll() noexcept {
    auto size = ReadableSize();
    Clear();
    return size;
}

std::string Buffer::RetrieveAllToString() noexcept {
    auto str = ReadableString();
    Clear();
    return str;
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
        std::copy(ReadIter(), WriteIter(), buf_.begin());
        write_pos_ -= read_pos_;
        read_pos_ = 0;
    }
}

std::vector<std::byte>::iterator Buffer::ReadIter() const noexcept {
    return buf_.begin() + read_pos_;
}

std::vector<std::byte>::iterator Buffer::WriteIter() const noexcept {
    return buf_.begin() + write_pos_;
}

std::size_t IOBuffer::ReadFrom(io::IReadWriter& io) {
    std::array<std::byte, 4096> buffer;
    auto read_size = io.Read(buffer);
    Append({buffer.data(), read_size});
    return read_size;
}

std::size_t IOBuffer::WriteTo(io::IReadWriter& io) {
    auto readable_bytes = ReadableBytes();
    auto write_size = io.Write(readable_bytes);
    Retrieve(write_size);
    return write_size;
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