## 設計仕様書

### 全体概要

本設計仕様書は、`ws::io`名前空間における入出力ストリーム関連クラスの再実装のためのものです。このドキュメントでは、提供されたC++ソースコード（F01/U01, F02/U02）を解析し、別のLLMが再実装できるように詳細な設計情報を記述します。

### 1. 正確な定義

| 型名 | 種別 | 実体 |
|---|---|---|
| `ws::Buffer` | class |  `include/containers/buffer.h` で定義されたバッファクラス。バイト列を格納し、読み書き操作を提供する。 |
| `ws::io::IReader` | abstract class | `include/io.h`で定義されたリーダーインターフェース。`ReadFrom`メソッドを持つ。 |
| `ws::io::IWriter` | abstract class | `include/io.h`で定義されたライターインターフェース。`WriteTo`メソッドを持つ。 |
| `ws::io::IReadWriter` | abstract class | `include/io.h`で定義された読み書き両方のインターフェース。`IReader`と`IWriter`を継承する。 |
| `ws::io::Null` | class | `include/io.h`で定義された、何もしないリーダー・ライターの実装。`IReadWriter`を継承する。 |
| `ws::io::StringStream` | class | `include/io.h`で定義された、標準ストリームをラップしたリーダー・ライターの実装。`IReadWriter`を継承する。 |
| `ws::io::FileDescriptor` | class | `include/io.h`で定義された、ファイルディスクリプタをラップしたリーダー・ライターの実装。`IReadWriter`を継承する。 |
| `ws::FileDescriptor` | typedef |  `include/util.h` で定義された整数型。ファイルディスクリプタを表す。 |

### 2. 直接依存インターフェースと利用方法

#### ws::io::IReader

*   **メソッド:** `virtual std::size_t ReadFrom(Buffer& buf) = 0;`
    *   引数: `buf`: バッファへの参照。読み込んだデータを格納する。
    *   戻り値: 実際に読み込んだバイト数。
*   利用方法:  派生クラスでオーバーライドして、特定のデータソースからバッファへデータを読み込む処理を実装する。

#### ws::io::IWriter

*   **メソッド:** `virtual std::size_t WriteTo(Buffer& buf) = 0;`
    *   引数: `buf`: バッファへの参照。書き出すデータが格納されている。
    *   戻り値: 実際に書き込んだバイト数。
*   利用方法:  派生クラスでオーバーライドして、バッファから特定のデータシンクへデータを書き出す処理を実装する。

#### ws::io::IReadWriter

*   `IReader`と`IWriter`のインターフェースを組み合わせたもの。

#### std::istream & std::ostream (StringStream)

*   `StringStream`は、標準ストリーム(`std::istream`, `std::ostream`)を利用してデータの読み書きを行う。
*   コンストラクタで渡されたストリームオブジェクトが保持され、`ReadFrom`と`WriteTo`メソッド内で使用される。

#### ws::FileDescriptor (FileDescriptor)

*   `FileDescriptor`は、ファイルディスクリプタを表す整数型(`int`)をラップする。
*   コンストラクタで渡されたファイルディスクリプタが保持され、`ReadFrom`と`WriteTo`メソッド内で使用される。

### 3. 結果を決める式・具体値

*   `FileDescriptor::WriteTo`: `readv`関数の戻り値によって書き込みサイズを決定する。
*   `FileDescriptor::ReadFrom`: `write`関数の戻り値によって読み込みサイズを決定する。
*   `Buffer::EnsureWriteableSize`: 指定されたサイズが現在のバッファの空き容量よりも大きい場合、内部バッファを再確保する。

### 4. 使用データ・更新データ

*   **Buffer:**  内部ベクトル(`buf_`)にバイト列を格納し、読み込み位置(`read_pos_`)と書き込み位置(`write_pos_`)で管理される。
*   **StringStream:** `read_` と `write_` メンバ変数で保持される `std::istream` および `std::ostream` オブジェクトを使用する。
*   **FileDescriptor:**  `read_` と `write_` メンバ変数で保持されるファイルディスクリプタを使用する。

### 5. 状態・副作用・不変条件

*   **Buffer:** バッファの読み込み位置と書き込み位置は、データの読み書きによって更新される。
*   **FileDescriptor:** ファイルディスクリプタの状態は、`readv`および`write`システムコールによって変更される可能性がある。
*   **Null:** 状態を持たない。副作用も発生しない。

### 6. クラス図

```mermaid
classDiagram
    class ws::Buffer {
        - std::vector<std::byte> buf_
        - std::atomic<std::size_t> read_pos_
        - std::atomic<std::size_t> write_pos_
        + Buffer(std::size_t size)
        + Buffer(std::span<const std::byte> bytes)
        + Buffer(std::initializer_list<std::byte> bytes)
        + Buffer(std::string_view str)
        + WritableSize()
        + ReadableSize()
        + Peek()
        + ReadableBytes()
        + ReadableString()
        + WritableBytes()
        + Append(std::span<const std::byte> bytes)
        + Append(std::initializer_list<std::byte> bytes)
        + Append(std::string_view str, std::optional<NewLine>)
        + Append(const void* data, std::size_t size)
        + Append(const Buffer& buf)
        + EnsureWriteableSize(std::size_t size)
        + HasWritten(std::size_t size)
        + Retrieve(std::size_t size)
        + RetrieveUntil(const void* addr)
        + RetrieveAll()
        + RetrieveAllToString()
        + Clear()
        + Empty()
    }

    class ws::io::IReader {
        {abstract} + ReadFrom(Buffer& buf) = 0
    }

    class ws::io::IWriter {
        {abstract} + WriteTo(Buffer& buf) = 0
    }

    class ws::io::IReadWriter {
        {abstract}
    }

    class ws::io::Null {
        + WriteTo(Buffer& buf)
        + ReadFrom(Buffer& buf)
    }

    class ws::io::StringStream {
        - std::istream& read_
        - std::ostream& write_
        + StringStream(std::istream& read, std::ostream& write)
        + WriteTo(Buffer& buf)
        + ReadFrom(Buffer& buf)
    }

    class ws::io::FileDescriptor {
        - ws::FileDescriptor read_
        - ws::FileDescriptor write_
        + FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write)
        + WriteTo(Buffer& buf)
        + ReadFrom(Buffer& buf)
    }

    IReadWriter --|> IReader
    IReadWriter --|> IWriter
    Null --|> IReadWriter
    StringStream --|> IReadWriter
    FileDescriptor --|> IReadWriter
```

### 7. クラス・メソッド・インターフェース詳細

| Class/Method | Signature | Description |
|---|---|---|
| `ws::Buffer` | `Buffer(std::size_t size)` | バッファを初期化。指定されたサイズの内部バッファを作成する。 |
| `ws::Buffer` | `Buffer(std::span<const std::byte> bytes)` | バッファを初期化。指定されたバイト列で内部バッファを埋める。 |
| `ws::Buffer` | `Buffer(std::initializer_list<std::byte> bytes)` | バッファを初期化。指定されたバイト列で内部バッファを埋める。 |
| `ws::Buffer` | `Buffer(std::string_view str)` | バッファを初期化。指定された文字列のバイト列で内部バッファを埋める。 |
| `ws::Buffer` | `WritableSize() const noexcept` | バッファの書き込み可能なサイズを返す。 |
| `ws::Buffer` | `ReadableSize() const noexcept` | バッファの読み取り可能なサイズを返す。 |
| `ws::io::Null::WriteTo(Buffer& buf) noexcept override` | `std::size_t WriteTo(Buffer& buf) noexcept` | 何もしないで、書き込みサイズを返す。 |
| `ws::io::Null::ReadFrom(Buffer& buf) noexcept override` | `std::size_t ReadFrom(Buffer& buf) noexcept` | バッファの内容全体を読み取り済みとしてマークし、そのサイズを返す。 |
| `ws::io::StringStream::StringStream(std::istream& read, std::ostream& write)` | `explicit StringStream(std::istream& read, std::ostream& write) noexcept` | ストリームをラップしてバッファを作成する。 |
| `ws::io::StringStream::WriteTo(Buffer& buf) noexcept override` | `std::size_t WriteTo(Buffer& buf) noexcept` | 入力ストリームから文字列を読み込み、バッファに追加する。 |
| `ws::io::StringStream::ReadFrom(Buffer& buf) noexcept override` | `std::size_t ReadFrom(Buffer& buf) noexcept` | バッファの内容を文字列として取得し、出力ストリームに書き込む。 |
| `ws::io::FileDescriptor::FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write)` | `explicit FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept` | ファイルディスクリプタをラップしてバッファを作成する。 |
| `ws::io::FileDescriptor::WriteTo(Buffer& buf) override` | `std::size_t WriteTo(Buffer& buf)` | バッファの内容をファイルに書き込む。 |
| `ws::io::FileDescriptor::ReadFrom(Buffer& buf) override` | `std::size_t ReadFrom(Buffer& buf)` | ファイルからデータを読み込み、バッファに追加する。 |

### 8. シーケンス図

（シーケンス図は複雑になるため省略。必要に応じて、特定のユースケースにおけるクラス間の相互作用を示す図を作成すること。）

### 9. メソッド仕様書

(上記「クラス・メソッド・インターフェース詳細」に記載)
