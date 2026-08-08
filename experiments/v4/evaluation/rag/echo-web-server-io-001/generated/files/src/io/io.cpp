#include "io.h"
#include "containers/buffer.h"
#include <sys/uio.h>
#include <unistd.h>
#include <array>
#include <string>

namespace ws {

namespace io {

std::size_t Null::WriteTo(Buffer& buf) noexcept {
    const auto writable = buf.WritableBytes();
    buf.HasWritten(writable);
    return writable;
}

std::size_t Null::ReadFrom(Buffer& buf) noexcept {
    const auto readable = buf.ReadableBytes();
    buf.RetrieveAll();
    return readable;
}

StringStream::StringStream(std::istream& read, std::ostream& write) noexcept
    : read_(read), write_(write) {}

std::size_t StringStream::WriteTo(Buffer& buf) noexcept {
    std::string str;
    if (std::getline(read_, str)) {
        buf.Append(str);
        return str.size();
    }
    return 0;
}

std::size_t StringStream::ReadFrom(Buffer& buf) noexcept {
    const auto readable = buf.ReadableBytes();
    if (readable > 0) {
        write_.write(buf.Peek(), readable);
        buf.RetrieveAll();
        return readable;
    }
    return 0;
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read,
                               ws::FileDescriptor write) noexcept
    : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    const auto readable = buf.ReadableBytes();
    if (readable > 0) {
        const iovec iov[] = { { buf.Peek(), readable } };
        ssize_t n = readv(read_.fd(), iov, 1);
        if (n < 0) {
            ThrowLastSystemError();
        }
        buf.Retrieve(static_cast<std::size_t>(n));
        return static_cast<std::size_t>(n);
    }
    return 0;
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    const auto writable = buf.WritableBytes();
    if (writable > 0) {
        ssize_t n = write(write_.fd(), buf.BeginWrite(), writable);
        if (n < 0) {
            ThrowLastSystemError();
        }
        buf.HasWritten(static_cast<std::size_t>(n));
        return static_cast<std::size_t>(n);
    }
    return 0;
}

}  // namespace io

}  // namespace ws