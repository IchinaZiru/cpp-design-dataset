以下は、与えられたC++ソースコードを解析し、別のLLMが再実装できるように設計仕様書を作成したものです。この仕様書では、入力から確認できない情報は推測せず、Fxx/Uxx識別子や名前空間などの構造を保持しています。

---

# HTTPサーバーライブラリ - 設計仕様書

## 概要
この設計仕様書は、HTTPリクエストとレスポンスを処理するためのC++ライブラリの実装を記述します。このライブラリは、HTTP/1.1プロトコルに準拠し、ファイルシステムから静的コンテンツを提供する機能を持っています。

## 名前空間
すべてのクラスと関数は`ws::http`名前空間内に配置されます。

## 依存関係
このライブラリは以下の外部ヘッダーに依存します：
- `containers/buffer.h`
- `ip.h`
- `util.h`

また、標準ライブラリから以下を使用します：
- `<filesystem>`
- `<iostream>`
- `<memory>`
- `<string>`
- `<string_view>`
- `<unordered_map>`

## 定数
### HTTPバージョン
```cpp
inline constexpr std::string_view version {"1.1"};
```

### 新規行
```cpp
inline constexpr std::string_view new_line {"\r\n"};
```

## 列挙型

### ステータスコード
```cpp
enum class StatusCode : std::uint32_t {
    OK = 200,
    BadRequest = 400,
    Forbidden = 403,
    NotFound = 404
};
```

### HTTPメソッド
```cpp
enum class Method { Get, Post, Put, Patch, Delete };
```

## 関数

### ステータスコード関連
```cpp
std::string_view StatusCodeToMessage(StatusCode code) noexcept;
std::uint32_t StatusCodeToInteger(StatusCode code) noexcept;
std::ostream& operator<<(std::ostream& os, StatusCode code) noexcept;
```

### メソッド関連
```cpp
std::string_view MethodToString(Method method) noexcept;
std::string to_string(Method method) noexcept;
Method StringToMethod(std::string str);
std::ostream& operator<<(std::ostream& os, Method method) noexcept;
```

### コンテンツタイプ判定
```cpp
std::string_view ContentTypeByFileName(std::string_view name) noexcept;
```

### URLデコード関連
```cpp
char DecodeURLEncodedCharacter(const std::string& str);
std::string DecodeURLEncodedString(const std::string& str);
```

### HTMLプレースホルダー関連
```cpp
std::string HTMLPlaceholder(std::string_view key) noexcept;
std::string PutParamIntoHTML(std::string html, const Parameters& params);
```

## クラス

### `ConnectionImpl`
HTTP接続を表す基底クラスです。ファイルディスクリプタ、読み書きバッファ、およびファイルマッピング機能を提供します。

#### メンバー関数
```cpp
static void SetRootDirectory(std::filesystem::path dir) noexcept;
static std::filesystem::path GetRootDirectory() noexcept;

void Close() noexcept;
bool Valid() const noexcept;
FileDescriptor Socket() const noexcept;
std::size_t Receive();
std::size_t Send();
bool KeepAlive() const noexcept;
bool Process() noexcept;
```

#### 静的メンバー
```cpp
static constexpr std::string_view true_tag {"true"};
static constexpr std::string_view false_tag {"false"};
```

### `Connection`
`ConnectionImpl`を継承した、IPアドレス付きの接続クラスです。

#### テンプレートパラメータ
```cpp
template <ValidIPAddr IPAddr>
class Connection : public ConnectionImpl {
public:
    using Ptr = std::shared_ptr<Connection>;

    explicit Connection(const FileDescriptor socket, IPAddr addr) noexcept;

    std::string IPAddress() const noexcept;
    std::uint16_t Port() const noexcept;
};
```

### `Request`
HTTPリクエストを解析するクラスです。ステートパターンを使用して、リクエストの各部分（ステータスライン、ヘッダー、ボディ）を順次解析します。

#### メンバー関数
```cpp
Request() noexcept;
explicit Request(Buffer& buf);
~Request() noexcept;

void Parse(Buffer& buf);

std::optional<std::string_view> Header(std::string_view key) const noexcept;
std::optional<std::string_view> Post(std::string_view key) const noexcept;
std::size_t PostSize() const noexcept;

http::Method Method() const noexcept;
std::string_view Path() const noexcept;
std::string_view Version() const noexcept;
bool KeepAlive() const noexcept;
```

#### 内部ステートクラス
- `NotStarted`
- `Header`
- `Body`
- `Finished`

### `Response`
HTTPレスポンスを構築するクラスです。ファイルシステムからコンテンツを読み込み、適切なヘッダーとボディを生成します。

#### メンバー関数
```cpp
explicit Response(std::filesystem::path root_dir) noexcept;
~Response() noexcept;

Response& SetKeepAlive(bool set) noexcept;

std::optional<MappedReadOnlyFile> Build(Buffer& buf,
                                        std::filesystem::path file,
                                        StatusCode& code) noexcept;
void Build(Buffer& buf, std::filesystem::path html,
           const Parameters& params, StatusCode& code) noexcept;
void Build(Buffer& buf, StatusCode code, std::string msg = "") noexcept;
```

## 実装注意事項
1. **バッファ管理**：`IOBuffer`と`MappedReadOnlyFile`は、外部ライブラリによって提供されるものとします。
2. **エラーハンドリング**：例外を投げる関数では、適切なエラーメッセージを含む`std::invalid_argument`または`std::system_error`を投げます。
3. **スレッドセーフティ**：このライブラリはスレッドセーフではないため、呼び出し側で同期処理を行う必要があります。

## 使用例
```cpp
#include "http.h"

int main() {
    ws::http::ConnectionImpl::SetRootDirectory("/var/www");

    // ファイルディスクリプタを取得して接続を作成
    FileDescriptor fd = ...;
    auto connection = std::make_shared<ws::http::Connection>(fd, ip_addr);

    if (connection->Process()) {
        connection->Send();
    }

    return 0;
}
```

この仕様書に従って、別のLLMがこのHTTPライブラリを再実装できるはずです。必要な外部依存関係や構造体定義（`FileDescriptor`、`IOBuffer`、`MappedReadOnlyFile`など）は、呼び出し側で提供されるものとします。