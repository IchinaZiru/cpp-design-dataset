## 責務
- `IReader` インターフェース: バッファからデータを読み取る機能を提供する。
- `IWriter` インターフェース: バッファにデータを書き込む機能を提供する。
- `IReadWriter` インターフェース: 読み取りと書き込みの両方の機能を提供する。
- `Null` クラス: バッファの読み取り可能な領域や書き込み可能な領域を消費するが、実際には何も読み書きしない。
- `StringStream` クラス: 文字列ストリームからバッファへデータを読み取り、バッファから文字列ストリームへデータを書き込む機能を提供する。
- `FileDescriptor` クラス: ファイルディスクリプタを使用してバッファとデータのやりとりを行う。

## 公開インターフェース
- `IReader::ReadFrom(Buffer& buf)`: バッファからデータを読み取る。
- `IWriter::WriteTo(Buffer& buf)`: バッファにデータを書き込む。
- `Null::WriteTo(Buffer& buf)`: バッファの書き込み可能な領域を消費する。
- `Null::ReadFrom(Buffer& buf)`: バッファの読み取り可能な領域を消費する。
- `StringStream::StringStream(std::istream& read, std::ostream& write)`: 文字列ストリームとバッファとのやりとりを行うオブジェクトを作成する。
- `StringStream::WriteTo(Buffer& buf)`: バッファから文字列ストリームへデータを書き込む。
- `StringStream::ReadFrom(Buffer& buf)`: 文字列ストリームからバッファへデータを読み取る。
- `FileDescriptor::FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write)`: ファイルディスクリプタとバッファとのやりとりを行うオブジェクトを作成する。
- `FileDescriptor::WriteTo(Buffer& buf)`: バッファからファイルディスクリプタへデータを書き込む。
- `FileDescriptor::ReadFrom(Buffer& buf)`: ファイルディスクリプタからバッファへデータを読み取る。

## 入力
- `IReader::ReadFrom(Buffer& buf)`: 読み取り対象のバッファ。
- `IWriter::WriteTo(Buffer& buf)`: 書き込み対象のバッファ。
- `StringStream::StringStream(std::istream& read, std::ostream& write)`: バッファとやりとりするための読み取り用と書き込み用の文字列ストリーム。
- `FileDescriptor::FileDescriptor(ws::FileDescriptor read, ws::FileDescriptor write)`: バッファとやりとりするための読み取り用と書き込み用のファイルディスクリプタ。

## 出力
- `IReader::ReadFrom(Buffer& buf)`: 読み取ったバイト数。
- `IWriter::WriteTo(Buffer& buf)`: 書き込んだバイト数。
- `Null::WriteTo(Buffer& buf)`: 消費した書き込み可能なバッファのサイズ。
- `Null::ReadFrom(Buffer& buf)`: 消費した読み取り可能なバッファのサイズ。
- `StringStream::WriteTo(Buffer& buf)`: 文字列ストリームからバッファへ書き込んだ文字数。
- `StringStream::ReadFrom(Buffer& buf)`: バッファから文字列ストリームへ読み取った文字数。
- `FileDescriptor::WriteTo(Buffer& buf)`: ファイルディスクリプタからバッファへ読み取ったバイト数。
- `FileDescriptor::ReadFrom(Buffer& buf)`: バッファからファイルディスクリプタへ書き込んだバイト数。

## 状態
- `StringStream` クラス: 読み取り用と書き込み用の文字列ストリームへの参照を保持する。
- `FileDescriptor` クラス: 読み取り用と書き込み用のファイルディスクリプタを保持する。

## 処理手順
- `Null::WriteTo(Buffer& buf)`: バッファの書き込み可能なサイズを取得し、そのサイズ分バッファの書き込み位置を進める。
- `Null::ReadFrom(Buffer& buf)`: バッファから全てのデータを取り出し、読み取り位置を最後まで進める。
- `StringStream::WriteTo(Buffer& buf)`: 文字列ストリームから文字列を読み取り、バッファに追加する。
- `StringStream::ReadFrom(Buffer& buf)`: バッファから全てのデータを取り出し、それを文字列ストリームへ書き込む。
- `FileDescriptor::WriteTo(Buffer& buf)`: ファイルディスクリプタからデータを読み取り、バッファに追加する。バッファが十分な空きがない場合は追加のバッファを使用して読み取ったデータを保持し、その後バッファへ追加する。
- `FileDescriptor::ReadFrom(Buffer& buf)`: バッファからデータを取り出し、ファイルディスクリプタに書き込む。

## 例外・失敗条件
- `FileDescriptor::WriteTo(Buffer& buf)`: `readv` 関数がエラーを返した場合、システムエラーをスローする。
- `FileDescriptor::ReadFrom(Buffer& buf)`: `write` 関数がエラーを返した場合、システムエラーをスローする。

## 依存関係
- `Buffer` クラス: バッファの操作に使用される。
- `util.h`: システムエラー処理に使用される（`ThrowLastSystemError()` 関数）。
- `<iostream>`: 文字列ストリームの読み書きに使用される。
- `<sys/uio.h>`: ファイルディスクリプタからのデータ読み取りに `readv` 関数を使用する。
- `<unistd.h>`: ファイルディスクリプタへのデータ書き込みに `write` 関数を使用する。

## 重要な不変条件
- `StringStream` クラス: 文字列ストリームへの参照は有効である必要がある。
- `FileDescriptor` クラス: ファイルディスクリプタは有効である必要がある。