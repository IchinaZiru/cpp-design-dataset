# 設計文書

## 1. 概要と責務

このモジュールはHTTP通信の実装を提供します。主な機能として、HTTPリクエストのパース、レスポンスの生成、ソケットを通じたデータ送受信が含まれます。

## 2. 構造図
```mermaid
classDiagram
    class ConnectionImpl {
        +static void SetRootDirectory(std::filesystem::path dir) noexcept
        +static std::filesystem::path GetRootDirectory() noexcept
        +void Close() noexcept
        +bool Valid() const noexcept
        +FileDescriptor Socket() const noexcept
        +std::size_t Receive()
        +std::size_t Send()
        +bool KeepAlive() const noexcept
        +bool Process() noexcept
        -static constexpr std::string_view true_tag {"true"}
        -static constexpr std::string_view false_tag {"false"}
        -explicit ConnectionImpl(FileDescriptor socket) noexcept
        -virtual ~ConnectionImpl() noexcept
        -static std::filesystem::path root_dir_
        -FileDescriptor socket_ {invalid_file_descriptor}
        -bool keep_alive_ {false}
        -IOBuffer read_buf_
        -IOBuffer write_buf_
        -MappedReadOnlyFile file_
    }
    
    class Connection~IPAddr~ {
        +explicit Connection(const FileDescriptor socket, IPAddr addr) noexcept
        +std::string IPAddress() const noexcept
        +std::uint16_t Port() const noexcept
    }

    class Request {
        +Request() noexcept
        +explicit Request(Buffer& buf)
        +void Parse(Buffer& buf)
        +std::optional<std::string_view> Header(std::string_view key) const noexcept
        +std::optional<std::string_view> Post(std::string_view key) const noexcept
        +std::size_t PostSize() const noexcept
        +http::Method Method() const noexcept
        +std::string_view Path() const noexcept
        +std::string_view Version() const noexcept
        +bool KeepAlive() const noexcept
        -void SetState(std::unique_ptr<State> state) noexcept
        -void Clear() noexcept
        -std::unique_ptr<State> state_
        -http::Method method_ {Method::Get}
        -std::string version_
        -std::string path_
        -Parameters headers_
        -Parameters post_
    }

    class Response {
        +explicit Response(std::filesystem::path root_dir) noexcept
        +~Response() noexcept
        +Response& SetKeepAlive(bool set) noexcept
        +std::optional<MappedReadOnlyFile> Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept
        +void Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept
        +void Build(Buffer& buf, StatusCode code, std::string msg = "") noexcept
        -void Clear() noexcept
        -void Build(Buffer& buf, const Parameters* params = nullptr) noexcept
        -void CheckFile()
        -void MapFile()
        -void AddStatusLine(Buffer& buf) const noexcept
        -void AddHeaders(Buffer& buf) const noexcept
        -void AddMappedContent(Buffer& buf) noexcept
        -void AddParamContent(Buffer& buf, const Parameters& params) const noexcept
        -void AddPredefinedErrorContent(Buffer& buf, std::string_view msg = "") noexcept
        -std::filesystem::path root_dir_
        -std::filesystem::path file_path_
        -MappedReadOnlyFile file_
        -bool keep_alive_ {false}
        -StatusCode status_code_ {StatusCode::OK}
    }

    ConnectionImpl <|-- Connection~IPAddr~
```

## 3. インターフェースと依存関係

### ConnectionImpl
- **完全な名前**: `ws::http::ConnectionImpl`
- **引数**:
  - `socket`: `FileDescriptor`型、ソケットディスクリプタ。
- **戻り値の型**: 無し
- **修飾**: `noexcept`
- **使用するメンバ**: `root_dir_`, `socket_`, `keep_alive_`, `read_buf_`, `write_buf_`, `file_`
- **呼び出す関数・メソッド**:
  - `SetRootDirectory(std::filesystem::path dir)`
  - `GetRootDirectory()`
  - `Close()`
  - `Valid()`
  - `Socket()`
  - `Receive()`
  - `Send()`
  - `KeepAlive()`
  - `Process()`
- **継承元**: 無し
- **テンプレート型**: 無し

### Connection<IPAddr>
- **完全な名前**: `ws::http::Connection<IPAddr>`
- **引数**:
  - `socket`: `FileDescriptor`型、ソケットディスクリプタ。
  - `addr`: `IPAddr`型、IPアドレス情報。
- **戻り値の型**: 無し
- **修飾**: `noexcept`
- **使用するメンバ**: `addr_`
- **呼び出す関数・メソッド**:
  - `IPAddress()`
  - `Port()`
- **継承元**: `ConnectionImpl`
- **テンプレート型**: `IPAddr`

### Request
- **完全な名前**: `ws::http::Request`
- **引数**:
  - `buf`: `Buffer&`型、バッファ。
- **戻り値の型**: 無し
- **修飾**: 無し
- **使用するメンバ**: `state_`, `method_`, `version_`, `path_`, `headers_`, `post_`
- **呼び出す関数・メソッド**:
  - `Parse(Buffer& buf)`
  - `Header(std::string_view key) const noexcept`
  - `Post(std::string_view key) const noexcept`
  - `PostSize() const noexcept`
  - `Method() const noexcept`
  - `Path() const noexcept`
  - `Version() const noexcept`
  - `KeepAlive() const noexcept`
- **継承元**: 無し
- **テンプレート型**: 無し

### Response
- **完全な名前**: `ws::http::Response`
- **引数**:
  - `root_dir`: `std::filesystem::path`型、ルートディレクトリ。
- **戻り値の型**: 無し
- **修飾**: `noexcept`
- **使用するメンバ**: `root_dir_`, `file_path_`, `file_`, `keep_alive_`, `status_code_`
- **呼び出す関数・メソッド**:
  - `SetKeepAlive(bool set) noexcept`
  - `Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept`
  - `Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept`
  - `Build(Buffer& buf, StatusCode code, std::string msg = "") noexcept`
- **継承元**: 無し
- **テンプレート型**: 無し

## 4. 処理フロー図
```mermaid
flowchart TD
    A[Receive()] --> B{read_buf_.ReadableSize() == 0?}
    B -- Yes --> C[return size]
    B -- No --> D[read_buf_.ReadFrom(io)]
    D --> E[size += read_buf_.ReadFrom(io)]
    E --> F{catch std::system_error?}
    F -- Yes --> G{err.code() != std::errc::resource_unavailable_try_again?}
    G -- Yes --> H[throw]
    G -- No --> I[return size]
    F -- No --> I

    J[Process()] --> K{read_buf_.ReadableSize() == 0?}
    K -- Yes --> L[return false]
    K -- No --> M[request.Parse(read_buf_)]
    M --> N{catch std::exception?}
    N -- Yes --> O[error_msg = err.what()]
    N -- No --> P[keep_alive_ = request.KeepAlive()]
    P --> Q[response.SetKeepAlive(keep_alive_)]
    Q --> R{!error_msg.has_value()?}
    R -- Yes --> S[path = request.Path()]
    S --> T{path.empty() || path == "/"?}
    T -- Yes --> U[path = index_page]
    T -- No --> V[StatusCode status_code {StatusCode::OK}]
    V --> W{path == index_page?}
    W -- Yes --> X[auto params {ExtractUserMessage(request).value_or(Parameters {})}]
    X --> Y[params.insert({hide_msg_tag.data(), params.empty() ? true_tag.data() : false_tag.data()})]
    Y --> Z[response.Build(write_buf_, index_page, params, status_code)]
    W -- No --> AA[file {response.Build(write_buf_, std::move(path), status_code)}]
    AA --> AB{file.has_value()?}
    AB -- Yes --> AC[file_ = std::move(*file)]
    AB -- No --> AD[return true]
    R -- No --> AE[response.Build(write_buf_, StatusCode::BadRequest, *error_msg)]
    AE --> AF[return true]

    BG[Send()] --> BH{!write_buf_.Empty()?}
    BH -- Yes --> BI[header_size += write_buf_.WriteTo(io)]
    BH -- No --> BJ[file_size {0}]
    BJ --> BK{file_size < file_.Size()?}
    BK -- Yes --> BL[size {write(socket_, file_.Data() + file_size, file_.Size() - file_size)}]
    BL --> BM{size >= 0?}
    BM -- Yes --> BN[file_size += size]
    BM -- No --> BO[ThrowLastSystemError()]
    BK -- No --> BP[return header_size + file_size]
```

## 5. シーケンス図
該当なし。元コードから複数の関数、メソッド、オブジェクト間の呼び出し順序を直接確認できない。

## 6. 関数・メソッド仕様書

### ConnectionImpl::Receive()
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::http::ConnectionImpl::Receive()` |
| 目的 | HTTPリクエストを受信する。 |
| 引数 | 無し |
| 戻り値 | 受信したバイト数 (`std::size_t`) |
| 前提条件 | ソケットが有効であること |
| 事後条件 | リクエストデータが読み込みバッファに格納されること |
| 動作の説明 | ソケットからデータを読み取り、読み込みバッファに蓄積する。エラー発生時は例外を投げる。 |
| 状態変更・副作用 | 読み込みバッファへの追加 |
| 依存関係 | `read_buf_`, `socket_` |
| 境界条件 | ソケットが無効な場合、エラー発生時 |
| エラー処理 | データ読み取り中にエラーが発生した場合は例外を投げる。リソース利用不可の場合は再試行する。 |

### ConnectionImpl::Process()
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::http::ConnectionImpl::Process()` |
| 目的 | 受信したHTTPリクエストを処理し、適切なレスポンスを作成する。 |
| 引数 | 無し |
| 戻り値 | リクエストデータが存在しない場合`false`、それ以外は`true` (`bool`) |
| 前提条件 | ソケットが有効であること |
| 事後条件 | レスポンスデータが書き込みバッファに格納されること |
| 動作の説明 | 受信したリクエストを解析し、適切なレスポンスを作成する。エラー発生時はエラーメッセージと共にレスポンスを作成する。 |
| 状態変更・副作用 | リクエストデータの解析結果に基づく書き込みバッファへの追加 |
| 依存関係 | `read_buf_`, `write_buf_`, `file_` |
| 境界条件 | リクエストデータが存在しない場合、リクエストデータにエラーがある場合 |
| エラー処理 | リクエスト解析中にエラーが発生した場合はエラーメッセージと共にレスポンスを作成する。 |

### Request::Parse(Buffer& buf)
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::http::Request::Parse(Buffer& buf)` |
| 目的 | HTTPリクエストを解析し、内部状態に格納する。 |
| 引数 | `buf`: リクエストデータが含まれるバッファ (`Buffer&`) |
| 戻り値 | 無し |
| 前提条件 | バッファが空でないこと |
| 事後条件 | リクエストデータが解析され、内部状態に格納されること |
| 動作の説明 | バッファからリクエストデータを読み取り、ステートマシンを使用して解析する。エラー発生時は例外を投げる。 |
| 状態変更・副作用 | 内部状態への追加 |
| 依存関係 | `state_`, `method_`, `version_`, `path_`, `headers_`, `post_` |
| 境界条件 | バッファが空の場合、リクエストデータにエラーがある場合 |
| エラー処理 | リクエスト解析中にエラーが発生した場合は例外を投げる。 |

### Response::Build(Buffer& buf, std::filesystem::path file, StatusCode& code)
| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `ws::http::Response::Build(Buffer& buf, std::filesystem::path file, StatusCode& code)` |
| 目的 | ファイルリクエストに基づいてHTTPレスポンスを作成する。 |
| 引数 | 
  - `buf`: レスポンスデータが含まれるバッファ (`Buffer&`)
  - `file`: リクエストされたファイルのパス (`std::filesystem::path`)
  - `code`: HTTPステータスコード (`StatusCode&`) |
| 戻り値 | マップされた読み取り専用ファイル (`std::optional<MappedReadOnlyFile>`) |
| 前提条件 | 無し |
| 事後条件 | レスポンスデータがバッファに格納されること |
| 動作の説明 | ファイルリクエストに基づいてレスポンスを作成する。ファイルマッピングに失敗した場合はステータスコードを変更し、エラーメッセージと共にレスポンスを作成する。 |
| 状態変更・副作用 | バッファへの追加 |
| 依存関係 | `root_dir_`, `file_path_`, `file_`, `keep_alive_`, `status_code_` |
| 境界条件 | ファイルリクエストに失敗した場合 |
| エラー処理 | ファイルマッピング中にエラーが発生した場合はステータスコードを変更し、エラーメッセージと共にレスポンスを作成する。 |

## 7. 状態遷移と重要な条件

### ConnectionImpl::Process()
- **更新前の状態**: リクエストデータが読み込みバッファに存在すること
- **更新条件**: リクエストデータの解析結果に基づく
- **更新対象と更新値**:
  - `keep_alive_`: リクエストヘッダから取得した値
  - `status_code_`: レスポンスステータスコード
  - `file_path_`: リクエストパスに基づいたファイルパス
- **更新されない条件**: リクエストデータが存在しない場合、リクエスト解析中にエラーが発生した場合
- **更新順序**:
  1. リクエストデータの解析
  2. `keep_alive_`の設定
  3. ステータスコードとファイルパスの設定
  4. レスポンスデータの作成

## 8. 確認不能事項
確認不能事項なし