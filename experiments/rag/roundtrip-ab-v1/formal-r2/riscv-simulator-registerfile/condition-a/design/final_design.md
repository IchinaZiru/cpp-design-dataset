# 設計仕様書

## 概要
この設計仕様書は、`RegisterFile` クラスの再実装を目的としています。元のソースコードから得られる情報を基に、新たなソースコードを作成します。ただし、特定の識別子（Fxx/Uxx）については名前、型、シグネチャ、名前空間、置換境界を保持する必要があります。

## 対象
- **対象ファイル**: `src/Common/RegisterFile.hpp`
- **対象クラス**: `RegisterFile`

## 要件

### クラス定義
`RegisterFile` クラスは以下の要件を満たすように実装します。

#### 定数
- `REG_NUM`: 登録ファイルのレジスタ数を表す静的定数。値は32です。

#### メンバ変数
- `prev[REG_NUM]`: 前回のクロックサイクルのレジスタ値を保持する配列。
- `next[REG_NUM]`: 次のクロックサイクルのレジスタ値を保持する配列。

#### コンストラクタ
- **シグネチャ**: `RegisterFile()`
- **動作**: 
  - `prev` 配列と `next` 配列をゼロで初期化します。
  - 使用関数: `memset`

#### メソッド
- **tick**
  - **シグネチャ**: `void tick()`
  - **動作**:
    - `next` 配列の内容を `prev` 配列にコピーします。
    - 使用関数: `memcpy`

- **read**
  - **シグネチャ**: `Immediate read(int id)`
  - **動作**:
    - 引数 `id` が0の場合、0を返します。
    - それ以外の場合、`prev[id]` の値を返します。

- **write**
  - **シグネチャ**: `void write(int id, Immediate val)`
  - **動作**:
    - 引数 `val` を `next[id]` に設定します。

- **debug**
  - **シグネチャ**: `void debug()`
  - **動作**:
    - レジスタのデバッグ情報を出力します。
    - 各レジスタの名前と値をフォーマットして表示します。
    - 使用関数: `std::cout`, `sprintf`, `std::setw`

### 注意事項
- **Fxx/Uxx 識別子**: これらの識別子は不透明であり、元のソースコードで使用されている名前、型、シグネチャ、名前空間を保持する必要があります。
- **Immediate 型**: この型は外部で定義されており、この仕様書では詳細な定義は提供されません。ただし、`Immediate` 型の変数が使用されることに注意してください。

## 出力ファイル
- `src/Common/RegisterFile.hpp`

## 例

```cpp
// src/Common/RegisterFile.hpp

#include <cstring>
#include <iostream>
#include <iomanip>
#include <vector>

class Immediate; // 外部で定義されている型

class RegisterFile { // : public Tickable {
public:
    static const int REG_NUM = 32;

    Immediate prev[REG_NUM];
    Immediate next[REG_NUM];

    RegisterFile() {
        memset(prev, 0, sizeof(prev));
        memset(next, 0, sizeof(next));
    }

    void tick() { memcpy(prev, next, sizeof(prev)); }

    Immediate read(int id) { return id == 0 ? 0 : prev[id]; }

    void write(int id, Immediate val) { next[id] = val; }

    void debug() {
        static std::vector<std::string> rf_name = {"0", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
                                                   "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
                                                   "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
                                                   "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"};
        for (int i = 0; i < 4; i++) {
            for (int j = i * 8; j < i * 8 + 8; j++) {
                char buffer[20];
                sprintf(buffer, "#%d", j);
                std::cout << std::setw(20) << buffer
                          << std::setw(4) << rf_name[j];
            }
            std::cout << std::endl;
            for (int j = i * 8; j < i * 8 + 8; j++) {
                debug_immediate(next[j], 11);
            }
            std::cout << std::endl;
        }
    }

private:
    void debug_immediate(const Immediate& imm, int width) {
        // Immediate 型のデバッグ出力関数
        // 実装は外部で定義されていると仮定
    }
};
```

## まとめ
この設計仕様書に基づいて `RegisterFile` クラスを再実装してください。元のソースコードの構造や識別子を尊重し、必要な機能を提供することを目指します。