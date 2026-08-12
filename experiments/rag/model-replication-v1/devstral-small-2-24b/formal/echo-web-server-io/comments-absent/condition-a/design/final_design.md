以下は、与えられたC++ソースコードを解析し、別のLLMが再実装できるように設計仕様書を作成したものです。

---

# 設計仕様書: I/Oインターフェース

## 概要
この仕様書は、入出力操作のための抽象インターフェースとその具体的な実装について記述します。主にバッファベースの読み書き操作を提供するクラス群です。

## 1. 型定義

### 1.1 依存関係
- `ws::Buffer`: バッファ操作のためのクラス（外部定義）
- `ws::FileDescriptor`: ファイルディスクリプタ型（外部定義）

### 1.2 インターフェース

#### IReader
```cpp
namespace ws::io {
class IReader {
public:
    virtual ~IReader() noexcept = default;
    virtual std::size_t ReadFrom(Buffer& buf) = 0;
};
}
```
- 説明: バッファからの読み込み操作を提供するインターフェース
- メソッド:
  - `ReadFrom`: バッファにデータを読み込む。戻り値は読み込んだバイト数。

#### IWriter
```cpp
namespace ws::io {
class IWriter {
public:
    virtual ~IWriter() noexcept = default;
    virtual std::size_t WriteTo(Buffer& buf) = 0;
};
}
```
- 説明: バッファへの書き込み操作を提供するインターフェース
- メソッド:
  - `WriteTo`: バッファからデータを書き出す。戻り値は書き出したバイト数。

#### IReadWriter
```cpp
namespace ws::io {
class IReadWriter : public virtual IReader, public virtual IWriter {};
}
```
- 説明: 読み書き両方の操作を提供するインターフェース（仮想継承）

## 2. 具体的実装

### Null
```cpp
namespace ws::io {
class Null : public virtual IReadWriter {
public:
    std::size_t WriteTo(Buffer& buf) noexcept override;
    std::size_t ReadFrom(Buffer& buf) noexcept override;
};
}
```
- 説明: データを消費せずにダミーの読み書き操作を行うクラス
- 実装:
  - `WriteTo`: バッファの書き込み可能領域全てを"書き込んだ"と見なす（実際には何もしない）
  - `ReadFrom`: バッファからデータを取り出し、そのサイズを返す

### StringStream
```cpp
namespace ws::io {
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
}
```
- 説明: ストリームを介した読み書き操作を行うクラス
- 実装:
  - `WriteTo`: `read_`から文字列を読み込み、バッファに追加する
  - `ReadFrom`: バッファの内容を`write_`に出力する

### FileDescriptor
```cpp
namespace ws::io {
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
}
```
- 説明: ファイルディスクリプタを介した読み書き操作を行うクラス
- 実装:
  - `WriteTo`: `read_`からデータを読み込み、バッファに追加する（必要に応じて拡張バッファを使用）
  - `ReadFrom`: バッファの内容を`write_`に書き出す

## 3. 実装上の注意点
1. 仮想継承を使用しているため、ダイヤモンド問題に注意すること。
2. コピー/ムーブ演算子は明示的に削除されているため、インスタンスは移動できない。
3. `FileDescriptor`クラスではシステムコール（`readv`/`write`）を使用しているため、エラー処理に注意すること。

## 4. 外部依存
- `util.h`: `ThrowLastSystemError()`関数の定義が必要。
- `containers/buffer.h`: `Buffer`クラスの定義が必要。

---

この仕様書を基に、別のLLMでも同じ機能を持つコードを再実装できるはずです。