# 対象
- target: http
- granularity: module_files
- source_files: ["include/http.h", "src/http/http.cpp", "src/http/request.h", "src/http/request.cpp", "src/http/response.h", "src/http/response.cpp"]

# 対象範囲
元コードとして示したsource_files全体を1つのモジュールとして扱ってください。
設計文書は、各ファイルの責務、ファイル間の関係、公開インターフェース、実装上の処理を含めて作成してください。
再実装ではsource_filesにある各ファイル全体を生成するため、ファイルごとの構造と責務を区別してください。

## 責務
HTTP通信の受信、解析、応答生成を行う。具体的には、HTTPリクエストのパース、レスポンスの作成、ソケットを通じたデータ送受信を行います。

## 公開インターフェース
- `http.h`: HTTPステータスコード、メソッド、コンテンツタイプの定義と変換関数、URLエンコーディングのデコード関数、HTMLテンプレートへのパラメータ挿入関数、HTTP接続クラス`ConnectionImpl`とその派生クラス`Connection`
- `request.h`: HTTPリクエストを解析するためのクラス`Request`
- `response.h`: HTTPレスポンスを作成するためのクラス`Response`

## 入力
- HTTPリクエストデータ（ソケットから受信）
- ファイルパスやパラメータなどの内部処理に必要な情報

## 出力
- 解析されたHTTPリクエスト情報
- 生成されたHTTPレスポンスデータ（ソケットへ送信）

## 状態
- HTTP接続の状態（有効/無効）
- ソケットの状態（開閉）
- リクエストやレスポンスのバッファリング状態

## 処理手順
1. `ConnectionImpl::Receive()`でHTTPリクエストデータを受信し、`read_buf_`に格納する。
2. `Request::Parse()`で受信したリクエストデータを解析し、メソッド、パス、ヘッダー、POSTパラメータなどを抽出する。
3. `ConnectionImpl::Process()`でリクエストの内容に基づいて適切なレスポンスを作成する。`Response::Build()`を使用してHTTPヘッダーやコンテンツを作成し、`write_buf_`に格納する。
4. `ConnectionImpl::Send()`で生成したレスポンスデータをソケットを通じて送信する。

## 例外・失敗条件
- リクエストのパース中に不正なフォーマットが検出された場合、`std::invalid_argument`が投げられる。
- ソケット操作中にシステムエラーが発生した場合、`std::system_error`が投げられる。

## 依存関係
- `http.h`: `containers/buffer.h`, `ip.h`, `util.h`
- `request.cpp`: `request.h`, `util.h`
- `response.cpp`: `response.h`, `util.h`

## 重要な不変条件
- HTTP接続が有効である場合、`socket_`は無効なファイルディスクリプタでない。
- リクエストの解析中に例外が発生した場合、内部状態はクリアされるべきである。