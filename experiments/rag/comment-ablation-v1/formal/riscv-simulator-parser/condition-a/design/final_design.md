# デザイン仕様書

## 概要
この設計仕様書は、`Parser` クラスの再実装を目的としています。元のソースコードから抽出した `F01/U01` 単位のみが再実装対象となります。

## 対象範囲
- ファイルパス: `src/Common/Parser.hpp`
- クラス名: `Parser`

## 必要な機能
`Parser` クラスは、入力ストリームからデータを読み取り、それをメモリに書き込む機能を持っています。具体的には以下の2つの静的メソッドが定義されています。

1. **parse_hex メソッド**
   - 機能: 16進数文字列を符号なし整数に変換します。
   - 引数:
     - `const std::string &hex`: 変換したい16進数文字列
   - 戻り値: 変換後の符号なし整数

2. **parse メソッド**
   - 機能: 入力ストリームからデータを読み取り、それをメモリに書き込みます。各行が `@` で始まる場合はベースアドレスとして解釈し、それ以外の行は16進数データと見なします。
   - 引数:
     - `std::istream &in`: 入力ストリーム
     - `Memory &mem`: 書き込み先メモリオブジェクト

3. **parse_hex メソッド (オーバーロード)**
   - 機能: 入力ストリームから16進数データを読み取り、それを4バイト単位でメモリに書き込みます。
   - 引数:
     - `std::istream &in`: 入力ストリーム
     - `Memory &mem`: 書き込み先メモリオブジェクト

## クラス定義
`Parser` クラスは以下の通りです。

```cpp
class Parser {
public:
    static unsigned parse_hex(const std::string &hex);
    static void parse(std::istream &in, Memory &mem);
    static void parse_hex(std::istream &in, Memory &mem);
};
```

## メソッド詳細

### 1. `parse_hex` メソッド
- **シグネチャ**: `static unsigned parse_hex(const std::string &hex)`
- **機能**: 与えられた16進数文字列を符号なし整数に変換します。
- **引数**:
  - `const std::string &hex`: 変換したい16進数文字列
- **戻り値**: 変換後の符号なし整数

### 2. `parse` メソッド
- **シグネチャ**: `static void parse(std::istream &in, Memory &mem)`
- **機能**: 入力ストリームからデータを読み取り、それをメモリに書き込みます。各行が `@` で始まる場合はベースアドレスとして解釈し、それ以外の行は16進数データと見なします。
- **引数**:
  - `std::istream &in`: 入力ストリーム
  - `Memory &mem`: 書き込み先メモリオブジェクト

### 3. `parse_hex` メソッド (オーバーロード)
- **シグネチャ**: `static void parse_hex(std::istream &in, Memory &mem)`
- **機能**: 入力ストリームから16進数データを読み取り、それを4バイト単位でメモリに書き込みます。
- **引数**:
  - `std::istream &in`: 入力ストリーム
  - `Memory &mem`: 書き込み先メモリオブジェクト

## 注意事項
- `Fxx/Uxx` 識別子は不透明であり、名前、型、シグネチャ、名前空間、置換境界を保持する必要があります。
- 再実装対象外の単位（REFERENCE-ONLY INPUTS）は出力に含まれるべきではありません。

## 依存関係
- `std::string`
- `std::istream`
- `std::stringstream`
- `std::cerr`
- `Memory` クラス (外部定義)

この仕様書に基づいて、`Parser` クラスを再実装してください。