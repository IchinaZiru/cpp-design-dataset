# デザイン文書: Instructionモジュール

## 概要
この設計文書は、RISC-Vアーキテクチャの命令を表す`Instruction`モジュールについて記述します。このモジュールは命令の解析とデバッグ出力を行うためのクラス群で構成されています。

## 責務
- RISC-Vアーキテクチャの命令を解析し、その内容をメンバ変数に格納する。
- 命令の種類（R型、I型、S型、B型、U型、J型）に応じて適切なフィールドを設定する。
- 命令のデバッグ情報を出力する。

## 公開インターフェース
### クラス: InstructionBase
#### メンバ変数
- `unsigned opcode`: 命令コード
- `unsigned rs1, rs2, rd`: 一般レジスタ番号（ソース1、ソース2、デスト）
- `Immediate imm`: 即値
- `unsigned funct3, funct7`: 機能フィールド
- `Instruction inst`: 原始命令データ
- `enum Type t`: 命令の型

#### メンバ関数
- `InstructionBase()`: デフォルトコンストラクタ。NOP命令を初期化する。
- `InstructionBase(unsigned)`: NOP命令を初期化する特別なコンストラクタ。
- `static InstructionBase nop()`: NOP命令を作成して返す静的メソッド。
- `bool is_nop()`: このインスタンスがNOP命令であるか判定する。
- `static constexpr unsigned int bin_mask(int digits)`: 指定されたビット数のマスクを生成する。
- `static unsigned int get_digits(unsigned int n, int hi, int lo)`: ビットフィールドから指定範囲の値を取り出す。
- `static unsigned int expand_digit(unsigned int digit, int lo)`: 符号拡張を行う。
- `bool is_valid(const std::string &key)`: 指定されたキーが現在の命令型に有効か判定する。
- `void verify(const std::string &key)`: 指定されたキーが無効な場合、例外を投げる。
- `void debug()`: 命令のデバッグ情報を出力する。
- `bool has_op1()`: この命令にオペランド1があるか判定する。
- `bool has_op2()`: この命令にオペランド2があるか判定する。

### クラス: InstructionR, InstructionI, InstructionS, InstructionB, InstructionU, InstructionJ
#### コンストラクタ
- 各クラスは、与えられた命令データから必要なフィールドを抽出し初期化します。

## 入力
- `Instruction`型の命令データ

## 出力
- 命令の解析結果（メンバ変数）
- デバッグ情報（標準出力）

## 状態
- 各命令クラスのインスタンスは、命令データを解析してメンバ変数に格納します。

## 処理手順
1. コンストラクタが呼び出される。
2. 命令データから必要なフィールド（opcode, rs1, rs2, rd, funct3, funct7, imm）を抽出し、メンバ変数に設定する。
3. 必要に応じて符号拡張を行う。

## 例外・失敗条件
- `verify()`メソッドが呼び出され、指定されたキーが無効な場合、`InvalidAccess`例外が投げられる。

## 依存関係
- `Common.h`: 型定義や共通のユーティリティ関数を提供する。
- `<utility>`: 標準ライブラリのユーティリティ機能を使用する。
- `<string>`: 文字列操作に使用する。
- `<iostream>`: デバッグ情報出力に使用する。

## 重要な不変条件
- 各命令クラスは、自身の型に対応するフィールドのみを設定し、他のフィールドは適切な初期値（通常0）に設定される。
- `inst`メンバ変数は、コンストラクタで与えられた命令データと一致する。