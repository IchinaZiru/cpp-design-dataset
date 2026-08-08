# デザイン文書

## 責務
`buffer.h`と`buffer.cpp`は、自動的に拡張可能なバッファを提供します。このバッファはバイトや文字列の格納をサポートし、読み取りオフセットと書き込みオフセットを使用してデータの範囲を管理します。

## 公開インターフェース
- `Buffer`クラス:
  - コンストラクタ: 初期サイズ、バイト配列、初期化リスト、文字列からバッファを作成。
  - メソッド: `WritableSize`, `ReadableSize`, `Peek`, `ReadableBytes`, `ReadableString`, `WritableBytes`, `Append`, `EnsureWriteableSize`, `HasWritten`, `Retrieve`, `RetrieveUntil`, `RetrieveAll`, `RetrieveAllToString`, `Clear`, `Empty`.
- `IOBuffer`クラス:
  - メソッド: `ReadFrom`, `WriteTo`.
- グローバルオペレータ: `<<` (バッファへの文字列、バッファ、バイト配列、初期化リストの追加).

## 入力
- 文字列 (`std::string_view`)
- バイト配列 (`std::span<const std::byte>`, `std::initializer_list<std::byte>`)
- その他のバッファ (`Buffer&`)

## 出力
- 読み取り可能なバイト数 (`std::size_t`)
- 読み取り可能なバイトデータ (`std::span<const std::byte>`)
- 読み取り可能な文字列 (`std::string`)
- 書き込み可能なバイトデータ (`std::span<std::byte>`)

## 状態
- `buf_`: バッファの内部ストレージ (`std::vector<std::byte>`)
- `read_pos_`: 読み取りオフセット (`std::atomic<std::size_t>`)
- `write_pos_`: 書き込みオフセット (`std::atomic<std::size_t>`)

## 処理手順
1. バッファの初期化: コンストラクタを使用してバッファを作成し、必要なサイズを確保する。
2. データの追加: `Append`メソッドを使用してデータをバッファに追加する。必要に応じて書き込み可能なスペースを確保する。
3. データの読み取り: `ReadableBytes`, `ReadableString`メソッドを使用してデータを読み取る。読み取りオフセットを適切に進める。
4. バッファのクリア: `Clear`メソッドを使用してバッファを空にする。

## 例外・失敗条件
- `Append`メソッドで`data`がnullptrの場合、assertionが発生する。
- `HasWritten`, `Retrieve`メソッドで指定されたサイズが現在の書き込み可能なサイズや読み取り可能なサイズを超える場合、assertionが発生する。

## 依存関係
- `std::atomic`
- `std::optional`
- `std::span`
- `std::string`
- `std::string_view`
- `std::vector`
- `io.h` (IOBufferクラスのため)

## 重要な不変条件
- `read_pos_`は常に`write_pos_`以下である。
- `buf_.size()`は常に`write_pos_ + WritableSize()`以上である。