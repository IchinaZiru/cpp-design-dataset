# デザイン文書: Bufferモジュール

## 概要
この設計文書は、`buffer.h`と`buffer.cpp`で定義されているBufferクラスおよびその派生クラスIOBufferの設計を詳細に記述します。これらのクラスはバイトデータや文字列を格納し、読み書きを行うための自動拡張可能なバッファを提供します。

## ファイル構造と責務

### `include/containers/buffer.h`
- **ファイルの役割**: BufferクラスおよびIOBufferクラスの定義。
- **公開インターフェース**:
  - `class Buffer`: バイトデータや文字列を格納し、読み書きを行うための自動拡張可能なバッファ。
  - `enum class NewLine`: 改行コードを表す列挙型。
  - `class IOBuffer`: I/Oオブジェクトとの読み書きをサポートするBufferクラスの派生クラス。
  - グローバルな演算子オーバーロード: Bufferへの追加操作。

### `src/containers/buffer/buffer.cpp`
- **ファイルの役割**: buffer.hで定義されたクラスの実装。
- **公開インターフェース**:
  - BufferクラスおよびIOBufferクラスのコンストラクタ、デストラクタ、代入演算子。
  - バッファ操作メソッド: Append, EnsureWriteableSize, MakeSpace, Peek, ReadableBytes, WritableBytes, HasWritten, Retrieve, Clearなど。

## 公開インターフェース

### `class Buffer`
- **コンストラクタ**:
  - `Buffer(std::size_t size = 1000) noexcept`: 初期サイズを指定してバッファを作成。
  - `Buffer(std::span<const std::byte> bytes) noexcept`: バイトデータで初期化したバッファを作成。
  - `Buffer(std::initializer_list<std::byte> bytes) noexcept`: バイトデータのリストで初期化したバッファを作成。
  - `Buffer(std::string_view str) noexcept`: 文字列で初期化したバッファを作成。

- **メソッド**:
  - `std::size_t WritableSize() const noexcept`: 書き込み可能なサイズを返す。
  - `std::size_t ReadableSize() const noexcept`: 読み取り可能なサイズを返す。
  - `std::optional<std::byte> Peek() const noexcept`: 最初のバイトを読み取るがオフセットは進めない。
  - `std::span<const std::byte> ReadableBytes() const noexcept`: 読み取り可能なバイトデータを取得する。
  - `std::string ReadableString() const noexcept`: 読み取り可能な文字列を取得する。
  - `std::span<std::byte> WritableBytes() const noexcept`: 書き込み可能なスペースを取得する。
  - `void Append(std::span<const std::byte> bytes) noexcept`: バッファにバイトデータを追加する。
  - `void Append(std::initializer_list<std::byte> bytes) noexcept`: バッファにバイトデータのリストを追加する。
  - `void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept`: 文字列とオプションで改行コードを追加する。
  - `void Append(const void* data, std::size_t size) noexcept`: バッファにデータポインタから指定サイズのバイトデータを追加する。
  - `void Append(const Buffer& buf) noexcept`: 別のBufferオブジェクトの読み取り可能な部分を追加する。
  - `void EnsureWriteableSize(std::size_t size) noexcept`: 指定したサイズの書き込みスペースが確保されるようにする。
  - `void HasWritten(std::size_t size) noexcept`: 書き込みオフセットを指定したサイズだけ進める。
  - `void Retrieve(std::size_t size) noexcept`: 読み取りオフセットを指定したサイズだけ進める。
  - `std::size_t RetrieveUntil(const void* addr) noexcept`: 指定したアドレスまで読み取りオフセットを進める。
  - `std::size_t RetrieveAll() noexcept`: 全ての読み取り可能なデータを読み取り、バッファをクリアする。
  - `std::string RetrieveAllToString() noexcept`: 全ての読み取り可能なデータを文字列として取得し、バッファをクリアする。
  - `void Clear() noexcept`: バッファをクリアする。
  - `bool Empty() const noexcept`: バッファが空かどうかを返す。

- **保護されたメソッド**:
  - `std::size_t PrependableSize() const noexcept`: 再利用可能な先頭スペースのサイズを取得する。
  - `void MakeSpace(std::size_t size) noexcept`: 指定したサイズの書き込みスペースが確保されるようにバッファをリサイズまたは再配置する。
  - `std::vector<std::byte>::iterator ReadIter() const noexcept`: 読み取りオフセットに対応するイテレータを取得する。
  - `std::vector<std::byte>::iterator WriteIter() const noexcept`: 書き込みオフセットに対応するイテレータを取得する。

### `class IOBuffer`
- **コンストラクタ**: Bufferクラスのコンストラクタを継承。
- **メソッド**:
  - `std::size_t ReadFrom(io::IReadWriter& io)`: I/Oオブジェクトからデータを読み取りバッファに追加する。
  - `std::size_t WriteTo(io::IReadWriter& io)`: バッファのデータをI/Oオブジェクトに書き込む。

### グローバルな演算子オーバーロード
- `Buffer& operator<<(Buffer& buf, std::string_view str) noexcept`: 文字列をバッファに追加する。
- `Buffer& operator<<(Buffer& to, const Buffer& from) noexcept`: 別のバッファの内容を現在のバッファに追加する。
- `Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept`: バイトデータをバッファに追加する。
- `Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept`: バイトデータのリストをバッファに追加する。

## 入力と出力
### Bufferクラス
- **入力**:
  - コンストラクタ: 初期サイズ、バイトデータ、文字列。
  - Appendメソッド: バイトデータ、文字列、データポインタとサイズ、別のBufferオブジェクト。
  - EnsureWriteableSize, HasWritten, Retrieve, RetrieveUntil, Clear: サイズやアドレス。

- **出力**:
  - WritableSize, ReadableSize, PrependableSize: サイズ。
  - Peek: 最初のバイトデータ。
  - ReadableBytes, WritableBytes: バイトデータの範囲。
  - ReadableString: 文字列。
  - RetrieveAll, RetrieveUntil: 読み取りサイズ。
  - Empty: 真偽値。

### IOBufferクラス
- **入力**:
  - I/Oオブジェクトへの参照。

- **出力**:
  - 読み書きしたバイト数。

## 状態
- `buf_`: バッファデータを格納する`std::vector<std::byte>`。
- `read_pos_`: 読み取り位置を示す`std::atomic<std::size_t>`。
- `write_pos_`: 書き込み位置を示す`std::atomic<std::size_t>`。

## 処理手順
### バッファの初期化
1. コンストラクタが呼び出される。
2. 初期サイズやデータでバッファを初期化する。

### データの追加
1. Appendメソッドが呼び出される。
2. 必要に応じて書き込みスペースを確保する。
3. バッファにデータをコピーし、書き込みオフセットを進める。

### データの読み取り
1. Peek, ReadableBytes, ReadableStringメソッドが呼び出される。
2. 読み取り可能な範囲や最初のバイトデータを返す。

### オフセットの操作
1. HasWritten, Retrieve, RetrieveUntil, RetrieveAllメソッドが呼び出される。
2. 読み取り位置または書き込み位置を指定したサイズだけ進める。

### バッファのクリア
1. Clearメソッドが呼び出される。
2. 読み取り位置と書き込み位置を初期化する。

## 例外・失敗条件
- `Append`や`HasWritten`, `Retrieve`などのメソッドでサイズが不適切な場合、assertによって検査される。
- バッファのリサイズに失敗した場合は、std::bad_allocがスローされる可能性がある。

## 依存関係
- `buffer.h`: `<atomic>`, `<optional>`, `<span>`, `<string>`, `<string_view>`, `<vector>`を含む標準ライブラリヘッダ。
- `buffer.cpp`: `buffer.h`と`io.h`を含む。

## 重要な不変条件
- `read_pos_ <= write_pos_`: 読み取り位置は常に書き込み位置以下である。
- `write_pos_ <= buf_.size()`: 書き込み位置はバッファのサイズを超えない。