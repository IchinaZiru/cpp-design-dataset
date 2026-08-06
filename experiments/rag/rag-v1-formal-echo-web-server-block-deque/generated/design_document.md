# デザイン文書: `BlockDeque` クラス

## 責務
- スレッドセーフな双方向キューを提供する。
- 容量制限があり、満杯の場合はプッシュ操作がブロックされる。
- 消費者が要素を取り出すまでプロデューサーは待つことができる。
- キューが空になった場合も同様に消費者は待つことができる。

## 公開インターフェース
### コンストラクタ
```cpp
explicit BlockDeque(std::size_t capacity = 1000) noexcept;
```
- ブロックデキューを作成し、最大容量を設定する。
- `capacity` (オプション): キューの最大容量。既定値は1000。

### デストラクタ
```cpp
~BlockDeque() noexcept;
```
- デストラクタでキューを閉じる。

### その他のメソッド
```cpp
void Clear() noexcept;
bool Empty() const noexcept;
bool Full() const noexcept;
std::size_t Size() const noexcept;
std::size_t Capacity() const noexcept;
void PushBack(T item) noexcept;
void PushFront(T item) noexcept;
const T& Front() const noexcept;
const T& Back() const noexcept;
T& Front() noexcept;
T& Back() noexcept;
std::optional<T> Pop(std::optional<Clock::duration> time_out = std::nullopt) noexcept;
void Flush() noexcept;
void Close() noexcept;
```

## 入力
- `PushBack(T item)` と `PushFront(T item)`: 追加する要素。
- `Pop(std::optional<Clock::duration> time_out)`: タイムアウト時間（オプション）。

## 出力
- `Pop()`: 取り出された要素またはタイムアウト/キューが閉じられた場合の `std::nullopt`。

## 状態
- `closed_`: キューが閉じられているかどうかを示すフラグ。
- `capacity_`: キューの最大容量。
- `deq_`: 実際のデータを保持するデキュー。
- `mtx_`: スレッドセーフな操作のために使用されるミューテックス。
- `consumer_cond_`: 消費者が待つための条件変数。
- `producer_cond_`: プロデューサーが待つための条件変数。

## 処理手順
1. **PushBack/PushFront**:
   - ミューテックスをロックする。
   - キューに空きがあるまで待つ（必要に応じて）。
   - 要素を追加し、ミューテックスをアンロックする。
   - 消費者スレッドに通知する。

2. **Pop**:
   - ミューテックスをロックする。
   - キューが空でないか、またはキューが閉じられるまで待つ（必要に応じて）。
   - キューが閉じられていたら `std::nullopt` を返す。
   - 最初の要素を取り出し、ミューテックスをアンロックする。
   - プロデューサースレッドに通知する。

3. **Clear**:
   - ミューテックスをロックする。
   - キュー内のすべての要素をクリアする。
   - ミューテックスをアンロックする。

4. **Close**:
   - ミューテックスをロックする。
   - キュー内のすべての要素をクリアし、閉じたフラグを設定する。
   - すべてのプロデューサーと消費者スレッドに通知する。
   - ミューテックスをアンロックする。

## 例外・失敗条件
- `PushBack`/`PushFront`: キューが閉じられている場合、操作は無視される。
- `Pop`: タイムアウト時間が指定され、その時間内に要素が追加されない場合、`std::nullopt` を返す。

## 依存関係
- `<cassert>`
- `<condition_variable>`
- `<deque>`
- `<mutex>`
- `<optional>`
- `<utility>`

## 重要な不変条件
- `capacity_ > 0`: キューの最大容量は常に正である。
- `deq_.size() <= capacity_`: キュー内の要素数は最大容量を超えない。
