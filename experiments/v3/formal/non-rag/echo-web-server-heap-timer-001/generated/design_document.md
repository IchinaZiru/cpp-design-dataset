# デザイン文書

## 責務
`HeapTimer`クラスは、キーとコールバック関数を持つタイマーを最小ヒープ構造で管理します。タイマーの有効期限が切れると、そのタイマーに関連付けられたコールバック関数が呼び出されます。

## 公開インターフェース
- `HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept`: ロガーを指定して`HeapTimer`オブジェクトを作成します。
- `void Adjust(const Key& key, Clock::duration expiration)`: タイマーの有効期限時間を調整します（相対時間）。
- `void Adjust(const Key& key, Clock::time_point expiration)`: タイマーの有効期限時間を調整します（絶対時間）。
- `void Push(const Key& key, Clock::duration expiration, TimeOutCallback callback) noexcept`: 新しいタイマーを追加します（相対時間）。
- `void Push(const Key& key, Clock::time_point expiration, TimeOutCallback callback) noexcept`: 新しいタイマーを追加します（絶対時間）。
- `void Tick() noexcept`: 有効期限切れのタイマーを処理し、コールバック関数を呼び出します。
- `bool Remove(const Key& key) noexcept`: 指定されたキーを持つタイマーを削除します。
- `void Invoke(const Key& key)`: 指定されたキーを持つタイマーを強制的に呼び出し、その後削除します。
- `Key Pop() noexcept`: 最も有効期限が近いタイマーを取り出します。
- `void Clear() noexcept`: すべてのタイマーをクリアします。
- `bool Contain(const Key& key) const noexcept`: 指定されたキーを持つタイマーが存在するかどうかを返します。
- `bool Empty() const noexcept`: タイマーが空であるかどうかを返します。
- `std::size_t Size() const noexcept`: 管理されているタイマーの数を返します。
- `Clock::duration ToNextTick() noexcept`: 次に有効期限切れになるまでの時間を返します。

## 入力
- タイマーのキー（`Key`型）
- 有効期限時間（相対時間または絶対時間）
- コールバック関数（`TimeOutCallback`型）

## 出力
- `bool`: 操作が成功したかどうかを示すブーリアン値。
- `Key`: 取り出されたタイマーのキー。
- `std::size_t`: 管理されているタイマーの数。
- `Clock::duration`: 次に有効期限切れになるまでの時間。

## 状態
- タイマーが空であるかどうか（`Empty()`メソッドを通じて確認可能）。
- 管理されているタイマーの数（`Size()`メソッドを通じて確認可能）。
- 各タイマーの有効期限とコールバック関数。

## 処理手順
1. `Push`: 新しいノードを追加し、ヒーププロパティを維持するために`ShiftUp`を呼び出す。
2. `Adjust`: 既存のノードの有効期限時間を更新し、必要に応じて`ShiftUp`または`ShiftDown`を呼び出す。
3. `Tick`: ヒープの先頭から有効期限切れのノードを取り出し、コールバック関数を呼び出す。その後、ヒーププロパティを維持するために`ShiftDown`を呼び出す。
4. `RemoveByIndex`: 指定されたインデックスのノードを削除し、ヒーププロパティを維持するために`ShiftUp`と`ShiftDown`を呼び出す。
5. `Invoke`: 指定されたキーを持つノードを取り出し、コールバック関数を呼び出します。その後、ノードを削除します。

## 例外・失敗条件
- `std::out_of_range`: 存在しないキーに対して`Adjust`, `Remove`, `Invoke`メソッドが呼ばれた場合。
- コールバック関数内で例外が発生した場合はキャッチされ、ログに記録されます。呼び出し元には伝播しません。

## 依存関係
- `log::Logger`: ロギング機能を提供するクラス。
- `std::chrono`: 時間の管理と操作を行うための標準ライブラリ。
- `std::function`, `std::optional`, `std::unordered_map`, `std::deque`: コンテナや関数オブジェクト、オプショナル値を扱うための標準ライブラリ。

## 重要な不変条件
- ヒーププロパティ: タイマーは最小ヒープ構造で管理され、親ノードの有効期限が子ノードよりも短いまたは等しい。
- `key_to_idx_`と`nodes_`の整合性: 各キーが`key_to_idx_`に存在する場合、対応するインデックスは`nodes_`で有効な範囲内である。逆もまた真。
- コールバック関数の呼び出し: 有効期限切れになったタイマーに対してのみコールバック関数が呼び出される。