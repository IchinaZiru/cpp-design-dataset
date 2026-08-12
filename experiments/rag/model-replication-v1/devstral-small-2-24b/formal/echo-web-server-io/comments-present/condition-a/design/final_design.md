以下は、与えられたC++ソースコードを基にした詳細な設計仕様書です。この仕様書は、別のLLMが再実装できるように作成されています。

---

# 設計仕様書: I/O オブジェクト

## 概要
この仕様書は、`ws::io` 名前空間内のI/Oオブジェクトを定義します。これらのオブジェクトはバッファとの読み書き操作をサポートします。

## 依存関係
- `include/util.h`: エラーハンドリング機能（`ThrowLastSystemError()`）を提供する。
- `src/containers/buffer.h`: バッファクラスを定義する。

## 名前空間構造
```cpp
namespace ws {
    class Buffer;  // 前方宣言

    namespace io {
        // I/Oインターフェースと実装クラス
    }
}
```

## クラス定義

### `IReader`
**役割**: バッファからの読み取り操作を抽象化するインターフェース。

```cpp
class IReader {
public:
    virtual ~IReader() noexcept = default;
    virtual std::size_t ReadFrom(Buffer& buf) = 0;
};
```

### `IWriter`
**役割**: バッファへの書き込み操作を抽象化するインターフェース。

```cpp
class IWriter {
public:
    virtual ~IWriter() noexcept = default;
    virtual std::size_t WriteTo(Buffer& buf) = 0;
};
```

### `IReadWriter`
**役割**: 読み書き両方の操作をサポートするインターフェース。

```cpp
class IReadWriter : public virtual IReader, public virtual IWriter {};
```

---

## 実装クラス

### `Null`
**役割**: バッファの読み書きスペースを消費するだけで、実際にはデータを読み書きしないダミーI/O。

```cpp
class Null : public virtual IReadWriter {
public:
    std::size_t WriteTo(Buffer& buf) noexcept override;
    std::size_t ReadFrom(Buffer& buf) noexcept override;
};
```

#### メソッド仕様
- `WriteTo`: バッファの書き込み可能サイズを消費し、そのサイズを返す。
- `ReadFrom`: バッファから読み取り可能なデータを全て取得し、そのサイズを返す。

---

### `StringStream`
**役割**: `std::istream`/`std::ostream`とバッファ間のI/O操作を橋渡しする。

```cpp
class StringStream : public virtual IReadWriter {
public:
    explicit StringStream(std::istream& read, std::ostream& write) noexcept;
    // コピー/ムーブ禁止

    std::size_t WriteTo(Buffer& buf) noexcept override;
    std::size_t ReadFrom(Buffer& buf) noexcept override;

private:
    std::istream& read_;
    std::ostream& write_;
};
```

#### メソッド仕様
- `WriteTo`:
  - `read_`から文字列を読み取り、バッファに追加する。
  - 読み取った文字数を返す。
- `ReadFrom`:
  - バッファから全てのデータを文字列として取得し、`write_`に書き込む。
  - 書き込んだ文字数を返す。

---

### `FileDescriptor`
**役割**: ファイルディスクリプタとバッファ間のI/O操作を橋渡しする。

```cpp
class FileDescriptor : public virtual IReadWriter {
public:
    explicit FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept;
    // コピー/ムーブ禁止

    std::size_t WriteTo(Buffer& buf) override;
    std::size_t ReadFrom(Buffer& buf) override;

private:
    ws::FileDescriptor read_;
    ws::FileDescriptor write_;
};
```

#### メソッド仕様
- `WriteTo`:
  - バッファの書き込み可能領域を読み取り、データをバッファに追加する。
  - 読み取ったバイト数を返す。
  - 追加バッファ (`ext_bytes`) を使用して、バッファが小さい場合でもデータを読み取る。
- `ReadFrom`:
  - バッファから読み取り可能なデータを書き込む。
  - 書き込んだバイト数を返す。

---

## 注意事項
1. **名前の保持**: `Fxx/Uxx`識別子はそのまま使用する。
2. **依存関係**: `Buffer`クラスは前方宣言のみで、実装は外部に委ねる。
3. **エラーハンドリング**: システムエラー発生時は`ThrowLastSystemError()`を呼び出す。

---

## 例
```cpp
// 使用例（参考）
ws::io::StringStream io(std::cin, std::cout);
ws::Buffer buf;
io.WriteTo(buf);  // 標準入力からバッファに書き込む
io.ReadFrom(buf); // バッファから標準出力に読み取る
```

この仕様書を基に、別のLLMが再実装を行うことができます。