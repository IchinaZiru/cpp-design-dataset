#include "ip.h"
#include <arpa/inet.h>
#include <stdexcept>
#include <cstring>

namespace ws {

IPv4Addr::IPv4Addr(sockaddr_in addr)
    : raw_(addr) {
    char ip_str[INET_ADDRSTRLEN];
    inet_ntop(AF_INET, &raw_.sin_addr, ip_str, INET_ADDRSTRLEN);
    ip_ = ip_str;
}

IPv4Addr::IPv4Addr(std::string ip, std::uint16_t port)
    : ip_(std::move(ip)) {
    if (inet_pton(AF_INET, ip_.c_str(), &raw_.sin_addr) <= 0) {
        throw std::runtime_error("Invalid IPv4 address");
    }
    raw_.sin_family = AF_INET;
    raw_.sin_port = htons(port);
}

int IPv4Addr::Version() const noexcept {
    return version;
}

std::size_t IPv4Addr::Size() const noexcept {
    return sizeof(raw_);
}

const sockaddr* IPv4Addr::Raw() const noexcept {
    return reinterpret_cast<const sockaddr*>(&raw_);
}

std::uint16_t IPv4Addr::Port() const noexcept {
    return ntohs(raw_.sin_port);
}

std::string IPv4Addr::IPAddress() const noexcept {
    return ip_;
}

IPv6Addr::IPv6Addr(sockaddr_in6 addr)
    : raw_(addr) {
    char ip_str[INET6_ADDRSTRLEN];
    inet_ntop(AF_INET6, &raw_.sin6_addr, ip_str, INET6_ADDRSTRLEN);
    ip_ = ip_str;
}

IPv6Addr::IPv6Addr(std::string ip, std::uint16_t port)
    : ip_(std::move(ip)) {
    if (inet_pton(AF_INET6, ip_.c_str(), &raw_.sin6_addr) <= 0) {
        throw std::runtime_error("Invalid IPv6 address");
    }
    raw_.sin6_family = AF_INET6;
    raw_.sin6_port = htons(port);
}

int IPv6Addr::Version() const noexcept {
    return version;
}

std::size_t IPv6Addr::Size() const noexcept {
    return sizeof(raw_);
}

const sockaddr* IPv6Addr::Raw() const noexcept {
    return reinterpret_cast<const sockaddr*>(&raw_);
}

std::uint16_t IPv6Addr::Port() const noexcept {
    return ntohs(raw_.sin6_port);
}

std::string IPv6Addr::IPAddress() const noexcept {
    return ip_;
}

}  // namespace ws