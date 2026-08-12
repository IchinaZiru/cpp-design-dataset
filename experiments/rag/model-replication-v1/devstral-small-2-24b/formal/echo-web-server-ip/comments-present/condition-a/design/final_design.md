# IP Address Interface Design Specification

## Overview
This document specifies the design of an IP address interface for handling both IPv4 and IPv6 addresses in a network application. The implementation provides a common base class (`IPAddr`) with two derived classes (`IPv4Addr` and `IPv6Addr`) that implement specific functionality for each address family.

## Class Hierarchy

### Base Class: `ws::IPAddr`
An abstract interface class defining the common operations for IP addresses.

#### Public Interface
- **Virtual Destructor**: `~IPAddr() noexcept = default`
  - Ensures proper cleanup of derived classes
- **Version()**: `virtual int Version() const noexcept = 0`
  - Returns the IP version (AF_INET or AF_INET6)
- **Size()**: `virtual std::size_t Size() const noexcept = 0`
  - Returns the size of the socket address structure
- **Raw()**: `virtual const sockaddr* Raw() const noexcept = 0`
  - Returns a pointer to the raw socket address structure
- **Port()**: `virtual std::uint16_t Port() const noexcept = 0`
  - Returns the port number in host byte order
- **IPAddress()**: `virtual std::string IPAddress() const noexcept = 0`
  - Returns the IP address as a string

### Derived Class: `ws::IPv4Addr`
Implements IPv4-specific functionality.

#### Constants
- `version`: AF_INET (4)
- `loop_back`: "127.0.0.1"
- `any`: "0.0.0.0"
- `max_length`: 15

#### Public Interface
- **Constructors**:
  - From `sockaddr_in`: Converts existing socket address to IPv4Addr
  - From string and port: Creates new IPv4 address from components
- Inherited virtual methods (implemented):
  - Version()
  - Size()
  - Raw()
  - Port()
  - IPAddress()

#### Private Members
- `ip_`: Stores the IP address as a string
- `raw_`: Stores the raw socket address structure

### Derived Class: `ws::IPv6Addr`
Implements IPv6-specific functionality.

#### Constants
- `version`: AF_INET6 (10)
- `loop_back`: "::1"
- `any`: "::"
- `max_length`: 45

#### Public Interface
- **Constructors**:
  - From `sockaddr_in6`: Converts existing socket address to IPv6Addr
  - From string and port: Creates new IPv6 address from components
- Inherited virtual methods (implemented):
  - Version()
  - Size()
  - Raw()
  - Port()
  - IPAddress()

#### Private Members
- `ip_`: Stores the IP address as a string
- `raw_`: Stores the raw socket address structure

## Concepts
- **ValidIPAddr**: A concept that checks if a type is either IPv4Addr or IPv6Addr
  - Used for template constraints where IP address types are required

## Implementation Details

### Construction from sockaddr_in/sockaddr_in6
1. Store the raw address in the member variable
2. Convert the binary address to string representation using `inet_ntop()`
3. Throw an exception if conversion fails (using `ThrowLastSystemError()`)

### Construction from IP string and port
1. Store the IP string in the member variable
2. Set up the raw socket address structure:
   - Family: AF_INET or AF_INET6
   - Port: Convert to network byte order using `htons()`
3. Validate the IP string using `inet_pton()`
4. Throw an exception if validation fails

### Port Handling
- All port numbers are stored in network byte order in the raw structure
- The `Port()` method converts from network to host byte order before returning

## Error Handling
- Uses `ThrowLastSystemError()` for system call failures
- No exceptions thrown from const methods (marked noexcept)

## Dependencies
- `<concepts>`: For type constraints
- `<cstdint>`: For fixed-width integer types
- `<string>` and `<string_view>`: For string handling
- `<netinet/in.h>`: For socket address structures
- `<arpa/inet.h>`: For IP address conversion functions

## Usage Example
```cpp
ws::IPv4Addr addr1("192.168.1.1", 8080);
std::cout << "Version: " << addr1.Version() << std::endl;
std::cout << "Address: " << addr1.IPAddress() << std::endl;
std::cout << "Port: " << addr1.Port() << std::endl;

ws::IPv6Addr addr2("::1", 443);
std::cout << "Version: " << addr2.Version() << std::endl;
```

## Design Considerations
1. **Immutability**: Once created, IP addresses cannot be modified (no setters)
2. **String Storage**: IP strings are stored for easy access and comparison
3. **Raw Access**: Provides direct access to socket structures for system calls
4. **Portability**: Uses standard POSIX functions for IP address manipulation

This specification provides all necessary information for a complete reimplementation of the IP address interface while preserving all target-owned identifiers and structure.