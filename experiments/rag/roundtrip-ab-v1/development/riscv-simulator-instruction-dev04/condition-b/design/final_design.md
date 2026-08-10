# 詳細設計仕様書

## 1. 概要

この設計仕様書は、`Instruction.hpp` ファイルの再実装に必要な詳細情報を提供します。ファイル内の各クラス、構造体、メソッド、インターフェースについて記述し、再生成に必要な正確性を確保します。

## 2. 対象情報

- **F01/U01**
  - **path**: `src/Common/Instruction.hpp`
  - **role**: 完全なヘッダオンリーターゲット実装と宣言
  - **replacement_required**: true

## 3. クラス図

```mermaid
classDiagram
    class InstructionBase {
        +unsigned opcode
        +unsigned rs1
        +unsigned rs2
        +unsigned rd
        +unsigned funct3
        +unsigned funct7
        +Immediate imm
        +Instruction inst
        +enum Type { R, I, S, B, U, J } t
        +static constexpr unsigned int bin_mask(int digits)
        +static unsigned int get_digits(unsigned int n, int hi, int lo)
        +static unsigned int expand_digit(unsigned int digit, int lo)
        +bool is_valid(const std::string &key)
        +void verify(const std::string &key)
        +void debug()
        +bool has_op1()
        +bool has_op2()
    }
    
    class InstructionR {
        -Instruction inst
        +InstructionR(const Instruction &inst)
    }

    class InstructionI {
        -Instruction inst
        +InstructionI(const Instruction &inst)
    }

    class InstructionS {
        -Instruction inst
        +InstructionS(const Instruction &inst)
    }

    class InstructionB {
        -Instruction inst
        +InstructionB(const Instruction &inst)
    }

    class InstructionU {
        -Instruction inst
        +InstructionU(const Instruction &inst)
    }

    class InstructionJ {
        -Instruction inst
        +InstructionJ(const Instruction &inst)
    }
    
    InstructionBase <|-- InstructionR
    InstructionBase <|-- InstructionI
    InstructionBase <|-- InstructionS
    InstructionBase <|-- InstructionB
    InstructionBase <|-- InstructionU
    InstructionBase <|-- InstructionJ

    class InvalidAccess {
        +InvalidAccess()
    }

    InstructionBase *-- InvalidAccess : throws
```

## 4. クラス・メソッド・インターフェース詳細

### InstructionBase

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| opcode | unsigned | public | - | - | - |
| rs1 | unsigned | public | - | - | - |
| rs2 | unsigned | public | - | - | - |
| rd | unsigned | public | - | - | - |
| funct3 | unsigned | public | - | - | - |
| funct7 | unsigned | public | - | - | - |
| imm | Immediate | public | - | - | - |
| inst | Instruction | public | - | - | - |
| t | Type | public | - | - | - |
| bin_mask | unsigned int | static constexpr | - | digits: int | unsigned int |
| get_digits | unsigned int | static | - | n: unsigned int, hi: int, lo: int | unsigned int |
| expand_digit | unsigned int | static | - | digit: unsigned int, lo: int | unsigned int |
| is_valid | bool | public | - | key: const std::string & | bool |
| verify | void | public | - | key: const std::string & | void |
| debug | void | public | - | - | void |
| has_op1 | bool | public | - | - | bool |
| has_op2 | bool | public | - | - | bool |

### InstructionR

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| inst | Instruction | private | - | - | - |
| InstructionR | - | public | - | inst: const Instruction & | - |

### InstructionI

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| inst | Instruction | private | - | - | - |
| InstructionI | - | public | - | inst: const Instruction & | - |

### InstructionS

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| inst | Instruction | private | - | - | - |
| InstructionS | - | public | - | inst: const Instruction & | - |

### InstructionB

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| inst | Instruction | private | - | - | - |
| InstructionB | - | public | - | inst: const Instruction & | - |

### InstructionU

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| inst | Instruction | private | - | - | - |
| InstructionU | - | public | - | inst: const Instruction & | - |

### InstructionJ

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| inst | Instruction | private | - | - | - |
| InstructionJ | - | public | - | inst: const Instruction & | - |

### InvalidAccess

| 名前 | 型 | 可視性 | const/static/constexpr | 引数名と型 | 戻り値型 |
|------|----|--------|--------------------------|------------|----------|
| InvalidAccess | - | public | - | - | - |

## 5. シーケンス図

該当なし

## 6. メソッド仕様書

### InstructionBase::InstructionBase()

- **目的**: `InstructionBase` のデフォルトコンストラクタ
- **引数**: 無し
- **戻り値型**: void
- **動作**: 各フィールドを初期化する。
- **副作用**: フィールドの初期化
- **エラー処理**: 該当なし

### InstructionBase::InstructionBase(unsigned)

- **目的**: `InstructionBase` のコンストラクタ（特定の初期値設定）
- **引数**: 無し
- **戻り値型**: void
- **動作**: 各フィールドを初期化し、特定の値を設定する。
- **副作用**: フィールドの初期化と設定
- **エラー処理**: 該当なし

### InstructionBase::nop()

- **目的**: NOP命令を作成する静的メソッド
- **引数**: 無し
- **戻り値型**: InstructionBase
- **動作**: NOP命令を表す `InstructionBase` オブジェクトを返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionBase::is_nop()

- **目的**: 現在のインストラクションがNOPかどうか判定するメソッド
- **引数**: 無し
- **戻り値型**: bool
- **動作**: `inst` フィールドが -1 であるかを返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionBase::bin_mask(int digits)

- **目的**: 指定されたビット数のマスクを作成する静的メソッド
- **引数**: digits: int
- **戻り値型**: unsigned int
- **動作**: `digits` ビット分のマスクを返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionBase::get_digits(unsigned int n, int hi, int lo)

- **目的**: 指定された範囲のビットを取り出す静的メソッド
- **引数**: n: unsigned int, hi: int, lo: int
- **戻り値型**: unsigned int
- **動作**: `n` の `hi` から `lo` ビットを取り出して返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionBase::expand_digit(unsigned int digit, int lo)

- **目的**: 指定されたビットを拡張する静的メソッド
- **引数**: digit: unsigned int, lo: int
- **戻り値型**: unsigned int
- **動作**: `digit` が 0 の場合は 0 を、それ以外の場合は `lo` ビット目から上位ビットを 1 に設定した値を返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionBase::is_valid(const std::string &key)

- **目的**: 指定されたキーが有効かどうか判定するメソッド
- **引数**: key: const std::string &
- **戻り値型**: bool
- **動作**: `t` に応じて `key` の有効性を返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionBase::verify(const std::string &key)

- **目的**: 指定されたキーが有効かどうか検証するメソッド
- **引数**: key: const std::string &
- **戻り値型**: void
- **動作**: `is_valid(key)` が false の場合は `InvalidAccess` をスローする。
- **副作用**: 例外のスロー
- **エラー処理**: `InvalidAccess` スロー

### InstructionBase::debug()

- **目的**: インストラクションをデバッグ出力するメソッド
- **引数**: 無し
- **戻り値型**: void
- **動作**: インストラクションの詳細情報を `std::cout` に出力する。
- **副作用**: 標準出力への書き込み
- **エラー処理**: 該当なし

### InstructionBase::has_op1()

- **目的**: オペランド1が存在するかどうか判定するメソッド
- **引数**: 無し
- **戻り値型**: bool
- **動作**: `t` が U または J の場合は false を、それ以外の場合は true を返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionBase::has_op2()

- **目的**: オペランド2が存在するかどうか判定するメソッド
- **引数**: 無し
- **戻り値型**: bool
- **動作**: `t` が R, S, B の場合は true を、それ以外の場合は false を返す。
- **副作用**: 該当なし
- **エラー処理**: 該当なし

### InstructionR::InstructionR(const Instruction &inst)

- **目的**: `InstructionR` のコンストラクタ
- **引数**: inst: const Instruction &
- **戻り値型**: void
- **動作**: `inst` から R 型のインストラクション情報を抽出し、フィールドに設定する。
- **副作用**: フィールドへの設定
- **エラー処理**: 該当なし

### InstructionI::InstructionI(const Instruction &inst)

- **目的**: `InstructionI` のコンストラクタ
- **引数**: inst: const Instruction &
- **戻り値型**: void
- **動作**: `inst` から I 型のインストラクション情報を抽出し、フィールドに設定する。
- **副作用**: フィールドへの設定
- **エラー処理**: 該当なし

### InstructionS::InstructionS(const Instruction &inst)

- **目的**: `InstructionS` のコンストラクタ
- **引数**: inst: const Instruction &
- **戻り値型**: void
- **動作**: `inst` から S 型のインストラクション情報を抽出し、フィールドに設定する。
- **副作用**: フィールドへの設定
- **エラー処理**: 該当なし

### InstructionB::InstructionB(const Instruction &inst)

- **目的**: `InstructionB` のコンストラクタ
- **引数**: inst: const Instruction &
- **戻り値型**: void
- **動作**: `inst` から B 型のインストラクション情報を抽出し、フィールドに設定する。
- **副作用**: フィールドへの設定
- **エラー処理**: 該当なし

### InstructionU::InstructionU(const Instruction &inst)

- **目的**: `InstructionU` のコンストラクタ
- **引数**: inst: const Instruction &
- **戻り値型**: void
- **動作**: `inst` から U 型のインストラクション情報を抽出し、フィールドに設定する。
- **副作用**: フィールドへの設定
- **エラー処理**: 該当なし

### InstructionJ::InstructionJ(const Instruction &inst)

- **目的**: `InstructionJ` のコンストラクタ
- **引数**: inst: const Instruction &
- **戻り値型**: void
- **動作**: `inst` から J 型のインストラクション情報を抽出し、フィールドに設定する。
- **副作用**: フィールドへの設定
- **エラー処理**: 該当なし

## 7. 処理フロー図

該当なし

## 8. 状態遷移・副作用

| 更新前状態 | 遷移条件 | 変更対象 | 更新後状態 | 更新順序 | 副作用 |
|------------|----------|----------|------------|----------|--------|
| -          | コンストラクタ呼び出し | 各フィールド | 初期化された状態 | 任意 | フィールドの初期化 |
| -          | verify() 呼び出しかつ is_valid(key) == false | -      | -          | -        | InvalidAccess スロー |

## 9. データ変換・制約

### InstructionBase::get_digits()

- **入力**: n: unsigned int, hi: int, lo: int
- **出力**: (n >> lo) & bin_mask(hi - lo + 1)
- **制約**: `hi` >= `lo`

### InstructionBase::expand_digit()

- **入力**: digit: unsigned int, lo: int
- **出力**: digit ? (0xffffffff << lo) : 0
- **制約**: 該当なし

### InstructionR::InstructionR()

- **入力**: inst: const Instruction &
- **出力**: 各フィールドに `inst` のビットを抽出して設定
- **制約**: 該当なし

### InstructionI::InstructionI()

- **入力**: inst: const Instruction &
- **出力**: 各フィールドに `inst` のビットを抽出して設定
- **制約**: 該当なし

### InstructionS::InstructionS()

- **入力**: inst: const Instruction &
- **出力**: 各フィールドに `inst` のビットを抽出して設定
- **制約**: 該当なし

### InstructionB::InstructionB()

- **入力**: inst: const Instruction &
- **出力**: 各フィールドに `inst` のビットを抽出して設定
- **制約**: 該当なし

### InstructionU::InstructionU()

- **入力**: inst: const Instruction &
- **出力**: 各フィールドに `inst` のビットを抽出して設定
- **制約**: 該当なし

### InstructionJ::InstructionJ()

- **入力**: inst: const Instruction &
- **出力**: 各フィールドに `inst` のビットを抽出して設定
- **制約**: 該当なし

## 10. 追加詳細設計情報

### 完全再構築台帳

#### ファイルヘッダ

```cpp
#ifndef RISCV_SIMULATOR_INSTRUCTION_HPP
#define RISCV_SIMULATOR_INSTRUCTION_HPP

#include <utility>
#include "Common.h"
#include <string>
#include <iostream>

using Instruction = unsigned int;
```

#### クラス定義: InstructionBase

```cpp
struct InstructionBase {
    class InvalidAccess {
    };

    InstructionBase() {
        rs1 = rs2 = rd = 0;
        opcode = 0;
        imm = 0;
        funct3 = funct7 = 0;
        this->inst = 0;
    }

    InstructionBase(unsigned) {
        rs1 = rs2 = rd = 0;
        opcode = 0b0010011;
        t = I;
        imm = 0;
        funct3 = funct7 = 0;
        this->inst = -1;
    }

    static InstructionBase nop() { return InstructionBase(0); }

    bool is_nop() { return this->inst == -1; }

    unsigned opcode, rs1, rs2, rd, funct3, funct7;
    Immediate imm;
    Instruction inst;
    enum Type {
        R, I, S, B, U, J
    } t;

    static constexpr unsigned int bin_mask(int digits) {
        return (1 << digits) - 1;
    }

    static unsigned int get_digits(unsigned int n, int hi, int lo) {
        return (n >> lo) & bin_mask(hi - lo + 1);
    }

    static unsigned int expand_digit(unsigned int digit, int lo) {
        return digit ? (0xffffffff << lo) : 0;
    }

    bool is_valid(const std::string &key) {
        if (t == R) { if (key == "imm") return false; }
        if (t == I) { if (key == "rs2" || key == "funct7") return false; }
        if (t == S) { if (key == "rd" || key == "funct7") return false; }
        if (t == B) { if (key == "rd" || key == "funct7") return false; }
        if (t == U || t == J) { if (key == "rs1" || key == "rs2" || key == "funct3" || key == "funct7") return false; }
        return true;
    }

    void verify(const std::string &key) {
        if (!is_valid(key)) throw InvalidAccess();
    };

    void debug() {
        std::cout << std::hex << inst << " ";
        if (inst == 0x00000013) std::cout << "nop";
        else if (opcode == 0b0110111) std::cout << "lui ";
        else if (opcode == 0b0010111) std::cout << "auipc ";
        else if (opcode == 0b1101111) std::cout << "jal ";
        else if (opcode == 0b1100111) std::cout << "jalr ";
        else if (opcode == 0b1100011) std::cout << "branch";
        else if (opcode == 0b0000011) std::cout << "load";
        else if (opcode == 0b0100011) std::cout << "store";
        else if (opcode == 0b0010011) {
            static std::string opi[] = {
                    "addi", "slli", "slti", "sltiu", "xori", "srli / srai",
                    "ori", "andi"
            };
            std::cout << opi[funct3];
        }
        else if (opcode == 0b0110011) std::cout << "op";
        else std::cout << "unknown";
        std::cout << std::endl;
    }

    bool has_op1() {
        return t != InstructionBase::U && t != InstructionBase::J;
    }

    bool has_op2() {
        return t == InstructionBase::R || t == InstructionBase::S
               || t == InstructionBase::B;
    }
};
```

#### クラス定義: InstructionR

```cpp
struct InstructionR : InstructionBase {
    InstructionR(const Instruction &inst) {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        funct7 = get_digits(inst, 31, 25);
        t = R;
        this->inst = inst;
    }
};
```

#### クラス定義: InstructionI

```cpp
struct InstructionI : InstructionBase {
    InstructionI(const Instruction &inst) {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        imm = get_digits(inst, 30, 20) | expand_digit(get_digits(inst, 31, 31), 11);
        t = I;
        this->inst = inst;
    }
};
```

#### クラス定義: InstructionS

```cpp
struct InstructionS : InstructionBase {
    InstructionS(const Instruction &inst) {
        opcode = get_digits(inst, 6, 0);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        imm = get_digits(inst, 11, 7) |
              (get_digits(inst, 30, 25) << 5) |
              expand_digit(get_digits(inst, 31, 31), 11);
        t = S;
        this->inst = inst;
    }
};
```

#### クラス定義: InstructionB

```cpp
struct InstructionB : InstructionBase {
    InstructionB(const Instruction &inst) {
        opcode = get_digits(inst, 6, 0);
        funct3 = get_digits(inst, 14, 12);
        rs1 = get_digits(inst, 19, 15);
        rs2 = get_digits(inst, 24, 20);
        imm = (get_digits(inst, 11, 8) << 1) |
              (get_digits(inst, 30, 25) << 5) |
              (get_digits(inst, 7, 7) << 11) |
              expand_digit(get_digits(inst, 31, 31), 12);
        t = B;
        this->inst = inst;
    }
};
```

#### クラス定義: InstructionU

```cpp
struct InstructionU : InstructionBase {
    InstructionU(const Instruction &inst) {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        imm = (get_digits(inst, 19, 12) << 12) |
              (get_digits(inst, 30, 20) << 20) |
              (get_digits(inst, 31, 31) << 31);
        t = U;
        this->inst = inst;
    }
};
```

#### クラス定義: InstructionJ

```cpp
struct InstructionJ : InstructionBase {
    InstructionJ(const Instruction &inst) {
        opcode = get_digits(inst, 6, 0);
        rd = get_digits(inst, 11, 7);
        imm = (get_digits(inst, 30, 21) << 1) |
              (get_digits(inst, 20, 20) << 11) |
              (get_digits(inst, 19, 12) << 12) |
              expand_digit(get_digits(inst, 31, 31), 20);
        t = J;
        this->inst = inst;
    }
};
```

#### ファイルフッタ

```cpp
#endif //RISCV_SIMULATOR_INSTRUCTION_HPP
```

この設計仕様書は、`Instruction.hpp` ファイルの再実装に必要な詳細情報を提供します。各クラス、構造体、メソッドについて記述し、再生成に必要な正確性を確保しています。