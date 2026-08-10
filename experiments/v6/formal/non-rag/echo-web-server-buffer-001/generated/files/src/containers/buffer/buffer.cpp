#include "buffer.h"
#include "io.h"
#include <algorithm>
#include <cassert>

namespace ws {

Buffer::Buffer(std::size_t size) noexcept : buf_(size) {}

Buffer::Buffer(std::span<const std::byte> bytes) noexcept : buf_(bytes.begin(), bytes.end()) {}

Buffer::Buffer(std::initializer_list<std::byte> bytes) noexcept : buf_(bytes) {}

Buffer::Buffer(std::string_view str) noexcept {
    Append(str);
}

Buffer::Buffer(const Buffer& o) noexcept : buf_(o.buf_), read_pos_(o.read_pos_.load()), write_pos_(o.write_pos_.load()) {}

Buffer::Buffer(Buffer&& o) noexcept : buf_(std::move(o.buf_)), read_pos_(o.read_pos_.load()), write_pos_(o.write_pos_.load()) {}

Buffer& Buffer::operator=(const Buffer& o) noexcept {
    if (this != &o) {
        buf_ = o.buf_;
        read_pos_ = o.read_pos_.load();
        write_pos_ = o.write_pos_.load();
    }
    return *this;
}

Buffer& Buffer::operator=(Buffer&& o) noexcept {
    if (this != &o) {
        buf_ = std::move(o.buf_);
        read_pos_ = o.read_pos_.load();
        write_pos_ = o.write_pos_.load();
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
    return {ReadIter().base(), ReadableSize()};
}

std::string Buffer::ReadableString() const noexcept {
    return {reinterpret_cast<char*>(ReadIter().base()), ReadableSize()};
}

std::span<std::byte> Buffer::WritableBytes() const noexcept {
    return {WriteIter().base(), WritableSize()};
}

void Buffer::Append(std::span<const std::byte> bytes) noexcept {
    EnsureWriteableSize(bytes.size());
    std::copy(bytes.begin(), bytes.end(), WriteIter());
    HasWritten(bytes.size());
}

void Buffer::Append(std::initializer_list<std::byte> bytes) noexcept {
    Append(bytes.begin(), bytes.size());
}

void Buffer::Append(std::string_view str, std::optional<NewLine> new_line) noexcept {
    std::string full_str {str};
    if (new_line.has_value()) {
        switch (*new_line) {
            case NewLine::LF:
                full_str += "\n";
                break;
            case NewLine::CRLF:
                full_str += "\r\n";
                break;
        }
    }
    Append(full_str.data(), full_str.length());
}

void Buffer::Append(const void* data, std::size_t size) noexcept {
    assert(data);
    EnsureWriteableSize(size);
    const auto base {reinterpret_cast<const std::byte*>(data)};
    std::copy(base, base + size, WriteIter());
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
    assert(WritableSize() >= size);
    write_pos_ += size;
}

void Buffer::Retrieve(std::size_t size) noexcept {
    assert(ReadableSize() >= size);
    read_pos_ += size;
}

std::size_t Buffer::RetrieveUntil(const void* addr) noexcept {
    const auto end {static_cast<const std::byte*>(addr)};
    const auto begin {ReadIter().base()};
    assert(begin <= end);
    const auto read_size {end - begin};
    Retrieve(read_size);
    return read_size;
}

std::size_t Buffer::RetrieveAll() noexcept {
    const auto read_size {ReadableSize()};
    Retrieve(read_size);
    return read_size;
}

std::string Buffer::RetrieveAllToString() noexcept {
    const auto str {ReadableString()};
    Clear();
    return str;
}

void Buffer::Clear() noexcept {
    buf_.clear();
    read_pos_ = 0;
    write_pos_ = 0;
}

bool Buffer::Empty() const noexcept {
    return ReadableSize() == 0;
}

std::size_t Buffer::PrependableSize() const noexcept {
    return read_pos_;
}

void Buffer::MakeSpace(std::size_t size) noexcept {
    if (WritableSize() + PrependableSize() < size) {
        buf_.resize(write_pos_ + size);
    } else {
        std::copy(ReadIter(), WriteIter(), buf_.begin());
        const auto readable_size {ReadableSize()};
        read_pos_ = 0;
        write_pos_ = readable_size;
        assert(readable_size == ReadableSize());
    }
}

std::vector<std::byte>::iterator Buffer::ReadIter() const noexcept {
    return buf_.begin() + read_pos_;
}

std::vector<std::byte>::iterator Buffer::WriteIter() const noexcept {
    return buf_.begin() + write_pos_;
}

std::size_t IOBuffer::ReadFrom(io::IReadWriter& io) {
    char data[1024];
    std::size_t total_read = 0;
    while (true) {
        const auto read_size {io.Read(data, sizeof(data))};
        if (read_size == 0) {
            break;
        }
        Append(data, read_size);
        total_read += read_size;
    }
    return total_read;
}

std::size_t IOBuffer::WriteTo(io::IReadWriter& io) {
    const auto readable_bytes {ReadableBytes()};
    if (readable_bytes.empty()) {
        return 0;
    }
    const auto write_size {io.Write(reinterpret_cast<const char*>(readable_bytes.data()), readable_bytes.size())};
    Retrieve(write_size);
    return write_size;
}

Buffer& operator<<(Buffer& buf, std::string_view str) noexcept {
    return buf << Buffer(str);
}

Buffer& operator<<(Buffer& to, const Buffer& from) noexcept {
    return to.Append(from);
}

Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept {
    return buf.Append(bytes);
}

Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept {
    return buf.Append(bytes);
}

}  // namespace ws