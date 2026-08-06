#include "io.h"
#include "util.h"

#include <cstring>
#include <system_error>

namespace ws {

class Buffer;

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

StringStream::StringStream(std::istream& read, std::ostream& write) noexcept
    : read_(read), write_(write) {}

std::size_t StringStream::WriteTo(Buffer& buf) noexcept {
    std::string str(buf.ReadableBytes(), '\0');
    read_.read(str.data(), str.size());
    const auto bytes_read = static_cast<std::size_t>(read_.gcount());
    if (bytes_read > 0) {
        buf.Retrieve(bytes_read);
    }
    return bytes_read;
}

std::size_t StringStream::ReadFrom(Buffer& buf) noexcept {
    const auto readable = buf.ReadableBytes();
    write_.write(buf.Peek(), readable);
    buf.Retrieve(readable);
    return readable;
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read,
                               ws::FileDescriptor write) noexcept
    : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    const auto writable = buf.WritableBytes();
    if (writable == 0) {
        return 0;
    }

    iovec iov[1];
    iov[0].iov_base = buf.WriteBegin();
    iov[0].iov_len = writable;

    const auto bytes_written = writev(write_.fd(), iov, 1);
    if (bytes_written < 0) {
        ThrowLastSystemError();
    }
    buf.HasWritten(static_cast<std::size_t>(bytes_written));
    return static_cast<std::size_t>(bytes_written);
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    const auto readable = buf.ReadableBytes();
    if (readable == 0) {
        return 0;
    }

    iovec iov[1];
    iov[0].iov_base = buf.WriteBegin();
    iov[0].iov_len = readable;

    const auto bytes_read = readv(read_.fd(), iov, 1);
    if (bytes_read < 0) {
        ThrowLastSystemError();
    }
    buf.HasWritten(static_cast<std::size_t>(bytes_read));
    return static_cast<std::size_t>(bytes_read);
}

}  // namespace io

}  // namespace ws
