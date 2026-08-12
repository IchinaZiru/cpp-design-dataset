以下は、与えられたC++ソースコードを解析し、別のLLMが再実装できるように設計仕様書を作成したものです。この仕様書では、各ファイルの役割、クラス構造、関数シグネチャ、および重要なロジックを詳細に記述しています。

---

# HTTPライブラリ設計仕様書

## 概要
このHTTPライブラリは、HTTPサーバー機能を提供するためのC++実装です。主に以下の機能を持っています：
- HTTPリクエストのパース
- HTTPレスポンスの生成
- ファイルの送信とHTMLテンプレートへのパラメータ埋め込み

## 依存関係
このライブラリは以下の外部コンポーネントに依存しています：
- `containers/buffer.h`：バッファ管理用
- `ip.h`：IPアドレス処理用
- `util.h`：ユーティリティ関数用

## クラス構造

### `ws::http` 名前空間内の主要クラス

#### `ConnectionImpl`
HTTP接続のコア実装クラス。以下の機能を提供します：
- ソケット管理
- リクエスト受信とレスポンス送信
- 保持中の接続の処理

**メンバー変数:**
- `socket_`：ソケットファイルディスクリプタ
- `keep_alive_`：接続を維持するかどうか
- `read_buf_`：読み込みバッファ
- `write_buf_`：書き込みバッファ
- `file_`：送信するファイル

**主要メソッド:**
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

#### `Connection<IPAddr>`
`ConnectionImpl`を継承したテンプレートクラス。クライアントのIPアドレス情報を追加します。

**メンバー変数:**
- `addr_`：クライアントのIPアドレス

**主要メソッド:**
```cpp
std::string IPAddress() const noexcept;
std::uint16_t Port() const noexcept;
```

#### `Request`
HTTPリクエストをパースするクラス。ステートパターンを使用してパース処理を行います。

**メンバー変数:**
- `state_`：現在のパース状態
- `method_`：HTTPメソッド
- `version_`：HTTPバージョン
- `path_`：リクエストパス
- `headers_`：ヘッダー情報
- `post_`：POSTパラメータ

**主要メソッド:**
```cpp
void Parse(Buffer& buf);
std::optional<std::string_view> Header(std::string_view key) const noexcept;
std::optional<std::string_view> Post(std::string_view key) const noexcept;
std::size_t PostSize() const noexcept;
http::Method Method() const noexcept;
std::string_view Path() const noexcept;
std::string_view Version() const noexcept;
bool KeepAlive() const noexcept;
```

#### `Response`
HTTPレスポンスを生成するクラス。ファイル送信やHTMLテンプレートへのパラメータ埋め込みをサポートします。

**メンバー変数:**
- `root_dir_`：ルートディレクトリ
- `file_path_`：送信するファイルのパス
- `file_`：マップされたファイルデータ
- `keep_alive_`：接続維持フラグ
- `status_code_`：HTTPステータスコード

**主要メソッド:**
```cpp
Response& SetKeepAlive(bool set) noexcept;
std::optional<MappedReadOnlyFile> Build(Buffer& buf, std::filesystem::path file, StatusCode& code) noexcept;
void Build(Buffer& buf, std::filesystem::path html, const Parameters& params, StatusCode& code) noexcept;
void Build(Buffer& buf, StatusCode code, std::string msg = "") noexcept;
```

## 列挙型と定数

### `StatusCode`
HTTPステータスコードを表す列挙型。
```cpp
enum class StatusCode : std::uint32_t {
    OK = 200,
    BadRequest = 400,
    Forbidden = 403,
    NotFound = 404
};
```

### `Method`
HTTPメソッドを表す列挙型。
```cpp
enum class Method { Get, Post, Put, Patch, Delete };
```

### 定数
```cpp
inline constexpr std::string_view version {"1.1"};
inline constexpr std::string_view new_line {"\r\n"};
```

## ユーティリティ関数

### HTTPメソッド変換
```cpp
std::string_view MethodToString(Method method) noexcept;
Method StringToMethod(std::string str);
```

### ステータスコード変換
```cpp
std::string_view StatusCodeToMessage(StatusCode code) noexcept;
std::uint32_t StatusCodeToInteger(StatusCode code) noexcept;
```

### URLデコード
```cpp
char DecodeURLEncodedCharacter(const std::string& str);
std::string DecodeURLEncodedString(const std::string& str);
```

### HTMLテンプレート処理
```cpp
std::string HTMLPlaceholder(std::string_view key) noexcept;
std::string PutParamIntoHTML(std::string html, const Parameters& params);
```

## 実装注意事項

1. **ステートパターンの使用**：`Request`クラスはステートパターンを使用してリクエストのパース処理を行います。以下の状態クラスが存在します：
   - `NotStarted`：パース開始前
   - `Header`：ヘッダー処理中
   - `Body`：ボディ処理中
   - `Finished`：パース完了

2. **ファイルマッピング**：`Response`クラスは`MappedReadOnlyFile`を使用してファイルデータをメモリにマップします。

3. **バッファ管理**：`Buffer`クラスを使用して入出力データの管理を行います。具体的な実装は`containers/buffer.h`を参照してください。

4. **エラーハンドリング**：例外を投げてエラーを報告します。主に以下の場合で発生します：
   - 無効なHTTPリクエスト
   - サポートされていないHTTPメソッド
   - ファイルアクセスエラー

5. **接続維持**：`ConnectionImpl::KeepAlive()`を使用して接続を維持するかどうかを判定します。

## 実装例

以下は、この仕様書に基づいて再実装されたコードの一部です。

```cpp
// http.h
namespace ws::http {

class ConnectionImpl {
public:
    // ... メソッド宣言 ...
private:
    static std::filesystem::path root_dir_;
    FileDescriptor socket_ {invalid_file_descriptor};
    bool keep_alive_ {false};
    IOBuffer read_buf_;
    IOBuffer write_buf_;
    MappedReadOnlyFile file_;
};

}  // namespace ws::http
```

## 結論

この設計仕様書は、与えられたC++ソースコードを解析し、別のLLMが再実装できるように詳細に記述しました。各クラスの役割、メンバー変数、メソッドシグネチャ、および重要なロジックについて説明しています。この仕様書を基に、新しいHTTPライブラリを実装することができます。

---

この仕様書は、与えられたコードから直接抽出された情報のみを含んでおり、推測や外部の知識は使用されていません。再実装時には、実際の`containers/buffer.h`、`ip.h`、`util.h`などの依存関係も考慮する必要があります。