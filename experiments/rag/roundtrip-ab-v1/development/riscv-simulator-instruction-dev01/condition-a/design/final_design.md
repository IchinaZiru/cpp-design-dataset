# デザイン仕様書

## 概要
この設計仕様書は、与えられたC++ソースコードを再実装するための詳細なガイドラインを提供します。ソースコードはRISC-Vシミュレータの命令処理部分を含んでおり、ヘッダーファイルとして機能します。

## 対象入力
### REPLACEMENT UNITS:
- **F01/U01**
  - パス: `src/Common/Instruction.hpp`
  - 役割: 完全なヘッダーオンリーターゲットの実装と宣言
  - 置換必要: true

### REFERENCE-ONLY INPUTS:
- none

## REPLACEMENT UNIT CONTRACT
- **置換対象**: `replacement_required=true`が設定されているユニットのみがコード再生成と置換の対象となります。
- **参照専用**: `replacement_required=false`が設定されているユニットは、既存コードとして利用できますが再生成してはいけません。

## 詳細仕様

### ファイル: Instruction.hpp
#### 概要
このヘッダーファイルはRISC-Vシミュレータの命令処理部分を定義しています。命令の種類（R型、I型、S型、B型、U型、J型）に対応する構造体と、それらの命令を解析・生成するための関数が含まれています。

#### インクルードファイル
- `<utility>`
- `"Common.h"`
- `<string>`
- `<iostream>`

#### 型定義
- `Instruction`: `unsigned int`型

#### 構造体: InstructionBase
**役割**: すべての命令種類で共通するフィールドとメソッドを提供します。

##### メンバ変数:
- `opcode`: 命令コード (6ビット)
- `rs1`, `rs2`, `rd`: レジスタ番号
- `funct3`, `funct7`: 機能フィールド
- `imm`: 即値
- `inst`: 完全な命令を表す整数値
- `t`: 命令の型 (R, I, S, B, U, J)

##### メンバ関数:
- **コンストラクタ**:
  - `InstructionBase()`: 各フィールドを初期化します。
  - `InstructionBase(unsigned)`: 特定の命令コードを持つI型命令として初期化します。

- **静的メソッド**:
  - `nop()`: NOP命令を生成して返します。
  - `bin_mask(int digits)`: 指定されたビット数に対応するマスク値を計算します。
  - `get_digits(unsigned int n, int hi, int lo)`: 整数nから指定された範囲のビットを取り出します。
  - `expand_digit(unsigned int digit, int lo)`: 指定されたビットが1の場合、その位置から上位ビットを1に設定した値を返します。

- **インスタンスメソッド**:
  - `is_nop()`: NOP命令であるかどうかを判定します。
  - `is_valid(const std::string &key)`: 指定されたキーが現在の命令型で有効なフィールドであるかを判定します。
  - `verify(const std::string &key)`: 指定されたキーが無効な場合、`InvalidAccess`例外をスローします。
  - `debug()`: 命令の詳細情報を出力します。
  - `has_op1()`: 命令にオペランド1が必要かどうかを判定します。
  - `has_op2()`: 命令にオペランド2が必要かどうかを判定します。

##### クラス: InvalidAccess
- **役割**: 無効なフィールドアクセス時にスローされる例外クラスです。

#### 構造体: InstructionR, InstructionI, InstructionS, InstructionB, InstructionU, InstructionJ
**役割**: 各命令型（R型、I型、S型、B型、U型、J型）に対応する構造体で、`InstructionBase`を継承しています。

##### コンストラクタ:
- `InstructionX(const Instruction &inst)`: 命令コードから各フィールドを解析して初期化します。ここでXはR, I, S, B, U, Jのいずれかです。

## まとめ
この設計仕様書では、`Instruction.hpp`ファイルの構造と機能について詳細に説明しました。再実装を行う際には、これらの仕様を基に新たなコードを生成し、既存の参照専用部分は変更せずに利用してください。