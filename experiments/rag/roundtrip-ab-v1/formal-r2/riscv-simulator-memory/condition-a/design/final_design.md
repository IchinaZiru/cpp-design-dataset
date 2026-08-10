# 設計仕様書

## 1. 概要
この設計仕様書は、`Memory`クラスの定義を再実装するための詳細な指示を提供します。再実装対象は`F01/U01`と指定されており、その他の部分は参照のみとなります。

## 2. 対象ファイル
- ファイルパス: `src/Common/Memory.hpp`
- 役割: `Memory`クラスの完全な定義

## 3. クラス定義詳細

### 3.1 クラス名とメンバ変数
- **クラス名**: `Memory`
- **メンバ変数**:
  - `unsigned char mem[MEMORY_SIZE];`: メモリ配列。`MEMORY_SIZE`は定義されていないが、このサイズの配列を確保する。
  - `unsigned char placeholder;`: アドレスチェックに失敗した場合に返されるプレースホルダ値。

### 3.2 コンストラクタ
- **シグネチャ**: `Memory()`
- **機能**: メモリ配列`mem`をゼロで初期化する。
- **実装詳細**:
  ```cpp
  Memory() { memset(mem, 0, sizeof(mem)); }
  ```

### 3.3 アドレスチェック関数
- **シグネチャ**: `bool check_addr(unsigned int addr)`
- **機能**: 指定されたアドレスが有効な範囲内であるかを確認する。
- **実装詳細**:
  ```cpp
  bool check_addr(unsigned int addr) {
      if (0 <= addr && addr < MEMORY_SIZE) return true;
      // TODO: there may be exception when checking address,
      //       I'm looking forward to solving this.
      // assert(false);
      return false;
  }
  ```

### 3.4 ワード読み書き関数
- **シグネチャ**: `Immediate read_word(unsigned int addr)`
- **機能**: 指定されたアドレスからワード（`Immediate`型）を読み込む。
- **実装詳細**:
  ```cpp
  Immediate read_word(unsigned int addr) {
      if (!check_addr(addr)) return 0;
      return *(Immediate *) (mem + addr);
  }
  ```

- **シグネチャ**: `void write_word(unsigned int addr, Immediate imm)`
- **機能**: 指定されたアドレスにワード（`Immediate`型）を書き込む。
- **実装詳細**:
  ```cpp
  void write_word(unsigned int addr, Immediate imm) {
      if (!check_addr(addr)) return;
      *(Immediate *) (mem + addr) = imm;
  }
  ```

### 3.5 ショート読み書き関数
- **シグネチャ**: `unsigned short read_ushort(unsigned int addr)`
- **機能**: 指定されたアドレスからショート（`unsigned short`型）を読み込む。
- **実装詳細**:
  ```cpp
  unsigned short read_ushort(unsigned int addr) {
      if (!check_addr(addr)) return 0;
      return *(short *) (mem + addr);
  }
  ```

- **シグネチャ**: `void write_ushort(unsigned int addr, unsigned short imm)`
- **機能**: 指定されたアドレスにショート（`unsigned short`型）を書き込む。
- **実装詳細**:
  ```cpp
  void write_ushort(unsigned int addr, unsigned short imm) {
      if (!check_addr(addr)) return;
      *(short *) (mem + addr) = imm;
  }
  ```

### 3.6 オペレータオーバーロード
- **シグネチャ**: `unsigned char &operator[](unsigned int addr)`
- **機能**: 指定されたアドレスのメモリ値への参照を返す。
- **実装詳細**:
  ```cpp
  unsigned char &operator[](unsigned int addr) {
      if (!check_addr(addr)) return placeholder;
      return mem[addr];
  }
  ```

### 3.7 デバッグ関数
- **シグネチャ**: `void debug()`
- **機能**: メモリの特定範囲（`0x20000 - 0x10`から`0x20000`まで）を16進数で出力する。
- **実装詳細**:
  ```cpp
  void debug() {
      for (int i = 0x20000 - 0x10; i <= 0x20000; i++) {
          std::cout << std::hex << (unsigned) mem[i] << " ";
      }
      std::cout << std::endl;
  }
  ```

## 4. 注意事項
- `Fxx/Uxx`識別子は不透明であり、名前、型、シグネチャ、名前空間、置換境界を保持する。
- 再実装対象は`replacement_required=true`のユニットのみで、参照のみの入力は出力には含まれない。

## 5. 完全なクラス定義
```cpp
class Memory {
public:
    unsigned char mem[MEMORY_SIZE];
    unsigned char placeholder;

    Memory() { memset(mem, 0, sizeof(mem)); }

    bool check_addr(unsigned int addr) {
        if (0 <= addr && addr < MEMORY_SIZE) return true;
        // TODO: there may be exception when checking address,
        //       I'm looking forward to solving this.
        // assert(false);
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

この仕様書に基づいて、`Memory`クラスを再実装してください。