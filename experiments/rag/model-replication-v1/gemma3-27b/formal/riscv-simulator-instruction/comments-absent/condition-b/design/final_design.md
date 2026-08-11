## Instruction.hpp 詳細設計仕様書

### 1. 正確な定義

*   **`Instruction`**: `unsigned int` (32ビット符号なし整数)
*   **`Immediate`**: `unsigned int` (32ビット符号なし整数) - Common.hで定義
*   **`SImmediate`**: `int` (32ビット符号付き整数) - Common.hで定義
*   **`InstructionBase::Type`**: 列挙型。値は `R`, `I`, `S`, `B`, `U`, `J`。
*   **`InstructionBase::InvalidAccess`**:  クラス。例外処理に使用されるマーカーとして機能する。

### 2. 直接依存インターフェースと利用方法

*   **`<utility>`**: 標準ライブラリヘッダ。`std::pair`などのユーティリティを提供。
*   **`<string>`**: 標準ライブラリヘッダ。`std::string`クラスを提供。
*   **`<iostream>`**: 標準ライブラリヘッダ。`std::cout`など、入出力ストリームを提供。
*   **`Common.h`**:  `Immediate`, `SImmediate` 型定義を含むヘッダファイル。

### 3. 結果を決める式・具体値

*   **`bin_mask(int digits)`**:  `(1 << digits) - 1` を返す関数。ビットマスクを生成する。
*   **`get_digits(unsigned int n, int hi, int lo)`**: `(n >> lo) & bin_mask(hi - lo + 1)` を返す関数。整数から指定されたビット範囲の値を抽出する。
*   **`expand_digit(unsigned int digit, int lo)`**:  `digit ? (0xffffffff << lo) : 0` を返す関数。最上位ビットをセットした値を生成する。
*   **opcode値**: 各命令タイプ（LUI, AUIPC, JAL, JALR, BRANCH, LOAD, STORE, ADDIなど）に対応する具体的なopcodeの値は、コード内でハードコーディングされている。
*   **`nop()`**:  インスタンスを初期化し、`inst` を -1 に設定して `InstructionBase` の静的メソッド。

### 4. 使用データ・更新データ

*   **`InstructionBase`**:
    *   `opcode`, `rs1`, `rd`, `funct3`, `funct7`: 命令の各フィールドを保持するunsigned int型変数。
    *   `imm`: Immediate値を保持する`Immediate`型変数。
    *   `inst`: 命令全体を保持する`Instruction`型変数。
    *   `t`: 命令タイプを示す`Type` enum型の変数。
*   **派生クラス (`InstructionR`, `InstructionI`, `InstructionS`, `InstructionB`, `InstructionU`, `InstructionJ`)**:  ベースクラスのメンバに加えて、命令タイプ固有のフィールドを初期化する。

### 5. 状態・副作用・不変条件

*   `InstructionBase` のコンストラクタは、メンバ変数を初期値 (0) に設定する。
*   `verify()` メソッドは、指定されたキーに基づいて命令の有効性を検証し、無効な場合は `InvalidAccess` 例外をスローする。
*   `debug()` メソッドは、標準出力に命令情報を出力する（副作用あり）。

## クラス図

```mermaid
classDiagram
    class InstructionBase {
        - opcode : unsigned int
        - rs1 : unsigned int
        - rs2 : unsigned int
        - rd : unsigned int
        - funct3 : unsigned int
        - funct7 : unsigned int
        - imm : Immediate
        - inst : Instruction
        + t : Type
        + bin_mask(digits : int) : unsigned int
        + get_digits(n : unsigned int, hi : int, lo : int) : unsigned int
        + expand_digit(digit : unsigned int, lo : int) : unsigned int
        + is_valid(key : string) : bool
        + verify(key : string)
        + debug()
    }
    enum Type {
        R
        I
        S
        B
        U
        J
    }
    class InstructionR {
        + InstructionR(inst : Instruction)
    }
    class InstructionI {
        + InstructionI(inst : Instruction)
    }
    class InstructionS {
        + InstructionS(inst : Instruction)
    }
    class InstructionB {
        + InstructionB(inst : Instruction)
    }
    class InstructionU {
        + InstructionU(inst : Instruction)
    }
    class InstructionJ {
        + InstructionJ(inst : Instruction)
    }

    InstructionBase <|-- InstructionR
    InstructionBase <|-- InstructionI
    InstructionBase <|-- InstructionS
    InstructionBase <|-- InstructionB
    InstructionBase <|-- InstructionU
    InstructionBase <|-- InstructionJ
```

## クラス・メソッド・インターフェース詳細

| Class/Method | Name | Type | Visibility | Parameters | Return Type | Notes |
|---|---|---|---|---|---|---|
| `InstructionBase` | `opcode` | `unsigned int` | private |  |  |  |
| `InstructionBase` | `rs1` | `unsigned int` | private |  |  |  |
| `InstructionBase` | `rs2` | `unsigned int` | private |  |  |  |
| `InstructionBase` | `rd` | `unsigned int` | private |  |  |  |
| `InstructionBase` | `funct3` | `unsigned int` | private |  |  |  |
| `InstructionBase` | `funct7` | `unsigned int` | private |  |  |  |
| `InstructionBase` | `imm` | `Immediate` | private |  |  |  |
| `InstructionBase` | `inst` | `Instruction` | private |  |  |  |
| `InstructionBase` | `t` | `Type` | public |  |  |  |
| `InstructionBase` | `InstructionBase()` | constructor | public |  | void | Initializes members to 0. |
| `InstructionBase` | `InstructionBase(unsigned)` | constructor | public | `unsigned` | void | Initializes members with specific values for NOP instruction.|
| `InstructionBase` | `nop()` | static method | public |  | `InstructionBase` | Returns a NOP InstructionBase object. |
| `InstructionBase` | `is_nop()` | method | public |  | bool | Checks if the instruction is a NOP. |
| `InstructionBase` | `bin_mask(int digits)` | static method | public | `digits : int` | `unsigned int` | Returns a bit mask with specified number of bits set to 1. |
| `InstructionBase` | `get_digits(unsigned int n, int hi, int lo)` | static method | public | `n : unsigned int`, `hi : int`, `lo : int` | `unsigned int` | Extracts a range of bits from an integer. |
| `InstructionBase` | `expand_digit(unsigned int digit, int lo)` | static method | public | `digit : unsigned int`, `lo : int` | `unsigned int` | Expands a single bit to a specific position. |
| `InstructionBase` | `is_valid(string key)` | method | public | `key : string` | bool | Checks if the instruction is valid for a given key. |
| `InstructionBase` | `verify(string key)` | method | public | `key : string` | void | Throws InvalidAccess exception if the instruction is invalid. |
| `InstructionBase` | `debug()` | method | public |  | void | Prints debug information about the instruction to stdout. |
| `InstructionBase` | `has_op1()` | method | public |  | bool | Checks if the instruction has op1.|
| `InstructionBase` | `has_op2()` | method | public |  | bool | Checks if the instruction has op2.|
| `InstructionR` | `InstructionR(Instruction inst)` | constructor | public | `inst : Instruction` | void | Initializes members based on the input instruction. |
| `InstructionI` | `InstructionI(Instruction inst)` | constructor | public | `inst : Instruction` | void | Initializes members based on the input instruction. |
| `InstructionS` | `InstructionS(Instruction inst)` | constructor | public | `inst : Instruction` | void | Initializes members based on the input instruction. |
| `InstructionB` | `InstructionB(Instruction inst)` | constructor | public | `inst : Instruction` | void | Initializes members based on the input instruction. |
| `InstructionU` | `InstructionU(Instruction inst)` | constructor | public | `inst : Instruction` | void | Initializes members based on the input instruction. |
| `InstructionJ` | `InstructionJ(Instruction inst)` | constructor | public | `inst : Instruction` | void | Initializes members based on the input instruction. |

## シーケンス図

該当なし。このコードは主にデータ構造の定義であり、複雑なシーケンスインタラクションを含んでいないため。

## メソッド仕様書

**`InstructionBase::bin_mask(int digits)`**

*   **目的**: 指定された桁数のビットマスクを生成する。
*   **引数**: `digits`: マスクのビット数。
*   **戻り値**:  `(1 << digits) - 1` の結果。
*   **副作用**: なし。

**`InstructionBase::get_digits(unsigned int n, int hi, int lo)`**

*   **目的**: 整数から指定されたビット範囲の値を抽出する。
*   **引数**: `n`: 入力整数、`hi`: 上位ビット位置、`lo`: 下位ビット位置。
*   **戻り値**:  抽出されたビットの値。
*   **副作用**: なし。

## 処理フロー図

該当なし。このコードは主にデータ構造の定義であり、複雑な制御フローを含んでいないため。

## 状態遷移・副作用

各コンストラクタは、オブジェクトの状態（メンバ変数）を初期化する。`debug()` メソッドは標準出力に情報を書き出すという副作用を持つ。それ以外に状態遷移や副作用はない。

## データ変換・制約

*   **ビット抽出**: `get_digits` 関数は、入力整数から指定された範囲のビットを抽出し、符号なし整数として返す。
*   **ビット拡張**: `expand_digit` 関数は、単一のビットを特定のビット位置に拡張し、符号なし整数として返す。
*   **命令タイプ**: 各派生クラスのコンストラクタは、入力された命令（Instruction）から適切なフィールドを抽出し、対応するメンバ変数を初期化する。
