# 対象
- target: buffer
- granularity: module_files
- source_files: ["include/containers/buffer.h", "src/containers/buffer/buffer.cpp"]

# 責務
`Buffer`クラスはバイトや文字列を格納する自動拡張可能なバッファを提供します。読み取りオフセットと書き込みオフセットを使用して、バッファ内のデータの位置を管理します。また、バッファの読み取りと書き込み操作をサポートし、必要に応じてバッファのサイズを自動的に拡張します。

`IOBuffer`クラスは`Buffer`クラスを継承し、I/Oオブジェクトからのデータの読み書き機能を追加します。

# 公開インターフェース
- `Buffer::Buffer(std::size_t size = 1000) noexcept`
- `Buffer::Buffer(std::span<const std::byte> bytes) noexcept`
- `Buffer::Buffer(std::initializer_list<std::byte> bytes) noexcept`
- `Buffer::Buffer(std::string_view str) noexcept`
- `Buffer(const Buffer&) noexcept`
- `Buffer(Buffer&&) noexcept`
- `Buffer& operator=(const Buffer&) noexcept`
- `Buffer& operator=(Buffer&&) noexcept`
- `std::size_t WritableSize() const noexcept`
- `std::size_t ReadableSize() const noexcept`
- `std::optional<std::byte> Peek() const noexcept`
- `std::span<const std::byte> ReadableBytes() const noexcept`
- `std::string ReadableString() const noexcept`
- `std::span<std::byte> WritableBytes() const noexcept`
- `void Append(std::span<const std::byte> bytes) noexcept`
- `void Append(std::initializer_list<std::byte> bytes) noexcept`
- `void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept`
- `void Append(const void* data, std::size_t size) noexcept`
- `void Append(const Buffer& buf) noexcept`
- `void EnsureWriteableSize(std::size_t size) noexcept`
- `void HasWritten(std::size_t size) noexcept`
- `void Retrieve(std::size_t size) noexcept`
- `std::size_t RetrieveUntil(const void* addr) noexcept`
- `std::size_t RetrieveAll() noexcept`
- `std::string RetrieveAllToString() noexcept`
- `void Clear() noexcept`
- `bool Empty() const noexcept`
- `IOBuffer::ReadFrom(io::IReadWriter& io)`
- `IOBuffer::WriteTo(io::IReadWriter& io)`
- `operator<<(Buffer& buf, std::string_view str) noexcept`
- `operator<<(Buffer& to, const Buffer& from) noexcept`
- `operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept`
- `operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept`

# 入力
- バッファの初期サイズ（`std::size_t size`）
- 追加するバイトデータ（`std::span<const std::byte>`、`std::initializer_list<std::byte>`、`const void* data`）
- 追加する文字列データ（`std::string_view str`）
- バッファオブジェクト（`Buffer& buf`）
- 書き込みサイズ（`std::size_t size`）
- 読み取りサイズ（`std::size_t size`）
- 任意のアドレス（`const void* addr`）

# 出力
- バッファの書き込み可能なサイズ（`std::size_t`）
- バッファの読み取り可能なサイズ（`std::size_t`）
- 最初のバイトデータ（`std::optional<std::byte>`）
- 読み取り可能なバイトデータ（`std::span<const std::byte>`）
- 読み取り可能な文字列データ（`std::string`）
- 書き込み可能なスペース（`std::span<std::byte>`）
- 読み取ったサイズ（`std::size_t`）
- 文字列データ（`std::string`）

# 状態
- バッファの内部バイト配列 (`buf_`)
- 読み取りオフセット (`read_pos_`)
- 書き込みオフセット (`write_pos_`)

# 処理手順
1. `Buffer` クラスのコンストラクタは、初期サイズやデータを指定してバッファを作成します。
2. データの追加は `Append` メソッドを使用し、必要に応じてバッファのサイズが拡張されます。
3. 読み取り操作は `Peek`, `ReadableBytes`, `ReadableString` メソッドを使用して行います。これらのメソッドは読み取りオフセットを変更せずにデータを取得します。
4. 書き込み操作後、`HasWritten` メソッドで書き込みオフセットを調整します。
5. 読み取り操作後、`Retrieve`, `RetrieveUntil`, `RetrieveAll`, `RetrieveAllToString` メソッドで読み取りオフセットを調整します。
6. バッファのクリアは `Clear` メソッドを使用して行います。

# 例外・失敗条件
- `Append` メソッドでは、追加するデータが nullptr の場合に assert が発生します。
- `HasWritten`, `Retrieve` メソッドでは、オフセットの範囲外アクセスを検出し assert が発生します。

# 依存関係
- `<atomic>`
- `<optional>`
- `<span>`
- `<string>`
- `<string_view>`
- `<vector>`
- `io::IReadWriter`（`IOBuffer`クラス）

# 重要な不変条件
- 読み取りオフセットは常に書き込みオフセット以下である。
- バッファのサイズは必要に応じて自動的に拡張される。

## 追加詳細設計情報

### クラス図
```mermaid
classDiagram
    class Buffer {
        +Buffer(std::size_t size = 1000) noexcept
        +Buffer(std::span<const std::byte> bytes) noexcept
        +Buffer(std::initializer_list<std::byte> bytes) noexcept
        +Buffer(std::string_view str) noexcept
        +Buffer(const Buffer&) noexcept
        +Buffer(Buffer&&) noexcept
        +Buffer& operator=(const Buffer&) noexcept
        +Buffer& operator=(Buffer&&) noexcept
        +std::size_t WritableSize() const noexcept
        +std::size_t ReadableSize() const noexcept
        +std::optional<std::byte> Peek() const noexcept
        +std::span<const std::byte> ReadableBytes() const noexcept
        +std::string ReadableString() const noexcept
        +std::span<std::byte> WritableBytes() const noexcept
        +void Append(std::span<const std::byte> bytes) noexcept
        +void Append(std::initializer_list<std::byte> bytes) noexcept
        +void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept
        +void Append(const void* data, std::size_t size) noexcept
        +void Append(const Buffer& buf) noexcept
        +void EnsureWriteableSize(std::size_t size) noexcept
        +void HasWritten(std::size_t size) noexcept
        +void Retrieve(std::size_t size) noexcept
        +std::size_t RetrieveUntil(const void* addr) noexcept
        +std::size_t RetrieveAll() noexcept
        +std::string RetrieveAllToString() noexcept
        +void Clear() noexcept
        +bool Empty() const noexcept
        -std::size_t PrependableSize() const noexcept
        -void MakeSpace(std::size_t size) noexcept
        -std::vector<std::byte>::iterator ReadIter() const noexcept
        -std::vector<std::byte>::iterator WriteIter() const noexcept
        -std::vector<std::byte> buf_
        -std::atomic<std::size_t> read_pos_ {0}
        -std::atomic<std::size_t> write_pos_ {0}
    }
    
    class IOBuffer {
        +IOBuffer(std::size_t size = 1000) noexcept
        +IOBuffer(std::span<const std::byte> bytes) noexcept
        +IOBuffer(std::initializer_list<std::byte> bytes) noexcept
        +IOBuffer(std::string_view str) noexcept
        +std::size_t ReadFrom(io::IReadWriter& io)
        +std::size_t WriteTo(io::IReadWriter& io)
    }
    
    IOBuffer --|> Buffer
```

### クラス・メソッド・インターフェース詳細

| 完全な名前 | 属性 | 引数名と型 | 戻り値型 | 可視性 | const | noexcept | static | virtual |
|------------|------|------------|----------|--------|-------|----------|--------|---------|
| Buffer::Buffer | コンストラクタ | size: std::size_t | void | public | なし | あり | なし | なし |
| Buffer::Buffer | コンストラクタ | bytes: std::span<const std::byte> | void | public | なし | あり | なし | なし |
| Buffer::Buffer | コンストラクタ | bytes: std::initializer_list<std::byte> | void | public | なし | あり | なし | なし |
| Buffer::Buffer | コンストラクタ | str: std::string_view | void | public | なし | あり | なし | なし |
| Buffer::Buffer | コピーコンストラクタ | o: const Buffer& | void | public | なし | あり | なし | なし |
| Buffer::Buffer | ムーブコンストラクタ | o: Buffer&& | void | public | なし | あり | なし | なし |
| Buffer::operator= | コピー代入演算子 | o: const Buffer& | Buffer& | public | なし | あり | なし | なし |
| Buffer::operator= | ムーブ代入演算子 | o: Buffer&& | Buffer& | public | なし | あり | なし | なし |
| Buffer::WritableSize | メソッド | なし | std::size_t | public | あり | あり | なし | なし |
| Buffer::ReadableSize | メソッド | なし | std::size_t | public | あり | あり | なし | なし |
| Buffer::Peek | メソッド | なし | std::optional<std::byte> | public | あり | あり | なし | なし |
| Buffer::ReadableBytes | メソッド | なし | std::span<const std::byte> | public | あり | あり | なし | なし |
| Buffer::ReadableString | メソッド | なし | std::string | public | あり | あり | なし | なし |
| Buffer::WritableBytes | メソッド | なし | std::span<std::byte> | public | あり | あり | なし | なし |
| Buffer::Append | メソッド | bytes: std::span<const std::byte> | void | public | なし | あり | なし | なし |
| Buffer::Append | メソッド | bytes: std::initializer_list<std::byte> | void | public | なし | あり | なし | なし |
| Buffer::Append | メソッド | str: std::string_view, new_line: std::optional<NewLine> = std::nullopt | void | public | なし | あり | なし | なし |
| Buffer::Append | メソッド | data: const void*, size: std::size_t | void | public | なし | あり | なし | なし |
| Buffer::Append | メソッド | buf: const Buffer& | void | public | なし | あり | なし | なし |
| Buffer::EnsureWriteableSize | メソッド | size: std::size_t | void | public | なし | あり | なし | なし |
| Buffer::HasWritten | メソッド | size: std::size_t | void | public | なし | あり | なし | なし |
| Buffer::Retrieve | メソッド | size: std::size_t | void | public | なし | あり | なし | なし |
| Buffer::RetrieveUntil | メソッド | addr: const void* | std::size_t | public | なし | あり | なし | なし |
| Buffer::RetrieveAll | メソッド | なし | std::size_t | public | なし | あり | なし | なし |
| Buffer::RetrieveAllToString | メソッド | なし | std::string | public | なし | あり | なし | なし |
| Buffer::Clear | メソッド | なし | void | public | なし | あり | なし | なし |
| Buffer::Empty | メソッド | なし | bool | public | あり | あり | なし | なし |
| Buffer::PrependableSize | メソッド | なし | std::size_t | protected | あり | あり | なし | なし |
| Buffer::MakeSpace | メソッド | size: std::size_t | void | protected | なし | あり | なし | なし |
| Buffer::ReadIter | メソッド | なし | std::vector<std::byte>::iterator | protected | あり | あり | なし | なし |
| Buffer::WriteIter | メソッド | なし | std::vector<std::byte>::iterator | protected | あり | あり | なし | なし |
| IOBuffer::IOBuffer | コンストラクタ | size: std::size_t = 1000 | void | public | なし | あり | なし | なし |
| IOBuffer::IOBuffer | コンストラクタ | bytes: std::span<const std::byte> | void | public | なし | あり | なし | なし |
| IOBuffer::IOBuffer | コンストラクタ | bytes: std::initializer_list<std::byte> | void | public | なし | あり | なし | なし |
| IOBuffer::IOBuffer | コンストラクタ | str: std::string_view | void | public | なし | あり | なし | なし |
| IOBuffer::ReadFrom | メソッド | io: io::IReadWriter& | std::size_t | public | なし | なし | なし | なし |
| IOBuffer::WriteTo | メソッド | io: io::IReadWriter& | std::size_t | public | なし | なし | なし | なし |

### シーケンス図
該当なし（元コードに複数の関数、メソッド、オブジェクト間の相互作用が確認できない）

### メソッド仕様書

| メソッド名 | 目的 | 引数 | 戻り値 | 動作の説明 | サイドエフェクト | 使用例 | エラー処理 |
|------------|------|------|--------|--------------|------------------|--------|-------------|
| Buffer::Append | バッファにデータを追加する | bytes: std::span<const std::byte> | void | 指定されたバイトデータをバッファの末尾に追加し、書き込みオフセットを更新する。必要に応じてバッファのサイズが拡張される。 | 書き込みオフセットが更新される。 | `Buffer buf; std::byte data[] = {0x1, 0x2}; buf.Append(data);` | 確認不能 |
| Buffer::Append | バッファにデータを追加する | bytes: std::initializer_list<std::byte> | void | 指定されたバイトデータをバッファの末尾に追加し、書き込みオフセットを更新する。必要に応じてバッファのサイズが拡張される。 | 書き込みオフセットが更新される。 | `Buffer buf; std::byte data[] = {0x1, 0x2}; buf.Append(data);` | 確認不能 |
| Buffer::Append | バッファに文字列を追加する | str: std::string_view, new_line: std::optional<NewLine> = std::nullopt | void | 指定された文字列データとオプションの改行コードをバッファの末尾に追加し、書き込みオフセットを更新する。必要に応じてバッファのサイズが拡張される。 | 書き込みオフセットが更新される。 | `Buffer buf; buf.Append("Hello");` | 確認不能 |
| Buffer::Append | バッファにデータを追加する | data: const void*, size: std::size_t | void | 指定されたバイトデータをバッファの末尾に追加し、書き込みオフセットを更新する。必要に応じてバッファのサイズが拡張される。 | 書き込みオフセットが更新される。 | `Buffer buf; std::byte data[] = {0x1, 0x2}; buf.Append(data, sizeof(data));` | 確認不能 |
| Buffer::Append | バッファにバッファを追加する | buf: const Buffer& | void | 指定されたバッファの読み取り可能なデータを現在のバッファの末尾に追加し、書き込みオフセットを更新する。必要に応じてバッファのサイズが拡張される。 | 書き込みオフセットが更新される。 | `Buffer buf1, buf2; buf1.Append(buf2);` | 確認不能 |
| Buffer::RetrieveAllToString | バッファから全てのデータを読み取り、文字列として返す | なし | std::string | バッファ内の全ての読み取り可能なデータを文字列として取得し、バッファをクリアする。 | バッファがクリアされる。 | `Buffer buf; buf.Append("Hello"); auto str = buf.RetrieveAllToString();` | 確認不能 |

### 処理フロー図
```mermaid
flowchart TD
    A[Append] --> B{WritableSize < size?}
    B -- はい --> C[MakeSpace(size)]
    B -- いいえ --> D[Copy data to WriteIter]
    C --> E[Resize buf_]
    D --> F[Increment write_pos_]
    E --> F
```

### 状態遷移・副作用

| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| 任意の状態 | Append() | write_pos_ | write_pos_ + size | 1. EnsureWriteableSize(size)<br>2. Copy data to WriteIter<br>3. Increment write_pos_ | 書き込みオフセットが更新される |
| 任意の状態 | Retrieve(size) | read_pos_ | read_pos_ + size | Increment read_pos_ | 読み取りオフセットが更新される |
| 任意の状態 | Clear() | read_pos_, write_pos_ | 0, 0 | Set read_pos_ and write_pos_ to 0 | バッファがクリアされる |

### データ変換・制約

| 入力形式 | 出力形式 | 変換規則 | 値域 | 境界値 | 単位 | 精度 | エンコーディング | 検証条件 | 特殊値・欠損値の扱い |
|----------|----------|----------|------|--------|------|------|------------------|------------|-----------------------|
| std::span<const std::byte> | なし | バイトデータをバッファに追加する | 確認不能 | 確認不能 | byte | 確認不能 | 確認不能 | 確認不能 | 確認不能 |
| std::initializer_list<std::byte> | なし | バイトデータをバッファに追加する | 確認不能 | 確認不能 | byte | 確認不能 | 確認不能 | 確認不能 | 確認不能 |
| std::string_view | なし | 文字列データとオプションの改行コードをバッファに追加する | 確認不能 | 確認不能 | char | 確認不能 | UTF-8 | 確認不能 | 確認不能 |
| const void* | なし | バイトデータをバッファに追加する | 確認不能 | 確認不能 | byte | 確認不能 | 確認不能 | 確認不能 | 確認不能 |
| Buffer& | なし | 指定されたバッファの読み取り可能なデータを現在のバッファに追加する | 確認不能 | 確認不能 | byte | 確認不能 | 確認不能 | 確認不能 | 確認不能 |
| なし | std::string | バッファ内の全ての読み取り可能なデータを文字列として取得し、バッファをクリアする | 確認不能 | 確認不能 | char | 確認不能 | UTF-8 | 確認不能 | 確認不能 |