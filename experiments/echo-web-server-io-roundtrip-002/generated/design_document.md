# デザイン文書: I/Oモジュール

## 概要
このドキュメントは、`io.h`と`io.cpp`で定義されているI/O操作に関する設計を記述します。主な機能はバッファとの読み書きです。

## 責務
- バッファからのデータの読み取りとバッファへのデータの書き込みを行う。
- さまざまな入出力ソース（文字列ストリーム、ファイルディスクリプタ）に対応する。

## 公開インターフェース

### クラス: IReader
- **メソッド**: `std::size_t ReadFrom(Buffer& buf)`
  - バッファからデータを読み取ります。
  
### クラス: IWriter
- **メソッド**: `std::size_t WriteTo(Buffer& buf)`
  - バッファにデータを書き込みます。

### クラス: IReadWriter
- **継承**: `public virtual IReader, public virtual IWriter`
  - 読み取りと書き込みの両方を行うインターフェースです。

### クラス: Null
- **継承**: `public virtual IReadWriter`
- **メソッド**:
  - `std::size_t WriteTo(Buffer& buf) noexcept`: バッファの書き込み可能なスペースを消費しますが、実際には何も書き込みません。
  - `std::size_t ReadFrom(Buffer& buf) noexcept`: バッファから読み取り可能なデータを全て消費しますが、実際には何も読み取りません。

### クラス: StringStream
- **継承**: `public virtual IReadWriter`
- **コンストラクタ**: `StringStream(std::istream& read, std::ostream& write) noexcept`
  - 文字列ストリームの参照を受け取ります。
- **メソッド**:
  - `std::size_t WriteTo(Buffer& buf) noexcept`: バッファから文字列を読み取り、指定された出力文字列ストリームに書き込みます。
  - `std::size_t ReadFrom(Buffer& buf) noexcept`: 指定された入力文字列ストリームから文字列を読み取り、バッファに追加します。

### クラス: FileDescriptor
- **継承**: `public virtual IReadWriter`
- **コンストラクタ**: `FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write) noexcept`
  - ファイルディスクリプタを受け取ります。
- **メソッド**:
  - `std::size_t WriteTo(Buffer& buf)`: バッファからデータを読み取り、指定されたファイルディスクリプタに書き込みます。
  - `std::size_t ReadFrom(Buffer& buf)`: 指定されたファイルディスクリプタからデータを読み取り、バッファに追加します。

## 入力
- **Buffer**: データの読み書き対象となるバッファオブジェクト。
- **std::istream**: 文字列ストリームからの入力ソース。
- **std::ostream**: 文字列ストリームへの出力先。
- **ws::FileDescriptor**: ファイルディスクリプタの読み書き対象。

## 出力
- `std::size_t`: 読み取ったバイト数または書き込んだバイト数を返します。

## 状態
- 各クラスは内部状態を持たないが、`Buffer`オブジェクトの状態に依存します。
- `StringStream`と`FileDescriptor`は外部リソース（文字列ストリームやファイルディスクリプタ）への参照を保持します。

## 処理手順
1. **Null::WriteTo**: バッファの書き込み可能なスペースを消費し、そのサイズを返します。
2. **Null::ReadFrom**: バッファから読み取り可能なデータを全て消費し、そのサイズを返します。
3. **StringStream::WriteTo**: 文字列ストリームから文字列を読み取り、バッファに追加します。追加した文字列の長さを返します。
4. **StringStream::ReadFrom**: バッファから文字列を取得し、文字列ストリームに出力します。出力した文字列の長さを返します。
5. **FileDescriptor::WriteTo**: ファイルディスクリプタからデータを読み取り、バッファに追加します。追加したデータのサイズを返します。
6. **FileDescriptor::ReadFrom**: バッファからデータを取得し、ファイルディスクリプタに出力します。出力したデータのサイズを返します。

## 例外・失敗条件
- `StringStream`と`FileDescriptor`のメソッドは、入出力操作に失敗した場合にシステムエラーを投げます。
- ファイルディスクリプタが無効な場合やバッファのサイズが不適切な場合など、具体的な例外条件は実装コードで定義されています。

## 依存関係
- **Buffer**: `io`モジュールは`containers/buffer.h`に定義された`Buffer`クラスに依存します。
- **util.h**: システムエラーを投げるためのユーティリティ関数（`ThrowLastSystemError()`）が含まれています。

## 重要な不変条件
- `StringStream`と`FileDescriptor`は、コンストラクタで受け取った入出力ソースへの参照を保持し、それらが有効であることを保証します。
- バッファの読み取り可能なデータや書き込み可能なスペースは、それぞれのメソッドによって適切に更新されます。