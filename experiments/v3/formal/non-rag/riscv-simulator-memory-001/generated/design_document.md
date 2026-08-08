# 対象
- target: Memory
- granularity: target_span
- target_kind: class
- target_symbol: Memory

# 対象範囲
元コード全体は対象部分を理解するための文脈として参照してください。
設計文書はtarget_symbolで指定した対象部分だけについて作成してください。
対象外の関数やクラスは、対象部分との関係を説明する場合に限って記載してください。

# 基本設計項目の出力構成（全条件共通・固定）

## 責務
`Memory` クラスは、指定されたメモリサイズを持つメモリ空間を提供し、そのメモリへの読み書き操作を行います。また、アドレス範囲チェックとデバッグ用の出力機能も備えています。

## 公開インターフェース
- `Memory()`: メモリを初期化するコンストラクタ。
- `bool check_addr(unsigned int addr)`: 指定されたアドレスが有効範囲内であるかチェックします。
- `Immediate read_word(unsigned int addr)`: 指定されたアドレスからワード（4バイト）を読み出します。
- `void write_word(unsigned int addr, Immediate imm)`: 指定されたアドレスにワード（4バイト）を書き込みます。
- `unsigned short read_ushort(unsigned int addr)`: 指定されたアドレスからハーフワード（2バイト）を読み出します。
- `void write_ushort(unsigned int addr, unsigned short imm)`: 指定されたアドレスにハーフワード（2バイト）を書き込みます。
- `unsigned char &operator[](unsigned int addr)`: 指定されたアドレスのメモリへの参照を返します。
- `void debug()`: メモリの特定範囲をデバッグ出力します。

## 入力
- `Memory()` コンストラクタ: なし（内部で初期化）
- `check_addr(unsigned int addr)`: アドレス値 (`unsigned int`)
- `read_word(unsigned int addr)`: アドレス値 (`unsigned int`)
- `write_word(unsigned int addr, Immediate imm)`: アドレス値 (`unsigned int`)、書き込むワード値 (`Immediate`)
- `read_ushort(unsigned int addr)`: アドレス値 (`unsigned int`)
- `write_ushort(unsigned int addr, unsigned short imm)`: アドレス値 (`unsigned int`)、書き込むハーフワード値 (`unsigned short`)
- `operator[](unsigned int addr)`: アドレス値 (`unsigned int`)

## 出力
- `check_addr(unsigned int addr)`: ブール値 (`bool`)
- `read_word(unsigned int addr)`: ワード値 (`Immediate`)
- `write_word(unsigned int addr, Immediate imm)`: なし（副作用あり）
- `read_ushort(unsigned int addr)`: ハーフワード値 (`unsigned short`)
- `write_ushort(unsigned int addr, unsigned short imm)`: なし（副作用あり）
- `operator[](unsigned int addr)`: メモリの参照 (`unsigned char &`)
- `debug()`: なし（標準出力への副作用あり）

## 状態
- `mem[MEMORY_SIZE]`: メモリ空間を表す配列。
- `placeholder`: アドレス範囲外アクセス時のダミー値。

## 処理手順
1. **初期化**: コンストラクタが呼び出されると、`mem` 配列全体がゼロで初期化されます。
2. **アドレスチェック**: 各読み書き操作前に `check_addr` が呼び出され、アドレスが有効範囲内であるか確認します。
3. **データ読み込み**:
   - `read_word`: アドレスが有効な場合、指定された位置からワード（4バイト）を読み取ります。
   - `read_ushort`: アドレスが有効な場合、指定された位置からハーフワード（2バイト）を読み取ります。
4. **データ書き込み**:
   - `write_word`: アドレスが有効な場合、指定されたワード値をメモリの該当位置に書き込みます。
   - `write_ushort`: アドレスが有効な場合、指定されたハーフワード値をメモリの該当位置に書き込みます。
5. **デバッグ出力**: `debug` メソッドは、特定範囲のメモリ内容を16進数形式で標準出力します。

## 例外・失敗条件
- アドレスが有効範囲外の場合:
  - `check_addr`: `false` を返します。
  - `read_word`, `write_word`, `read_ushort`, `write_ushort`: 操作を行わず、デフォルト値（0やダミー参照）を返します。

## 依存関係
- `Common.h`: システム全体の共通定義を含むヘッダファイル。
- `<cstring>`: `memset` 関数を使用しています。
- `<iostream>`: デバッグ出力用に `std::cout` を使用しています。
- `<cassert>`: アサーション機能を使用しています（現状ではコメントアウトされています）。

## 重要な不変条件
- `mem` 配列のサイズは常に `MEMORY_SIZE` (0x400000) です。
- `check_addr` メソッドが `true` を返す場合のみ、メモリへの読み書き操作が行われます。