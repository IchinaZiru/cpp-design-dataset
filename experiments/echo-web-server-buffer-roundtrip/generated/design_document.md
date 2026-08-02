# デザイン文書: `Buffer` クラスと `IOBuffer` クラス

## 概要
この設計文書は、バイトや文字列を格納し操作できる自動拡張可能なバッファクラスである `Buffer` およびその派生クラスである `IOBuffer` の仕様を記載します。これらのクラスは主にネットワーク通信におけるデータの読み書きに使用されます。

## 責務
- バイトや文字列の格納と操作。
- 自動的なバッファサイズ拡張。
- データの読み込み位置と書き込み位置の管理。
- データの追加、削除、クリアなどの基本的な操作を提供。

## 公開インターフェース

### `Buffer` クラス
#### コンストラクタ
- `explicit Buffer(std::size_t size = 1000) noexcept;`
- `explicit Buffer(std::span<const std::byte> bytes) noexcept;`
- `explicit Buffer(std::initializer_list<std::byte> bytes) noexcept;`
- `explicit Buffer(std::string_view str) noexcept;`

#### コピーコンストラクタとムーブコンストラクタ
- `Buffer(const Buffer&) noexcept;`
- `Buffer(Buffer&&) noexcept;`

#### 代入演算子
- `Buffer& operator=(const Buffer&) noexcept;`
- `Buffer& operator=(Buffer&&) noexcept;`

#### サイズ関連メソッド
- `std::size_t WritableSize() const noexcept;`
- `std::size_t ReadableSize() const noexcept;`
- `std::optional<std::byte> Peek() const noexcept;`
- `std::span<const std::byte> ReadableBytes() const noexcept;`
- `std::string ReadableString() const noexcept;`
- `std::span<std::byte> WritableBytes() const noexcept;`

#### データ追加メソッド
- `void Append(std::span<const std::byte> bytes) noexcept;`
- `void Append(std::initializer_list<std::byte> bytes) noexcept;`
- `void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept;`
- `void Append(const void* data, std::size_t size) noexcept;`
- `void Append(const Buffer& buf) noexcept;`

#### オフセット操作メソッド
- `void EnsureWriteableSize(std::size_t size) noexcept;`
- `void HasWritten(std::size_t size) noexcept;`
- `void Retrieve(std::size_t size) noexcept;`
- `std::size_t RetrieveUntil(const void* addr) noexcept;`
- `std::size_t RetrieveAll() noexcept;`
- `std::string RetrieveAllToString() noexcept;`

#### その他の操作メソッド
- `void Clear() noexcept;`
- `bool Empty() const noexcept;`

### `IOBuffer` クラス (派生クラス)
#### コンストラクタ
- `using Buffer::Buffer;`

#### I/O 関連メソッド
- `std::size_t ReadFrom(io::IReadWriter& io);`
- `std::size_t WriteTo(io::IReadWriter& io);`

### グローバルオペレータ
- `Buffer& operator<<(Buffer& buf, std::string_view str) noexcept;`
- `Buffer& operator<<(Buffer& to, const Buffer& from) noexcept;`
- `Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept;`
- `Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept;`

## 入力
- バイト列 (`std::span<const std::byte>` や `std::initializer_list<std::byte>`)
- 文字列 (`std::string_view`)
- 任意のデータポインタとサイズ (`const void*`, `std::size_t`)
- 別の `Buffer` オブジェクト
- I/Oオブジェクト (`io::IReadWriter&`)

## 出力
- バイト列 (`std::span<const std::byte>`)
- 文字列 (`std::string`)
- 書き込み可能なバッファサイズ (`std::size_t`)
- 読み取り可能なバッファサイズ (`std::size_t`)
- その他の操作結果 (`std::size_t`)

## 状態
- バッファの内部データ (`std::vector<std::byte> buf_`)
- 読み取り位置 (`std::atomic<std::size_t> read_pos_`)
- 書き込み位置 (`std::atomic<std::size_t> write_pos_`)

## 処理手順
1. **初期化**: コンストラクタを通じてバッファを初期化する。
2. **データ追加**: `Append` メソッドを使用してデータをバッファに追加する。必要に応じてバッファサイズを拡張する。
3. **読み取り操作**: `ReadableBytes`, `Peek`, `Retrieve` などのメソッドを使用してデータを読み取る。
4. **書き込み位置調整**: `HasWritten` メソッドを使用して書き込み位置を進める。
5. **バッファクリア**: `Clear` メソッドを使用してバッファを空にする。

## 例外・失敗条件
- `Append` メソッドでデータポインタが `nullptr` の場合、assert により検出される。
- `HasWritten`, `Retrieve` メソッドで指定されたサイズが現在の読み取り可能または書き込み可能な範囲を超える場合、assert により検出される。

## 依存関係
- `<atomic>`
- `<optional>`
- `<span>`
- `<string>`
- `<string_view>`
- `<vector>`
- `io::IReadWriter` (外部定義)

## 重要な不変条件
- 読み取り位置は常に書き込み位置以下である。
- バッファのサイズは常に読み取り可能なバイト数と書き込み可能なバイト数の合計以上である。