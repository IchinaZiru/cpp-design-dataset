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
    auto writable = buf.WritableBytes();
    if (writable == 0) {
        return 0;
    }
    std::string data(writable, '\0');
    read_.read(data.data(), writable);
    auto bytes_read = static_cast<std::size_t>(read_.gcount());
    buf.Append(data.data(), bytes_read);
    return bytes_read;
}

std::size_t StringStream::ReadFrom(Buffer& buf) noexcept {
    auto readable = buf.ReadableBytes();
    if (readable == 0) {
        return 0;
    }
    std::string data(buf.Peek(), readable);
    write_.write(data.data(), readable);
    buf.Retrieve(readable);
    return readable;
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read,
                               ws::FileDescriptor write) noexcept
    : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    auto writable = buf.WritableBytes();
    if (writable == 0) {
        return 0;
    }
    std::array<iovec, 1> iov{{buf.WriteBegin(), writable}};
    ssize_t bytes_written = writev(write_.fd(), iov.data(), iov.size());
    if (bytes_written < 0) {
        ThrowLastSystemError();
    }
    buf.HasWritten(static_cast<std::size_t>(bytes_written));
    return static_cast<std::size_t>(bytes_written);
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    auto readable = buf.ReadableBytes();
    if (readable == 0) {
        return 0;
    }
    std::array<iovec, 1> iov{{buf.Peek(), readable}};
    ssize_t bytes_read = readv(read_.fd(), iov.data(), iov.size());
    if (bytes_read < 0) {
        ThrowLastSystemError();
    }
    buf.Retrieve(static_cast<std::size_t>(bytes_read));
    return static_cast<std::size_t>(bytes_read);
}

}  // namespace io

}  // namespace ws