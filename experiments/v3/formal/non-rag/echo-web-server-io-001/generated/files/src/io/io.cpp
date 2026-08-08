#include "io.h"
#include "util.h"
#include "containers/buffer.h"
#include <sys/uio.h>
#include <unistd.h>
#include <array>

namespace ws {

namespace io {

std::size_t Null::WriteTo(Buffer& buf) noexcept {
    auto writable = buf.WritableBytes();
    buf.HasWritten(writable);
    return writable;
}

std::size_t Null::ReadFrom(Buffer& buf) noexcept {
    auto readable = buf.ReadableBytes();
    buf.Retrieve(readable);
    return readable;
}

StringStream::StringStream(std::istream& read, std::ostream& write) noexcept
    : read_(read), write_(write) {}

std::size_t StringStream::WriteTo(Buffer& buf) noexcept {
    auto readable = buf.ReadableBytes();
    if (readable == 0) {
        return 0;
    }
    write_.write(buf.Peek(), static_cast<std::streamsize>(readable));
    buf.Retrieve(readable);
    return readable;
}

std::size_t StringStream::ReadFrom(Buffer& buf) noexcept {
    std::array<char, 4096> buffer;
    read_.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
    auto bytesRead = read_.gcount();
    if (bytesRead > 0) {
        buf.Append(buffer.data(), static_cast<size_t>(bytesRead));
    }
    return static_cast<size_t>(bytesRead);
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read,
                               ws::FileDescriptor write) noexcept
    : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    auto readable = buf.ReadableBytes();
    if (readable == 0) {
        return 0;
    }
    iovec iov[1];
    iov[0].iov_base = const_cast<char*>(buf.Peek());
    iov[0].iov_len = readable;
    ssize_t bytesWritten = readv(read_.fd(), iov, 1);
    if (bytesWritten < 0) {
        ThrowLastSystemError();
    }
    buf.Retrieve(static_cast<size_t>(bytesWritten));
    return static_cast<size_t>(bytesWritten);
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    std::array<char, 4096> buffer;
    ssize_t bytesRead = write(write_.fd(), buffer.data(), buffer.size());
    if (bytesRead < 0) {
        ThrowLastSystemError();
    }
    if (bytesRead > 0) {
        buf.Append(buffer.data(), static_cast<size_t>(bytesRead));
    }
    return static_cast<size_t>(bytesRead);
}

}  // namespace io

}  // namespace ws