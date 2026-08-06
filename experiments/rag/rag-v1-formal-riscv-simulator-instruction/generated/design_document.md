# デザイン文書: Instructionモジュール

## 概要
この設計文書は、RISC-VシミュレータにおけるInstructionモジュールの仕様を詳細に記載します。Instructionモジュールは、RISC-Vアーキテクチャの命令を解析し、適切な形式に変換する役割を持ちます。

## 責務
- RISC-Vアーキテクチャの命令を解析し、その種類（R型、I型、S型、B型、U型、J型）に応じたInstructionオブジェクトを作成します。
- 各命令のフィールド（opcode, rs1, rs2, rd, funct3, funct7, imm）を適切に抽出し設定します。

## 公開インターフェース
### クラス: InstructionBase
#### メソッド:
- `InstructionBase()`: デフォルトコンストラクタ。すべてのフィールドを初期化します。
- `InstructionBase(unsigned)`: NOP命令用のコンストラクタ。NOP命令として設定します。
- `static InstructionBase nop()`: NOP命令を作成して返します。
- `bool is_nop()`: 現在のインスタンスがNOP命令であるかを判定します。
- `unsigned opcode, rs1, rs2, rd, funct3, funct7; Immediate imm;`: 命令フィールドへのアクセス用メンバ変数です。
- `enum Type { R, I, S, B, U, J };`: 命令の種類を表す列挙型です。
- `static constexpr unsigned int bin_mask(int digits)`: 指定されたビット長のマスクを作成します。
- `static unsigned int get_digits(unsigned int n, int hi, int lo)`: 指定された範囲のビットを抽出します。
- `static unsigned int expand_digit(unsigned int digit, int lo)`: 符号拡張を行います。
- `bool is_valid(const std::string &key)`: 指定されたフィールドが現在の命令種類で有効であるかを判定します。
- `void verify(const std::string &key)`: 指定されたフィールドが無効な場合に例外をスローします。
- `void debug()`: 命令の詳細情報を出力します。
- `bool has_op1()`: 命令がオペランド1を持つかどうかを判定します。
- `bool has_op2()`: 命令がオペランド2を持つかどうかを判定します。

### 派生クラス:
- `InstructionR`
- `InstructionI`
- `InstructionS`
- `InstructionB`
- `InstructionU`
- `InstructionJ`

各派生クラスは、対応する命令種類のフィールドを適切に設定するコンストラクタを持ちます。

## 入力
- 命令コード（`unsigned int`型）
- インスタンス化時に必要な追加情報（必要に応じて）

## 出力
- `InstructionBase`またはその派生クラスのインスタンス

## 状態
- 各命令フィールド（opcode, rs1, rs2, rd, funct3, funct7, imm）
- 命令種類（Type列挙型）

## 処理手順
### InstructionBase::InstructionBase()
1. すべてのフィールドを初期化します。

### InstructionBase::InstructionBase(unsigned)
1. NOP命令として設定します。

### InstructionBase::nop()
1. NOP命令を作成して返します。

### InstructionBase::is_nop()
1. 現在のインスタンスがNOP命令であるかを判定します。

### InstructionBase::get_digits
1. 指定された範囲のビットを抽出します。

### InstructionBase::expand_digit
1. 符号拡張を行います。

### InstructionBase::is_valid
1. 指定されたフィールドが現在の命令種類で有効であるかを判定します。

### InstructionBase::verify
1. 指定されたフィールドが無効な場合に例外をスローします。

### InstructionBase::debug
1. 命令の詳細情報を出力します。

### InstructionBase::has_op1
1. 命令がオペランド1を持つかどうかを判定します。

### InstructionBase::has_op2
1. 命令がオペランド2を持つかどうかを判定します。

### InstructionR, InstructionI, InstructionS, InstructionB, InstructionU, InstructionJのコンストラクタ
1. 対応する命令種類のフィールドを適切に設定します。

## 例外・失敗条件
- `InstructionBase::verify`メソッドで無効なフィールドアクセスが行われた場合、`InvalidAccess`例外がスローされます。
- 不明な命令コードが与えられた場合、NOP命令として扱われます。

## 依存関係
- `Common.h`
- `std::string`
- `std::iostream`

## 重要な不変条件
- 各命令種類のインスタンスは、その命令種類に応じたフィールドのみを有効に設定する必要があります。
- NOP命令の場合、`inst`フィールドが-1である必要があります。
