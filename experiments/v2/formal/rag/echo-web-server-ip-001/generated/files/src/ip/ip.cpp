#include "ip.h"
#include <arpa/inet.h>
#include <stdexcept>
#include <system_error>

namespace {

void ThrowLastSystemError() {
    throw std::system_error(std::error_code(errno, std::generic_category()));
}

}  // namespace

namespace ws {

IPv4Addr::IPv4Addr(sockaddr_in addr) : raw_(addr), ip_(inet_ntoa(raw_.sin_addr)) {}

IPv4Addr::IPv4Addr(std::string ip, std::uint16_t port)
    : ip_(std::move(ip)), raw_({}) {
    if (inet_pton(AF_INET, ip_.data(), &raw_.sin_addr) != 1) {
        ThrowLastSystemError();
    }
    raw_.sin_family = AF_INET;
    raw_.sin_port = htons(port);
}

int IPv4Addr::Version() const noexcept { return version; }

std::size_t IPv4Addr::Size() const noexcept { return sizeof(raw_); }

const sockaddr* IPv4Addr::Raw() const noexcept {
    return reinterpret_cast<const sockaddr*>(&raw_);
}

std::uint16_t IPv4Addr::Port() const noexcept { return ntohs(raw_.sin_port); }

std::string IPv4Addr::IPAddress() const noexcept { return ip_; }

IPv6Addr::IPv6Addr(sockaddr_in6 addr) : raw_(addr), ip_([&]() {
    char buffer[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, &raw_.sin6_addr, buffer, INET6_ADDRSTRLEN);
    return std::string(buffer);
}()) {}

IPv6Addr::IPv6Addr(std::string ip, std::uint16_t port)
    : ip_(std::move(ip)), raw_({}) {
    if (inet_pton(AF_INET6, ip_.data(), &raw_.sin6_addr) != 1) {
        ThrowLastSystemError();
    }
    raw_.sin6_family = AF_INET6;
    raw_.sin6_port = htons(port);
}

int IPv6Addr::Version() const noexcept { return version; }

std::size_t IPv6Addr::Size() const noexcept { return sizeof(raw_); }

const sockaddr* IPv6Addr::Raw() const noexcept {
    return reinterpret_cast<const sockaddr*>(&raw_);
}

std::uint16_t IPv6Addr::Port() const noexcept { return ntohs(raw_.sin6_port); }

std::string IPv6Addr::IPAddress() const noexcept { return ip_; }

}  // namespace ws