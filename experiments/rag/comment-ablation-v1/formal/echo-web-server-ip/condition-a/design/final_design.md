### Design Specification for Reimplementation of IP Address Handling

#### Overview
This document provides a detailed design specification for reimplementing the IP address handling functionality as defined in the provided C++ source code. The goal is to ensure that the new implementation adheres strictly to the original structure, interfaces, and behavior while preserving all target-owned identifiers (Fxx/Uxx).

#### Target Files
- **include/ip.h**: Header file containing declarations for `IPAddr`, `IPv4Addr`, and `IPv6Addr` classes.
- **src/ip/ip.cpp**: Source file containing implementations of the constructors and methods defined in `ip.h`.

#### Key Components

##### 1. IP Address Base Class (`IPAddr`)
- **Namespace**: `ws`
- **Role**: Abstract base class for IP addresses.
- **Methods**:
  - `virtual ~IPAddr() noexcept = default;`: Virtual destructor.
  - `virtual int Version() const noexcept = 0;`: Returns the version of the IP address (IPv4 or IPv6).
  - `virtual std::size_t Size() const noexcept = 0;`: Returns the size of the raw socket address structure.
  - `virtual const sockaddr* Raw() const noexcept = 0;`: Returns a pointer to the raw socket address structure.
  - `virtual std::uint16_t Port() const noexcept = 0;`: Returns the port number associated with the IP address.
  - `virtual std::string IPAddress() const noexcept = 0;`: Returns the string representation of the IP address.

##### 2. IPv4 Address Class (`IPv4Addr`)
- **Namespace**: `ws`
- **Role**: Concrete class representing an IPv4 address.
- **Constants**:
  - `static constexpr int version {AF_INET};`: Version constant for IPv4.
  - `static constexpr std::string_view loop_back {"127.0.0.1"};`: Loopback address for IPv4.
  - `static constexpr std::string_view any {"0.0.0.0"};`: Any address for IPv4.
  - `static constexpr std::size_t max_length {15};`: Maximum length of an IPv4 address string.
- **Type Alias**:
  - `using RawType = sockaddr_in;`: Type alias for the raw socket address structure.
- **Constructors**:
  - `explicit IPv4Addr(sockaddr_in addr);`: Constructor from a `sockaddr_in` structure.
  - `explicit IPv4Addr(std::string ip, std::uint16_t port);`: Constructor from an IP string and port number.
- **Methods**:
  - `int Version() const noexcept override;`: Returns the version of the IP address (IPv4).
  - `std::size_t Size() const noexcept override;`: Returns the size of the raw socket address structure (`sockaddr_in`).
  - `const sockaddr* Raw() const noexcept override;`: Returns a pointer to the raw socket address structure.
  - `std::uint16_t Port() const noexcept override;`: Returns the port number associated with the IP address.
  - `std::string IPAddress() const noexcept override;`: Returns the string representation of the IPv4 address.

##### 3. IPv6 Address Class (`IPv6Addr`)
- **Namespace**: `ws`
- **Role**: Concrete class representing an IPv6 address.
- **Constants**:
  - `static constexpr int version {AF_INET6};`: Version constant for IPv6.
  - `static constexpr std::string_view loop_back {"::1"};`: Loopback address for IPv6.
  - `static constexpr std::string_view any {"::"};`: Any address for IPv6.
  - `static constexpr std::size_t max_length {45};`: Maximum length of an IPv6 address string.
- **Type Alias**:
  - `using RawType = sockaddr_in6;`: Type alias for the raw socket address structure.
- **Constructors**:
  - `explicit IPv6Addr(sockaddr_in6 addr);`: Constructor from a `sockaddr_in6` structure.
  - `explicit IPv6Addr(std::string ip, std::uint16_t port);`: Constructor from an IP string and port number.
- **Methods**:
  - `int Version() const noexcept override;`: Returns the version of the IP address (IPv6).
  - `std::size_t Size() const noexcept override;`: Returns the size of the raw socket address structure (`sockaddr_in6`).
  - `const sockaddr* Raw() const noexcept override;`: Returns a pointer to the raw socket address structure.
  - `std::uint16_t Port() const noexcept override;`: Returns the port number associated with the IP address.
  - `std::string IPAddress() const noexcept override;`: Returns the string representation of the IPv6 address.

##### 4. Concept (`ValidIPAddr`)
- **Namespace**: `ws`
- **Role**: Template concept to check if a type is either `IPv4Addr` or `IPv6Addr`.
- **Definition**:
  - `template <typename T> concept ValidIPAddr = std::same_as<T, IPv4Addr> || std::same_as<T, IPv6Addr>;`

#### Implementation Details

##### File: include/ip.h
- **Includes**: `<concepts>`, `<cstdint>`, `<string>`, `<string_view>`, `<netinet/in.h>`
- **Namespace**: `ws`
- **Classes**:
  - `IPAddr`: Abstract base class with pure virtual methods.
  - `IPv4Addr`: Inherits from `IPAddr` and implements all virtual methods.
  - `IPv6Addr`: Inherits from `IPAddr` and implements all virtual methods.
- **Concept**:
  - `ValidIPAddr`: Template concept to check if a type is either `IPv4Addr` or `IPv6Addr`.

##### File: src/ip/ip.cpp
- **Includes**: `"ip.h"`, `"util.h"`, `<arpa/inet.h>`, `<array>`
- **Namespace**: `ws`
- **Implementations**:
  - Constructors and methods for `IPv4Addr`.
  - Constructors and methods for `IPv6Addr`.

#### Error Handling
- The constructors of both `IPv4Addr` and `IPv6Addr` use `inet_ntop` and `inet_pton` to convert between string and binary representations of IP addresses.
- If these functions fail, they call `ThrowLastSystemError()` to handle the error.

#### Conclusion
This design specification provides a comprehensive guide for reimplementing the IP address handling functionality while preserving all target-owned identifiers and maintaining the original structure and behavior. The new implementation should adhere strictly to this specification to ensure compatibility and correctness.