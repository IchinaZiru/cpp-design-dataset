# デザイン文書: Instruction.hpp モジュール

## 概要
このモジュールは、RISC-Vアーキテクチャの命令を表現するためのクラスと構造体を定義しています。主に命令の解析とデバッグ出力を行う機能が含まれています。

## ファイル構造
- **Instruction.hpp**: RISC-V命令を表すための基本的な構造体と派生クラスを定義します。

## 責務
- 命令コードからRISC-V命令の各フィールド（opcode, rs1, rs2, rd, funct3, funct7, imm）を抽出し、保持する。
- 各種命令型（R型、I型、S型、B型、U型、J型）に対応したクラスを提供する。
- 命令のデバッグ情報を出力する機能を提供する。

## 公開インターフェース
### InstructionBase
- **コンストラクタ**
  - `InstructionBase()`: デフォルトコンストラクタ。すべてのフィールドを初期化します。
  - `InstructionBase(unsigned)`: NOP命令として初期化します。
  
- **静的メソッド**
  - `static InstructionBase nop()`: NOP命令を作成して返します。
  - `static constexpr unsigned int bin_mask(int digits)`: 指定されたビット数のマスクを生成します。
  - `static unsigned int get_digits(unsigned int n, int hi, int lo)`: 指定された範囲のビットを取り出します。
  - `static unsigned int expand_digit(unsigned int digit, int lo)`: ビットを拡張して符号付き値に変換します。

- **メンバメソッド**
  - `bool is_nop()`: 命令がNOPかどうかを判定します。
  - `bool is_valid(const std::string &key)`: 指定されたフィールドが現在の命令型で有効かを判定します。
  - `void verify(const std::string &key)`: 指定されたフィールドが無効な場合に例外をスローします。
  - `void debug()`: 命令のデバッグ情報を出力します。
  - `bool has_op1()`: 命令がオペランド1を持つかどうかを判定します。
  - `bool has_op2()`: 命令がオペランド2を持つかどうかを判定します。

- **メンバ変数**
  - `unsigned opcode, rs1, rs2, rd, funct3, funct7;`
  - `Immediate imm;`
  - `Instruction inst;`
  - `enum Type { R, I, S, B, U, J } t;`

### InstructionR
- **コンストラクタ**
  - `InstructionR(const Instruction &inst)`: R型命令を解析してフィールドを初期化します。

### InstructionI
- **コンストラクタ**
  - `InstructionI(const Instruction &inst)`: I型命令を解析してフィールドを初期化します。

### InstructionS
- **コンストラクタ**
  - `InstructionS(const Instruction &inst)`: S型命令を解析してフィールドを初期化します。

### InstructionB
- **コンストラクタ**
  - `InstructionB(const Instruction &inst)`: B型命令を解析してフィールドを初期化します。

### InstructionU
- **コンストラクタ**
  - `InstructionU(const Instruction &inst)`: U型命令を解析してフィールドを初期化します。

### InstructionJ
- **コンストラクタ**
  - `InstructionJ(const Instruction &inst)`: J型命令を解析してフィールドを初期化します。

## 入力
- 命令コード（`unsigned int`）

## 出力
- 各種命令のフィールド値
- デバッグ情報（標準出力）

## 状態
- 命令型 (`Type`)
- 各フィールド値 (opcode, rs1, rs2, rd, funct3, funct7, imm)

## 処理手順
1. コンストラクタが呼び出されると、命令コードから各フィールドを抽出します。
2. 抽出したフィールドはメンバ変数に格納されます。
3. 必要に応じて`is_valid()`や`verify()`メソッドでフィールドの有効性を確認します。
4. `debug()`メソッドが呼び出されると、命令の種類と詳細情報を標準出力に出力します。

## 例外・失敗条件
- `verify(const std::string &key)`メソッドで指定されたフィールドが無効な場合に`InvalidAccess`例外をスローします。

## 依存関係
- Common.h (未定義のImmediate型を使用しているため)

## 重要な不変条件
- 各命令型（R, I, S, B, U, J）に対応するフィールドのみが有効である。
- `inst`メンバ変数は、コンストラクタで設定された命令コードと一致する。

この設計文書は、元コードの機能を再現するために必要な構造とインターフェースを定義しています。