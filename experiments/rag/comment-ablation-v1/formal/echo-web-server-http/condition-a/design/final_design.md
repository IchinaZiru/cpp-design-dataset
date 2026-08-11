### Design Specification for HTTP Module

#### Overview
This document provides a detailed design specification for the HTTP module, which includes classes and functions to handle HTTP requests and responses. The module is designed to be part of a larger web server application.

#### Target Audience
- Developers responsible for implementing or maintaining the HTTP module.
- System architects who need to understand the architecture and dependencies of the HTTP module.

#### Dependencies
- `containers/buffer.h`
- `ip.h`
- `util.h`
- `<filesystem>`
- `<iostream>`
- `<memory>`
- `<string>`
- `<string_view>`
- `<unordered_map>`

### Module Components

#### 1. Header File: `include/http.h` (F01/U01)
This file contains the declarations for HTTP-related classes and functions.

**Namespaces**
- `ws::http`

**Constants**
- `version`: A constant string representing the HTTP version.
- `new_line`: A constant string representing a newline character sequence (`\r\n`).

**Types**
- `Parameters`: An alias for an unordered map of strings to strings, used to store query parameters.

**Enumerations**
- `StatusCode`: Represents HTTP status codes with values such as OK (200), BadRequest (400), Forbidden (403), NotFound (404).
- `Method`: Represents HTTP methods including Get, Post, Put, Patch, Delete.

**Functions**
- `StatusCodeToMessage(StatusCode code) noexcept`: Converts a status code to its corresponding message.
- `StatusCodeToInteger(StatusCode code) noexcept`: Converts a status code to an integer.
- `operator<<(std::ostream& os, StatusCode code) noexcept`: Overloads the stream insertion operator for `StatusCode`.
- `MethodToString(Method method) noexcept`: Converts a method to its string representation.
- `to_string(Method method) noexcept`: Converts a method to a string.
- `StringToMethod(std::string str)`: Converts a string to an HTTP method.
- `operator<<(std::ostream& os, Method method) noexcept`: Overloads the stream insertion operator for `Method`.
- `DecodeURLEncodedCharacter(const std::string& str)`: Decodes a URL-encoded character.
- `DecodeURLEncodedString(const std::string& str)`: Decodes a URL-encoded string.
- `HTMLPlaceholder(std::string_view key) noexcept`: Generates an HTML placeholder for a given key.
- `PutParamIntoHTML(std::string html, const Parameters& params)`: Replaces placeholders in HTML with parameters.

**Classes**
- **ConnectionImpl**: A base class representing an HTTP connection.
  - Methods:
    - `SetRootDirectory(std::filesystem::path dir) noexcept`
    - `GetRootDirectory() noexcept`
    - `Close() noexcept`
    - `Valid() const noexcept`
    - `Socket() const noexcept`
    - `Receive()`
    - `Send()`
    - `KeepAlive() const noexcept`
    - `Process() noexcept`

- **Connection<IPAddr>**: A template class representing a connection with an IP address.
  - Methods:
    - `IPAddress() const noexcept`
    - `Port() const noexcept`

#### 2. Source File: `src/http/http.cpp` (F02/U02)
This file contains the implementations for functions declared in `http.h`.

**Functions**
- `ContentTypeByFileName(const std::string_view name) noexcept`: Determines the content type based on a filename.
- `StatusCodeToMessage(const StatusCode code) noexcept`: Converts a status code to its corresponding message.
- `operator<<(std::ostream& os, const StatusCode code) noexcept`: Overloads the stream insertion operator for `StatusCode`.
- `StatusCodeToInteger(const StatusCode code) noexcept`: Converts a status code to an integer.
- `MethodToString(const Method method) noexcept`: Converts a method to its string representation.
- `to_string(const Method method) noexcept`: Converts a method to a string.
- `StringToMethod(std::string str)`: Converts a string to an HTTP method.
- `operator<<(std::ostream& os, const Method method) noexcept`: Overloads the stream insertion operator for `Method`.
- `DecodeURLEncodedCharacter(const std::string& str)`: Decodes a URL-encoded character.
- `DecodeURLEncodedString(const std::string& str)`: Decodes a URL-encoded string.
- `HTMLPlaceholder(std::string_view key) noexcept`: Generates an HTML placeholder for a given key.
- `PutParamIntoHTML(std::string html, const Parameters& params)`: Replaces placeholders in HTML with parameters.

**Classes**
- **ConnectionImpl**: Implements methods declared in the header file.
  - Methods:
    - `SetRootDirectory(std::filesystem::path dir) noexcept`
    - `GetRootDirectory() noexcept`
    - `Close() noexcept`
    - `Valid() const noexcept`
    - `Socket() const noexcept`
    - `Receive()`
    - `Send()`
    - `KeepAlive() const noexcept`
    - `Process() noexcept`

#### 3. Header File: `src/http/request.h` (F03/U03)
This file contains the declarations for the HTTP request class.

**Namespaces**
- `ws::http`

**Classes**
- **Request**: Represents an HTTP request.
  - Methods:
    - `Request() noexcept`
    - `explicit Request(Buffer& buf)`
    - `~Request() noexcept`
    - `void Parse(Buffer& buf)`
    - `std::optional<std::string_view> Header(std::string_view key) const noexcept`
    - `std::optional<std::string_view> Post(std::string_view key) const noexcept`
    - `std::size_t PostSize() const noexcept`
    - `http::Method Method() const noexcept`
    - `std::string_view Path() const noexcept`
    - `std::string_view Version() const noexcept`
    - `bool KeepAlive() const noexcept`

#### 4. Source File: `src/http/request.cpp` (F04/U04)
This file contains the implementations for functions and classes declared in `request.h`.

**Classes**
- **Request**: Implements methods declared in the header file.
  - Methods:
    - `Request() noexcept`
    - `explicit Request(Buffer& buf)`
    - `~Request() noexcept`
    - `void Parse(Buffer& buf)`
    - `std::optional<std::string_view> Header(std::string_view key) const noexcept`
    - `std::optional<std::string_view> Post(std::string_view key) const noexcept`
    - `std::size_t PostSize() const noexcept`
    - `http::Method Method() const noexcept`
    - `std::string_view Path() const noexcept`
    - `std::string_view Version() const noexcept`
    - `bool KeepAlive() const noexcept`

**State Classes**
- **Request::State**: Base class for parsing states.
  - Methods:
    - `explicit State(Request& parser) noexcept`
    - `virtual ~State() noexcept = default`
    - `virtual void Parse(const std::string& content) = 0`

- **NotStarted**: Parses the status line of an HTTP request.
  - Methods:
    - `void Parse(const std::string& line) override`

- **Header**: Parses headers in an HTTP request.
  - Methods:
    - `void Parse(const std::string& line) override`

- **Body**: Parses the body of an HTTP request.
  - Methods:
    - `void Parse(const std::string& body) override`
    - `void ParsePost(const std::string& body)`
    - `void ParseURLEncodedPost(const std::string& body)`

- **Finished**: Represents a finished parsing state.
  - Methods:
    - `[[noreturn]] void Parse(const std::string& content) override`

#### 5. Header File: `src/http/response.h` (F05/U05)
This file contains the declarations for the HTTP response class.

**Namespaces**
- `ws::http`

**Classes**
- **Response**: Represents an HTTP response.
  - Methods:
    - `explicit Response(std::filesystem::path root_dir) noexcept`
    - `~Response() noexcept`
    - `Response(const Response&) = delete`
    - `Response(Response&&) = delete`
    - `Response& operator=(const Response&) = delete`
    - `Response& operator=(Response&&) = delete`
    - `Response& SetKeepAlive(bool set) noexcept`
    - `std::optional<MappedReadOnlyFile> Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept`
    - `void Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept`
    - `void Build(Buffer& buf, StatusCode code, std::string msg = "") noexcept`

#### 6. Source File: `src/http/response.cpp` (F06/U06)
This file contains the implementations for functions and classes declared in `response.h`.

**Classes**
- **Response**: Implements methods declared in the header file.
  - Methods:
    - `explicit Response(std::filesystem::path root_dir) noexcept`
    - `~Response() noexcept`
    - `void Clear() noexcept`
    - `Response& SetKeepAlive(bool set) noexcept`
    - `std::optional<MappedReadOnlyFile> Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept`
    - `void Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept`
    - `void Build(Buffer& buf, StatusCode code, std::string msg = "") noexcept`

**Private Methods**
- `Build(Buffer& buf, const Parameters* params = nullptr) noexcept`: Builds the response based on parameters.
- `CheckFile()`: Checks if the file exists and is accessible.
- `MapFile()`: Maps the file into memory.
- `AddStatusLine(Buffer& buf) const noexcept`: Adds the status line to the buffer.
- `AddHeaders(Buffer& buf) const noexcept`: Adds headers to the buffer.
- `AddMappedContent(Buffer& buf) noexcept`: Adds content from a mapped file to the buffer.
- `AddParamContent(Buffer& buf, const Parameters& params) const noexcept`: Adds parameterized content to the buffer.
- `AddPredefinedErrorContent(Buffer& buf, std::string_view msg = "") noexcept`: Adds predefined error content to the buffer.

### Conclusion
This design specification provides a comprehensive overview of the HTTP module's components and their functionalities. It ensures that any developer can understand and implement the module accurately without needing access to the original source code.