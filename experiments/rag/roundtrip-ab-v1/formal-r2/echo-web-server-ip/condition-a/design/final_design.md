# Design Specification for IP Address Interface Implementation

## Overview

This document provides a detailed design specification for the implementation of an IP address interface in C++. The primary focus is on the `IPAddr` class and its derived classes, `IPv4Addr` and `IPv6Addr`. This specification includes the necessary interfaces, data structures, and methods required to handle IPv4 and IPv6 addresses.

## Target-Owned Inputs

### Identifiers
- **Fxx/Uxx identifiers**: These are opaque and must be preserved in the final implementation.
  - **F01/U01**: `include/ip.h`
  - **F02/U02**: `src/ip/ip.cpp`

## Replacement Units

### F01/U01: IP Address Interface Declaration (`ip.h`)

#### File Path
- `include/ip.h`

#### Role
- Complete target-owned implementation/declaration file.

#### Namespace
- `ws`

#### Classes and Interfaces

##### Class: `IPAddr`
- **Role**: The interface of an IP address.
- **Methods**:
  - `virtual ~IPAddr() noexcept = default;`: Virtual destructor.
  - `virtual int Version() const noexcept = 0;`: Get the IP version.
  - `virtual std::size_t Size() const noexcept = 0;`: Get the size of socket address.
  - `virtual const sockaddr* Raw() const noexcept = 0;`: Get the socket address.
  - `virtual std::uint16_t Port() const noexcept = 0;`: Get the port number.
  - `virtual std::string IPAddress() const noexcept = 0;`: Get the IP address as a string.

##### Class: `IPv4Addr`
- **Role**: Represents an IPv4 address.
- **Inheritance**: Inherits from `IPAddr`.
- **Constants**:
  - `static constexpr int version {AF_INET};`: Version of the IP address (IPv4).
  - `static constexpr std::string_view loop_back {"127.0.0.1"};`: Loopback address.
  - `static constexpr std::string_view any {"0.0.0.0"};`: Any address.
  - `static constexpr std::size_t max_length {15};`: Maximum length of an IPv4 address string.
- **Type Alias**:
  - `using RawType = sockaddr_in;`: Type alias for the raw socket address structure.
- **Constructors**:
  - `explicit IPv4Addr(sockaddr_in addr);`: Constructor from a `sockaddr_in` structure.
  - `explicit IPv4Addr(std::string ip, std::uint16_t port);`: Constructor from an IP string and port number.
- **Methods** (overrides):
  - `int Version() const noexcept override;`
  - `std::size_t Size() const noexcept override;`
  - `const sockaddr* Raw() const noexcept override;`
  - `std::uint16_t Port() const noexcept override;`
  - `std::string IPAddress() const noexcept override;`

##### Class: `IPv6Addr`
- **Role**: Represents an IPv6 address.
- **Inheritance**: Inherits from `IPAddr`.
- **Constants**:
  - `static constexpr int version {AF_INET6};`: Version of the IP address (IPv6).
  - `static constexpr std::string_view loop_back {"::1"};`: Loopback address.
  - `static constexpr std::string_view any {"::"};`: Any address.
  - `static constexpr std::size_t max_length {45};`: Maximum length of an IPv6 address string.
- **Type Alias**:
  - `using RawType = sockaddr_in6;`: Type alias for the raw socket address structure.
- **Constructors**:
  - `explicit IPv6Addr(sockaddr_in6 addr);`: Constructor from a `sockaddr_in6` structure.
  - `explicit IPv6Addr(std::string ip, std::uint16_t port);`: Constructor from an IP string and port number.
- **Methods** (overrides):
  - `int Version() const noexcept override;`
  - `std::size_t Size() const noexcept override;`
  - `const sockaddr* Raw() const noexcept override;`
  - `std::uint16_t Port() const noexcept override;`
  - `std::string IPAddress() const noexcept override;`

##### Concept: `ValidIPAddr`
- **Role**: A concept to check if a type is either `IPv4Addr` or `IPv6Addr`.
- **Definition**:
  ```cpp
  template <typename T>
  concept ValidIPAddr = std::same_as<T, IPv4Addr> || std::same_as<T, IPv6Addr>;
  ```

### F02/U02: IP Address Interface Implementation (`ip.cpp`)

#### File Path
- `src/ip/ip.cpp`

#### Role
- Complete target-owned implementation/declaration file.

#### Dependencies
- Includes `ip.h`
- Includes `util.h`
- Includes `<arpa/inet.h>`
- Includes `<array>`

#### Namespace
- `ws`

#### Class Implementations

##### Class: `IPv4Addr`
- **Constructors**:
  - `IPv4Addr(sockaddr_in addr);`: Initializes the object from a `sockaddr_in` structure.
    - Uses `inet_ntop` to convert the IP address to a string.
    - Throws an error if conversion fails using `ThrowLastSystemError`.
  - `IPv4Addr(std::string ip, std::uint16_t port);`: Initializes the object from an IP string and port number.
    - Sets the family and port in the `sockaddr_in` structure.
    - Uses `inet_pton` to convert the IP address from a string.
    - Throws an error if conversion fails using `ThrowLastSystemError`.
- **Methods**:
  - `int Version() const noexcept;`: Returns the version of the IP address (IPv4).
  - `std::size_t Size() const noexcept;`: Returns the size of the `sockaddr_in` structure.
  - `const sockaddr* Raw() const noexcept;`: Returns a pointer to the raw socket address.
  - `std::uint16_t Port() const noexcept;`: Returns the port number in host byte order.
  - `std::string IPAddress() const noexcept;`: Returns the IP address as a string.

##### Class: `IPv6Addr`
- **Constructors**:
  - `IPv6Addr(sockaddr_in6 addr);`: Initializes the object from a `sockaddr_in6` structure.
    - Uses `inet_ntop` to convert the IP address to a string.
    - Throws an error if conversion fails using `ThrowLastSystemError`.
  - `IPv6Addr(std::string ip, std::uint16_t port);`: Initializes the object from an IP string and port number.
    - Sets the family and port in the `sockaddr_in6` structure.
    - Uses `inet_pton` to convert the IP address from a string.
    - Throws an error if conversion fails using `ThrowLastSystemError`.
- **Methods**:
  - `int Version() const noexcept;`: Returns the version of the IP address (IPv6).
  - `std::size_t Size() const noexcept;`: Returns the size of the `sockaddr_in6` structure.
  - `const sockaddr* Raw() const noexcept;`: Returns a pointer to the raw socket address.
  - `std::uint16_t Port() const noexcept;`: Returns the port number in host byte order.
  - `std::string IPAddress() const noexcept;`: Returns the IP address as a string.

## Conclusion

This design specification provides a comprehensive guide for implementing and maintaining an IP address interface in C++. It ensures that the implementation adheres to the specified interfaces and handles both IPv4 and IPv6 addresses effectively. The use of concepts like `ValidIPAddr` helps enforce type safety and consistency across the codebase.