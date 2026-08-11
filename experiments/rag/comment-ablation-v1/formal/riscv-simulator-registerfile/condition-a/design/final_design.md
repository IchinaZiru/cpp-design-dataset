# 設計仕様書

## 概要
この設計仕様書は、`RegisterFile` クラスの再実装を目的としています。元のソースコードから得られる情報を基に、新たなソースコードを作成します。

## 対象範囲
- ファイルパス: `src/Common/RegisterFile.hpp`
- クラス名: `RegisterFile`

## 既存のクラス定義と役割

### クラス定義
```cpp
class RegisterFile {                       
    static const int REG_NUM = 32;
public:
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
};
```

### 役割
- `RegisterFile` クラスは、32個のレジスタを管理します。
- 各レジスタには現在値 (`next`) と前回の値 (`prev`) を保持します。
- レジスタの読み書き操作が可能で、デバッグ用の出力機能も備えています。

## クラス仕様

### 定数
- `REG_NUM`: レジスタの総数を表す定数。値は32です。

### メンバ変数
- `prev[REG_NUM]`: 各レジスタの前回の値を保持する配列。
- `next[REG_NUM]`: 各レジスタの現在値を保持する配列。

### コンストラクタ
- `RegisterFile()`: すべてのレジスタの初期値を0に設定します。

### メソッド

#### tick()
- **説明**: 前回の値 (`prev`) を現在の値 (`next`) で更新します。
- **引数**: 無し
- **戻り値**: 無し

#### read(int id)
- **説明**: 指定されたIDのレジスタの前回の値を返します。ただし、IDが0の場合には常に0を返します。
- **引数**:
  - `id`: レジスタのID (0からREG_NUM-1までの整数)
- **戻り値**: `Immediate` 型

#### write(int id, Immediate val)
- **説明**: 指定されたIDのレジスタに現在値を設定します。
- **引数**:
  - `id`: レジスタのID (0からREG_NUM-1までの整数)
  - `val`: 設定する値 (`Immediate` 型)
- **戻り値**: 無し

#### debug()
- **説明**: 各レジスタの現在値をデバッグ用に出力します。
- **引数**: 無し
- **戻り値**: 無し

### その他の情報
- `Immediate` 型は、この仕様書では定義されていません。呼び出し元で適切な型を使用することを想定しています。
- `debug_immediate(Immediate val, int width)` 関数は、このクラスの外部で定義されていると仮定します。

## 注意事項
- 既存のソースコード内の識別子 (`Fxx/Uxx`) を変更しないでください。
- 名前空間や型、シグネチャを保持してください。
- `REFERENCE-ONLY INPUTS` は存在しないため、再実装に影響を与えることはありません。

## 出力ファイルパス
- `src/Common/RegisterFile.hpp`

この仕様書に基づいて新たなソースコードを作成してください。