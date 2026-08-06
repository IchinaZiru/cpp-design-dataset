# デザイン文書: Register クラス

## 責務
`Register`クラスは、RISC-Vシミュレータにおいてデータの読み書きとステージ間でのデータ伝達を管理します。具体的には、現在の値(`next`)と前の値(`prev`)を保持し、必要に応じて値を更新または停止することができます。

## 公開インターフェース
- `T read()`: 前の値(`prev`)を返す。
- `T current()`: 現在の値(`next`)を返す。
- `void write(const T &t)`: 新しい値`t`を現在の値(`next`)に設定する。
- `void tick()`: `_stall`がfalseの場合、前の値(`prev`)を現在の値(`next`)に更新する。
- `void stall(bool stall)`: ストール状態を設定する。`true`に設定するとデータ伝達が停止し、`false`に設定すると再開する。
- `operator T()`: 前の値(`prev`)を返すようにオペレータをオーバーロードしている。
- `void operator=(T next)`: 新しい値`t`を現在の値(`next`)に設定するようにオペレータをオーバーロードしている。

## 入力
- コンストラクタ: 初期値`d` (省略可能)
- `write(const T &t)`: 書き込む新しい値`t`
- `stall(bool stall)`: ストール状態を設定するためのブーリアン値

## 出力
- `read()`, `current()`, キャスト演算子`operator T()`: 値を返す。

## 状態
- `prev`: 前の値。
- `next`: 現在の値。
- `_stall`: ストール状態。`true`の場合、データ伝達が停止する。

## 処理手順
1. **初期化**: コンストラクタで`prev`, `next`を初期値に設定し、`_stall`をfalseに設定。
2. **書き込み**: `write()`メソッドを使用して新しい値`t`を現在の値(`next`)に設定する。
3. **読み取り**: `read()`, `current()`, キャスト演算子`operator T()`を使用して前の値(`prev`)または現在の値(`next`)を取得する。
4. **ステージ更新**: `tick()`メソッドが呼ばれたときに、`_stall`がfalseの場合のみ前の値(`prev`)を現在の値(`next`)に更新する。
5. **ストール状態設定**: `stall(bool stall)`メソッドを使用してデータ伝達の停止や再開を行う。

## 例外・失敗条件
- コンストラクタ: 初期値が指定されない場合、デフォルトで0に初期化される。
- `write()`: 正常な入力を受け取ると仮定しているため、特定の例外処理は行われていない。
- `tick()`, `stall(bool stall)`: これらのメソッド自体が例外を投げることはない。

## 依存関係
- このクラスは他のクラスから直接参照され、値の読み書きやステージ間でのデータ伝達に使用される。具体的には`LoadStoreUnit::get_store_cnt_register`, `LoadStoreUnit::get_load_cnt_register`, `LoadStoreUnit::get_load_buffer`などのメソッドで利用されている。

## 重要な不変条件
- `_stall`がtrueの場合、`tick()`によって前の値(`prev`)は更新されない。
- `write(const T &t)`によって現在の値(`next`)が設定された後、`tick()`が呼ばれるまで前の値(`prev`)は変化しない。
