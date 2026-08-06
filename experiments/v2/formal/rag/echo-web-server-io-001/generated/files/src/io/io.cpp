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

StringStream::StringStream(std::istream& read, std::ostream& write) noexcept
    : read_(read), write_(write) {}

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
    const auto readable = buf.ReadableBytes();
    if (readable > 0) {
        write_ << std::string(buf.Peek(), readable);
        buf.Retrieve(readable);
        return readable;
    }
    return 0;
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read,
                               ws::FileDescriptor write) noexcept
    : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    const auto writable = buf.WritableBytes();
    if (writable == 0) return 0;

    std::array<iovec, 1> iov{{iov_base(buf.WriteBegin()), iov_len(writable)}};
    const ssize_t n = readv(read_.Fd(), iov.data(), iov.size());
    if (n < 0) {
        throw std::system_error(errno, std::generic_category(), "readv failed");
    }

    buf.HasWritten(static_cast<std::size_t>(n));
    return static_cast<std::size_t>(n);
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    const auto readable = buf.ReadableBytes();
    if (readable == 0) return 0;

    const ssize_t n = write(write_.Fd(), buf.Peek(), readable);
    if (n < 0) {
        throw std::system_error(errno, std::generic_category(), "write failed");
    }

    buf.Retrieve(static_cast<std::size_t>(n));
    return static_cast<std::size_t>(n);
}

}  // namespace io

}  // namespace ws