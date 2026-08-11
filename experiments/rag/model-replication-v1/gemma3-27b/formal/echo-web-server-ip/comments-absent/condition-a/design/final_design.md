## Design Specification for IP Address Classes (Fxx/Uxx)

This document details the design specification for a set of classes representing IPv4 and IPv6 addresses. It is intended to guide the re-implementation of the provided C++ code by another LLM, focusing on functionality and structure as defined in the source files F01/U01 (ip.h) and F02/U02 (ip.cpp).

**1. Overview**

The system provides classes for representing IP addresses, specifically IPv4 and IPv6. These classes encapsulate the address information and provide methods to access it in various formats.  The core functionality revolves around converting between string representations of IP addresses and their raw `sockaddr` equivalents. Error handling is delegated to a function named `ThrowLastSystemError()`, which is assumed to be defined elsewhere (not provided in input).

**2. Namespaces**

All classes are contained within the namespace `ws`.

**3. Classes & Interfaces**

### 3.1. IPAddr (Abstract Base Class)

*   **Role:** Defines a common interface for IPv4 and IPv6 address objects.
*   **Members:**
    *   `virtual ~IPAddr() noexcept = default;`: Virtual destructor to ensure proper cleanup of derived classes.
    *   `virtual int Version() const noexcept = 0;`:  Returns the IP version (e.g., `AF_INET` for IPv4, `AF_INET6` for IPv6).
    *   `virtual std::size_t Size() const noexcept = 0;`: Returns the size of the raw address structure (`sockaddr_in` or `sockaddr_in6`).
    *   `virtual const sockaddr* Raw() const noexcept = 0;`:  Returns a pointer to the underlying raw `sockaddr` structure. The returned pointer is `const`.
    *   `virtual std::uint16_t Port() const noexcept = 0;`: Returns the port number associated with the address.
    *   `virtual std::string IPAddress() const noexcept = 0;`:  Returns the IP address as a string.

### 3.2. IPv4Addr (Concrete Class)

*   **Role:** Represents an IPv4 address. Inherits from `IPAddr`.
*   **Constants:**
    *   `static constexpr int version {AF_INET};`: Defines the IPv4 protocol family constant.
    *   `static constexpr std::string_view loop_back {"127.0.0.1"};`:  Loopback address string.
    *   `static constexpr std::string_view any {"0.0.0.0"};`: Any address string.
    *   `static constexpr std::size_t max_length {15};`: Maximum length of the IPv4 address string (excluding null terminator).
*   **Internal Data:**
    *   `std::string ip_;`: Stores the IP address as a string.
    *   `sockaddr_in raw_ {};`:  Stores the raw IPv4 address structure. Initialized to zero.
*   **Constructors:**
    *   `explicit IPv4Addr(sockaddr_in addr);`: Constructs an `IPv4Addr` from a `sockaddr_in` structure. Converts the binary address in `addr` to a string and stores it in `ip_`.  Uses `inet_ntop` for conversion, throwing an exception via `ThrowLastSystemError()` if the conversion fails.
    *   `explicit IPv4Addr(std::string ip, std::uint16_t port);`: Constructs an `IPv4Addr` from a string representation of the IP address and a port number. Converts the string to a binary address using `inet_pton`, storing it in `raw_`. Throws an exception via `ThrowLastSystemError()` if conversion fails.
*   **Overridden Methods:**
    *   `int Version() const noexcept override;`: Returns `version` (which is `AF_INET`).
    *   `std::size_t Size() const noexcept override;`: Returns `sizeof(raw_)`.
    *   `const sockaddr* Raw() const noexcept override;`:  Returns a pointer to the underlying `raw_` structure, cast to `const sockaddr*`.
    *   `std::uint16_t Port() const noexcept override;`: Returns the port number from `raw_.sin_port`, converted from network byte order using `ntohs`.
    *   `std::string IPAddress() const noexcept override;`:  Returns the value of `ip_`.

### 3.3. IPv6Addr (Concrete Class)

*   **Role:** Represents an IPv6 address. Inherits from `IPAddr`.
*   **Constants:**
    *   `static constexpr int version {AF_INET6};`: Defines the IPv6 protocol family constant.
    *   `static constexpr std::string_view loop_back {"::1"};`: Loopback address string.
    *   `static constexpr std::string_view any {"::"};`: Any address string.
    *   `static constexpr std::size_t max_length {45};`: Maximum length of the IPv6 address string (excluding null terminator).
*   **Internal Data:**
    *   `std::string ip_;`: Stores the IP address as a string.
    *   `sockaddr_in6 raw_ {};`:  Stores the raw IPv6 address structure. Initialized to zero.
*   **Constructors:**
    *   `explicit IPv6Addr(sockaddr_in6 addr);`: Constructs an `IPv6Addr` from a `sockaddr_in6` structure, converting it to a string using `inet_ntop`. Throws exception on failure.
    *   `explicit IPv6Addr(std::string ip, std::uint16_t port);`: Constructs an `IPv6Addr` from a string representation of the IP address and a port number, converting it to binary using `inet_pton`.  Throws exception on failure.
*   **Overridden Methods:**
    *   `int Version() const noexcept override;`: Returns `version` (which is `AF_INET6`).
    *   `std::size_t Size() const noexcept override;`: Returns `sizeof(raw_)`.
    *   `const sockaddr* Raw() const noexcept override;`:  Returns a pointer to the underlying `raw_` structure, cast to `const sockaddr*`.
    *   `std::uint16_t Port() const noexcept override;`: Returns the port number from `raw_.sin6_port`, converted from network byte order using `ntohs`.
    *   `std::string IPAddress() const noexcept override;`:  Returns the value of `ip_`.

### 3.4. ValidIPAddr (Concept)

*   **Role:** Defines a concept to check if a type is either `IPv4Addr` or `IPv6Addr`.
*   **Definition:** `std::same_as<T, IPv4Addr> || std::same_as<T, IPv6Addr>`

**4. Dependencies**

*   `<concepts>`: For defining the `ValidIPAddr` concept.
*   `<cstdint>`: For fixed-width integer types like `std::uint16_t`.
*   `<string>`: For string manipulation.
*   `<string_view>`:  For efficient string views.
*   `<netinet/in.h>`: Defines the `sockaddr`, `sockaddr_in`, and `sockaddr_in6` structures, as well as constants like `AF_INET` and `AF_INET6`.
*   `<arpa/inet.h>`: Provides functions for converting between IP addresses in string and binary formats (`inet_ntop`, `inet_pton`, `htons`, `ntohs`).
*   `util.h`: Contains the declaration of `ThrowLastSystemError()`. This is a reference-only dependency; its implementation is not part of this specification.

**5. Error Handling**

The constructors for both `IPv4Addr` and `IPv6Addr` rely on `inet_pton` and `inet_ntop` for address conversion.  If these functions fail, the `ThrowLastSystemError()` function (defined elsewhere) is called to handle the error. The specification does not define how this error handling works; it only specifies that it *is* used.

**6. Network Byte Order**

The port numbers are stored in network byte order within the `sockaddr` structures.  The `Port()` methods use `ntohs` (network to host short) to convert the port number to host byte order before returning it.
