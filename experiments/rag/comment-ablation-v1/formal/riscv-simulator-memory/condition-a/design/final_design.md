# 設計仕様書

## 1. 概要
この設計仕様書は、`Memory`クラスの定義を再実装するための詳細な指示を提供します。再実装対象は`F01/U01`と指定されており、その他の部分は参照のみとなります。

## 2. 対象ファイル
- ファイルパス: `src/Common/Memory.hpp`
- 役割: `Memory`クラスの完全な定義

## 3. 再実装対象ユニット
### F01/U01
#### クラス名
- `Memory`

#### 名前空間
- 未指定（グローバル名前空間）

#### メンバ変数
| 変数名 | 型 | 説明 |
|--------|----|------|
| mem    | unsigned char[MEMORY_SIZE] | メモリ配列 |
| placeholder | unsigned char | アドレスチェックに失敗した場合のプレースホルダー |

#### コンストラクタ
- **シグネチャ**: `Memory()`
- **説明**: `mem`をゼロで初期化する。

#### メソッド
1. **check_addr**
   - **シグネチャ**: `bool check_addr(unsigned int addr)`
   - **説明**: アドレスが有効範囲内であるかチェックし、結果を返す。
   
2. **read_word**
   - **シグネチャ**: `Immediate read_word(unsigned int addr)`
   - **説明**: 指定されたアドレスから`Immediate`型の値を読み込む。アドレスが無効な場合は0を返す。

3. **write_word**
   - **シグネチャ**: `void write_word(unsigned int addr, Immediate imm)`
   - **説明**: 指定されたアドレスに`Immediate`型の値を書き込む。アドレスが無効な場合は何もしない。
   
4. **read_ushort**
   - **シグネチャ**: `unsigned short read_ushort(unsigned int addr)`
   - **説明**: 指定されたアドレスから`unsigned short`型の値を読み込む。アドレスが無効な場合は0を返す。
   
5. **write_ushort**
   - **シグネチャ**: `void write_ushort(unsigned int addr, unsigned short imm)`
   - **説明**: 指定されたアドレスに`unsigned short`型の値を書き込む。アドレスが無効な場合は何もしない。
   
6. **operator[]**
   - **シグネチャ**: `unsigned char &operator[](unsigned int addr)`
   - **説明**: 指定されたアドレスに対応する`mem`配列の要素への参照を返す。アドレスが無効な場合は`placeholder`を返す。
   
7. **debug**
   - **シグネチャ**: `void debug()`
   - **説明**: メモリの特定範囲（0x1FF90から0x20000）を16進数で出力する。

## 4. 注意事項
- `Fxx/Uxx`識別子は不透明であり、名前、型、シグネチャ、名前空間、置換境界を保持すること。
- 再実装対象外のユニット（REFERENCE-ONLY INPUTS）は出力に含まれてはならない。

## 5. 出力仕様
再実装後の`Memory.hpp`ファイルは以下の内容を含むこと:
```cpp
class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() { memset(mem, 0, sizeof(mem)); }

    bool check_addr(unsigned int addr) {
        if (0 <= addr && addr < MEMORY_SIZE) return true;
        return false;
    }

    Immediate read_word(unsigned int addr) {
        if (!check_addr(addr)) return 0;
        return *(Immediate *) (mem + addr);
    }

    void write_word(unsigned int addr, Immediate imm) {
        if (!check_addr(addr)) return;
        *(Immediate *) (mem + addr) = imm;
    }

    unsigned short read_ushort(unsigned int addr) {
        if (!check_addr(addr)) return 0;
        return *(short *) (mem + addr);
    }

    void write_ushort(unsigned int addr, unsigned short imm) {
        if (!check_addr(addr)) return;
        *(short *) (mem + addr) = imm;
    }

    unsigned char &operator[](unsigned int addr) {
        if (!check_addr(addr)) return placeholder;
        return mem[addr];
    }

    void debug() {
        for (int i = 0x20000 - 0x10; i <= 0x20000; i++) {
            std::cout << std::hex << (unsigned) mem[i] << " ";
        }
        std::cout << std::endl;
    }
};
```

## 6. 確認事項
- 再実装後のクラスが指定されたシグネチャと一致すること。
- `Fxx/Uxx`識別子の名前、型、シグネチャ、名前空間、置換境界が保持されていること。

この仕様書に基づいて再実装を行ってください。