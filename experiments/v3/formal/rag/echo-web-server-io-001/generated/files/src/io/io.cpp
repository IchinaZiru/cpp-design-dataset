#include "io.h"
#include "containers/buffer.h"
#include <sys/uio.h>
#include <unistd.h>
#include <array>

namespace ws {

namespace io {

std::size_t Null::WriteTo(Buffer& buf) noexcept {
    const auto writable = buf.WritableBytes();
    buf.HasWritten(writable);
    return writable;
}

std::size_t Null::ReadFrom(Buffer& buf) noexcept {
    const auto readable = buf.ReadableBytes();
    buf.Retrieve(readable);
    return readable;
}

StringStream::StringStream(std::istream& read, std::ostream& write) noexcept : read_(read), write_(write) {}

std::size_t StringStream::WriteTo(Buffer& buf) noexcept {
    std::string str;
    if (std::getline(read_, str)) {
        const auto size = str.size();
        buf.Append(str);
        return size;
    }
    return 0;
}

std::size_t StringStream::ReadFrom(Buffer& buf) noexcept {
    std::string str(buf.Peek(), buf.ReadableBytes());
    write_ << str;
    buf.RetrieveAll();
    return str.size();
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    const auto readable = buf.ReadableBytes();
    if (readable == 0) return 0;

    iovec iov[1];
    iov[0].iov_base = buf.Peek();
    iov[0].iov_len = readable;

    ssize_t n = writev(write_.Fd(), iov, 1);
    if (n < 0) {
        ThrowLastSystemError();
    }

    if (n > 0) {
        buf.Retrieve(static_cast<std::size_t>(n));
    }

    return static_cast<std::size_t>(n);
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    std::array<char, 65536> buffer;
    ssize_t n = read(read_.Fd(), buffer.data(), buffer.size());
    if (n < 0) {
        ThrowLastSystemError();
    }

    if (n > 0) {
        buf.Append(buffer.data(), static_cast<std::size_t>(n));
    }

    return static_cast<std::size_t>(n);
}

}  // namespace io

}  // namespace ws