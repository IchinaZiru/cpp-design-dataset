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
- **置換対象 (replacement_required=true):**
  - コード再生成と置換が対象となります。
- **参照専用 (replacement_required=false):**
  - 既存コードとして利用できますが、再生成してはいけません。

## 詳細仕様

### ファイル: `src/Common/Instruction.hpp`

#### インクルードファイル
```cpp
#include <utility>
#include "Common.h"
#include <string>
#include <iostream>
```

#### 型定義
```cpp
using Instruction = unsigned int;
```

#### 例外クラス
- **InvalidAccess**
  - `InstructionBase` 内部で使用される例外クラスです。

#### 構造体: `InstructionBase`
- **メンバ変数:**
  - `unsigned opcode, rs1, rs2, rd, funct3, funct7;`
  - `Immediate imm;`
  - `Instruction inst;`
  - `enum Type { R, I, S, B, U, J } t;`

- **コンストラクタ:**
  - デフォルトコンストラクタ
    ```cpp
    InstructionBase() {
        rs1 = rs2 = rd = 0;
        opcode = 0;
        imm = 0;
        funct3 = funct7 = 0;
        this->inst = 0;
    }
    ```
  - 引数付きコンストラクタ
    ```cpp
    InstructionBase(unsigned) {
        rs1 = rs2 = rd = 0;
        opcode = 0b0010011;
        t = I;
        imm = 0;
        funct3 = funct7 = 0;
        this->inst = -1;
    }
    ```

- **静的メソッド:**
  - `static InstructionBase nop()`
    ```cpp
    static InstructionBase nop() { return InstructionBase(0); }
    ```
  - `static constexpr unsigned int bin_mask(int digits)`
    ```cpp
    static constexpr unsigned int bin_mask(int digits) {
        return (1 << digits) - 1;
    }
    ```
  - `static unsigned int get_digits(unsigned int n, int hi, int lo)`
    ```cpp
    static unsigned int get_digits(unsigned int n, int hi, int lo) {
        return (n >> lo) & bin_mask(hi - lo + 1);
    }
    ```
  - `static unsigned int expand_digit(unsigned int digit, int lo)`
    ```cpp
    static unsigned int expand_digit(unsigned int digit, int lo) {
        return digit ? (0xffffffff << lo) : 0;
    }
    ```

- **メンバメソッド:**
  - `bool is_nop()`
    ```cpp
    bool is_nop() { return this->inst == -1; }
    ```
  - `bool is_valid(const std::string &key)`
    ```cpp
    bool is_valid(const std::string &key) {
        if (t == R) { if (key == "imm") return false; }
        if (t == I) { if (key == "rs2" || key == "funct7") return false; }
        if (t == S) { if (key == "rd" || key == "funct7") return false; }
        if (t == B) { if (key == "rd" || key == "funct7") return false; }
        if (t == U || t == J) { if (key == "rs1" || key == "rs2" || key == "funct3" || key == "funct7") return false; }
        return true;
    }
    ```
  - `void verify(const std::string &key)`
    ```cpp
    void verify(const std::string &key) {
        if (!is_valid(key)) throw InvalidAccess();
    };
    ```
  - `void debug()`
    ```cpp
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
    ```
  - `bool has_op1()`
    ```cpp
    bool has_op1() {
        return t != InstructionBase::U && t != InstructionBase::J;
    }
    ```
  - `bool has_op2()`
    ```cpp
    bool has_op2() {
        return t == InstructionBase::R || t == InstructionBase::S
               || t == InstructionBase::B;
    }
    ```

#### 構造体: `InstructionR` (継承元: `InstructionBase`)
- **コンストラクタ:**
  ```cpp
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
  ```

#### 構造体: `InstructionI` (継承元: `InstructionBase`)
- **コンストラクタ:**
  ```cpp
  InstructionI(const Instruction &inst) {
      opcode = get_digits(inst, 6, 0);
      rd = get_digits(inst, 11, 7);
      funct3 = get_digits(inst, 14, 12);
      rs1 = get_digits(inst, 19, 15);
      imm = get_digits(inst, 30, 20) | expand_digit(get_digits(inst, 31, 31), 11);
      t = I;
      this->inst = inst;
  }
  ```

#### 構造体: `InstructionS` (継承元: `InstructionBase`)
- **コンストラクタ:**
  ```cpp
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
  ```

#### 構造体: `InstructionB` (継承元: `InstructionBase`)
- **コンストラクタ:**
  ```cpp
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
  ```

#### 構造体: `InstructionU` (継承元: `InstructionBase`)
- **コンストラクタ:**
  ```cpp
  InstructionU(const Instruction &inst) {
      opcode = get_digits(inst, 6, 0);
      rd = get_digits(inst, 11, 7);
      imm = (get_digits(inst, 19, 12) << 12) |
            (get_digits(inst, 30, 20) << 20) |
            (get_digits(inst, 31, 31) << 31);
      t = U;
      this->inst = inst;
  }
  ```

#### 構造体: `InstructionJ` (継承元: `InstructionBase`)
- **コンストラクタ:**
  ```cpp
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
  ```

## 注意事項
- `replacement_required=true` のユニットのみが再生成と置換の対象となります。
- `replacement_required=false` のユニットは参照専用であり、既存コードとして利用できますが再生成してはいけません。

この設計仕様書を基に新たな実装を行ってください。