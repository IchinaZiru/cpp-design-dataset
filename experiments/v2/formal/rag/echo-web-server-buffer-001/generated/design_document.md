# 設計文書

## 1. 概要と責務

### モジュールの概要
`buffer.h`と`buffer.cpp`は、バイトや文字列を格納するための自動拡張可能なバッファクラス`Buffer`と、I/O操作に対応した拡張バッファクラス`IOBuffer`を提供します。

### モジュールの責務
- バッファの初期化とコピー。
- バッファへのデータ追加（バイト列や文字列）。
- バッファからのデータ読み取り（バイト列や文字列）。
- バッファの状態管理（読み込み位置、書き込み位置）。
- バッファの自動拡張機能。
- I/Oオブジェクトとのデータ交換。

## 2. 構造図

```mermaid
classDiagram
    class Buffer {
        +Buffer(std::size_t size) noexcept
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
        +IOBuffer()
        +std::size_t ReadFrom(io::IReadWriter& io)
        +std::size_t WriteTo(io::IReadWriter& io)
    }

    Buffer <|-- IOBuffer
```

## 3. インターフェースと依存関係

### 公開インターフェース

#### `class Buffer`
| 完全な名前 | 引数 | 戻り値の型 | 修飾 | 使用するメンバ/型/定数 | 呼び出す関数・メソッド | 継承元 |
|---|---|---|---|---|---|---|
| `Buffer::Buffer(std::size_t size)` | `size` (std::size_t) | なし | noexcept | buf_ | なし | なし |
| `Buffer::Buffer(std::span<const std::byte> bytes)` | `bytes` (std::span<const std::byte>) | なし | noexcept | Append() | Append() | なし |
| `Buffer::Buffer(std::initializer_list<std::byte> bytes)` | `bytes` (std::initializer_list<std::byte>) | なし | noexcept | Append() | Append() | なし |
| `Buffer::Buffer(std::string_view str)` | `str` (std::string_view) | なし | noexcept | Append() | Append() | なし |
| `Buffer::Buffer(const Buffer&)` | `o` (const Buffer&) | なし | noexcept | buf_, read_pos_, write_pos_ | なし | なし |
| `Buffer::Buffer(Buffer&&)` | `o` (Buffer&&) | なし | noexcept | buf_, read_pos_, write_pos_ | なし | なし |
| `Buffer::operator=(const Buffer&)` | `o` (const Buffer&) | Buffer& | noexcept | buf_, read_pos_, write_pos_ | なし | なし |
| `Buffer::operator=(Buffer&&)` | `o` (Buffer&&) | Buffer& | noexcept | buf_, read_pos_, write_pos_ | なし | なし |
| `Buffer::WritableSize()` | なし | std::size_t | const noexcept | write_pos_, buf_.size() | なし | なし |
| `Buffer::ReadableSize()` | なし | std::size_t | const noexcept | read_pos_, write_pos_ | なし | なし |
| `Buffer::Peek()` | なし | std::optional<std::byte> | const noexcept | ReadIter(), Empty() | なし | なし |
| `Buffer::ReadableBytes()` | なし | std::span<const std::byte> | const noexcept | ReadableSize(), ReadIter().base() | なし | なし |
| `Buffer::ReadableString()` | なし | std::string | const noexcept | ReadableSize(), ReadIter().base() | なし | なし |
| `Buffer::WritableBytes()` | なし | std::span<std::byte> | const noexcept | WritableSize(), WriteIter().base() | なし | なし |
| `Buffer::Append(std::span<const std::byte>)` | `bytes` (std::span<const std::byte>) | なし | noexcept | EnsureWriteableSize(), WriteIter(), HasWritten() | なし | なし |
| `Buffer::Append(std::initializer_list<std::byte>)` | `bytes` (std::initializer_list<std::byte>) | なし | noexcept | Append(bytes.begin(), bytes.size()) | Append() | なし |
| `Buffer::Append(std::string_view, std::optional<NewLine>)` | `str` (std::string_view), `new_line` (std::optional<NewLine>) | なし | noexcept | EnsureWriteableSize(), WriteIter(), HasWritten() | なし | なし |
| `Buffer::Append(const void*, std::size_t)` | `data` (const void*), `size` (std::size_t) | なし | noexcept | EnsureWriteableSize(), WriteIter(), HasWritten() | なし | なし |
| `Buffer::Append(const Buffer&)` | `buf` (const Buffer&) | なし | noexcept | Append(buf.ReadableBytes()) | Append() | なし |
| `Buffer::EnsureWriteableSize(std::size_t)` | `size` (std::size_t) | なし | noexcept | WritableSize(), MakeSpace() | なし | なし |
| `Buffer::HasWritten(std::size_t)` | `size` (std::size_t) | なし | noexcept | write_pos_ | なし | なし |
| `Buffer::Retrieve(std::size_t)` | `size` (std::size_t) | なし | noexcept | read_pos_ | なし | なし |
| `Buffer::RetrieveUntil(const void*)` | `addr` (const void*) | std::size_t | noexcept | ReadIter().base(), Retrieve() | なし | なし |
| `Buffer::RetrieveAll()` | なし | std::size_t | noexcept | ReadableSize(), Clear() | なし | なし |
| `Buffer::RetrieveAllToString()` | なし | std::string | noexcept | ReadableString(), Clear() | なし | なし |
| `Buffer::Clear()` | なし | なし | noexcept | read_pos_, write_pos_ | なし | なし |
| `Buffer::Empty()` | なし | bool | const noexcept | read_pos_, write_pos_ | なし | なし |

#### `class IOBuffer`
| 完全な名前 | 引数 | 戻り値の型 | 修飾 | 使用するメンバ/型/定数 | 呼び出す関数・メソッド | 継承元 |
|---|---|---|---|---|---|---|
| `IOBuffer::ReadFrom(io::IReadWriter&)` | `io` (io::IReadWriter&) | std::size_t | なし | なし | io.WriteTo(*this) | Buffer |
| `IOBuffer::WriteTo(io::IReadWriter&)` | `io` (io::IReadWriter&) | std::size_t | なし | なし | io.ReadFrom(*this) | Buffer |

#### グローバルオペレータ
| 完全な名前 | 引数 | 戻り値の型 | 修飾 | 使用するメンバ/型/定数 | 呼び出す関数・メソッド | 継承元 |
|---|---|---|---|---|---|---|
| `operator<<(Buffer&, std::string_view)` | `buf` (Buffer&), `str` (std::string_view) | Buffer& | noexcept | なし | buf.Append(str) | なし |
| `operator<<(Buffer&, const Buffer&)` | `to` (Buffer&), `from` (const Buffer&) | Buffer& | noexcept | なし | to.Append(from) | なし |
| `operator<<(Buffer&, std::span<const std::byte>)` | `buf` (Buffer&), `bytes` (std::span<const std::byte>) | Buffer& | noexcept | なし | buf.Append(bytes) | なし |
| `operator<<(Buffer&, std::initializer_list<std::byte>)` | `buf` (Buffer&), `bytes` (std::initializer_list<std::byte>) | Buffer& | noexcept | なし | buf.Append(bytes) | なし |

### 実装上の処理

#### `class Buffer`
| 完全な名前 | 引数 | 戻り値の型 | 修飾 | 使用するメンバ/型/定数 | 呼び出す関数・メソッド | 継承元 |
|---|---|---|---|---|---|---|
| `Buffer::PrependableSize()` | なし | std::size_t | const noexcept | read_pos_ | なし | なし |
| `Buffer::MakeSpace(std::size_t)` | `size` (std::size_t) | なし | noexcept | WritableSize(), PrependableSize(), ReadIter(), WriteIter() | buf_.resize(), std::copy() | なし |
| `Buffer::ReadIter()` | なし | std::vector<std::byte>::iterator | const noexcept | read_pos_, buf_ | なし | なし |
| `Buffer::WriteIter()` | なし | std::vector<std::byte>::iterator | const noexcept | write_pos_, buf_ | なし | なし |

## 4. 処理フロー図

### `void Buffer::Append(const void* data, std::size_t size)`

```mermaid
flowchart TD
    A[開始] --> B{size == 0?}
    B --はい--> C[終了]
    B --いいえ--> D[data != nullptr?]
    D --いいえ--> E[assert(false)]
    D --はい--> F[EnsureWriteableSize(size)]
    F --> G[base = reinterpret_cast<const std::byte*>(data)]
    H[std::copy(base, base + size, WriteIter())] --> I[HasWritten(size)]
    J[assert(ReadableSize() >= size)] --> C
```

### `void Buffer::MakeSpace(std::size_t size)`

```mermaid
flowchart TD
    A[開始] --> B{WritableSize() + PrependableSize() < size?}
    B --はい--> C[buf_.resize(write_pos_ + size)]
    B --いいえ--> D[readable_size = ReadableSize()]
    E[std::copy(ReadIter(), WriteIter(), buf_.begin())] --> F[read_pos_ = 0]
    G[write_pos_ = read_pos_ + readable_size] --> H{readable_size == ReadableSize()?}
    I[assert(false)] --> C
    H --いいえ--> J[assert(false)]
    H --はい--> K[終了]
```

## 5. シーケンス図

該当なし。元コードから複数の関数、メソッド、オブジェクト間の呼び出し順序を直接確認できない。

## 6. 関数・メソッド仕様書

### `void Buffer::Append(const void* data, std::size_t size)`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `Buffer::Append(const void* data, std::size_t size)` |
| 目的 | バッファにデータを追加し、書き込み位置を進める。 |
| 引数 | `data` (const void*): 追加するデータのポインタ。<br>`size` (std::size_t): 追加するデータのサイズ。 |
| 戻り値 | なし |
| 前提条件 | `data`がnullptrでない。<br>`size`が0以上の値である。 |
| 事後条件 | バッファに指定されたサイズのデータが追加され、書き込み位置が進む。 |
| 動作の説明 | 引数のサイズが0の場合終了する。<br>引数のデータポインタがnullptrの場合assertでエラーを発生させる。<br>必要な書き込みスペースがない場合は拡張する。<br>データをバッファにコピーし、書き込み位置を進める。 |
| 状態変更・副作用 | バッファの内容とサイズ、書き込み位置が変更される。 |
| 依存関係 | `EnsureWriteableSize()`, `HasWritten()` |
| 境界条件 | sizeが0の場合何もしない。<br>dataがnullptrの場合assertでエラーを発生させる。 |
| エラー処理 | dataがnullptrの場合assertでエラーを発生させる。 |
| 不変条件 | 書き込み位置は常に読み込み位置以上である。 |

### `void Buffer::MakeSpace(std::size_t size)`

| 項目 | 記述内容 |
|---|---|
| 完全な名前 | `Buffer::MakeSpace(std::size_t size)` |
| 目的 | バッファに指定されたサイズの書き込みスペースを確保する。 |
| 引数 | `size` (std::size_t): 必要とする書き込みスペースのサイズ。 |
| 戻り値 | なし |
| 前提条件 | sizeが0以上の値である。 |
| 事後条件 | バッファに指定されたサイズの書き込みスペースが確保される。 |
| 動作の説明 | 必要な書き込みスペースがない場合はバッファをリサイズする。<br>必要な書き込みスペースがある場合は、読み取り可能なデータを先頭に移動し、読み取り位置と書き込み位置を調整する。 |
| 状態変更・副作用 | バッファの内容とサイズ、読み取り位置と書き込み位置が変更される。 |
| 依存関係 | `WritableSize()`, `PrependableSize()`, `ReadIter()`, `WriteIter()` |
| 境界条件 | sizeが0の場合何もしない。<br>必要なスペースが既に確保されている場合、データの移動は行われない。 |
| エラー処理 | 確認できない |
| 不変条件 | 書き込み位置は常に読み込み位置以上である。 |

## 7. 状態遷移と重要な条件

### `Buffer`クラスの状態遷移

- **初期状態**: 読み取り位置と書き込み位置が0。
- **データ追加時**:
  - 更新前の状態: 書き込み可能なスペースがある場合、読み取り位置と書き込み位置は同じかそれ以上である。
  - 更新条件: データを追加する必要がある場合。
  - 更新対象と更新値: バッファの内容が追加されたデータで更新され、書き込み位置が追加したサイズ分進む。
- **データ読み取り時**:
  - 更新前の状態: 読み取り可能なデータがある場合、読み取り位置は書き込み位置より小さい。
  - 更新条件: データを読み取る必要がある場合。
  - 更新対象と更新値: 読み取り位置が読み取ったサイズ分進む。
- **バッファクリア時**:
  - 更新前の状態: バッファにデータが存在する場合、読み取り位置と書き込み位置は同じかそれ以上である。
  - 更新条件: バッファをクリアする必要がある場合。
  - 更新対象と更新値: 読み取り位置と書き込み位置が0に戻る。

## 8. 確認不能事項

確認不能事項なし