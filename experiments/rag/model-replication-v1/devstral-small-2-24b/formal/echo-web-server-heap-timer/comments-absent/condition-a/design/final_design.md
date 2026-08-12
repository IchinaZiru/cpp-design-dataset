# HeapTimer 設計仕様書

## 概要
`HeapTimer` は、キーバリュー型のキーとタイムアウトコールバックを管理する優先度付きキュー（ヒープ）を実装したクラスです。このクラスは、指定された時間が経過すると自動的にコールバック関数を呼び出す機能を提供します。

## クラス構造

### テンプレートパラメータ
- `Key`: キーの型（任意の型）

### 依存関係
- `log::Logger::Ptr`: ロギング機能のためのポインタ
- `std::chrono::steady_clock`: 時間測定に使用するクロック

## パブリックインターフェース

### コンストラクタとデストラクタ
```cpp
explicit HeapTimer(log::Logger::Ptr logger = log::RootLogger()) noexcept;
```
- ロガーを受け取り、初期化します。
- デフォルトではルートロガーが使用されます。

### メソッド

#### Push
```cpp
void Push(const Key& key, Clock::duration expiration,
          TimeOutCallback callback) noexcept;

void Push(const Key& key, Clock::time_point expiration,
          TimeOutCallback callback) noexcept;
```
- 新しいタイマーをキューに追加します。
- 同じキーが既に存在する場合は、そのタイマーの設定を更新します。

#### Adjust
```cpp
void Adjust(const Key& key, Clock::duration expiration);

void Adjust(const Key& key, Clock::time_point expiration);
```
- 既存のタイマーの有効期限を変更します。
- コールバックは変更しません。

#### Tick
```cpp
void Tick() noexcept;
```
- 有効期限が切れたすべてのタイマーのコールバックを実行します。
- 実行中に例外が発生した場合、エラーログを記録します。

#### Remove
```cpp
bool Remove(const Key& key) noexcept;
```
- 指定されたキーのタイマーを削除します。
- 削除に成功した場合は `true` を返します。

#### Invoke
```cpp
void Invoke(const Key& key);
```
- 指定されたキーのタイマーのコールバックを即座に実行し、そのタイマーを削除します。

#### Pop
```cpp
Key Pop() noexcept;
```
- 最も近い有効期限のタイマーをキューから取り出し、そのキーを返します。
- キューが空の場合は未定義動作となります。

#### Clear
```cpp
void Clear() noexcept;
```
- すべてのタイマーを削除します。

#### Contain
```cpp
bool Contain(const Key& key) const noexcept;
```
- 指定されたキーのタイマーが存在するかどうかを返します。

#### Empty
```cpp
bool Empty() const noexcept;
```
- キューが空であるかどうかを返します。

#### Size
```cpp
std::size_t Size() const noexcept;
```
- キューに含まれるタイマーの数を返します。

#### ToNextTick
```cpp
Clock::duration ToNextTick() noexcept;
```
- 次の `Tick()` を呼び出すまでの時間（最も近い有効期限のタイマーまでの時間）を返します。
- 有効期限が切れたタイマーがある場合は、それらを処理した後で計算します。

## プライベートメンバー

### Node 構造体
```cpp
struct Node {
    Key key;
    Clock::time_point expiration;
    TimeOutCallback callback;

    bool Expired() const noexcept;
    void Swap(Node&) noexcept;
};
```
- `Expired()`: 現在の時間が有効期限を過ぎているかどうかを返します。
- `Swap()`: 2つのノードの内容を交換します。

### ヒープ操作
```cpp
void ShiftUp(std::size_t idx) noexcept;
void ShiftDown(std::size_t idx) noexcept;
std::optional<std::size_t> Parent(std::size_t idx) const noexcept;
std::optional<std::size_t> SmallChild(std::size_t idx) const noexcept;
```
- `ShiftUp()`: 指定されたインデックスのノードを親と比較し、必要に応じて上方向へ移動します。
- `ShiftDown()`: 指定されたインデックスのノードを子と比較し、必要に応じて下方向へ移動します。
- `Parent()`: 指定されたインデックスの親のインデックスを返します。
- `SmallChild()`: 指定されたインデックスの最小の子のインデックスを返します。

### ヘルパーメソッド
```cpp
void Swap(std::size_t idx1, std::size_t idx2) noexcept;
bool ValidIndex(std::size_t idx) const noexcept;
Key RemoveByIndex(std::size_t idx) noexcept;
```
- `Swap()`: 2つのノードを交換し、インデックスマップも更新します。
- `ValidIndex()`: 指定されたインデックスが有効かどうかを返します。
- `RemoveByIndex()`: 指定されたインデックスのノードを削除し、そのキーを返します。

### データメンバー
```cpp
log::Logger::Ptr logger_;
std::unordered_map<Key, std::size_t> key_to_idx_;
std::deque<Node> nodes_;
```
- `logger_`: ロギングのためのポインタ。
- `key_to_idx_`: キーからノードのインデックスへのマッピング。
- `nodes_`: ヒープデータ構造を格納するコンテナ。

## 実装注意事項

1. **ヒーププロパティ**: ノードは常に最小ヒープとして維持されます（有効期限が最も早いノードがルート）。
2. **例外処理**: コールバックの実行中に発生した例外はキャッチされ、エラーログを記録します。
3. **スレッドセーフティ**: このクラス自体はスレッドセーフではありません。使用側で適切な同期を施す必要があります。
4. **アサーション**: デバッグビルドでは内部状態の整合性をチェックするためにアサーションが使用されています。

## 使用例

```cpp
HeapTimer<int> timer;
timer.Push(1, std::chrono::seconds(5), [](int key) {
    std::cout << "Timeout for key: " << key << std::endl;
});

while (!timer.Empty()) {
    auto next = timer.ToNextTick();
    std::this_thread::sleep_for(next);
    timer.Tick();
}
```

この設計仕様書は、与えられたソースコードを忠実に再現できるように作成されています。具体的な実装詳細（例外処理の方法など）については、元のソースコードを参照してください。