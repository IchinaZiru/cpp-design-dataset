# HTTPモジュール設計文書

## 概要
この設計文書は、HTTP通信を処理するためのソフトウェアモジュールについて記載しています。対象となるファイルは以下の通りです。

- `include/http.h`
- `src/http/http.cpp`
- `src/http/request.h`
- `src/http/request.cpp`
- `src/http/response.h`
- `src/http/response.cpp`

## ファイル構造と責務

### include/http.h
#### 責務
HTTP通信の基本的な定義、列挙型、関数、クラスを提供します。これにはHTTPステータスコード、メソッド、バッファ操作、URLエンコーディング処理などが含まれます。

#### 公開インターフェース
- `StatusCodeToMessage`
- `StatusCodeToInteger`
- `MethodToString`
- `StringToMethod`
- `DecodeURLEncodedCharacter`
- `DecodeURLEncodedString`
- `HTMLPlaceholder`
- `PutParamIntoHTML`

#### 依存関係
- `containers/buffer.h`
- `ip.h`
- `util.h`
- `<filesystem>`
- `<iostream>`
- `<memory>`
- `<string>`
- `<string_view>`
- `<unordered_map>`

### src/http/http.cpp
#### 責務
`include/http.h`で宣言された関数の実装を提供します。

#### 公開インターフェース
なし（内部使用）

#### 依存関係
- `http.h`
- `io.h`
- `request.h`
- `response.h`
- `<cassert>`
- `<filesystem>`
- `<sstream>`

### src/http/request.h
#### 責務
HTTPリクエストのパースを行うためのクラスを提供します。

#### 公開インターフェース
- `Request::Request()`
- `Request::Request(Buffer&)`
- `Request::~Request()`
- `Request::Parse(Buffer&)`
- `Request::Header(std::string_view) const noexcept`
- `Request::Post(std::string_view) const noexcept`
- `Request::PostSize() const noexcept`
- `Request::Method() const noexcept`
- `Request::Path() const noexcept`
- `Request::Version() const noexcept`
- `Request::KeepAlive() const noexcept`

#### 依存関係
- `containers/buffer.h`
- `http.h`
- `<memory>`
- `<optional>`

### src/http/request.cpp
#### 責務
`request.h`で宣言されたクラスの実装を提供します。

#### 公開インターフェース
なし（内部使用）

#### 依存関係
- `request.h`
- `util.h`
- `<cassert>`
- `<regex>`
- `<stdexcept>`

### src/http/response.h
#### 責務
HTTPレスポンスの生成を行うためのクラスを提供します。

#### 公開インターフェース
- `Response::Response(std::filesystem::path) noexcept`
- `Response::~Response() noexcept`
- `Response::SetKeepAlive(bool) noexcept`
- `Response::Build(Buffer&, std::filesystem::path, StatusCode&) noexcept`
- `Response::Build(Buffer&, std::filesystem::path, const Parameters&, StatusCode&) noexcept`
- `Response::Build(Buffer&, StatusCode, std::string = "") noexcept`

#### 依存関係
- `containers/buffer.h`
- `http.h`
- `util.h`
- `<filesystem>`
- `<optional>`

### src/http/response.cpp
#### 責務
`response.h`で宣言されたクラスの実装を提供します。

#### 公開インターフェース
なし（内部使用）

#### 依存関係
- `response.h`
- `<cassert>`
- `<sstream>`

## クラス詳細

### ConnectionImpl
#### 責務
HTTP接続のコア処理を提供します。

#### 入力
- ソケットディスクリプタ

#### 出力
- 受信したデータサイズ (`Receive`)
- 送信したデータサイズ (`Send`)

#### 状態
- `socket_`: ソケットディスクリプタ
- `keep_alive_`: 接続が維持されるかどうかのフラグ
- `read_buf_`: リクエストを読み込むためのバッファ
- `write_buf_`: レスポンスを書き込むためのバッファ
- `file_`: 要求されたファイル

#### 処理手順
1. コンストラクタでソケットディスクリプタを受け取り初期化する。
2. `Receive`メソッドでリクエストデータを読み込む。
3. `Process`メソッドでリクエストデータを解析し、レスポンスを作成する。
4. `Send`メソッドでレスポンスデータを送信する。

#### 例外・失敗条件
- ソケットが無効な場合
- リクエストのパースに失敗した場合

### Request
#### 責務
HTTPリクエストの解析を行う。

#### 入力
- バッファ (`Parse`メソッド)

#### 出力
- HTTPヘッダーやPOSTデータを取得するためのメソッド

#### 状態
- `method_`: HTTPメソッド
- `version_`: HTTPバージョン
- `path_`: リクエストパス
- `headers_`: HTTPヘッダー
- `post_`: POSTデータ

#### 処理手順
1. コンストラクタでバッファを受け取り解析する。
2. `Parse`メソッドでリクエストデータを解析し、内部状態を更新する。

#### 例外・失敗条件
- バッファが空の場合
- 不正なHTTPステータスラインやヘッダー、ボディーの場合

### Response
#### 責務
HTTPレスポンスの生成を行う。

#### 入力
- ルートディレクトリ (`Response`コンストラクタ)
- ファイルパス (`Build`メソッド)
- HTTPパラメータ (`Build`メソッド)

#### 出力
- レスポンスデータをバッファに書き込む

#### 状態
- `root_dir_`: ルートディレクトリ
- `file_path_`: ファイルパス
- `file_`: マップされたファイル
- `keep_alive_`: 接続が維持されるかどうかのフラグ
- `status_code_`: HTTPステータスコード

#### 処理手順
1. コンストラクタでルートディレクトリを受け取り初期化する。
2. `Build`メソッドでレスポンスデータを生成し、バッファに書き込む。

#### 例外・失敗条件
- ファイルマップに失敗した場合

## 重要な不変条件
- `ConnectionImpl::socket_`は常に有効なファイルディスクリプタであるか、無効な値（`invalid_file_descriptor`）である。
- `Request::state_`は常に有効な状態オブジェクトを指している。
- `Response::file_path_`が相対パスの場合、`root_dir_`からの相対パスとして解釈される。

## まとめ
この設計文書では、HTTPモジュールの各ファイルとクラスの責務、公開インターフェース、入出力、状態、処理手順、例外・失敗条件、依存関係、重要な不変条件について詳細に記載しました。これに基づいて再実装を行います。