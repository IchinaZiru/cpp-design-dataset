# 設計仕様書

## 1. 概要
この設計仕様書は、`Register` クラスの定義を再実装するための詳細な指示を提供します。再実装対象は `F01/U01` ユニットであり、その他のユニットは参照のみとなります。

## 2. 対象ファイル
- **パス**: `src/Common/Register.hpp`
- **役割**: `Register` クラスの完全な定義

## 3. 再実装対象
- **再実装が必要なユニット**: `F01/U01`

## 4. 参照のみの入力
- **なし**

## 5. クラス定義詳細

### 5.1 クラス名と継承関係
- **クラス名**: `Register`
- **継承**: 継承は行われていない (`// : public Tickable` はコメントアウトされているため)

### 5.2 メンバ変数
| 変数名 | 型   | 初期値       | 説明                     |
|--------|------|--------------|--------------------------|
| `prev` | `T`  | `(T)0`       | 前回の値を保持するメンバ変数 |
| `next` | `T`  | `(T)0`       | 次回の値を保持するメンバ変数 |
| `_stall` | `bool` | `false`    | ストール状態を保持するメンバ変数 |

### 5.3 コンストラクタ
1. **デフォルトコンストラクタ**
   - **シグネチャ**: `Register()`
   - **初期化リスト**: `prev((T)0), next((T)0), _stall(false)`
   
2. **パラメータ付きコンストラクタ**
   - **シグネチャ**: `Register(T d)`
   - **初期化リスト**: `prev(d), next(d), _stall(false)`

### 5.4 メンバ関数
1. **`read()` 関数**
   - **シグネチャ**: `T read()`
   - **戻り値**: `prev`
   - **説明**: 前回の値を返す

2. **`current()` 関数**
   - **シグネチャ**: `T current()`
   - **戻り値**: `next`
   - **説明**: 次回の値を返す

3. **`write(const T &t)` 関数**
   - **シグネチャ**: `void write(const T &t)`
   - **パラメータ**: `const T &t`
   - **説明**: 次回の値に指定された値を設定する

4. **`tick()` 関数**
   - **シグネチャ**: `void tick()`
   - **説明**: ストール状態が `false` の場合、`prev` を `next` に更新する

5. **`stall(bool stall)` 関数**
   - **シグネチャ**: `void stall(bool stall)`
   - **パラメータ**: `bool stall`
   - **説明**: ストール状態を設定する

### 5.5 オペレーターのオーバーロード
1. **型変換演算子**
   - **シグネチャ**: `operator T()`
   - **戻り値**: `read()`
   - **説明**: オブジェクトを `T` 型に暗黙的に変換する際に、`prev` の値を返す

2. **代入演算子**
   - **シグネチャ**: `void operator=(T next)`
   - **パラメータ**: `T next`
   - **説明**: オブジェクトに `next` の値を代入する際に、`write(next)` を呼び出す

## 6. 注意事項
- `Fxx/Uxx` 識別子は不透明であり、名前、型、シグネチャ、名前空間、置換境界を保持すること。
- 再実装対象外のユニットは参照のみとなり、出力には含まれない。

## 7. 完全なクラス定義
```cpp
class Register {
public:
    T prev, next;

    bool _stall;

    Register() : prev((T)0), next((T)0), _stall(false) {}

    Register(T d) : prev(d), next(d), _stall(false) {}

    T read() { return prev; }

    T current() { return next; }

    void write(const T &t) { next = t; }

    void tick() { if (!_stall) prev = next; }

    void stall(bool stall) { _stall = stall; }

    operator T() { return read(); }

    void operator=(T next) { write(next); }
};
```

この仕様書に基づいて、`Register` クラスを再実装してください。