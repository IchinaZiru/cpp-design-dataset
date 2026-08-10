# デザイン仕様書

## 概要
この設計仕様書は、与えられたC++ソースコードを再実装するための詳細なガイドラインを提供します。ソースコードはRISC-Vシミュレータの命令処理に関連しています。

## 対象入力
### REPLACEMENT UNITS:
- **F01/U01**
  - パス: `src/Common/Instruction.hpp`
  - 役割: 完全なヘッダオンリーターゲット実装と宣言
  - 置換必要: true

### REFERENCE-ONLY INPUTS:
- none

## REPLACEMENT UNIT CONTRACT
- **置換対象**: `replacement_required=true`のunitのみがコード再生成と置換の対象となります。
- **参照専用**: `replacement_required=false`のunitは参照専用で、既存コードとして利用できますが再生成してはいけません。

## 詳細仕様

### ファイル: Instruction.hpp
#### 概要
このヘッダファイルはRISC-Vシミュレータにおいて命令を処理するための基本的な構造体とクラスを定義しています。主に命令の解析、検証、デバッグ機能が含まれています。

#### クラス・構造体定義

1. **InstructionBase**
   - **役割**: 命令の共通部分を管理する基底クラス。
   - **メンバ変数**:
     - `unsigned opcode`: 命令コード
     - `unsigned rs1, rs2, rd`: レジスタ番号 (ソースレジスタ1, ソースレジスタ2, 宛先レジスタ)
     - `Immediate imm`: 即値
     - `Instruction inst`: 命令の生データ
     - `enum Type t`: 命令タイプ (R型, I型, S型, B型, U型, J型)

   - **メンバ関数**:
     - `InstructionBase()`: デフォルトコンストラクタ。すべてのフィールドを初期化する。
     - `InstructionBase(unsigned)`: 特定の命令コードを持つI型命令用のコンストラクタ。
     - `static InstructionBase nop()`: NOP命令を作成して返す静的メソッド。
     - `bool is_nop()`: 現在のインスタンスがNOP命令であるかを判定する。
     - `static constexpr unsigned int bin_mask(int digits)`: 指定されたビット数に対応するマスク値を計算する。
     - `static unsigned int get_digits(unsigned int n, int hi, int lo)`: 与えられた整数から指定された範囲のビットを取り出す。
     - `static unsigned int expand_digit(unsigned int digit, int lo)`: 指定されたビットが1の場合、その位置から下位ビットを全て1に設定する。
     - `bool is_valid(const std::string &key)`: 指定されたキーに対するフィールドアクセスが有効であるかを判定する。
     - `void verify(const std::string &key)`: 指定されたキーに対するフィールドアクセスが無効な場合、例外を投げる。
     - `void debug()`: 命令の詳細情報を出力する。命令コードに応じて適切な命令名を表示する。
     - `bool has_op1()`: 命令がオペランド1を持つかどうかを判定する。
     - `bool has_op2()`: 命令がオペランド2を持つかどうかを判定する。

2. **InstructionR**
   - **役割**: R型命令の解析と管理を行う派生クラス。
   - **コンストラクタ**:
     - `InstructionR(const Instruction &inst)`: 与えられた命令データからR型命令のフィールドを初期化する。

3. **InstructionI**
   - **役割**: I型命令の解析と管理を行う派生クラス。
   - **コンストラクタ**:
     - `InstructionI(const Instruction &inst)`: 与えられた命令データからI型命令のフィールドを初期化する。

4. **InstructionS**
   - **役割**: S型命令の解析と管理を行う派生クラス。
   - **コンストラクタ**:
     - `InstructionS(const Instruction &inst)`: 与えられた命令データからS型命令のフィールドを初期化する。

5. **InstructionB**
   - **役割**: B型命令の解析と管理を行う派生クラス。
   - **コンストラクタ**:
     - `InstructionB(const Instruction &inst)`: 与えられた命令データからB型命令のフィールドを初期化する。

6. **InstructionU**
   - **役割**: U型命令の解析と管理を行う派生クラス。
   - **コンストラクタ**:
     - `InstructionU(const Instruction &inst)`: 与えられた命令データからU型命令のフィールドを初期化する。

7. **InstructionJ**
   - **役割**: J型命令の解析と管理を行う派生クラス。
   - **コンストラクタ**:
     - `InstructionJ(const Instruction &inst)`: 与えられた命令データからJ型命令のフィールドを初期化する。

## 注意事項
- この仕様書では、`replacement_required=false`のunitは参照専用とされています。これらの部分は再生成してはいけません。
- `InstructionBase`クラスのメンバ関数や派生クラスのコンストラクタは命令データから必要な情報を抽出し、適切なフィールドに格納します。

## まとめ
この設計仕様書はRISC-Vシミュレータにおいて命令処理を行うための基本的な構造体とクラスを定義しています。`InstructionBase`クラスとその派生クラスを使用することで、様々な型の命令を解析し、検証し、デバッグすることができます。