# 詳細設計仕様書

## 1. 概要
この設計仕様書は、C++のバッファークラス`Buffer`とその派生クラス`IOBuffer`の再実装に必要な情報を提供します。ソースコードから確認できる事実のみを記述し、推測や補完は行いません。

## 2. 完全再構築台帳

### 2.1 ファイル構造
- **include/containers/buffer.h**: ヘッダーファイル（宣言）
- **src/containers/buffer/buffer.cpp**: 実装ファイル

### 2.2 依存関係
- `<atomic>`
- `<optional>`
- `<span>`
- `<string>`
- `<string_view>`
- `<vector>`
- `"io.h"` (ws::io::IReadWriter)

## 3. クラス図

```mermaid
classDiagram
    class Buffer {
        -std::vector<std::byte> buf_
        -std::atomic<std::size_t> read_pos_
        -std::atomic<std::size_t> write_pos_

        +Buffer(std::size_t size) noexcept
        +Buffer(std::span<const std::byte> bytes) noexcept
        +Buffer(std::initializer_list<std::byte> bytes) noexcept
        +Buffer(std::string_view str) noexcept
        +Buffer(const Buffer&) noexcept
        +Buffer(Buffer&&) noexcept
        +operator=(const Buffer&) noexcept
        +operator=(Buffer&&) noexcept
        +WritableSize() const noexcept
        +ReadableSize() const noexcept
        +Peek() const noexcept
        +ReadableBytes() const noexcept
        +ReadableString() const noexcept
        +WritableBytes() const noexcept
        +Append(std::span<const std::byte> bytes) noexcept
        +Append(std::initializer_list<std::byte> bytes) noexcept
        +Append(std::string_view str, std::optional<NewLine> new_line) noexcept
        +Append(const void* data, std::size_t size) noexcept
        +Append(const Buffer& buf) noexcept
        +EnsureWriteableSize(std::size_t size) noexcept
        +HasWritten(std::size_t size) noexcept
        +Retrieve(std::size_t size) noexcept
        +RetrieveUntil(const void* addr) noexcept
        +RetrieveAll() noexcept
        +RetrieveAllToString() noexcept
        +Clear() noexcept
        +Empty() const noexcept
        +PrependableSize() const noexcept
        +MakeSpace(std::size_t size) noexcept
        +ReadIter() const noexcept
        +WriteIter() const noexcept
    }

    class IOBuffer {
        +ReadFrom(io::IReadWriter& io)
        +WriteTo(io::IReadWriter& io)
    }

    Buffer <|-- IOBuffer

    enum NewLine {
        <<enumeration>>
        LF
        CRLF
    }
```

## 4. クラス・メソッド・インターフェース詳細

### 4.1 `ws::NewLine`列挙型
```markdown
| 名前 | 型 | 値 |
|------|----|----|
| LF   | NewLine | (未指定) |
| CRLF | NewLine | (未指定) |
```

### 4.2 `ws::Buffer`クラス

#### コンストラクタ
```markdown
| 名前 | シグネチャ | 備考 |
|------|------------|------|
| Buffer | explicit Buffer(std::size_t size = 1000) noexcept | デフォルトサイズ1000のバッファを作成 |
| Buffer | explicit Buffer(std::span<const std::byte> bytes) noexcept | バイト列から初期化 |
| Buffer | explicit Buffer(std::initializer_list<std::byte> bytes) noexcept | 初期化リストから初期化 |
| Buffer | explicit Buffer(std::string_view str) noexcept | 文字列から初期化 |
| Buffer | Buffer(const Buffer&) noexcept | コピーコンストラクタ |
| Buffer | Buffer(Buffer&&) noexcept | ムーブコンストラクタ |

#### アサインメント演算子
```markdown
| 名前 | シグネチャ | 備考 |
|------|------------|------|
| operator= | Buffer& operator=(const Buffer&) noexcept | コピー代入 |
| operator= | Buffer& operator=(Buffer&&) noexcept | ムーブ代入 |

#### パブリックメソッド
```markdown
| 名前 | シグネチャ | 備考 |
|------|------------|------|
| WritableSize | std::size_t WritableSize() const noexcept | 書き込み可能サイズを返す |
| ReadableSize | std::size_t ReadableSize() const noexcept | 読み取り可能サイズを返す |
| Peek | std::optional<std::byte> Peek() const noexcept | 先頭のバイトを返す（空ならnullopt） |
| ReadableBytes | std::span<const std::byte> ReadableBytes() const noexcept | 読み取り可能なバイト列を返す |
| ReadableString | std::string ReadableString() const noexcept | 読み取り可能な文字列を返す |
| WritableBytes | std::span<std::byte> WritableBytes() const noexcept | 書き込み可能なバイト列を返す |
| Append | void Append(std::span<const std::byte> bytes) noexcept | バイト列を追加 |
| Append | void Append(std::initializer_list<std::byte> bytes) noexcept | 初期化リストを追加 |
| Append | void Append(std::string_view str, std::optional<NewLine> new_line = std::nullopt) noexcept | 文字列と改行コードを追加 |
| Append | void Append(const void* data, std::size_t size) noexcept | ポインタからデータを追加 |
| Append | void Append(const Buffer& buf) noexcept | バッファを追加 |
| EnsureWriteableSize | void EnsureWriteableSize(std::size_t size) noexcept | 書き込み可能サイズを確保 |
| HasWritten | void HasWritten(std::size_t size) noexcept | 書き込み位置を進める |
| Retrieve | void Retrieve(std::size_t size) noexcept | 読み取り位置を進める |
| RetrieveUntil | std::size_t RetrieveUntil(const void* addr) noexcept | アドレスまで読み取り位置を進める |
| RetrieveAll | std::size_t RetrieveAll() noexcept | 全てのデータをクリアし、サイズを返す |
| RetrieveAllToString | std::string RetrieveAllToString() noexcept | 全てのデータを文字列として取得し、クリア |
| Clear | void Clear() noexcept | バッファをクリア |
| Empty | bool Empty() const noexcept | バッファが空かどうか |

#### プロテクトメソッド
```markdown
| 名前 | シグネチャ | 備考 |
|------|------------|------|
| PrependableSize | std::size_t PrependableSize() const noexcept | 先頭に挿入可能なサイズを返す |
| MakeSpace | void MakeSpace(std::size_t size) noexcept | 空き領域を確保 |
| ReadIter | std::vector<std::byte>::iterator ReadIter() const noexcept | 読み取り位置のイテレータを返す |
| WriteIter | std::vector<std::byte>::iterator WriteIter() const noexcept | 書き込み位置のイテレータを返す |

#### メンバ変数
```markdown
| 名前 | 型 | 初期値 | 備考 |
|------|----|--------|------|
| buf_ | std::vector<std::byte> | - | バッファデータ |
| read_pos_ | std::atomic<std::size_t> | 0 | 読み取り位置 |
| write_pos_ | std::atomic<std::size_t> | 0 | 書き込み位置 |
```

### 4.3 `ws::IOBuffer`クラス

#### メソッド
```markdown
| 名前 | シグネチャ | 備考 |
|------|------------|------|
| ReadFrom | std::size_t ReadFrom(io::IReadWriter& io) | IReadWriterから読み取り |
| WriteTo | std::size_t WriteTo(io::IReadWriter& io) | IReadWriterに書き込み |

### 4.4 オペレータオーバーロード
```markdown
| 名前 | シグネチャ | 備考 |
|------|------------|------|
| operator<< | Buffer& operator<<(Buffer& buf, std::string_view str) noexcept | 文字列を追加 |
| operator<< | Buffer& operator<<(Buffer& to, const Buffer& from) noexcept | バッファを追加 |
| operator<< | Buffer& operator<<(Buffer& buf, std::span<const std::byte> bytes) noexcept | バイト列を追加 |
| operator<< | Buffer& operator<<(Buffer& buf, std::initializer_list<std::byte> bytes) noexcept | 初期化リストを追加 |
```

## 5. メソッド仕様書

### 5.1 `Append(std::string_view str, std::optional<NewLine> new_line)`
- **目的**: 文字列とオプションの改行コードをバッファに追加
- **引数**:
  - `str`: 追加する文字列
  - `new_line`: 改行コード（LFまたはCRLF）
- **動作**:
  1. `full_str`として入力文字列をコピー
  2. `new_line`が指定されている場合、対応する改行コードを追加
  3. `Append(const void*, std::size_t)`を呼び出し
- **副作用**: バッファの内容が変更される

### 5.2 `MakeSpace(std::size_t size)`
- **目的**: 指定されたサイズ分の書き込み可能領域を確保
- **引数**:
  - `size`: 必要な最小サイズ
- **動作**:
  1. 現在の`WritableSize() + PrependableSize()`が`size`未満なら、バッファを拡張
  2. それ以外の場合、読み取り可能なデータを先頭にコピーし、位置をリセット
- **副作用**: バッファの内容と位置が変更される

### 5.3 `RetrieveUntil(const void* addr)`
- **目的**: 指定アドレスまで読み取り位置を進める
- **引数**:
  - `addr`: 終了アドレス（バイト列内）
- **戻り値**: 進めたサイズ
- **動作**:
  1. `end`として`static_cast<const std::byte*>(addr)`を取得
  2. `begin`として`ReadIter().base()`を取得
  3. `read_size`として`end - begin`を計算
  4. `Retrieve(read_size)`を呼び出し
- **副作用**: 読み取り位置が変更される

## 6. 処理フロー図

### 6.1 `Append(const void* data, std::size_t size)`
```mermaid
flowchart TD
    A[開始] --> B{size == 0?}
    B -- Yes --> C[終了]
    B -- No --> D[data != nullptr?]
    D -- No --> E[assert(false)]
    D -- Yes --> F[EnsureWriteableSize(size)]
    F --> G[base = reinterpret_cast<const std::byte*>(data)]
    G --> H[std::copy(base, base + size, WriteIter())]
    H --> I[HasWritten(size)]
    I --> J[assert(ReadableSize() >= size)]
    J --> K[終了]
```

### 6.2 `MakeSpace(std::size_t size)`
```mermaid
flowchart TD
    A[開始] --> B{WritableSize() + PrependableSize() < size?}
    B -- Yes --> C[buf_.resize(write_pos_ + size)]
    B -- No --> D[readable_size = ReadableSize()]
    D --> E[std::copy(ReadIter(), WriteIter(), buf_.begin())]
    E --> F[read_pos_ = 0]
    F --> G[write_pos_ = read_pos_ + readable_size]
    G --> H[assert(readable_size == ReadableSize())]
    H --> I[終了]
```

## 7. 状態遷移・副作用

### 7.1 バッファの状態管理
```markdown
| 操作 | 前提条件 | 副作用 |
|------|----------|--------|
| Append系メソッド | WritableSize() >= 必要サイズ | write_pos_が増加 |
| Retrieve系メソッド | ReadableSize() >= 要求サイズ | read_pos_が増加 |
| Clear() | - | read_pos_ = 0, write_pos_ = 0 |
| MakeSpace(size) | - | バッファ内容が移動、位置がリセット |
```

### 7.2 原子操作
- `read_pos_`と`write_pos_`は両方とも`std::atomic<std::size_t>`として宣言されているため、並行アクセスが安全

## 8. データ変換・制約

### 8.1 バイト列と文字列の相互変換
```markdown
| 変換方向 | メソッド | 注意事項 |
|----------|----------|----------|
| バイト → 文字列 | ReadableString() | reinterpret_cast<char*>を使用 |
| 文字列 → バイト | Append(std::string_view) | char*からstd::byteへの変換 |
```

### 8.2 サイズ制約
```markdown
| メソッド | 制約条件 |
|----------|----------|
| Append系 | WritableSize() >= 必要サイズ（EnsureWriteableSizeで確保） |
| Retrieve系 | ReadableSize() >= 要求サイズ |
```

## 9. 追加詳細設計情報

### 9.1 メモリ管理
- バッファは`std::vector<std::byte>`を使用して動的にメモリを管理
- `MakeSpace()`で必要に応じてバッファを拡張またはデータを移動

### 9.2 並行性
- `read_pos_`と`write_pos_`は原子変数として宣言されているため、マルチスレッド環境での安全な読み書きが可能
- ただし、バッファの内容自体へのアクセスは同期が必要

### 9.3 エラー処理
- `assert()`を使用して前提条件を検証（リリースビルドでは無効化される）
- 実際のエラー処理は行わない（例外も投げない）

## 10. 再実装に必要な具体的事実

### 10.1 型と定数
```markdown
| 名前 | 型 | 値/定義 |
|------|----|---------|
| NewLine::LF | NewLine | (未指定) |
| NewLine::CRLF | NewLine | (未指定) |
| Bufferデフォルトサイズ | std::size_t | 1000 |
```

### 10.2 具体的な式と演算
```markdown
| 操作 | 式 |
|------|----|
| 読み取り位置の計算 | buf_.begin() + read_pos_ |
| 書き込み位置の計算 | buf_.begin() + write_pos_ |
| 書き込み可能サイズ | buf_.size() - write_pos_ |
| 読み取り可能サイズ | write_pos_ - read_pos_ |
| 先頭に挿入可能サイズ | read_pos_ |
```

### 10.3 データアクセスパターン
```markdown
| メソッド | アクセスパターン |
|----------|------------------|
| ReadableBytes() | {ReadIter().base(), ReadableSize()} |
| WritableBytes() | {WriteIter().base(), WritableSize()} |
```

この設計仕様書は、与えられたソースコードから確認できる事実のみを記述しています。再実装時には、これらの情報に忠実に従ってください。