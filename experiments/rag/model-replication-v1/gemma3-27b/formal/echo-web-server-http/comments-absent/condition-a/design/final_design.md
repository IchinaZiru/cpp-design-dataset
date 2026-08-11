## Design Specification for HTTP Server Components

This document details the design of several components of an HTTP server, based on the provided C++ source code. It aims to be comprehensive enough for another LLM to reimplement these components without access to the original code.  The specification adheres to the constraints outlined in the prompt: preserving names, types, signatures, namespaces and replacement boundaries.

**1. Overview**

The system consists of classes and functions related to handling HTTP requests and responses. Key functionalities include parsing requests, building responses (including serving files and generating error pages), and managing connections.  The code utilizes a buffer-based I/O approach for efficient data transfer.

**2. Namespaces**

All components reside within the `ws::http` namespace.

**3. Replacement Units & Their Responsibilities**

*   **F01/U01: `include/http.h`**:  Defines core HTTP types, enums, and function declarations. This is the primary header file for the module.
*   **F02/U02: `src/http/http.cpp`**: Implements helper functions and utility methods related to HTTP processing (content type detection, status code conversion, URL decoding etc.).  Also contains implementations of connection management logic.
*   **F03/U03: `src/http/request.h`**: Defines the `Request` class for parsing incoming HTTP requests.
*   **F04/U04: `src/http/request.cpp`**: Implements the `Request` class, including its state machine-based parser.
*   **F05/U05: `src/http/response.h`**: Defines the `Response` class for building outgoing HTTP responses.
*   **F06/U06: `src/http/response.cpp`**: Implements the `Response` class, including methods for constructing different types of responses (file serving, error pages).

**4. Data Types & Structures**

*   **`StatusCode` (enum class):** Represents HTTP status codes (e.g., OK, BadRequest, NotFound).  Underlying type is `std::uint32_t`.
*   **`Method` (enum class):** Represents HTTP methods (GET, POST, PUT, DELETE, PATCH).
*   **`Parameters` (typedef):** A `std::unordered_map<std::string, std::string>` used to store request parameters and response placeholders.
*   **`FileDescriptor`:** An integer representing a file descriptor (used for socket communication).  Defined in `ip.h` (not provided but assumed).
*   **`IOBuffer`:** A custom buffer class (defined in `containers/buffer.h`, not provided) used for reading and writing data to the socket.
*   **`MappedReadOnlyFile`:** A class representing a memory-mapped file (presumably for efficient serving of static content).  Details are not fully available, but it provides access to file data via `Data()` and size via `Size()`.

**5. Key Classes & Interfaces**

**5.1. `ConnectionImpl` (Abstract Base Class)**

*   **Purpose:** Manages a single HTTP connection.
*   **Members:**
    *   `socket_`:  The file descriptor for the socket.
    *   `keep_alive_`: A boolean indicating whether the connection should be kept alive.
    *   `read_buf_`: An `IOBuffer` used for reading data from the socket.
    *   `write_buf_`: An `IOBuffer` used for writing data to the socket.
    *   `file_`: A `MappedReadOnlyFile` representing the file being served (if any).
    *   `root_dir_`: Static member storing the root directory for serving files.
*   **Methods:**
    *   `Close()`: Closes the socket connection.
    *   `Valid()`: Checks if the socket is still valid.
    *   `Socket()`: Returns the file descriptor.
    *   `Receive()`: Reads data from the socket into `read_buf_`.
    *   `Send()`: Writes data from `write_buf_` and `file_` to the socket.
    *   `KeepAlive()`: Returns whether keep-alive is enabled.
    *   `Process()`: Parses the request, builds the response, and sends it.

**5.2. `Connection<IPAddr>` (Template Class)**

*   **Purpose:**  A concrete implementation of `ConnectionImpl`, parameterized by an IP address type (`IPAddr`).
*   **Members:**
    *   `addr_`: An instance of the `IPAddr` class, storing the client's IP address and port.
*   **Methods:**
    *   `IPAddress()`: Returns the client's IP address as a string.
    *   `Port()`: Returns the client's port number.

**5.3. `Request`**

*   **Purpose:** Parses incoming HTTP requests.  Uses a state machine pattern for parsing.
*   **Members:**
    *   `state_`: A pointer to a `State` object, representing the current parsing state.
    *   `method_`: The HTTP method (GET, POST, etc.).
    *   `version_`: The HTTP version string.
    *   `path_`: The requested path.
    *   `headers_`: A `Parameters` map storing request headers.
    *   `post_`: A `Parameters` map storing POST parameters.
*   **Methods:**
    *   `Parse(Buffer& buf)`: Parses the request from a buffer.
    *   `Header(std::string_view key)`: Returns the value of a header, or `nullopt` if not found.
    *   `Post(std::string_view key)`: Returns the value of a POST parameter, or `nullopt` if not found.
    *   `Method()`: Returns the HTTP method.
    *   `Path()`: Returns the requested path.
    *   `Version()`: Returns the HTTP version.

**5.4. `Response`**

*   **Purpose:** Builds outgoing HTTP responses.
*   **Members:**
    *   `root_dir_`: The root directory for serving files.
    *   `file_path_`: The path to the file being served (if any).
    *   `file_`: A `MappedReadOnlyFile` representing the file being served.
    *   `keep_alive_`: Whether keep-alive is enabled.
    *   `status_code_`: The HTTP status code.
*   **Methods:**
    *   `Build(Buffer& buf, std::filesystem::path file, StatusCode& code)`: Serves a static file and sets the status code.
    *   `Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code)`: Builds a response from an HTML template, replacing placeholders with parameters.
    *   `Build(Buffer& buf, StatusCode code, std::string msg)`: Builds an error response.

**6. Global Functions & Constants**

*   `version`: A `constexpr std::string_view` holding the HTTP version ("1.1").
*   `new_line`: A `constexpr std::string_view` representing the CRLF sequence ("\r\n").
*   `ContentTypeByFileName(std::string_view name)`: Returns the Content-Type header based on the file extension.
*   `StatusCodeToMessage(StatusCode code)`: Returns a human-readable message for a given status code.
*   `StatusCodeToInteger(StatusCode code)`: Converts a `StatusCode` to its integer representation.
*   `MethodToString(Method method)`: Returns a string representation of an HTTP method.
*   `StringToMethod(std::string str)`: Parses a string into an HTTP method.
*   `DecodeURLEncodedCharacter(const std::string& str)`: Decodes a URL-encoded character.
*   `DecodeURLEncodedString(const std::string& str)`: Decodes a URL-encoded string.
*   `HTMLPlaceholder(std::string_view key)`: Returns a placeholder string for HTML templates (e.g., "<$key>").
*   `PutParamIntoHTML(std::string html, const Parameters& params)`: Replaces placeholders in an HTML string with parameter values.

**7. Error Handling**

The code uses exceptions (`std::invalid_argument`, `std::system_error`) to signal errors during parsing and file operations.  Error responses are generated by the `Response` class.

**8. Concurrency Considerations**

This specification does not explicitly address concurrency. However, the use of `shared_ptr` suggests that multiple threads might access `ConnectionImpl` objects concurrently. Appropriate synchronization mechanisms (e.g., mutexes) may be required in a multi-threaded environment.
