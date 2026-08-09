#include "io.h"
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
    buf.RetrieveAll();
    return readable;
}

StringStream::StringStream(std::istream& read, std::ostream& write) noexcept
    : read_(read), write_(write) {}

std::size_t StringStream::WriteTo(Buffer& buf) noexcept {
    std::string str((std::istreambuf_iterator<char>(read_)),
                      std::istreambuf_iterator<char>());
    buf.Append(str);
    return str.size();
}

std::size_t StringStream::ReadFrom(Buffer& buf) noexcept {
    auto readable = buf.ReadableBytes();
    write_.write(buf.Peek(), readable);
    buf.RetrieveAll();
    return readable;
}

FileDescriptor::FileDescriptor(ws::FileDescriptor read,
                               ws::FileDescriptor write) noexcept
    : read_(read), write_(write) {}

std::size_t FileDescriptor::WriteTo(Buffer& buf) {
    auto writable = buf.WritableBytes();
    std::array<iovec, 2> bufs;
    size_t nbufs = buf.GetWritableIov(bufs);
    ssize_t size = readv(read_.fd(), bufs.data(), nbufs);

    if (size < 0) {
        ThrowLastSystemError();
    }

    if (static_cast<size_t>(size) <= writable) {
        buf.HasWritten(size);
    } else {
        buf.HasWritten(writable);
        std::array<char, 65536> ext;
        size_t n = static_cast<size_t>(size - writable);
        while (n > 0) {
            ssize_t s = read(read_.fd(), ext.data(),
                             std::min(n, ext.size()));
            if (s < 0) {
                ThrowLastSystemError();
            }
            buf.Append({ext.cbegin(), ext.cbegin() + static_cast<size_t>(s)});
            n -= static_cast<size_t>(s);
        }
    }

    return size;
}

std::size_t FileDescriptor::ReadFrom(Buffer& buf) {
    auto readable = buf.ReadableBytes();
    ssize_t size = write(write_.fd(), buf.Peek(), readable);

    if (size < 0) {
        ThrowLastSystemError();
    }

    buf.Retrieve(size);
    return size;
}

}  // namespace io

}  // namespace ws