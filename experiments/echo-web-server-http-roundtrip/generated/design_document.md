# HTTP通信モジュールの設計文書

## 概要
このドキュメントは、HTTP通信を処理するためのソフトウェアモジュールの設計を記述します。このモジュールは、HTTPリクエストの受信、解析、レスポンスの生成と送信を行う機能を持っています。

## 責務
- HTTPリクエストの受信と解析。
- リクエストに基づいた適切なHTTPレスポンスの生成。
- ソケットを通じたデータの送受信管理。
- ファイルシステムからのファイル読み込みとその内容をHTTPレスポンスに埋め込む。

## 公開インターフェース
### `http.h`
- `StatusCodeToMessage(StatusCode code) noexcept`: HTTPステータスコードからメッセージを取得する。
- `StatusCodeToInteger(StatusCode code) noexcept`: HTTPステータスコードを整数値に変換する。
- `MethodToString(Method method) noexcept`: HTTPメソッドを文字列に変換する。
- `StringToMethod(std::string str)`: 文字列からHTTPメソッドを取得する。
- `ContentTypeByFileName(std::string_view name) noexcept`: ファイル名からコンテンツタイプを取得する。
- `DecodeURLEncodedCharacter(const std::string& str)`: URLエンコードされた文字をデコードする。
- `DecodeURLEncodedString(const std::string& str)`: URLエンコードされた文字列をデコードする。
- `HTMLPlaceholder(std::string_view key) noexcept`: HTMLプレースホルダーを作成する。
- `PutParamIntoHTML(std::string html, const Parameters& params)`: パラメータをHTMLテンプレートに埋め込む。

### `ConnectionImpl`
- `SetRootDirectory(std::filesystem::path dir) noexcept`: ルートディレクトリを設定する。
- `GetRootDirectory() noexcept`: ルートディレクトリを取得する。
- `Close() noexcept`: コネクションを閉じる。
- `Valid() const noexcept`: コネクションが有効かどうかを確認する。
- `Socket() const noexcept`: ソケットを取得する。
- `Receive()`: HTTPリクエストを受け取る。
- `Send()`: HTTPレスポンスを送信する。
- `KeepAlive() const noexcept`: 保持接続が有効かどうかを確認する。
- `Process() noexcept`: リクエストを処理し、適切なレスポンスを作成する。

### `Connection<IPAddr>`
- `IPAddress() const noexcept`: IPアドレスを取得する。
- `Port() const noexcept`: ポート番号を取得する。

## 入力
- HTTPリクエスト（ソケットを通じて受信）。
- ルートディレクトリのパス。

## 出力
- HTTPレスポンス（ソケットを通じて送信）。

## 状態
- コネクションが開いているかどうか。
- 保持接続が有効かどうか。
- 受信バッファと送信バッファの状態。
- マップされたファイルの情報。

## 処理手順
1. `ConnectionImpl::Receive()`でHTTPリクエストを受信する。
2. `Request::Parse(Buffer& buf)`でリクエストを解析する。
3. `ConnectionImpl::Process()`でリクエストに基づいてレスポンスを作成する。
4. `Response::Build(Buffer& buf, ...)`でレスポンスヘッダとコンテンツを作成する。
5. `ConnectionImpl::Send()`でHTTPレスポンスを送信する。

## 例外・失敗条件
- リクエストの解析に失敗した場合（`std::invalid_argument`）。
- URLエンコードされた文字列のデコードに失敗した場合（`std::invalid_argument`）。
- ファイルのマッピングに失敗した場合（`std::exception`）。

## 依存関係
- `containers/buffer.h`: バッファ操作用クラス。
- `ip.h`: IPアドレス操作用クラス。
- `util.h`: その他のユーティリティ関数。
- `io.h`: I/O操作用クラス。
- `request.h`: HTTPリクエスト解析用クラス。
- `response.h`: HTTPレスポンス生成用クラス。

## 重要な不変条件
- ルートディレクトリは設定されなければなりません。
- ソケットが開かれている間、`ConnectionImpl::Valid()`は常に`true`を返す必要があります。
- ファイルのマッピングが行われた場合、`MappedReadOnlyFile::Data()`は有効なポインタを返す必要があります。