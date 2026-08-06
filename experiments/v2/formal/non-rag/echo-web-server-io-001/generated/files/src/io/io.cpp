#include "io.h"
#include "containers/buffer.h"
#include <sys/uio.h>
#include <unistd.h>
#include <array>

namespace ws {

std::size_t io::Null::WriteTo(Buffer& buf) noexcept {
    const auto writable = buf.WritableBytes();
    buf.HasWritten(writable);
    return writable;
}

std::size_t io::Null::ReadFrom(Buffer& buf) noexcept {
    const auto readable = buf.ReadableBytes();
    buf.RetrieveAll();
    return readable;
}

io::StringStream::StringStream(std::istream& read, std::ostream& write) noexcept
    : read_(read), write_(write) {}

std::size_t io::StringStream::WriteTo(Buffer& buf) noexcept {
    std::string data(buf.Peek(), buf.ReadableBytes());
    write_ << data;
    buf.RetrieveAll();
    return data.size();
}

std::size_t io::StringStream::ReadFrom(Buffer& buf) noexcept {
    std::string data;
    read_ >> data;
    buf.Append(data);
    return data.size();
}

io::FileDescriptor::FileDescriptor(ws::FileDescriptor read,
                                   ws::FileDescriptor write) noexcept
    : read_(read), write_(write) {}

std::size_t io::FileDescriptor::WriteTo(Buffer& buf) {
    const auto readable = buf.ReadableBytes();
    if (readable == 0) {
        return 0;
    }

    std::array<iovec, 1> iov{{buf.Peek(), readable}};
    const ssize_t n = readv(read_.Fd(), iov.data(), iov.size());
    if (n < 0) {
        ThrowLastSystemError();
    }
    buf.Retrieve(static_cast<std::size_t>(n));
    return static_cast<std::size_t>(n);
}

std::size_t io::FileDescriptor::ReadFrom(Buffer& buf) {
    const auto writable = buf.WritableBytes();
    if (writable == 0) {
        return 0;
    }

    void* data = buf.BeginWrite();
    const ssize_t n = write(write_.Fd(), data, writable);
    if (n < 0) {
        ThrowLastSystemError();
    }
    buf.HasWritten(static_cast<std::size_t>(n));
    return static_cast<std::size_t>(n);
}

}  // namespace ws