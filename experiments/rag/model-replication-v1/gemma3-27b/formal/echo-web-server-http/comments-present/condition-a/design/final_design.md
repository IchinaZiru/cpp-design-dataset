## Design Specification for HTTP Components

This document details the design of several C++ components related to handling HTTP connections, requests, and responses. It is intended as a guide for re-implementation based on the provided source code (`F01/U01` through `F06/U06`).  The specification focuses solely on what can be derived from the given files; no external assumptions are made.

**Overall Architecture:**

The system revolves around handling HTTP connections, parsing requests, and building responses. The core components include:

*   **HTTP Definitions (`http.h`):** Defines fundamental types like `StatusCode`, `Method`, `Parameters`, and constants such as the HTTP version string.
*   **Request Parser (`request.h`, `request.cpp`):** Parses incoming HTTP requests from a buffer, extracting method, path, headers, and POST parameters.  Uses a state machine approach for parsing.
*   **Response Builder (`response.h`, `response.cpp`):** Constructs HTTP responses based on the request, potentially serving files or generating dynamic content (HTML with parameter substitution).
*   **Connection Implementation (`http.h`, `http.cpp`):**  Handles the low-level socket interaction, receiving requests and sending responses. Uses a shared pointer for managing connection lifetime.

**1. `F01/U01: include/http.h` - HTTP Definitions & Connection Interface**

*   **Namespace:** `ws::http`
*   **Constants:**
    *   `version`:  A string literal `"1.1"` representing the supported HTTP version.
*   **Types:**
    *   `Parameters`: A `std::unordered_map<std::string, std::string>` used to store key-value pairs for headers and POST data.
    *   `StatusCode`: An enum class (`std::uint32_t`) representing HTTP status codes (OK, BadRequest, Forbidden, NotFound).
*   **Functions:**
    *   `StatusCodeToMessage(StatusCode code)`: Converts a `StatusCode` to its string representation.  Noexcept.
    *   `StatusCodeToInteger(StatusCode code)`: Converts a `StatusCode` to its integer value. Noexcept.
    *   `operator<<(std::ostream& os, StatusCode code)`: Overloads the output stream operator for `StatusCode`. Noexcept.
    *   `Method`: An enum class representing HTTP methods (Get, Post, Put, Patch, Delete).
    *   `MethodToString(Method method)`: Converts a `Method` to its string representation. Noexcept.
    *   `StringToMethod(std::string str)`: Converts a string to a `Method`. Throws `std::invalid_argument` if the string is not a valid method.
    *   `operator<<(std::ostream& os, Method method)`: Overloads the output stream operator for `Method`. Noexcept.
    *   `new_line`: A string literal `"\r\n"` representing the HTTP line separator.
    *   `ContentTypeByFileName(std::string_view name)`: Returns a content type string based on the file extension. Uses a hardcoded map of extensions to content types; defaults to "application/octet-stream". Noexcept.
    *   `DecodeURLEncodedCharacter(const std::string& str)`: Decodes a URL-encoded character (e.g., "%20" becomes a space). Throws `std::invalid_argument` for invalid input.
    *   `DecodeURLEncodedString(const std::string& str)`: Decodes a URL-encoded string. Throws `std::invalid_argument` for invalid input.
    *   `HTMLPlaceholder(std::string_view key)`: Returns an HTML placeholder string in the format `<${key}>`. Noexcept.
    *   `PutParamIntoHTML(std::string html, const Parameters& params)`: Replaces placeholders in an HTML string with values from a `Parameters` map. Ignores parameters without corresponding placeholders.
*   **Class:** `ConnectionImpl` (Abstract Base Class)
    *   Private Members: `socket_`, `keep_alive_`, `read_buf_`, `write_buf_`, `file_`.  Static member `root_dir_`.
    *   Protected Methods: Virtual destructor.
    *   Public Methods:
        *   `SetRootDirectory(std::filesystem::path dir)`: Static method to set the root directory for file serving. Noexcept.
        *   `GetRootDirectory()`: Static method to get the current root directory. Noexcept.
        *   Deleted copy/move constructors and assignment operators.
        *   `Close()`: Closes the socket. Noexcept.
        *   `Valid()`: Checks if the connection is valid (socket is open). Noexcept.
        *   `Socket()`: Returns the file descriptor of the socket. Noexcept.
        *   `Receive()`: Receives data from the socket into `read_buf_`.  Returns the number of bytes received.
        *   `Send()`: Sends data from `write_buf_` and potentially from a mapped file to the socket. Returns the number of bytes sent.
        *   `KeepAlive()`: Returns whether the connection should keep alive. Noexcept.
        *   `Process()`: Processes an HTTP request, reads from `read_buf_`, writes to `write_buf_`, and potentially serves a file.  Returns `false` if no data was read, otherwise `true`.
*   **Template Class:** `Connection<ValidIPAddr>`
    *   Inherits from `ConnectionImpl`.
    *   Stores an IP address object (`addr_`).
    *   Provides methods to access the IP address and port.

**2. `F02/U02: src/http/http.cpp` - HTTP Implementation**

This file provides the implementation for the functions declared in `http.h`, as well as internal helper functions.  It includes logic for content type determination, status code conversion, method string conversion, URL decoding, and HTML parameter substitution. It also contains the implementations of the methods within the `ConnectionImpl` class.

**3. `F03/U03: src/http/request.h` - Request Parser Interface**

*   **Class:** `Request`
    *   Nested Classes: `State`, `NotStarted`, `Header`, `Body`, `Finished`. These represent the states of the request parsing state machine.
    *   Methods:
        *   `Parse(Buffer& buf)`: Parses an HTTP request from a buffer. Throws `std::invalid_argument` on error.
        *   `Header(std::string_view key)`: Retrieves a header value by its key. Returns `std::optional<std::string_view>`. Noexcept.
        *   `Post(std::string_view key)`: Retrieves a POST parameter value by its key. Returns `std::optional<std::string_view>`. Noexcept.
        *   `PostSize()`: Returns the number of POST parameters. Noexcept.
        *   `Method()`, `Path()`, `Version()`: Accessors for request method, path, and version. Noexcept.
        *   `KeepAlive()`: Checks if the connection should keep alive based on headers. Noexcept.

**4. `F04/U04: src/http/request.cpp` - Request Parser Implementation**

This file implements the request parsing logic using a state machine pattern. Each nested class within `Request` represents a different parsing state, handling specific parts of the HTTP request (status line, headers, body).  The code uses regular expressions for parsing and URL decoding functions from `http.h`.

**5. `F05/U05: src/http/response.h` - Response Builder Interface**

*   **Class:** `Response`
    *   Methods:
        *   `Build(Buffer& buf, std::filesystem::path file, StatusCode& code)`: Builds a response serving a file. Returns an optional mapped read-only file.
        *   `Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code)`: Builds a dynamic HTML response with parameter substitution.
        *   `Build(Buffer& buf, StatusCode code, std::string msg)`: Builds a simple error response.
        *   `SetKeepAlive(bool set)`: Sets the keep-alive flag.

**6. `F06/U06: src/http/response.cpp` - Response Builder Implementation**

This file implements the response building logic, including handling files, generating HTML with parameter substitution, and constructing error responses. It uses a mapped read-only file for efficient file serving.
