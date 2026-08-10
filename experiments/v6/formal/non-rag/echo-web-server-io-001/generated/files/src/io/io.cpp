#include "io.h"
#include "containers/buffer.h"
#include <sys/uio.h>
#include <unistd.h>
#include <array>

namespace ws {

namespace io {

std::size_t Null::WriteTo(Buffer& buf) noexcept {
    const auto size {buf.WritableSize()};
    buf.HasWritten(size);
    return size;
}

std::size_t Null::ReadFrom(Buffer& buf) noexcept {
    buf.RetrieveAll();
    return 0;
}

StringStream::StringStream(std::istream& read, std::ostream& write) noexcept : read_(read), write_(write) {}

std::size_t StringStream::WriteTo(Buffer& buf) noexcept {
    std::string str;
    if (std::getline(read_, str)) {
        buf.Append(str);
        return str.length();
    }
    return 0;
}

std::size_t StringStream::ReadFrom(Buffer& buf) noexcept {
    const std::string str {buf.RetrieveAllToString()};
    write_ << str;
    return str.length();
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    const auto buf_bytes {buf.WritableBytes()};
    std::array<std::byte, 0x10000> ext_bytes;
    const std::array bufs { iovec {.iov_base = buf_bytes.data(), .iov_len = buf_bytes.size_bytes()}, iovec {.iov_base = ext_bytes.data(), .iov_len = ext_bytes.size()}};
    const auto size {readv(read_.fd_, bufs.data(), bufs.size())};
    if (size < 0) {
        ThrowLastSystemError();
    }
    buf.HasWritten(buf_bytes.size_bytes());
    if (static_cast<std::size_t>(size) > buf_bytes.size_bytes()) {
        buf.Append({ext_bytes.cbegin(), ext_bytes.cbegin() + (size - buf_bytes.size_bytes())});
    }
    return size;
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    const auto bytes {buf.ReadableBytes()};
    const auto size {write(write_.fd_, bytes.data(), bytes.size_bytes())};
    if (size < 0) {
        ThrowLastSystemError();
    }
    buf.Retrieve(size);
    return size;
}

}  // namespace io

}  // namespace ws